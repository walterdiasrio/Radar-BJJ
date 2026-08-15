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
import os
import sqlite3
import threading
import traceback
from datetime import date
from pathlib import Path

import requests

import auth
from connectors import FEDERACOES, TODAS, buscar_atletas_agregado

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "alertas.db"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
REMETENTE = os.environ.get("ALERTA_REMETENTE", "Radar BJJ <onboarding@resend.dev>")
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
    atletas, _erros, _total = buscar_atletas_agregado(federacao, TODAS, filtros)
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


def enviar_email(destinatario, assunto, corpo_html):
    if not RESEND_API_KEY:
        print(f"[alertas] RESEND_API_KEY não configurada — e-mail não enviado "
              f"(para={destinatario}, assunto={assunto!r})")
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": REMETENTE, "to": [destinatario], "subject": assunto, "html": corpo_html},
            timeout=15,
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
