"""Notícias/destaques da página principal — cadastradas só pelo admin,
visíveis pra todo mundo (com ou sem login). Cada notícia tem manchete +
foto. As fotos ficam salvas em DATA_DIR/noticias_imagens — fora do
static/, porque é conteúdo enviado em tempo de execução, não parte do
código versionado."""
import os
import sqlite3
import uuid
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "noticias.db"
DIR_IMAGENS = DATA_DIR / "noticias_imagens"

EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "webp", "gif"}


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DIR_IMAGENS.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS noticias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manchete TEXT NOT NULL,
                imagem_arquivo TEXT NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def _extensao(nome_arquivo):
    return (nome_arquivo or "").rsplit(".", 1)[-1].lower() if "." in (nome_arquivo or "") else ""


def criar_noticia(manchete, arquivo_imagem, nome_original):
    """arquivo_imagem é o FileStorage do Flask (request.files[...]).
    Retorna (noticia_id, erro)."""
    manchete = (manchete or "").strip()
    if not manchete:
        return None, "informe a manchete"

    ext = _extensao(nome_original)
    if ext not in EXTENSOES_PERMITIDAS:
        return None, "imagem inválida (use jpg, png, webp ou gif)"

    DIR_IMAGENS.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.{ext}"
    arquivo_imagem.save(DIR_IMAGENS / nome_arquivo)

    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO noticias (manchete, imagem_arquivo) VALUES (?, ?)",
            (manchete, nome_arquivo),
        )
        return cursor.lastrowid, None


def listar_noticias(limite=20):
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM noticias ORDER BY criado_em DESC LIMIT ?", (limite,)
        ).fetchall()
    return [dict(linha) for linha in linhas]


def remover_noticia(noticia_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT imagem_arquivo FROM noticias WHERE id = ?", (noticia_id,)
        ).fetchone()
        if not linha:
            return False
        conn.execute("DELETE FROM noticias WHERE id = ?", (noticia_id,))

    arquivo = DIR_IMAGENS / linha["imagem_arquivo"]
    if arquivo.exists():
        arquivo.unlink()
    return True
