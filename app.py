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
import noticias
from connectors import FEDERACOES, TODAS, listar_eventos, buscar_atletas_agregado, listar_competicoes
from connectors import adcc
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


def _iniciar_verificacao_periodica_de_alertas():
    def loop():
        while True:
            time.sleep(INTERVALO_ALERTAS_SEGUNDOS)
            try:
                alertas.verificar_todos()
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


@app.get("/")
def index():
    # Pública: qualquer um vê as notícias em destaque. O Buscador em si
    # (dentro da página) fica escondido pelo próprio JS até logar.
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


@app.get("/api/noticias")
def api_listar_noticias():
    return jsonify([
        {
            "id": n["id"],
            "manchete": n["manchete"],
            "texto": n["texto"],
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
    arquivo = request.files.get("imagem")
    if not arquivo or not arquivo.filename:
        return jsonify({"erro": "selecione uma imagem"}), 400
    noticia_id, erro = noticias.criar_noticia(manchete, texto, arquivo, arquivo.filename)
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
    return jsonify({
        "logado": True,
        "email": usuario["email"],
        "admin": eh_admin,
        "tipo_perfil": usuario["tipo_perfil"],
        "mestre": eh_admin or usuario["tipo_perfil"] == "mestre",
    })


@app.post("/api/cadastro")
def api_cadastro():
    dados = request.get_json(silent=True) or {}
    usuario_id, erro = auth.cadastrar(dados.get("email"), dados.get("senha"), dados.get("tipo_perfil"))
    if erro:
        return jsonify({"erro": erro}), 400
    session["usuario_id"] = usuario_id
    return jsonify({"ok": True, "email": dados.get("email", "").strip().lower()})


@app.post("/api/entrar")
def api_entrar():
    dados = request.get_json(silent=True) or {}
    usuario, erro = auth.autenticar(dados.get("email"), dados.get("senha"))
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


@app.get("/api/eventos")
@api_login_necessario
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
    if federacao == "adcc":
        resultado = {"categoria_idade": None}
        if not data_nascimento:
            return resultado
        if not evento_id or evento_id == TODAS:
            resultado["aviso_categoria"] = "selecione uma competição específica"
            return resultado
        data_referencia = adcc.data_referencia_evento(evento_id)
        idade_exata = adcc.idade_exata(data_nascimento, data_referencia)
        categoria = adcc.categoria_exata_para_idade(evento_id, idade_exata)
        resultado["categoria_idade"] = categoria
        resultado["idade_exata"] = idade_exata
        resultado["data_referencia"] = data_referencia.strftime("%d/%m/%Y")

        if peso_sem_kimono is not None and categoria:
            if not genero:
                resultado["aviso_peso"] = "selecione o gênero"
            else:
                resultado["peso_categoria"] = adcc.categoria_peso_exata(evento_id, categoria, genero, peso_sem_kimono)
        return resultado

    idade_categoria = idade_mod.categoria_para(federacao, ano_nascimento)
    resultado = {"categoria_idade": idade_categoria}
    if peso_kg is not None:
        idade = idade_mod.idade_a_partir_do_ano(ano_nascimento)
        if idade >= 16 and not genero:
            resultado["peso_categoria"] = None
            resultado["aviso_peso"] = "selecione o gênero"
        else:
            resultado["peso_categoria"] = peso_mod.categoria_peso_para(federacao, idade, peso_kg, genero)
    return resultado


@app.get("/api/categoria")
@api_login_necessario
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
@api_login_necessario
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
    return send_from_directory("static", "alertas.html")


@app.get("/api/alertas")
@api_login_necessario
def api_listar_alertas():
    return jsonify(alertas.listar_alertas(session["usuario_id"]))


@app.post("/api/alertas")
@api_login_necessario
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

    alerta_id = alertas.criar_alerta(
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
    return jsonify({"ok": True, "id": alerta_id})


@app.delete("/api/alertas/<int:alerta_id>")
@api_login_necessario
def api_remover_alerta(alerta_id):
    removido = alertas.remover_alerta(session["usuario_id"], alerta_id)
    if not removido:
        return jsonify({"erro": "alerta não encontrado"}), 404
    return jsonify({"ok": True})


if __name__ == "__main__":
    # use_reloader=False: com o reload automático ligado, o Flask importa
    # este módulo duas vezes (processo monitor + processo de trabalho), o
    # que duplicaria a thread de verificação de alertas.
    app.run(debug=True, port=5050, use_reloader=False)
