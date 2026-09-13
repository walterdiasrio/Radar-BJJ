"""Alertas por e-mail: o usuário salva um conjunto de filtros (os mesmos do
Buscador de Atletas) e recebe e-mail quando aparece um atleta NOVO batendo
com esse filtro em qualquer competição futura de todas as federações.

Reaproveita a mesma busca do Buscador (connectors.buscar_atletas_agregado)
em vez de duplicar a lógica de filtro — um alerta é só uma busca salva,
verificada periodicamente em background (ver app.py). Como os resultados
não têm um ID estável entre buscas, cada atleta encontrado ganha uma
"chave" (hash dos campos que o identificam) guardada em alertas_vistos;
só o que aparece pela primeira vez gera e-mail.

Envio de e-mail via Resend (https://resend.com). Sem RESEND_API_KEY
configurada, o e-mail só é logado no console (útil pra testar localmente
sem gastar envio de verdade).
"""
import hashlib
import html as html_mod
import os
import re
import sqlite3
import threading
import traceback
from datetime import date
from pathlib import Path

import requests

import agenda
import auth
import pagamentos
from connectors import FEDERACOES, TODAS, buscar_atletas_agregado
from connectors import datas as datas_mod

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "alertas.db"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
REMETENTE = os.environ.get("ALERTA_REMETENTE", "Radar BJJ <no-reply@radarbjj.com>")
URL_SITE = os.environ.get("URL_SITE", "http://localhost:5050")

# Limite por conta — evita que um único login seja usado pra criar alertas
# de várias pessoas diferentes (cada assinatura é pensada pra um atleta só).
LIMITE_ALERTAS_POR_USUARIO = 2

