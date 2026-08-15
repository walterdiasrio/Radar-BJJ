import os
import secrets
import threading
import time
import traceback
from datetime import date
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session

import alertas
import auth
import carreira
import contato
import noticias
import pagamentos
import turmas
from connectors import FEDERACOES, TODAS, listar_eventos, buscar_atletas_agregado, listar_competicoes, evento_sem_kimono
from connectors import adcc
from connectors import ajp
from connectors import FEDERACOES_SMOOTHCOMP, FEDERACOES_SMOOTHCOMP_SEM_KIMONO
from connectors import idade as idade_mod
from connectors import peso as peso_mod

INTERVALO_ALERTAS_SEGUNDOS = int(os.environ.get("INTERVALO_ALERTAS_SEGUNDOS", 30 * 60))

app = Flask(__name__, static_folder="static", static_url_path="")

ADMIN_EMAIL = "walterdiasrio@gmail.com"

# Em produção (Render), DATA_DIR aponta pro disco persistente (ex: /var/data)
# — sem isso, cadastros e competições importadas do ADCC somem a cada deploy.
# Localmente, sem essa variável definida, usa a própria pasta do projeto.
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_SECRET_KEY_PATH = DATA_DIR / ".secret_key"
if not _SECRET_KEY_PATH.exists():
    _SECRET_KEY_PATH.write_text(secrets.token_hex(32))
app.secret_key = os.environ.get("SECRET_KEY") or _SECRET_KEY_PATH.read_text().strip()

auth.init_db()
alertas.init_db()
noticias.init_db()
pagamentos.init_db()
carreira.init_db()
contato.init_db()
turmas.init_db()
noticias.remover_noticias_expiradas()  # limpa logo na subida, não só no próximo ciclo


def _iniciar_verificacao_periodica_de_alertas():
    def loop():
        while True:
            time.sleep(INTERVALO_ALERTAS_SEGUNDOS)
            try:
                alertas.verificar_todos()
            except Exception:
                traceback.print_exc()
            try:
                alertas.verificar_todas_competicoes()
            except Exception:
                traceback.print_exc()
            try:
                noticias.remover_noticias_expiradas()
            except Exception:
                traceback.print_exc()

    threading.Thread(target=loop, daemon=True).start()


_iniciar_verificacao_periodica_de_alertas()


def _parse_federacao(bruto):
    """Aceita "todas", um único id ("cbjj") ou vários separados por vírgula
    ("cbjj,fjjrio"). Retorna TODAS, um id único, ou uma lista de ids — ou
    None se nada válido foi informado."""
    if not bruto:
        return None
    if bruto == TODAS:
        return TODAS
    ids = [f.strip() for f in bruto.split(",") if f.strip() in FEDERACOES]
    if not ids:
        return None
    return ids[0] if len(ids) == 1 else ids


def _federacoes_da_lista(federacao):
    """Normaliza o resultado de _parse_federacao numa lista de ids, para
    iterar (usado no preview de categoria/peso)."""
    if federacao == TODAS:
        return list(FEDERACOES.keys())
    if isinstance(federacao, list):
        return federacao
    return [federacao]


def login_necessario(view):
    """Protege páginas: sem sessão válida, manda pro login."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapper


def api_login_necessario(view):
    """Protege endpoints de API: sem sessão válida, 401 em JSON."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return jsonify({"erro": "faça login para continuar"}), 401
        return view(*args, **kwargs)
    return wrapper


def _usuario_atual_eh_admin():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return False
    usuario = auth.buscar_por_id(usuario_id)
    return bool(usuario) and usuario["email"] == ADMIN_EMAIL


def _usuario_atual_eh_mestre():
    """Admin conta como Mestre também (não perde acesso por causa do
    perfil escolhido no cadastro)."""
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return False
    usuario = auth.buscar_por_id(usuario_id)
    if not usuario:
        return False
    return usuario["email"] == ADMIN_EMAIL or usuario["tipo_perfil"] == "mestre"


def admin_necessario(view):
    """Protege páginas restritas ao admin: sem sessão válida manda pro
    login; logado mas não-admin recebe 404 (não revela que a página existe)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect("/login")
        if not _usuario_atual_eh_admin():
            return "Página não encontrada", 404
        return view(*args, **kwargs)
    return wrapper


def api_admin_necessario(view):
    """Protege endpoints de API restritos ao admin."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return jsonify({"erro": "faça login para continuar"}), 401
        if not _usuario_atual_eh_admin():
            return jsonify({"erro": "acesso restrito"}), 403
        return view(*args, **kwargs)
    return wrapper


def _usuario_atual_tem_assinatura():
    """Admin sempre tem acesso, sem precisar assinar."""
    return _usuario_atual_eh_admin() or pagamentos.usuario_tem_acesso(session.get("usuario_id"))


def assinatura_necessaria(view):
    """Protege páginas do Buscador/Alertas: sem sessão manda pro login,
    logado mas sem assinatura ativa (nem em teste grátis) manda pra
    página de planos."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return redirect("/login")
        if not _usuario_atual_tem_assinatura():
            return redirect(f"/assinatura?de={request.path}")
        return view(*args, **kwargs)
    return wrapper


def api_assinatura_necessaria(view):
    """Protege endpoints de API do Buscador/Alertas."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return jsonify({"erro": "faça login para continuar"}), 401
        if not _usuario_atual_tem_assinatura():
            return jsonify({"erro": "assinatura necessária", "requer_assinatura": True}), 402
        return view(*args, **kwargs)
    return wrapper


@app.get("/")
def home():
    # Pública — página inicial, com o BJJ News em destaque.
    return send_from_directory("static", "home.html")


@app.get("/buscador")
@assinatura_necessaria
def index():
    return send_from_directory("static", "index.html")


