"""Notícias/destaques da página principal — cadastradas só pelo admin,
visíveis pra todo mundo (com ou sem login). Cada notícia tem manchete +
foto. As fotos ficam salvas em DATA_DIR/noticias_imagens — fora do
static/, porque é conteúdo enviado em tempo de execução, não parte do
código versionado."""
import os
import sqlite3
import uuid
from datetime import date
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
                texto TEXT NOT NULL DEFAULT '',
                imagem_arquivo TEXT NOT NULL,
                data_limite TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Migrações pra bancos criados antes desses campos existirem.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(noticias)")}
        if "texto" not in colunas:
            conn.execute("ALTER TABLE noticias ADD COLUMN texto TEXT NOT NULL DEFAULT ''")
        if "data_limite" not in colunas:
            conn.execute("ALTER TABLE noticias ADD COLUMN data_limite TEXT")


def _extensao(nome_arquivo):
    return (nome_arquivo or "").rsplit(".", 1)[-1].lower() if "." in (nome_arquivo or "") else ""


def criar_noticia(manchete, texto, data_limite, arquivo_imagem, nome_original):
    """arquivo_imagem é o FileStorage do Flask (request.files[...]).
    data_limite (opcional) é uma data ISO "AAAA-MM-DD" — a notícia é
    apagada automaticamente assim que essa data passa.
    Retorna (noticia_id, erro)."""
    manchete = (manchete or "").strip()
    if not manchete:
        return None, "informe a manchete"

    data_limite = (data_limite or "").strip() or None
    if data_limite:
        try:
            date.fromisoformat(data_limite)
        except ValueError:
            return None, "data limite inválida"

    ext = _extensao(nome_original)
    if ext not in EXTENSOES_PERMITIDAS:
        return None, "imagem inválida (use jpg, png, webp ou gif)"

    DIR_IMAGENS.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{uuid.uuid4().hex}.{ext}"
    arquivo_imagem.save(DIR_IMAGENS / nome_arquivo)

    with _conn() as conn:
        cursor = conn.execute(
            "INSERT INTO noticias (manchete, texto, imagem_arquivo, data_limite) VALUES (?, ?, ?, ?)",
            (manchete, (texto or "").strip(), nome_arquivo, data_limite),
        )
        return cursor.lastrowid, None


def listar_noticias(limite=20):
    with _conn() as conn:
        linhas = conn.execute(
            """SELECT * FROM noticias
               WHERE data_limite IS NULL OR data_limite >= date('now')
               ORDER BY criado_em DESC LIMIT ?""",
            (limite,),
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


def remover_noticias_expiradas():
    """Apaga (registro + arquivo de imagem) toda notícia cuja data_limite
    já passou. Chamada periodicamente em background (ver app.py)."""
    with _conn() as conn:
        expiradas = conn.execute(
            "SELECT id, imagem_arquivo FROM noticias WHERE data_limite IS NOT NULL AND data_limite < date('now')"
        ).fetchall()
        if not expiradas:
            return 0
        conn.executemany("DELETE FROM noticias WHERE id = ?", [(linha["id"],) for linha in expiradas])

    for linha in expiradas:
        arquivo = DIR_IMAGENS / linha["imagem_arquivo"]
        if arquivo.exists():
            arquivo.unlink()
    return len(expiradas)