# Alertas de competição nova são liberados pro Plano Free (sem exigir
# assinatura), mas com o mesmo limite dos alertas de atleta por conta.
LIMITE_ALERTAS_COMPETICAO_POR_USUARIO = 2


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                federacao TEXT NOT NULL,
                data_nascimento TEXT,
                genero TEXT,
                faixa TEXT,
                peso_kg TEXT,
                peso_sem_kimono TEXT,
                nome_atleta TEXT,
                equipe TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertas_vistos (
                alerta_id INTEGER NOT NULL,
                chave TEXT NOT NULL,
                visto_em TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (alerta_id, chave)
            )
        """)
        # Alertas de "competição nova" (ver seção mais abaixo) são um tipo
        # separado — sem os filtros de atleta, e liberado pro Plano Free
        # (só precisa estar logado, não precisa assinatura), então ficam em
        # tabelas próprias em vez de reaproveitar "alertas"/"alertas_vistos".
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertas_competicao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                federacao TEXT NOT NULL,
                publico TEXT NOT NULL DEFAULT 'todos',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertas_competicao_vistas (
                alerta_id INTEGER NOT NULL,
                chave TEXT NOT NULL,
                vista_em TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (alerta_id, chave)
            )
        """)
        # Alerta de prazo de inscrição (Plano PRO, ver verificar_prazos_
        # agenda mais abaixo): marca que já mandamos o e-mail de "faltam N
        # dias" pra essa marcação "Tenho Interesse" específica, pra nunca
        # mandar duas vezes o mesmo aviso (o verificador roda a cada
        # INTERVALO_ALERTAS_SEGUNDOS, bem mais frequente que uma vez por dia).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agenda_alertas_prazo_enviados (
                usuario_id INTEGER NOT NULL,
                chave TEXT NOT NULL,
                tipo TEXT NOT NULL,
                enviado_em TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (usuario_id, chave, tipo)
            )
        """)


def _parse_federacao(bruto):
    if not bruto or bruto == TODAS:
        return TODAS
    ids = [f.strip() for f in bruto.split(",") if f.strip() in FEDERACOES]
    if not ids:
        return TODAS
    return ids[0] if len(ids) == 1 else ids


def _chave_atleta(atleta):
    """Identifica um atleta+inscrição de forma estável entre buscas (os
    conectores não expõem um ID único de registro)."""
    partes = [
        atleta.get("federacao", ""), atleta.get("evento", ""), atleta.get("nome", ""),
        atleta.get("equipe", ""), atleta.get("categoria_idade", ""), atleta.get("genero", ""),
        atleta.get("peso", ""), atleta.get("faixa", ""),
    ]
    bruto = "|".join((p or "").strip().lower() for p in partes)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _rodar_busca(alerta):
    federacao = _parse_federacao(alerta["federacao"])

    ano_nascimento = ""
    if alerta["data_nascimento"]:
        try:
            ano_nascimento = str(date.fromisoformat(alerta["data_nascimento"]).year)
        except ValueError:
            pass

    filtros = {
        "nome": alerta["nome_atleta"] or "",
        "equipe": alerta["equipe"] or "",
        "ano_nascimento": ano_nascimento,
        "data_nascimento": alerta["data_nascimento"] or "",
        "genero": alerta["genero"] or "",
        "peso_kg": alerta["peso_kg"] or "",
        "peso_sem_kimono": alerta["peso_sem_kimono"] or "",
        "faixa": alerta["faixa"] or "",
    }
    atletas, _erros, _total = buscar_atletas_agregado(federacao, TODAS, filtros, contexto="alerta")
    return atletas


def _marcar_vistos(alerta_id, atletas):
    if not atletas:
        return
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO alertas_vistos (alerta_id, chave) VALUES (?, ?)",
            [(alerta_id, _chave_atleta(a)) for a in atletas],
        )


def criar_alerta(usuario_id, titulo, federacao, data_nascimento, genero, faixa,
                  peso_kg, peso_sem_kimono, nome_atleta, equipe):
    """Cria o alerta (inativo) e devolve na hora — a busca pra descobrir
    quem já está inscrito hoje (pra marcar como "visto" e não gerar e-mail
    de gente que já estava lá antes do alerta existir) pode demorar dezenas
    de segundos quando cobre várias federações, então roda em background;
    o alerta só fica ativo (entra na verificação periódica) depois que essa
    captura inicial termina.

    Retorna (alerta_id, erro) — erro é None em caso de sucesso."""
    with _conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM alertas WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()["total"]
        if total >= LIMITE_ALERTAS_POR_USUARIO:
            return None, (
                f"limite de {LIMITE_ALERTAS_POR_USUARIO} alertas por conta atingido — "
                "remova um alerta antes de criar outro"
            )

        cursor = conn.execute("""
            INSERT INTO alertas
                (usuario_id, titulo, federacao, data_nascimento, genero, faixa,
                 peso_kg, peso_sem_kimono, nome_atleta, equipe, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (usuario_id, titulo, federacao, data_nascimento, genero, faixa,
              peso_kg, peso_sem_kimono, nome_atleta, equipe))
        alerta_id = cursor.lastrowid

    alerta = {
        "id": alerta_id, "federacao": federacao, "data_nascimento": data_nascimento,
        "genero": genero, "faixa": faixa, "peso_kg": peso_kg,
        "peso_sem_kimono": peso_sem_kimono, "nome_atleta": nome_atleta, "equipe": equipe,
    }

    def _preparar():
        try:
            _marcar_vistos(alerta_id, _rodar_busca(alerta))
        except Exception:
            traceback.print_exc()
        finally:
            with _conn() as conn:
                conn.execute("UPDATE alertas SET ativo = 1 WHERE id = ?", (alerta_id,))

    threading.Thread(target=_preparar, daemon=True).start()
    return alerta_id, None


def listar_alertas(usuario_id):
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM alertas WHERE usuario_id = ? ORDER BY criado_em DESC", (usuario_id,)
        ).fetchall()
    return [dict(linha) for linha in linhas]