@app.get("/competicoes")
def competicoes():
    # Pública — Competições e Notícias são abertas a todos; só o Buscador
    # de Atletas e os Alertas exigem login.
    return send_from_directory("static", "competicoes.html")


@app.get("/cadastro")
def pagina_cadastro():
    return send_from_directory("static", "cadastro.html")


@app.get("/login")
def pagina_login():
    return send_from_directory("static", "login.html")


@app.get("/planos")
def pagina_planos():
    return send_from_directory("static", "planos.html")


@app.get("/esqueci-senha")
def pagina_esqueci_senha():
    return send_from_directory("static", "esqueci-senha.html")


@app.get("/redefinir-senha")
def pagina_redefinir_senha():
    return send_from_directory("static", "redefinir-senha.html")


@app.post("/api/esqueci-senha")
def api_esqueci_senha():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()

    usuario = auth.buscar_por_email(email) if email else None
    if usuario:
        token = auth.criar_token_reset(usuario["id"])
        link = f"{alertas.URL_SITE}/redefinir-senha?token={token}"
        corpo = (
            "<p>Recebemos um pedido pra redefinir sua senha no Radar BJJ.</p>"
            f'<p><a href="{link}">Clique aqui pra criar uma senha nova</a></p>'
            "<p>Esse link vale por 1 hora. Se você não pediu isso, pode ignorar este e-mail.</p>"
        )
        alertas.enviar_email(usuario["email"], "Radar BJJ — redefinir senha", corpo)

    # Sempre a mesma resposta, exista ou não o e-mail — evita confirmar
    # pra quem está tentando descobrir e-mails cadastrados no sistema.
    return jsonify({"ok": True})


@app.post("/api/redefinir-senha")
def api_redefinir_senha():
    dados = request.get_json(silent=True) or {}
    token = dados.get("token") or ""
    nova_senha = dados.get("senha") or ""

    if not token:
        return jsonify({"erro": "link inválido"}), 400

    ok, erro = auth.redefinir_senha(token, nova_senha)
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


def _enviar_email_confirmacao(usuario_id, email):
    token = auth.criar_token_verificacao(usuario_id)
    link = f"{alertas.URL_SITE}/confirmar-email?token={token}"
    corpo = (
        "<p>Falta só confirmar seu e-mail pra ativar sua conta no Radar BJJ.</p>"
        f'<p><a href="{link}">Clique aqui pra confirmar seu e-mail</a></p>'
        "<p>Esse link vale por 24 horas. Se você não se cadastrou no Radar BJJ, pode ignorar este e-mail.</p>"
    )
    alertas.enviar_email(email, "Radar BJJ — confirme seu e-mail", corpo)


@app.get("/confirmar-email")
def pagina_confirmar_email():
    return send_from_directory("static", "confirmar-email.html")


@app.post("/api/confirmar-email")
def api_confirmar_email():
    dados = request.get_json(silent=True) or {}
    token = dados.get("token") or ""

    if not token:
        return jsonify({"erro": "link inválido"}), 400

    ok, erro = auth.confirmar_email(token)
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


@app.post("/api/reenviar-confirmacao")
def api_reenviar_confirmacao():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()

    usuario = auth.buscar_por_email(email) if email else None
    if usuario and not usuario["email_verificado"]:
        _enviar_email_confirmacao(usuario["id"], usuario["email"])

    # Mesma resposta sempre — não revela se o e-mail existe ou já foi confirmado.
    return jsonify({"ok": True})


@app.get("/api/noticias")
def api_listar_noticias():
    return jsonify([
        {
            "id": n["id"],
            "manchete": n["manchete"],
            "texto": n["texto"],
            "data_limite": n["data_limite"],
            "imagem_url": f"/noticias-imagens/{n['imagem_arquivo']}",
            "criado_em": n["criado_em"],
        }
        for n in noticias.listar_noticias()
    ])


@app.get("/noticias-imagens/<path:nome_arquivo>")
def servir_imagem_noticia(nome_arquivo):
    return send_from_directory(noticias.DIR_IMAGENS, nome_arquivo)


@app.post("/api/noticias")
@api_admin_necessario
def api_criar_noticia():
    manchete = request.form.get("manchete", "")
    texto = request.form.get("texto", "")
    data_limite = request.form.get("data_limite", "")
    arquivo = request.files.get("imagem")
    if not arquivo or not arquivo.filename:
        return jsonify({"erro": "selecione uma imagem"}), 400
    noticia_id, erro = noticias.criar_noticia(manchete, texto, data_limite, arquivo, arquivo.filename)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": noticia_id})


@app.delete("/api/noticias/<int:noticia_id>")
@api_admin_necessario
def api_remover_noticia(noticia_id):
    removida = noticias.remover_noticia(noticia_id)
    if not removida:
        return jsonify({"erro": "notícia não encontrada"}), 404
    return jsonify({"ok": True})


@app.get("/noticias")
def pagina_noticias():
    # Pública — igual Competições, aberta a todo mundo.
    return send_from_directory("static", "noticias.html")


@app.get("/gerenciar-noticias")
@admin_necessario
def pagina_gerenciar_noticias():
    return send_from_directory("static", "gerenciar-noticias.html")


@app.get("/fale-conosco")
def pagina_fale_conosco():
    # Pública — aberta a todo mundo, logado ou não.
    return send_from_directory("static", "fale-conosco.html")


@app.get("/termos")
def pagina_termos():
    # Pública — aberta a todo mundo, logado ou não.
    return send_from_directory("static", "termos.html")


@app.post("/api/contato")
def api_criar_mensagem_contato():
    dados = request.get_json(silent=True) or {}
    usuario_id = session.get("usuario_id")
    mensagem_id, erro = contato.criar_mensagem(
        dados.get("nome"), dados.get("email"), dados.get("assunto"), dados.get("mensagem"),
        usuario_id=usuario_id,
    )
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": mensagem_id})


