"""Fale Conosco — mensagens de contato ficam salvas num painel pro admin
consultar. Aberto a qualquer visitante (logado ou não). Quando o domínio
próprio tiver e-mail configurado, dá pra trocar isso por notificação por
e-mail (reaproveitando o enviar_email de alertas.py)."""
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "contato.db"

ASSUNTOS = ("duvida", "sugestao", "problema_tecnico", "assinatura", "parceria", "outro")

ASSUNTO_LABEL = {
    "duvida": "Dúvida",
    "sugestao": "Sugestão",
    "problema_tecnico": "Problema técnico",
    "assinatura": "Assinatura/Cobrança",
    "parceria": "Parceria/Patrocínio",
    "outro": "Outro",
}


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL,
                assunto TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                usuario_id INTEGER,
                lida INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def criar_mensagem(nome, email, assunto, mensagem, usuario_id=None):
    """Retorna (mensagem_id, erro)."""
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    mensagem = (mensagem or "").strip()

    if not nome:
        return None, "informe seu nome"
    if not email or "@" not in email:
        return None, "informe um e-mail válido"
    if assunto not in ASSUNTOS:
        return None, "selecione um assunto"
    if not mensagem:
        return None, "escreva sua mensagem"

    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO mensagens (nome, email, assunto, mensagem, usuario_id) VALUES (?, ?, ?, ?, ?)",
            (nome, email, assunto, mensagem, usuario_id),
        )
        return cursor.lastrowid, None


def listar_mensagens():
    with _conn() as conn:
        linhas = conn.execute("SELECT * FROM mensagens ORDER BY lida ASC, criado_em DESC").fetchall()
    return [dict(linha) for linha in linhas]


def marcar_lida(mensagem_id, lida=True):
    with _conn() as conn:
        cursor = conn.execute(
            "UPDATE mensagens SET lida = ? WHERE id = ?", (1 if lida else 0, mensagem_id)
        )
        return cursor.rowcount > 0


def remover_mensagem(mensagem_id):
    with _conn() as conn:
        cursor = conn.execute("DELETE FROM mensagens WHERE id = ?", (mensagem_id,))
        return cursor.rowcount > 0


def contar_nao_lidas():
    with _conn() as conn:
        linha = conn.execute("SELECT COUNT(*) AS total FROM mensagens WHERE lida = 0").fetchone()
    return linha["total"]