def remover_alerta(usuario_id, alerta_id):
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM alertas WHERE id = ? AND usuario_id = ?", (alerta_id, usuario_id)
        )
        conn.execute("DELETE FROM alertas_vistos WHERE alerta_id = ?", (alerta_id,))
        return cursor.rowcount > 0


def contar_alertas_por_usuario():
    """{usuario_id: total de alertas (atleta + competição) cadastrados
    agora} — usado no admin (Gerenciar Usuários). Conta os dois tipos
    juntos; remover_alerta apaga a linha de verdade, então isso já reflete
    só o que está ativo/existente, sem precisar filtrar por "ativo"."""
    with _conn() as conn:
        linhas = conn.execute("""
            SELECT usuario_id, COUNT(*) AS total FROM (
                SELECT usuario_id FROM alertas
                UNION ALL
                SELECT usuario_id FROM alertas_competicao
            )
            GROUP BY usuario_id
        """).fetchall()
    return {linha["usuario_id"]: linha["total"] for linha in linhas}


def usuarios_com_alerta_de_atleta_ativo():
    """IDs distintos de usuários com pelo menos um alerta de atleta ativo —
    usado periodicamente (ver app.py) pra cancelar quem não tem mais
    assinatura (alerta de atleta é exclusivo do Plano PRO)."""
    with _conn() as conn:
        linhas = conn.execute("SELECT DISTINCT usuario_id FROM alertas WHERE ativo = 1").fetchall()
    return [linha["usuario_id"] for linha in linhas]


def cancelar_alertas_de_atleta(usuario_id):
    """Cancela (apaga) todos os alertas de atleta de um usuário — chamado
    quando ele deixa de ter assinatura ativa (volta pro Plano Free, que só
    permite alerta de competição). Retorna quantos foram cancelados."""
    with _conn() as conn:
        ids = [
            linha["id"] for linha in
            conn.execute("SELECT id FROM alertas WHERE usuario_id = ?", (usuario_id,))
        ]
        if not ids:
            return 0
        conn.execute("DELETE FROM alertas WHERE usuario_id = ?", (usuario_id,))
        conn.executemany(
            "DELETE FROM alertas_vistos WHERE alerta_id = ?", [(aid,) for aid in ids]
        )
    return len(ids)


# ---------------------------------------------------------------------------
# Alertas de "competição nova" — criados na aba Competições, avisam por
# e-mail quando uma competição nova aparece pra federação/público
# escolhidos (sem filtro de atleta — é sobre o evento em si). Feature do
# Plano Free: não exige assinatura, só login (ver api_login_necessario em
# app.py), diferente dos alertas de atleta acima.
# ---------------------------------------------------------------------------
PUBLICOS_ALERTA_COMPETICAO = ("todos", "kids", "adulto")


def _chave_competicao(c):
    """Identifica uma competição de forma estável entre buscas (os
    conectores não expõem um ID único de evento)."""
    partes = [c.get("federacao", ""), c.get("nome", ""), c.get("data", "")]
    bruto = "|".join((p or "").strip().lower() for p in partes)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _rodar_busca_competicoes(alerta):
    from connectors import listar_competicoes  # import tardio: evita ciclo de import
    federacao = _parse_federacao(alerta["federacao"])
    competicoes, _erros = listar_competicoes(federacao)
    publico = alerta["publico"]
    if publico and publico != "todos":
        competicoes = [c for c in competicoes if c.get("publico") in (publico, "ambos")]
    return competicoes


def _marcar_competicoes_vistas(alerta_id, competicoes):
    if not competicoes:
        return
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO alertas_competicao_vistas (alerta_id, chave) VALUES (?, ?)",
            [(alerta_id, _chave_competicao(c)) for c in competicoes],
        )