@app.get("/gerenciar-mensagens")
@admin_necessario
def pagina_gerenciar_mensagens():
    return send_from_directory("static", "gerenciar-mensagens.html")


@app.get("/api/contato")
@api_admin_necessario
def api_listar_mensagens_contato():
    return jsonify(contato.listar_mensagens())


@app.post("/api/contato/<int:mensagem_id>/lida")
@api_admin_necessario
def api_marcar_mensagem_lida(mensagem_id):
    dados = request.get_json(silent=True) or {}
    ok = contato.marcar_lida(mensagem_id, dados.get("lida", True))
    if not ok:
        return jsonify({"erro": "mensagem não encontrada"}), 404
    return jsonify({"ok": True})


@app.delete("/api/contato/<int:mensagem_id>")
@api_admin_necessario
def api_remover_mensagem_contato(mensagem_id):
    ok = contato.remover_mensagem(mensagem_id)
    if not ok:
        return jsonify({"erro": "mensagem não encontrada"}), 404
    return jsonify({"ok": True})


@app.get("/gerenciar-usuarios")
@admin_necessario
def pagina_gerenciar_usuarios():
    return send_from_directory("static", "gerenciar-usuarios.html")


@app.get("/api/usuarios")
@api_admin_necessario
def api_listar_usuarios():
    usuarios = auth.listar_usuarios()
    resumo = {
        "total": len(usuarios),
        "por_perfil": {"atleta": 0, "mestre": 0},
        "por_status_assinatura": {"trialing": 0, "active": 0, "past_due": 0, "canceled": 0, "sem_assinatura": 0},
    }

    lista = []
    for usuario in usuarios:
        assinatura = pagamentos.obter_assinatura(usuario["id"])
        status = assinatura["status"] if assinatura else None

        resumo["por_perfil"][usuario["tipo_perfil"]] = resumo["por_perfil"].get(usuario["tipo_perfil"], 0) + 1
        chave_status = status if status in resumo["por_status_assinatura"] else "sem_assinatura"
        resumo["por_status_assinatura"][chave_status] += 1

        lista.append({
            "id": usuario["id"],
            "email": usuario["email"],
            "tipo_perfil": usuario["tipo_perfil"],
            "nome_usuario": usuario["nome_usuario"],
            "criado_em": usuario["criado_em"],
            "assinatura_status": status,
            "assinatura_plano": assinatura["plano"] if assinatura else None,
            "assinatura_periodicidade": assinatura["periodicidade"] if assinatura else None,
        })

    return jsonify({"resumo": resumo, "usuarios": lista})


@app.get("/importar-adcc")
@admin_necessario
def pagina_importar_adcc():
    return send_from_directory("static", "importar-adcc.html")


@app.post("/api/adcc/importar-evento")
@api_admin_necessario
def api_adcc_importar_evento():
    dados = request.get_json(silent=True) or {}
    html = dados.get("html", "")
    if not html.strip():
        return jsonify({"erro": "nenhum HTML recebido"}), 400
    try:
        evento = adcc.parse_evento_html(html)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não consegui interpretar essa página: {exc}"}), 400
    adcc.salvar_evento(evento)
    return jsonify({"ok": True, "evento": evento})


@app.post("/api/adcc/importar-atletas")
@api_admin_necessario
def api_adcc_importar_atletas():
    dados = request.get_json(silent=True) or {}
    evento_id = dados.get("evento_id", "")
    html = dados.get("html", "")
    if not evento_id:
        return jsonify({"erro": "evento_id é obrigatório — importe a página do evento primeiro"}), 400
    if not html.strip():
        return jsonify({"erro": "nenhum HTML recebido"}), 400
    try:
        atletas = adcc.parse_atletas_html(html)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não consegui interpretar essa página: {exc}"}), 400
    if not atletas:
        return jsonify({"erro": "não encontrei nenhum atleta nessa página — confirma que rolou a tela até o final antes de salvar?"}), 400
    adcc.salvar_atletas(evento_id, atletas)
    return jsonify({"ok": True, "total": len(atletas)})


@app.get("/importar-ajp")
@admin_necessario
def pagina_importar_ajp():
    return send_from_directory("static", "importar-ajp.html")


@app.post("/api/ajp/importar-evento")
@api_admin_necessario
def api_ajp_importar_evento():
    dados = request.get_json(silent=True) or {}
    html = dados.get("html", "")
    if not html.strip():
        return jsonify({"erro": "nenhum HTML recebido"}), 400
    try:
        evento = ajp.parse_evento_html(html)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não consegui interpretar essa página: {exc}"}), 400
    ajp.salvar_evento(evento)
    return jsonify({"ok": True, "evento": evento})


@app.post("/api/ajp/importar-atletas")
@api_admin_necessario
def api_ajp_importar_atletas():
    dados = request.get_json(silent=True) or {}
    evento_id = dados.get("evento_id", "")
    html = dados.get("html", "")
    if not evento_id:
        return jsonify({"erro": "evento_id é obrigatório — importe a página do evento primeiro"}), 400
    if not html.strip():
        return jsonify({"erro": "nenhum HTML recebido"}), 400
    try:
        atletas = ajp.parse_atletas_html(html)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não consegui interpretar essa página: {exc}"}), 400
    if not atletas:
        return jsonify({"erro": "não encontrei nenhum atleta nessa página — confirma que rolou a tela até o final antes de salvar?"}), 400
    ajp.salvar_atletas(evento_id, atletas)
    return jsonify({"ok": True, "total": len(atletas)})


