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


def _validar_manchete_e_prazo(manchete, data_limite):
    """Compartilhado por criar_noticia/atualizar_noticia. Retorna
    (manchete_limpa, data_limite_limpa, erro)."""
    manchete = (manchete or "").strip()
    if not manchete:
        return None, None, "informe a manchete"

    data_limite = (data_limite or "").strip() or None
    if data_limite:
        try:
            data_limite_obj = date.fromisoformat(data_limite)
        except ValueError:
            return None, None, "data limite inválida"
        # Achado ao vivo em 11/09/2026: uma notícia postada com data limite
        # sem querer no passado (ex: dia/mês trocado — "7 de novembro" virou
        # "07/11" lido como mês 07/dia 11) some da lista assim que criada,
        # já que listar_noticias() só mostra data_limite >= hoje — e é
        # apagada de vez no próximo remover_noticias_expiradas(). Rejeitar
        # aqui, com erro claro, evita esse "postei e não foi pro ar"
        # silencioso — vale tanto pra criar quanto pra editar.
        if data_limite_obj < date.today():
            return None, None, "data limite não pode ser uma data no passado"

    return manchete, data_limite, None


def criar_noticia(manchete, texto, data_limite, arquivo_imagem, nome_original):
    """arquivo_imagem é o FileStorage do Flask (request.files[...]).
    data_limite (opcional) é uma data ISO "AAAA-MM-DD" — a notícia é
    apagada automaticamente assim que essa data passa.
    Retorna (noticia_id, erro)."""
    manchete, data_limite, erro = _validar_manchete_e_prazo(manchete, data_limite)
    if erro:
        return None, erro

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


def atualizar_noticia(noticia_id, manchete, texto, data_limite, arquivo_imagem=None, nome_original=None):
    """Edita manchete/texto/data_limite de uma notícia existente. A foto só
    é trocada se arquivo_imagem for enviado (senão mantém a atual) — assim
    dá pra corrigir só o texto ou só a data sem precisar reenviar a imagem.
    Retorna (ok, erro)."""
    manchete, data_limite, erro = _validar_manchete_e_prazo(manchete, data_limite)
    if erro:
        return False, erro

    with _conn() as conn:
        atual = conn.execute("SELECT imagem_arquivo FROM noticias WHERE id = ?", (noticia_id,)).fetchone()
        if not atual:
            return False, "notícia não encontrada"

        nome_arquivo = atual["imagem_arquivo"]
        if arquivo_imagem:
            ext = _extensao(nome_original)
            if ext not in EXTENSOES_PERMITIDAS:
                return False, "imagem inválida (use jpg, png, webp ou gif)"
            novo_nome = f"{uuid.uuid4().hex}.{ext}"
            arquivo_imagem.save(DIR_IMAGENS / novo_nome)
            antigo = DIR_IMAGENS / nome_arquivo
            if antigo.exists():
                antigo.unlink()
            nome_arquivo = novo_nome

        conn.execute(
            "UPDATE noticias SET manchete = ?, texto = ?, imagem_arquivo = ?, data_limite = ? WHERE id = ?",
            (manchete, (texto or "").strip(), nome_arquivo, data_limite, noticia_id),
        )
    return True, None


def listar_noticias(limite=20):
    with _conn() as conn:
        linhas = conn.execute(
            """SELECT * FROM noticias
               WHERE data_limite IS NULL OR data_limite >= date('now')
               ORDER BY criado_em DESC LIMIT ?""",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def listar_todas_noticias(limite=50):
    """Pro painel de administração — sem o filtro de data_limite de
    listar_noticias(), pra quem gerencia conseguir achar (e corrigir, via
    atualizar_noticia) uma notícia que ficou com uma data limite errada e
    por isso já não aparece mais no site público."""
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT * FROM noticias ORDER BY criado_em DESC LIMIT ?", (limite,)
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_noticia(noticia_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT * FROM noticias WHERE id = ?", (noticia_id,)
        ).fetchone()
    return dict(linha) if linha else None


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