def criar_alerta_competicao(usuario_id, titulo, federacao, publico):
    """Retorna (alerta_id, erro). Mesma lógica do alerta de atleta: cria
    inativo, marca as competições de hoje como "já vistas" em background
    (pra não gerar e-mail de coisa que já existia antes do alerta) e só
    depois ativa."""
    publico = publico if publico in PUBLICOS_ALERTA_COMPETICAO else "todos"
    with _conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS total FROM alertas_competicao WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()["total"]
        if total >= LIMITE_ALERTAS_COMPETICAO_POR_USUARIO:
            return None, (
                f"limite de {LIMITE_ALERTAS_COMPETICAO_POR_USUARIO} alertas de competição por conta "
                "atingido — remova um alerta antes de criar outro"
            )

        cursor = conn.execute(
            """INSERT INTO alertas_competicao (usuario_id, titulo, federacao, publico, ativo)
               VALUES (?, ?, ?, ?, 0)""",
            (usuario_id, titulo, federacao, publico),
        )
        alerta_id = cursor.lastrowid

    alerta = {"id": alerta_id, "federacao": federacao, "publico": publico}

    def _preparar():
        try:
            _marcar_competicoes_vistas(alerta_id, _rodar_busca_competicoes(alerta))
        except Exception:
            traceback.print_exc()
        finally:
            with _conn() as conn:
                conn.execute("UPDATE alertas_competicao SET ativo = 1 WHERE id = ?", (alerta_id,))

    threading.Thread(target=_preparar, daemon=True).start()
    return alerta_id, None


def listar_alertas_competicao(usuario_id):
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM alertas_competicao WHERE usuario_id = ? ORDER BY criado_em DESC", (usuario_id,)
        ).fetchall()
    return [dict(linha) for linha in linhas]


def remover_alerta_competicao(usuario_id, alerta_id):
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM alertas_competicao WHERE id = ? AND usuario_id = ?", (alerta_id, usuario_id)
        )
        conn.execute("DELETE FROM alertas_competicao_vistas WHERE alerta_id = ?", (alerta_id,))
        return cursor.rowcount > 0


def _enviar_email_alerta_competicao(destinatario, titulo_alerta, competicoes):
    linhas = "".join(
        f"<li><b>{c.get('nome', '')}</b> — {c.get('federacao', '')}, "
        f"{c.get('data', '')} — {c.get('local', '')}</li>"
        for c in competicoes
    )
    corpo = (
        f'<p>Competição(ões) nova(s) pro seu alerta "<b>{titulo_alerta}</b>":</p>'
        f"<ul>{linhas}</ul>"
        f'<p><a href="{URL_SITE}/competicoes">Ver em Competições</a></p>'
    )
    enviar_email(destinatario, f'Radar BJJ — nova competição em "{titulo_alerta}"', corpo)


def _verificar_alerta_competicao(alerta):
    competicoes = _rodar_busca_competicoes(alerta)
    if not competicoes:
        return

    with _conn() as conn:
        vistas = {
            row["chave"] for row in
            conn.execute(
                "SELECT chave FROM alertas_competicao_vistas WHERE alerta_id = ?", (alerta["id"],)
            )
        }

    novas = [c for c in competicoes if _chave_competicao(c) not in vistas]
    _marcar_competicoes_vistas(alerta["id"], competicoes)

    if not novas:
        return

    usuario = auth.buscar_por_id(alerta["usuario_id"])
    if usuario:
        _enviar_email_alerta_competicao(usuario["email"], alerta["titulo"], novas)


def verificar_todas_competicoes():
    """Chamada periodicamente (mesma thread de fundo dos alertas de atleta,
    ver app.py) pra checar todos os alertas de competição ativos."""
    with _conn() as conn:
        alertas = [
            dict(linha) for linha in
            conn.execute("SELECT * FROM alertas_competicao WHERE ativo = 1")
        ]

    for alerta in alertas:
        try:
            _verificar_alerta_competicao(alerta)
        except Exception:
            traceback.print_exc()


# Dias antes do prazo de inscrição em que mandamos o aviso — 7 dias (dá
# tempo de se organizar) e 1 dia (último aviso antes de fechar).
DIAS_ALERTA_PRAZO_INSCRICAO = (7, 1)