@app.get("/api/sessao")
def api_sessao():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"logado": False})
    usuario = auth.buscar_por_id(usuario_id)
    if not usuario:
        session.clear()
        return jsonify({"logado": False})
    eh_admin = usuario["email"] == ADMIN_EMAIL
    assinatura = pagamentos.obter_assinatura(usuario["id"])
    return jsonify({
        "logado": True,
        "email": usuario["email"],
        "admin": eh_admin,
        "tipo_perfil": usuario["tipo_perfil"],
        "mestre": eh_admin or usuario["tipo_perfil"] == "mestre",
        "assinatura": {
            "tem_acesso": eh_admin or pagamentos.usuario_tem_acesso(usuario["id"]),
            "status": assinatura["status"] if assinatura else None,
            "plano": assinatura["plano"] if assinatura else None,
            "periodicidade": assinatura["periodicidade"] if assinatura else None,
        },
    })


@app.post("/api/cadastro")
def api_cadastro():
    dados = request.get_json(silent=True) or {}
    usuario_id, erro = auth.cadastrar(dados.get("email"), dados.get("senha"), dados.get("tipo_perfil"))
    if erro:
        return jsonify({"erro": erro}), 400

    email = dados.get("email", "").strip().lower()
    _enviar_email_confirmacao(usuario_id, email)
    # Sem login automático — o cadastro só é efetivado depois de confirmar
    # o e-mail (ver auth.autenticar, que bloqueia login não confirmado).
    return jsonify({"ok": True, "email": email, "precisa_confirmar": True})


@app.post("/api/entrar")
def api_entrar():
    dados = request.get_json(silent=True) or {}
    usuario, erro = auth.autenticar(dados.get("email"), dados.get("senha"))
    if erro == "email_nao_confirmado":
        return jsonify({"erro": "confirme seu e-mail antes de entrar", "email_nao_confirmado": True}), 403
    if erro:
        return jsonify({"erro": erro}), 401
    session["usuario_id"] = usuario["id"]
    return jsonify({"ok": True, "email": usuario["email"]})


@app.post("/api/sair")
def api_sair():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/federacoes")
def api_federacoes():
    return jsonify([
        {"id": fid, "label": info["label"]} for fid, info in FEDERACOES.items()
    ])


@app.get("/api/buscador/filtro-padrao")
@api_assinatura_necessaria
def api_obter_filtro_padrao():
    return jsonify({"filtro": auth.obter_filtro_padrao(session["usuario_id"])})


@app.post("/api/buscador/filtro-padrao")
@api_assinatura_necessaria
def api_salvar_filtro_padrao():
    dados = request.get_json(silent=True) or {}
    filtro = {
        "federacao": dados.get("federacao") or "",
        "genero": dados.get("genero") or "",
        "data_nascimento": dados.get("data_nascimento") or "",
        "faixa": dados.get("faixa") or "",
        "peso_kg": dados.get("peso_kg") or "",
        "peso_sem_kimono": dados.get("peso_sem_kimono") or "",
        "nome": dados.get("nome") or "",
        "equipe": dados.get("equipe") or "",
    }
    auth.salvar_filtro_padrao(session["usuario_id"], filtro)
    return jsonify({"ok": True})


@app.delete("/api/buscador/filtro-padrao")
@api_assinatura_necessaria
def api_remover_filtro_padrao():
    auth.salvar_filtro_padrao(session["usuario_id"], None)
    return jsonify({"ok": True})


@app.get("/api/eventos")
@api_assinatura_necessaria
def api_eventos():
    federacao = request.args.get("federacao")
    if federacao not in FEDERACOES:
        return jsonify({"erro": "federação inválida"}), 400
    try:
        eventos = listar_eventos(federacao)
    except Exception as exc:  # fonte externa pode falhar/mudar layout
        traceback.print_exc()
        return jsonify({"erro": f"não foi possível carregar eventos: {exc}"}), 502
    return jsonify(eventos)


def _normalizar_pesos(peso_kg, peso_sem_kimono):
    """ADCC e competições NO-GI usam o peso sem kimono; as demais usam o
    peso com kimono (a tabela de categorias já foi montada em cima disso).
    Se só um dos dois foi informado, deriva o outro considerando 1 kg de
    diferença pro kimono, pra sempre dar pra calcular os dois lados."""
    if peso_kg is None and peso_sem_kimono is not None:
        peso_kg = peso_sem_kimono + 1
    if peso_sem_kimono is None and peso_kg is not None:
        peso_sem_kimono = peso_kg - 1
    return peso_kg, peso_sem_kimono


def _categoria_completa(federacao, ano_nascimento, peso_kg, genero, data_nascimento=None, evento_id=None, peso_sem_kimono=None):
    if federacao in FEDERACOES_SMOOTHCOMP:
        modulo = FEDERACOES[federacao]["module"]
        resultado = {"categoria_idade": None}
        if not data_nascimento:
            return resultado
        if not evento_id or evento_id == TODAS:
            resultado["aviso_categoria"] = "selecione uma competição específica"
            return resultado
        data_referencia = modulo.data_referencia_evento(evento_id)
        idade_exata = modulo.idade_exata(data_nascimento, data_referencia)
        categoria = modulo.categoria_exata_para_idade(evento_id, idade_exata, data_nascimento)
        resultado["categoria_idade"] = categoria
        resultado["idade_exata"] = idade_exata
        resultado["data_referencia"] = data_referencia.strftime("%d/%m/%Y")

        peso_smoothcomp = peso_sem_kimono if federacao in FEDERACOES_SMOOTHCOMP_SEM_KIMONO else peso_kg
        if peso_smoothcomp is not None and categoria:
            if not genero:
                resultado["aviso_peso"] = "selecione o gênero"
            else:
                resultado["peso_categoria"] = modulo.categoria_peso_exata(evento_id, categoria, genero, peso_smoothcomp)
        return resultado

    idade_categoria = idade_mod.categoria_para(federacao, ano_nascimento)
    resultado = {"categoria_idade": idade_categoria}

    peso_bruto = peso_kg
    if evento_id and evento_id != TODAS:
        evento = next((e for e in listar_eventos(federacao) if e["id"] == evento_id), None)
        if evento and evento_sem_kimono(evento.get("nome", "")):
            peso_bruto = peso_sem_kimono

    if peso_bruto is not None:
        idade = idade_mod.idade_a_partir_do_ano(ano_nascimento)
        if idade >= 16 and not genero:
            resultado["peso_categoria"] = None
            resultado["aviso_peso"] = "selecione o gênero"
        else:
            resultado["peso_categoria"] = peso_mod.categoria_peso_para(federacao, idade, peso_bruto, genero)
    return resultado


