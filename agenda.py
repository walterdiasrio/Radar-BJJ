"""Minha Agenda — disponível pro Plano Free: o atleta marca competições
(na aba Competições) como "Tenho Interesse" ou "Inscrito", e elas aparecem
aqui, separadas por mês, até acontecerem.

Como as competições não têm um ID estável entre buscas (cada federação
devolve um HTML/JSON diferente a cada scrape — ver connectors/__init__.py
e o mesmo problema em alertas.py), guardamos os dados do evento (nome,
federação, data, local) direto na linha da agenda, com uma "chave" (hash)
pra identificar o mesmo evento entre visitas e não deixar duplicar.
"""
import hashlib
import os
import sqlite3
from datetime import date
from pathlib import Path

from connectors import datas as datas_mod

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "agenda.db"

STATUS_VALIDOS = ("interesse", "inscrito")


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agenda_competicoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                chave TEXT NOT NULL,
                federacao TEXT NOT NULL,
                nome TEXT NOT NULL,
                data TEXT NOT NULL,
                local TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(usuario_id, chave)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agenda_usuario ON agenda_competicoes(usuario_id)")


def chave_de(federacao, nome, data):
    bruto = "|".join((v or "").strip().lower() for v in (federacao, nome, data))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def marcar(usuario_id, federacao, nome, data, local, status):
    """Cria ou atualiza (upsert) a marcação de uma competição na agenda do
    usuário — marcar de novo com outro status (ex: de "interesse" pra
    "inscrito") só atualiza a linha existente. Retorna (ok, erro)."""
    federacao = (federacao or "").strip()
    nome = (nome or "").strip()
    data = (data or "").strip()
    if not federacao or not nome or not data:
        return False, "dados da competição incompletos"
    if status not in STATUS_VALIDOS:
        return False, f"status inválido (use: {', '.join(STATUS_VALIDOS)})"

    chave = chave_de(federacao, nome, data)
    with _conn() as conn:
        conn.execute("""
            INSERT INTO agenda_competicoes (usuario_id, chave, federacao, nome, data, local, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(usuario_id, chave) DO UPDATE SET status = excluded.status, local = excluded.local
        """, (usuario_id, chave, federacao, nome, data, local or "", status))
    return True, None


def desmarcar(usuario_id, federacao, nome, data):
    chave = chave_de(federacao, nome, data)
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM agenda_competicoes WHERE usuario_id = ? AND chave = ?", (usuario_id, chave)
        )
        return cursor.rowcount > 0


def listar(usuario_id):
    """Só competições que ainda não aconteceram, ordenadas por data, cada
    item já com "mes" calculado (ex: "Setembro 2026") pro front agrupar."""
    with _conn() as conn:
        linhas = [
            dict(linha) for linha in
            conn.execute("SELECT * FROM agenda_competicoes WHERE usuario_id = ?", (usuario_id,))
        ]

    hoje = date.today()
    com_data = []
    for linha in linhas:
        data_obj = datas_mod.extrair_data(linha["data"])
        if data_obj and data_obj < hoje:
            continue
        linha["mes"] = datas_mod.rotulo_mes(data_obj)
        com_data.append((data_obj or date.max, linha))

    com_data.sort(key=lambda par: par[0])
    return [linha for _, linha in com_data]


def mapa_status(usuario_id):
    """{chave: status} de TODAS as marcações do usuário (sem filtrar
    passado/futuro) — usado na aba Competições pra já mostrar o que ele
    marcou antes, mesmo que a competição não apareça mais em Minha Agenda
    por já ter passado."""
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT chave, status FROM agenda_competicoes WHERE usuario_id = ?", (usuario_id,)
        ).fetchall()
    return {linha["chave"]: linha["status"] for linha in linhas}