def _ja_avisou_prazo(usuario_id, chave, tipo):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT 1 FROM agenda_alertas_prazo_enviados WHERE usuario_id = ? AND chave = ? AND tipo = ?",
            (usuario_id, chave, tipo),
        ).fetchone()
    return linha is not None


def _marcar_prazo_avisado(usuario_id, chave, tipo):
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO agenda_alertas_prazo_enviados (usuario_id, chave, tipo) VALUES (?, ?, ?)",
            (usuario_id, chave, tipo),
        )


def _enviar_email_prazo_inscricao(destinatario, item, dias_restantes, prazo):
    prazo_texto = datas_mod.formatar_data_iso(prazo.isoformat())
    urgencia = "amanhã" if dias_restantes == 1 else f"em {dias_restantes} dias"
    corpo = (
        f'<p>As inscrições de <b>{item["nome"]}</b> ({item["federacao"]}) — competição que você marcou '
        f'"Tenho Interesse" na sua Agenda — encerram <b>{urgencia}</b>, no dia {prazo_texto}.</p>'
        f'<p>{item.get("local", "")}</p>'
        f'<p><a href="{URL_SITE}/competicoes">Ver em Competições</a></p>'
    )
    assunto = (
        f'Radar BJJ — inscrições de "{item["nome"]}" encerram amanhã'
        if dias_restantes == 1
        else f'Radar BJJ — faltam {dias_restantes} dias pro prazo de inscrição de "{item["nome"]}"'
    )
    enviar_email(destinatario, assunto, corpo)


def verificar_prazos_agenda():
    """Exclusivo do Plano PRO: pra cada competição marcada "Tenho
    Interesse" na Agenda (de qualquer usuário) cujo prazo de inscrição
    esteja a exatamente 7 ou 1 dia(s), manda um e-mail avisando — uma vez
    só por marcação/prazo (ver agenda_alertas_prazo_enviados).

    Faz UMA busca ao vivo "todas as federações" (bem mais barato que uma
    por usuário/marcação) e casa cada marcação pela mesma chave (hash de
    federação+nome+data) que agenda.py já usa — a mesma técnica de
    _chave_competicao logo acima, pro mesmo problema (conectores não têm
    ID de evento estável entre buscas)."""
    interesses = agenda.listar_interesses_ativos()
    if not interesses:
        return

    from connectors import listar_competicoes  # import tardio: evita ciclo de import
    competicoes, _erros = listar_competicoes(TODAS)
    prazo_por_chave = {}
    for c in competicoes:
        prazo_iso = c.get("prazo_inscricao_iso")
        if not prazo_iso:
            continue
        chave = agenda.chave_de(c.get("federacao", ""), c.get("nome", ""), c.get("data", ""))
        prazo_por_chave[chave] = prazo_iso

    hoje = date.today()
    for item in interesses:
        prazo_iso = prazo_por_chave.get(item["chave"])
        if not prazo_iso:
            continue
        try:
            prazo = date.fromisoformat(prazo_iso)
        except ValueError:
            continue

        dias_restantes = (prazo - hoje).days
        if dias_restantes not in DIAS_ALERTA_PRAZO_INSCRICAO:
            continue

        tipo = f"{dias_restantes}d"
        if _ja_avisou_prazo(item["usuario_id"], item["chave"], tipo):
            continue
        if not pagamentos.usuario_tem_acesso(item["usuario_id"]):
            continue

        usuario = auth.buscar_por_id(item["usuario_id"])
        if not usuario:
            continue

        try:
            _enviar_email_prazo_inscricao(usuario["email"], item, dias_restantes, prazo)
        except Exception:
            traceback.print_exc()
            continue
        _marcar_prazo_avisado(item["usuario_id"], item["chave"], tipo)