@app.get("/api/categoria")
@api_assinatura_necessaria
def api_categoria():
    federacao = _parse_federacao(request.args.get("federacao"))
    genero = request.args.get("genero", "")
    peso_kg = request.args.get("peso_kg")
    peso_sem_kimono = request.args.get("peso_sem_kimono")
    data_nascimento_str = request.args.get("data_nascimento")
    evento_id = request.args.get("evento")

    if federacao is None:
        return jsonify({"erro": "federação inválida"}), 400

    data_nascimento = None
    if data_nascimento_str:
        try:
            data_nascimento = date.fromisoformat(data_nascimento_str)
        except ValueError:
            return jsonify({"erro": "data de nascimento inválida"}), 400
        ano_nascimento = data_nascimento.year
    else:
        try:
            ano_nascimento = int(request.args.get("ano_nascimento"))
        except (TypeError, ValueError):
            return jsonify({"erro": "informe a data de nascimento"}), 400

    try:
        peso_kg = float(peso_kg.replace(",", ".")) if peso_kg else None
        peso_sem_kimono = float(peso_sem_kimono.replace(",", ".")) if peso_sem_kimono else None
    except ValueError:
        return jsonify({"erro": "peso inválido"}), 400
    peso_kg, peso_sem_kimono = _normalizar_pesos(peso_kg, peso_sem_kimono)

    if federacao == TODAS or isinstance(federacao, list):
        resultado = {
            fid: _categoria_completa(fid, ano_nascimento, peso_kg, genero, data_nascimento, evento_id, peso_sem_kimono)
            for fid in _federacoes_da_lista(federacao)
        }
        return jsonify({"categorias": resultado})

    return jsonify(_categoria_completa(federacao, ano_nascimento, peso_kg, genero, data_nascimento, evento_id, peso_sem_kimono))


@app.get("/api/atletas")
@api_assinatura_necessaria
def api_atletas():
    federacao = _parse_federacao(request.args.get("federacao"))
    evento_id = request.args.get("evento")
    if federacao is None or not evento_id:
        return jsonify({"erro": "federação e evento são obrigatórios"}), 400

    data_nascimento_str = request.args.get("data_nascimento", "")
    ano_nascimento = ""
    if data_nascimento_str:
        try:
            ano_nascimento = str(date.fromisoformat(data_nascimento_str).year)
        except ValueError:
            return jsonify({"erro": "data de nascimento inválida"}), 400

    try:
        peso_kg = float(request.args.get("peso_kg", "").replace(",", ".")) if request.args.get("peso_kg") else None
        peso_sem_kimono = (
            float(request.args.get("peso_sem_kimono", "").replace(",", "."))
            if request.args.get("peso_sem_kimono") else None
        )
    except ValueError:
        return jsonify({"erro": "peso inválido"}), 400
    peso_kg, peso_sem_kimono = _normalizar_pesos(peso_kg, peso_sem_kimono)

    equipe = request.args.get("equipe", "")
    if equipe and not _usuario_atual_eh_mestre():
        return jsonify({"erro": "busca por equipe é exclusiva do perfil Mestre"}), 403

    filtros = {
        "nome": request.args.get("nome", ""),
        "equipe": equipe,
        "ano_nascimento": ano_nascimento,
        "data_nascimento": data_nascimento_str,
        "genero": request.args.get("genero", ""),
        "peso_kg": str(peso_kg) if peso_kg is not None else "",
        "peso_sem_kimono": str(peso_sem_kimono) if peso_sem_kimono is not None else "",
        "faixa": request.args.get("faixa", ""),
    }

    try:
        atletas, erros, total_eventos = buscar_atletas_agregado(federacao, evento_id, filtros)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não foi possível buscar atletas: {exc}"}), 502

    avisos = list(erros)
    if not atletas:
        avisos.append(
            "Nenhum atleta encontrado. Se for CBJJD ou CBJJO, a lista de "
            "inscritos só fica disponível enquanto a checagem do evento "
            "está aberta."
        )

    return jsonify({
        "total": len(atletas),
        "atletas": atletas,
        "eventos_pesquisados": total_eventos,
        "avisos": avisos,
    })


@app.get("/api/competicoes")
def api_competicoes():
    federacao = _parse_federacao(request.args.get("federacao", TODAS))
    if federacao is None:
        return jsonify({"erro": "federação inválida"}), 400

    try:
        competicoes_lista, erros = listar_competicoes(federacao)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"erro": f"não foi possível carregar competições: {exc}"}), 502

    return jsonify({"total": len(competicoes_lista), "competicoes": competicoes_lista, "avisos": erros})


@app.get("/alertas")
@login_necessario
def pagina_alertas():
    # A página mistura dois tipos de alerta: o de atleta (exige assinatura,
    # checado em /api/alertas) e o de competição nova (Plano Free, só
    # exige login) — por isso aqui é só login_necessario, não
    # assinatura_necessaria; quem não paga ainda consegue usar a parte
    # de competição.
    return send_from_directory("static", "alertas.html")


