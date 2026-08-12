"""Turmas — cada Mestre organiza suas aulas em turmas (Baby, Kids,
Adolescente, Adulto) com horário de início/fim, e opcionalmente coloca
alunos dela dentro. Só aceita alunos já vinculados ao Mestre em Meus
Alunos (ver app.py) — turmas não criam vínculo novo, só organizam quem
já é aluno."""
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "turmas.db"

CATEGORIAS = ("Baby", "Kids", "Adolescente", "Adulto")


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turmas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mestre_id INTEGER NOT NULL,
                nome TEXT NOT NULL DEFAULT '',
                categoria TEXT NOT NULL,
                horario_inicio TEXT NOT NULL,
                horario_fim TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turma_alunos (
                turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
                aluno_id INTEGER NOT NULL,
                PRIMARY KEY (turma_id, aluno_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_turmas_mestre ON turmas(mestre_id)")


def _validar_dados(dados):
    categoria = (dados.get("categoria") or "").strip()
    if categoria not in CATEGORIAS:
        return None, f"categoria inválida (use: {', '.join(CATEGORIAS)})"
    horario_inicio = (dados.get("horario_inicio") or "").strip()
    horario_fim = (dados.get("horario_fim") or "").strip()
    if not horario_inicio or not horario_fim:
        return None, "informe horário de início e fim"
    nome = (dados.get("nome") or "").strip()
    return {
        "nome": nome,
        "categoria": categoria,
        "horario_inicio": horario_inicio,
        "horario_fim": horario_fim,
    }, None


def criar_turma(mestre_id, dados):
    """Retorna (turma_id, erro)."""
    validado, erro = _validar_dados(dados)
    if erro:
        return None, erro
    with _conn() as conn:
        cursor = conn.execute(
            """INSERT INTO turmas (mestre_id, nome, categoria, horario_inicio, horario_fim)
               VALUES (?, ?, ?, ?, ?)""",
            (mestre_id, validado["nome"], validado["categoria"], validado["horario_inicio"], validado["horario_fim"]),
        )
        return cursor.lastrowid, None


def atualizar_turma(mestre_id, turma_id, dados):
    """Retorna (ok, erro)."""
    validado, erro = _validar_dados(dados)
    if erro:
        return False, erro
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False, "turma não encontrada"
        conn.execute(
            "UPDATE turmas SET nome=?, categoria=?, horario_inicio=?, horario_fim=? WHERE id=?",
            (validado["nome"], validado["categoria"], validado["horario_inicio"], validado["horario_fim"], turma_id),
        )
    return True, None


def remover_turma(mestre_id, turma_id):
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        )
        return cursor.rowcount > 0


def listar_turmas(mestre_id):
    with _conn() as conn:
        turmas = [
            dict(linha) for linha in conn.execute(
                "SELECT * FROM turmas WHERE mestre_id = ? ORDER BY horario_inicio, id", (mestre_id,)
            ).fetchall()
        ]
        for t in turmas:
            alunos = conn.execute(
                "SELECT aluno_id FROM turma_alunos WHERE turma_id = ? ORDER BY aluno_id", (t["id"],)
            ).fetchall()
            t["aluno_ids"] = [linha["aluno_id"] for linha in alunos]
    return turmas


def turma_pertence_ao_mestre(mestre_id, turma_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT 1 FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
    return linha is not None


def adicionar_aluno(mestre_id, turma_id, aluno_id):
    """Retorna (ok, erro). Quem chama já deve ter checado que aluno_id é
    de fato aluno desse mestre (ver carreira.vinculo_existe)."""
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False, "turma não encontrada"
        conn.execute(
            "INSERT OR IGNORE INTO turma_alunos (turma_id, aluno_id) VALUES (?, ?)", (turma_id, aluno_id)
        )
    return True, None


def remover_aluno(mestre_id, turma_id, aluno_id):
    with _conn() as conn:
        dona = conn.execute(
            "SELECT id FROM turmas WHERE id = ? AND mestre_id = ?", (turma_id, mestre_id)
        ).fetchone()
        if not dona:
            return False
        conn.execute(
            "DELETE FROM turma_alunos WHERE turma_id = ? AND aluno_id = ?", (turma_id, aluno_id)
        )
    return True