def _html_para_texto_simples(html_str):
    """Fallback text/plain gerado a partir do HTML — não é sofisticado (só
    pras tags/entidades que a gente mesmo gera nos e-mails daqui, não pra
    HTML arbitrário de terceiros), mas evita mandar e-mail só em HTML.
    Motivo (11/09/2026): relato de contas @outlook/@hotmail não recebendo
    o e-mail de confirmação de cadastro — e-mail 100% HTML (sem a parte
    text/plain alternativa) é um sinal que os filtros da Microsoft pesam
    mais que os do Gmail. Não é garantia de resolver sozinho (o principal
    suspeito é reputação do remetente com a Microsoft, não corrigível por
    código — ver auth.py/app.py), mas é uma melhoria de graça, sem risco,
    que vale fazer de qualquer forma."""
    texto = re.sub(r"(?i)<(br|/p|/li|/div|/h[1-6])\s*/?>", "\n", html_str)
    texto = re.sub(
        r'(?is)<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        lambda m: f"{re.sub('<[^>]+>', '', m.group(2))} ({m.group(1)})",
        texto,
    )
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = html_mod.unescape(texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n\n", texto)
    return texto.strip()


def enviar_email(destinatario, assunto, corpo_html, anexos=None):
    """anexos, se informado: lista de {"filename": ..., "content_base64": ...}
    (ver turmas/planner_pdf — usado pra mandar o Planner de Aulas em PDF)."""
    if not RESEND_API_KEY:
        print(f"[alertas] RESEND_API_KEY não configurada — e-mail não enviado "
              f"(para={destinatario}, assunto={assunto!r})")
        return False
    corpo = {
        "from": REMETENTE, "to": [destinatario], "subject": assunto,
        "html": corpo_html, "text": _html_para_texto_simples(corpo_html),
    }
    if anexos:
        corpo["attachments"] = [
            {"filename": a["filename"], "content": a["content_base64"]} for a in anexos
        ]
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json=corpo,
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"[alertas] falha de rede ao enviar e-mail: {exc}")
        return False
    if resp.status_code >= 300:
        print(f"[alertas] erro ao enviar e-mail: {resp.status_code} {resp.text}")
        return False
    return True


def _enviar_email_alerta(destinatario, titulo_alerta, atletas):
    linhas = "".join(
        f"<li><b>{a.get('nome', '')}</b> — {a.get('equipe', '')} — {a.get('federacao', '')}, "
        f"{a.get('evento', '')} ({a.get('data', '')}) — {a.get('categoria_idade', '')} / "
        f"{a.get('genero', '')} / {a.get('faixa', '')} / {a.get('peso', '')}</li>"
        for a in atletas
    )
    corpo = (
        f'<p>Novo(s) atleta(s) encontrado(s) pro seu alerta "<b>{titulo_alerta}</b>":</p>'
        f"<ul>{linhas}</ul>"
        f'<p><a href="{URL_SITE}/">Ver no Radar BJJ</a></p>'
    )
    enviar_email(destinatario, f'Radar BJJ — novidade no alerta "{titulo_alerta}"', corpo)


def _verificar_alerta(alerta):
    atletas = _rodar_busca(alerta)
    if not atletas:
        return

    with _conn() as conn:
        vistos = {
            row["chave"] for row in
            conn.execute("SELECT chave FROM alertas_vistos WHERE alerta_id = ?", (alerta["id"],))
        }

    novos = [a for a in atletas if _chave_atleta(a) not in vistos]
    _marcar_vistos(alerta["id"], atletas)

    if not novos:
        return

    usuario = auth.buscar_por_id(alerta["usuario_id"])
    if usuario:
        _enviar_email_alerta(usuario["email"], alerta["titulo"], novos)


def verificar_todos():
    """Chamada periodicamente (thread de fundo em app.py) pra checar todos
    os alertas ativos de todos os usuários."""
    with _conn() as conn:
        alertas = [dict(linha) for linha in conn.execute("SELECT * FROM alertas WHERE ativo = 1")]

    for alerta in alertas:
        try:
            _verificar_alerta(alerta)
        except Exception:
            traceback.print_exc()