@app.get("/api/alertas")
@api_assinatura_necessaria
def api_listar_alertas():
    return jsonify(alertas.listar_alertas(session["usuario_id"]))


@app.post("/api/alertas")
@api_assinatura_necessaria
def api_criar_alerta():
    dados = request.get_json(silent=True) or {}
    titulo = (dados.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "dê um nome pro alerta"}), 400

    if (dados.get("equipe") or "").strip() and not _usuario_atual_eh_mestre():
        return jsonify({"erro": "alerta por equipe é exclusivo do perfil Mestre"}), 403

    federacao_bruta = dados.get("federacao", "")
    if _parse_federacao(federacao_bruta) is None and federacao_bruta != TODAS:
        return jsonify({"erro": "federação inválida"}), 400

    data_nascimento = dados.get("data_nascimento") or ""
    if data_nascimento:
        try:
            date.fromisoformat(data_nascimento)
        except ValueError:
            return jsonify({"erro": "data de nascimento inválida"}), 400

    try:
        peso_kg = float(str(dados.get("peso_kg")).replace(",", ".")) if dados.get("peso_kg") else None
        peso_sem_kimono = (
            float(str(dados.get("peso_sem_kimono")).replace(",", "."))
            if dados.get("peso_sem_kimono") else None
        )
    except ValueError:
        return jsonify({"erro": "peso inválido"}), 400
    peso_kg, peso_sem_kimono = _normalizar_pesos(peso_kg, peso_sem_kimono)

    alerta_id, erro = alertas.criar_alerta(
        usuario_id=session["usuario_id"],
        titulo=titulo,
        federacao=federacao_bruta or TODAS,
        data_nascimento=data_nascimento,
        genero=dados.get("genero") or "",
        faixa=dados.get("faixa") or "",
        peso_kg=str(peso_kg) if peso_kg is not None else "",
        peso_sem_kimono=str(peso_sem_kimono) if peso_sem_kimono is not None else "",
        nome_atleta=dados.get("nome") or "",
        equipe=dados.get("equipe") or "",
    )
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": alerta_id})


@app.delete("/api/alertas/<int:alerta_id>")
@api_assinatura_necessaria
def api_remover_alerta(alerta_id):
    removido = alertas.remover_alerta(session["usuario_id"], alerta_id)
    if not removido:
        return jsonify({"erro": "alerta não encontrado"}), 404
    return jsonify({"ok": True})


@app.get("/api/alertas-competicao")
@api_login_necessario
def api_listar_alertas_competicao():
    return jsonify(alertas.listar_alertas_competicao(session["usuario_id"]))


@app.post("/api/alertas-competicao")
@api_login_necessario
def api_criar_alerta_competicao():
    dados = request.get_json(silent=True) or {}
    titulo = (dados.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"erro": "dê um nome pro alerta"}), 400

    federacao_bruta = dados.get("federacao", "")
    if _parse_federacao(federacao_bruta) is None and federacao_bruta != TODAS:
        return jsonify({"erro": "federação inválida"}), 400

    alerta_id, erro = alertas.criar_alerta_competicao(
        usuario_id=session["usuario_id"],
        titulo=titulo,
        federacao=federacao_bruta or TODAS,
        publico=dados.get("publico") or "todos",
    )
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": alerta_id})


@app.delete("/api/alertas-competicao/<int:alerta_id>")
@api_login_necessario
def api_remover_alerta_competicao(alerta_id):
    removido = alertas.remover_alerta_competicao(session["usuario_id"], alerta_id)
    if not removido:
        return jsonify({"erro": "alerta não encontrado"}), 404
    return jsonify({"ok": True})


@app.get("/carreira")
@assinatura_necessaria
def pagina_carreira():
    return send_from_directory("static", "carreira.html")


@app.get("/api/carreira/perfil")
@api_assinatura_necessaria
def api_carreira_obter_perfil():
    return jsonify(carreira.obter_perfil(session["usuario_id"]))


@app.post("/api/carreira/perfil")
@api_assinatura_necessaria
def api_carreira_salvar_perfil():
    dados = request.get_json(silent=True) or {}
    perfil = carreira.salvar_perfil(session["usuario_id"], dados)
    return jsonify(perfil)


@app.get("/api/carreira/competicoes")
@api_assinatura_necessaria
def api_carreira_listar_competicoes():
    filtros = {
        "campeonato": request.args.get("campeonato", ""),
        "adversario": request.args.get("adversario", ""),
        "de": request.args.get("de", ""),
        "ate": request.args.get("ate", ""),
    }
    return jsonify(carreira.listar_competicoes(session["usuario_id"], filtros))


@app.post("/api/carreira/competicoes")
@api_assinatura_necessaria
def api_carreira_criar_competicao():
    dados = request.get_json(silent=True) or {}
    competicao_id, erro = carreira.criar_competicao(session["usuario_id"], dados)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": competicao_id})


@app.put("/api/carreira/competicoes/<int:competicao_id>")
@api_assinatura_necessaria
def api_carreira_atualizar_competicao(competicao_id):
    dados = request.get_json(silent=True) or {}
    ok, erro = carreira.atualizar_competicao(session["usuario_id"], competicao_id, dados)
    if not ok:
        status = 404 if erro == "competição não encontrada" else 400
        return jsonify({"erro": erro}), status
    return jsonify({"ok": True})


@app.delete("/api/carreira/competicoes/<int:competicao_id>")
@api_assinatura_necessaria
def api_carreira_remover_competicao(competicao_id):
    removida = carreira.remover_competicao(session["usuario_id"], competicao_id)
    if not removida:
        return jsonify({"erro": "competição não encontrada"}), 404
    return jsonify({"ok": True})


