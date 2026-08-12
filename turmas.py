"""Turmas — cada Mestre organiza suas aulas em turmas (Baby, Kids,
Adolescente, Adulto) com horário de início/fim, e opcionalmente coloca
alunos dela dentro. Só aceita alunos já vinculados ao Mestre em Meus
Alunos (ver app.py) — turmas não criam vínculo novo, só organizam quem
já é aluno."""
import json
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "turmas.db"

CATEGORIAS = ("Baby", "Kids", "Adolescente", "Adulto")
DIAS_SEMANA = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

# Posições/técnicas disponíveis pro Plano de Aula, agrupadas pra exibição —
# lista fixa (não cadastrada pelo usuário) pra manter o registro consistente
# entre turmas e ao longo do tempo.
POSICOES = {
    "Guardas": [
        "Guarda Fechada", "Guarda Aberta", "Meia Guarda", "Guarda Borboleta",
        "De La Riva", "Guarda Aranha", "50/50",
    ],
    "Passagens de Guarda": [
        "Passagem por Pressão", "Passagem Torreando", "Passagem Leg Drag", "Passagem de Joelho",
    ],
    "Posições Dominantes": [
        "Montada", "100kg (Side Control)", "Joelho na Barriga", "Costas", "Norte-Sul",
    ],
    "Raspagens": [
        "Raspagem de Guarda Fechada", "Raspagem Flower Sweep", "Raspagem Scissor",
        "Raspagem Hip Bump", "Raspagem De La Riva",
    ],
    "Quedas": [
        "Dupla Queda de Perna", "Simples Queda de Perna", "Queda de Judô",
    ],
    "Finalizações — Chaves de Braço": [
        "Armlock", "Kimura", "Americana", "Omoplata",
    ],
    "Finalizações — Estrangulamentos": [
        "Mata-Leão", "Triângulo", "Guilhotina", "Ezekiel",
    ],
    "Finalizações — Chaves de Perna": [
        "Chave de Pé Reta", "Chave de Calcanhar", "Toe Hold",
    ],
    "Fundamentos / Escapes": [
        "Fuga de Quadril", "Escape de Montada", "Escape de 100kg", "Pontes (Bridge)",
    ],
}
_TODAS_POSICOES = {posicao for lista in POSICOES.values() for posicao in lista}


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
        # dias_semana entrou depois que a tabela já existia em produção —
        # ALTER TABLE em vez de recriar, pra não perder turmas já criadas.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(turmas)")}
        if "dias_semana" not in colunas:
            conn.execute("ALTER TABLE turmas ADD COLUMN dias_semana TEXT NOT NULL DEFAULT '[]'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS turma_alunos (
                turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
                aluno_id INTEGER NOT NULL,
                PRIMARY KEY (turma_id, aluno_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_turmas_mestre ON turmas(mestre_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS planos_aula (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turma_id INTEGER NOT NULL REFERENCES turmas(id) ON DELETE CASCADE,
                data TEXT NOT NULL,
                posicoes TEXT NOT NULL DEFAULT '[]',
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_planos_aula_turma ON planos_aula(turma_id)")


def _validar_dados(dados):
    categoria = (dados.get("categoria") or "").strip()
    if categoria not in CATEGORIAS:
        return None, f"categoria inválida (use: {', '.join(CATEGORIAS)})"
    horario_inicio = (dados.get("horario_inicio") or "").strip()
    horario_fim = (dados.get("horario_fim") or "").strip()
    if not horario_inicio or not horario_fim:
        return None, "informe horário de início e fim"
    dias_semana = [d for d in (dados.get("dias_semana") or []) if d in DIAS_SEMANA]
    nome = (dados.get("nome") or "").strip()
    return {
        "nome": nome,
        "categoria": categoria,
        "horario_inicio": horario_inicio,
        "horario_fim": horario_fim,
        "dias_semana": dias_semana,
    }, None


def criar_turma(mestre_id, dados):
    """Retorna (turma_id, erro)."""
    validado, erro = _validar_dados(dados)
    if erro:
        return None, erro
    with _conn() as conn:
        cursor = conn.execute(
            """INSERT INTO turmas (mestre_id, nome, categoria, horario_inicio, horario_fim, dias_semana)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                mestre_id, validado["nome"], validado["categoria"], validado["horario_inicio"],
                validado["horario_fim"], json.dumps(validado["dias_semana"], ensure_ascii=False),
            ),
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
            "UPDATE turmas SET nome=?, categoria=?, horario_inicio=?, horario_fim=?, dias_semana=? WHERE id=?",
            (
                validado["nome"], validado["categoria"], validado["horario_inicio"],
                validado["horario_fim"], json.dumps(validado["dias_semana"], ensure_ascii=False), turma_id,
            ),
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
            t["dias_semana"] = json.loads(t["dias_semana"]) if t.get("dias_semana") else []
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


def criar_plano_aula(mestre_id, turma_id, dados):
    """Retorna (plano_id, erro)."""
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return None, "turma não encontrada"

    data = (dados.get("data") or "").strip()
    if not data:
        return None, "informe a data da aula"

    posicoes = [p for p in (dados.get("posicoes") or []) if p in _TODAS_POSICOES]
    if not posicoes:
        return None, "selecione pelo menos uma posição"

    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO planos_aula (turma_id, data, posicoes) VALUES (?, ?, ?)",
            (turma_id, data, json.dumps(posicoes, ensure_ascii=False)),
        )
        return cursor.lastrowid, None


def listar_planos_aula(mestre_id, turma_id):
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return []
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM planos_aula WHERE turma_id = ? ORDER BY data DESC, id DESC", (turma_id,)
        ).fetchall()
    planos = []
    for linha in linhas:
        plano = dict(linha)
        plano["posicoes"] = json.loads(plano["posicoes"]) if plano["posicoes"] else []
        planos.append(plano)
    return planos


def remover_plano_aula(mestre_id, turma_id, plano_id):
    if not turma_pertence_ao_mestre(mestre_id, turma_id):
        return False
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM planos_aula WHERE id = ? AND turma_id = ?", (plano_id, turma_id)
        )
        return cursor.rowcount > 0