@app.get("/api/carreira/estatisticas")
@api_assinatura_necessaria
def api_carreira_estatisticas():
    return jsonify(carreira.calcular_estatisticas(session["usuario_id"]))


@app.get("/api/conta/nome-usuario")
@api_login_necessario
def api_obter_nome_usuario():
    usuario = auth.buscar_por_id(session["usuario_id"])
    return jsonify({"nome_usuario": usuario["nome_usuario"] if usuario else None})


@app.post("/api/conta/nome-usuario")
@api_login_necessario
def api_definir_nome_usuario():
    dados = request.get_json(silent=True) or {}
    ok, erro = auth.definir_nome_usuario(session["usuario_id"], dados.get("nome_usuario"))
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


@app.get("/meus-alunos")
@assinatura_necessaria
def pagina_meus_alunos():
    if not _usuario_atual_eh_mestre():
        return "Página não encontrada", 404
    return send_from_directory("static", "meus-alunos.html")


def _perfil_publico_vinculo(usuario_id):
    """Nome/faixa/academia pra exibir em Meus Alunos / Meu Mestre — usa o
    perfil de Minha Carreira quando existe, senão cai pro nome de usuário
    (o vínculo pode ter sido criado antes da outra parte preencher algo)."""
    perfil = carreira.obter_perfil(usuario_id)
    if not perfil.get("nome"):
        usuario = auth.buscar_por_id(usuario_id)
        perfil["nome"] = (usuario and (usuario.get("nome_usuario") or usuario.get("email"))) or "(perfil incompleto)"
    return perfil


@app.get("/api/meus-alunos")
@api_assinatura_necessaria
def api_listar_meus_alunos():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    ids = carreira.listar_ids_alunos_do_mestre(session["usuario_id"])
    return jsonify([_perfil_publico_vinculo(aluno_id) for aluno_id in ids])


@app.post("/api/meus-alunos")
@api_assinatura_necessaria
def api_adicionar_aluno():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    aluno_id = dados.get("aluno_id")
    aluno = auth.buscar_por_id(aluno_id) if aluno_id else auth.buscar_por_nome_usuario(dados.get("nome_usuario"))
    if not aluno:
        return jsonify({"erro": "nenhum usuário encontrado"}), 404
    ok, erro = carreira.criar_vinculo(mestre_id=session["usuario_id"], aluno_id=aluno["id"])
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


@app.get("/api/meus-alunos/buscar")
@api_assinatura_necessaria
def api_buscar_alunos_por_academia():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403

    academia = (request.args.get("academia") or "").strip()
    if not academia:
        academia = (carreira.obter_perfil(session["usuario_id"]).get("academia") or "").strip()
    if not academia:
        return jsonify({"erro": "informe uma academia (ou cadastre a sua em Minha Carreira → Perfil)"}), 400

    ja_vinculados = set(carreira.listar_ids_alunos_do_mestre(session["usuario_id"]))
    ja_vinculados.add(session["usuario_id"])
    candidatos = carreira.buscar_atletas_por_academia(academia, ja_vinculados)

    atletas = []
    for perfil in candidatos:
        usuario = auth.buscar_por_id(perfil["usuario_id"])
        if not usuario or usuario["tipo_perfil"] == "mestre" or usuario["email"] == ADMIN_EMAIL:
            continue
        atletas.append(perfil)
    return jsonify({"academia": academia, "atletas": atletas})


@app.delete("/api/meus-alunos/<int:aluno_id>")
@api_assinatura_necessaria
def api_remover_aluno(aluno_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    carreira.remover_vinculo(mestre_id=session["usuario_id"], aluno_id=aluno_id)
    return jsonify({"ok": True})


@app.get("/meus-alunos/<int:aluno_id>")
@assinatura_necessaria
def pagina_aluno_detalhe(aluno_id):
    if not _usuario_atual_eh_mestre():
        return "Página não encontrada", 404
    return send_from_directory("static", "aluno-detalhe.html")


@app.get("/api/meus-alunos/<int:aluno_id>")
@api_assinatura_necessaria
def api_aluno_detalhe(aluno_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    if not carreira.vinculo_existe(mestre_id=session["usuario_id"], aluno_id=aluno_id):
        return jsonify({"erro": "aluno não encontrado"}), 404

    usuario_aluno = auth.buscar_por_id(aluno_id)
    return jsonify({
        "perfil": carreira.obter_perfil(aluno_id),
        "email": usuario_aluno["email"] if usuario_aluno else None,
        "competicoes": carreira.listar_competicoes(aluno_id),
        "estatisticas": carreira.calcular_estatisticas(aluno_id),
    })


@app.get("/turmas")
@assinatura_necessaria
def pagina_turmas():
    if not _usuario_atual_eh_mestre():
        return "Página não encontrada", 404
    return send_from_directory("static", "turmas.html")


def _turma_com_alunos(turma):
    turma = dict(turma)
    turma["alunos"] = [_perfil_publico_vinculo(aid) for aid in turma.pop("aluno_ids")]
    return turma


@app.get("/api/turmas")
@api_assinatura_necessaria
def api_listar_turmas():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    return jsonify([_turma_com_alunos(t) for t in turmas.listar_turmas(session["usuario_id"])])


@app.post("/api/turmas")
@api_assinatura_necessaria
def api_criar_turma():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    turma_id, erro = turmas.criar_turma(session["usuario_id"], dados)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": turma_id})


@app.put("/api/turmas/<int:turma_id>")
@api_assinatura_necessaria
def api_atualizar_turma(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    ok, erro = turmas.atualizar_turma(session["usuario_id"], turma_id, dados)
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


@app.delete("/api/turmas/<int:turma_id>")
@api_assinatura_necessaria
def api_remover_turma(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    turmas.remover_turma(session["usuario_id"], turma_id)
    return jsonify({"ok": True})


@app.post("/api/turmas/<int:turma_id>/alunos")
@api_assinatura_necessaria
def api_turma_adicionar_aluno(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    try:
        aluno_id = int(dados.get("aluno_id"))
    except (TypeError, ValueError):
        return jsonify({"erro": "aluno_id inválido"}), 400
    if not carreira.vinculo_existe(mestre_id=session["usuario_id"], aluno_id=aluno_id):
        return jsonify({"erro": "esse aluno não está na sua lista de Meus Alunos"}), 400
    ok, erro = turmas.adicionar_aluno(session["usuario_id"], turma_id, aluno_id)
    if not ok:
        return jsonify({"erro": erro}), 404
    return jsonify({"ok": True})


@app.delete("/api/turmas/<int:turma_id>/alunos/<int:aluno_id>")
@api_assinatura_necessaria
def api_turma_remover_aluno(turma_id, aluno_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    turmas.remover_aluno(session["usuario_id"], turma_id, aluno_id)
    return jsonify({"ok": True})


@app.get("/api/turmas/posicoes")
@api_assinatura_necessaria
def api_listar_posicoes():
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    return jsonify(turmas.POSICOES)


@app.get("/api/turmas/<int:turma_id>/planos-aula")
@api_assinatura_necessaria
def api_listar_planos_aula(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    if not turmas.turma_pertence_ao_mestre(session["usuario_id"], turma_id):
        return jsonify({"erro": "turma não encontrada"}), 404
    return jsonify(turmas.listar_planos_aula(session["usuario_id"], turma_id))


@app.post("/api/turmas/<int:turma_id>/planos-aula")
@api_assinatura_necessaria
def api_criar_plano_aula(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    plano_id, erro = turmas.criar_plano_aula(session["usuario_id"], turma_id, dados)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "id": plano_id})


@app.delete("/api/turmas/<int:turma_id>/planos-aula/<int:plano_id>")
@api_assinatura_necessaria
def api_remover_plano_aula(turma_id, plano_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    turmas.remover_plano_aula(session["usuario_id"], turma_id, plano_id)
    return jsonify({"ok": True})


@app.post("/api/turmas/<int:turma_id>/plano-ia")
@api_assinatura_necessaria
def api_sugerir_plano_ia(turma_id):
    if not _usuario_atual_eh_mestre():
        return jsonify({"erro": "exclusivo do perfil Mestre"}), 403
    dados = request.get_json(silent=True) or {}
    foco = dados.get("foco", "")
    resumo = dados.get("resumo", "")
    resultado, erro = turmas.gerar_plano_ia(session["usuario_id"], turma_id, foco, resumo)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify(resultado)


@app.get("/api/carreira/meu-mestre")
@api_assinatura_necessaria
def api_listar_meus_mestres():
    ids = carreira.listar_ids_mestres_do_aluno(session["usuario_id"])
    return jsonify([_perfil_publico_vinculo(mestre_id) for mestre_id in ids])


@app.post("/api/carreira/meu-mestre")
@api_assinatura_necessaria
def api_adicionar_meu_mestre():
    dados = request.get_json(silent=True) or {}
    mestre = auth.buscar_por_nome_usuario(dados.get("nome_usuario"))
    if not mestre:
        return jsonify({"erro": "nenhum usuário encontrado com esse nome de usuário"}), 404
    if mestre["tipo_perfil"] != "mestre" and mestre["email"] != ADMIN_EMAIL:
        return jsonify({"erro": "esse usuário não é um perfil Mestre"}), 400
    ok, erro = carreira.criar_vinculo(mestre_id=mestre["id"], aluno_id=session["usuario_id"])
    if not ok:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True})


@app.delete("/api/carreira/meu-mestre/<int:mestre_id>")
@api_assinatura_necessaria
def api_remover_meu_mestre(mestre_id):
    carreira.remover_vinculo(mestre_id=mestre_id, aluno_id=session["usuario_id"])
    return jsonify({"ok": True})


@app.get("/assinatura")
@login_necessario
def pagina_assinatura():
    return send_from_directory("static", "assinatura.html")


@app.get("/assinatura/sucesso")
@login_necessario
def pagina_assinatura_sucesso():
    return send_from_directory("static", "assinatura-sucesso.html")


@app.post("/api/checkout")
@api_login_necessario
def api_checkout():
    dados = request.get_json(silent=True) or {}
    plano = dados.get("plano", "")
    periodicidade = dados.get("periodicidade", "")

    usuario = auth.buscar_por_id(session["usuario_id"])
    url, erro = pagamentos.criar_sessao_checkout(usuario, plano, periodicidade)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "url": url})


@app.post("/api/portal")
@api_login_necessario
def api_portal():
    usuario = auth.buscar_por_id(session["usuario_id"])
    url, erro = pagamentos.criar_sessao_portal(usuario)
    if erro:
        return jsonify({"erro": erro}), 400
    return jsonify({"ok": True, "url": url})


@app.post("/webhook/stripe")
def webhook_stripe():
    payload = request.get_data()
    assinatura_header = request.headers.get("Stripe-Signature", "")
    try:
        pagamentos.processar_evento_webhook(payload, assinatura_header)
    except ValueError:
        return "assinatura inválida", 400
    except Exception:
        traceback.print_exc()
        return "erro ao processar evento", 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    # use_reloader=False: com o reload automático ligado, o Flask importa
    # este módulo duas vezes (processo monitor + processo de trabalho), o
    # que duplicaria a thread de verificação de alertas.
    app.run(debug=True, port=5050, use_reloader=False)
