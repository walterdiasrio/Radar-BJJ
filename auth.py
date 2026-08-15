"""Cadastro e login de usuários, com senha em hash e sessão do Flask.

Guardado num SQLite local (usuarios.db). O cadastro só é efetivado depois
que o usuário confirma o e-mail (link com token, enviado via Resend —
ver criar_token_verificacao/confirmar_email); até lá, o login fica
bloqueado (ver campo email_verificado, checado em app.py)."""
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "usuarios.db"

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NOME_USUARIO_REGEX = re.compile(r"^[a-z0-9_]{3,20}$")

TIPOS_PERFIL = ("mestre", "atleta")

VALIDADE_TOKEN_RESET = timedelta(hours=1)
VALIDADE_TOKEN_VERIFICACAO = timedelta(hours=24)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                email_verificado INTEGER NOT NULL DEFAULT 0,
                tipo_perfil TEXT NOT NULL DEFAULT 'atleta',
                nome_usuario TEXT UNIQUE,
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Migração pra bancos criados antes do perfil Mestre/Atleta existir.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(usuarios)")}
        if "tipo_perfil" not in colunas:
            conn.execute("ALTER TABLE usuarios ADD COLUMN tipo_perfil TEXT NOT NULL DEFAULT 'atleta'")
        # Migração pra bancos onde o perfil ainda se chamava "aluno".
        conn.execute("UPDATE usuarios SET tipo_perfil = 'atleta' WHERE tipo_perfil = 'aluno'")
        # Migração pra bancos criados antes do nome de usuário existir —
        # usado pra vincular Mestre e Atleta (ver carreira.py/vínculos).
        if "nome_usuario" not in colunas:
            conn.execute("ALTER TABLE usuarios ADD COLUMN nome_usuario TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_nome_usuario ON usuarios(nome_usuario)")
        # Migração pra bancos criados antes do filtro padrão do Radar de
        # Atletas existir — guardado como JSON (ver salvar_filtro_padrao).
        if "filtro_padrao_busca" not in colunas:
            conn.execute("ALTER TABLE usuarios ADD COLUMN filtro_padrao_busca TEXT")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reset_senha (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                expira_em TEXT NOT NULL,
                usado INTEGER NOT NULL DEFAULT 0
            )
        """)

        # A tabela de verificação de e-mail só passou a existir com essa
        # migração — se ainda não existia, é a primeira subida com login
        # exigindo e-mail confirmado. Sem isso, toda conta criada antes
        # dessa mudança (email_verificado=0 por padrão desde sempre, mas
        # nunca de fato checado) ficaria bloqueada de repente.
        tabela_verificacao_ja_existia = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='verificacao_email'"
        ).fetchone() is not None

        conn.execute("""
            CREATE TABLE IF NOT EXISTS verificacao_email (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                expira_em TEXT NOT NULL,
                usado INTEGER NOT NULL DEFAULT 0
            )
        """)

        if not tabela_verificacao_ja_existia:
            conn.execute("UPDATE usuarios SET email_verificado = 1 WHERE email_verificado = 0")


def email_valido(email):
    return bool(email) and bool(_EMAIL_REGEX.match(email.strip()))


def cadastrar(email, senha, tipo_perfil):
    """Retorna (usuario_id, erro). Em caso de sucesso, erro é None."""
    email = (email or "").strip().lower()
    if not email_valido(email):
        return None, "E-mail inválido."
    if not senha or len(senha) < 8:
        return None, "A senha precisa ter pelo menos 8 caracteres."
    if tipo_perfil not in TIPOS_PERFIL:
        return None, "Selecione um tipo de perfil (Mestre ou Atleta)."

    senha_hash = generate_password_hash(senha)
    try:
        with _conn() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (email, senha_hash, tipo_perfil) VALUES (?, ?, ?)",
                (email, senha_hash, tipo_perfil),
            )
            return cursor.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "Esse e-mail já está cadastrado."


def autenticar(email, senha):
    """Retorna (usuario, erro). usuario é um dict se sucesso. Login fica
    bloqueado pra quem ainda não confirmou o e-mail (erro específico, pra
    a tela de login oferecer reenviar a confirmação)."""
    email = (email or "").strip().lower()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, senha_hash, tipo_perfil, nome_usuario, email_verificado FROM usuarios WHERE email = ?",
            (email,),
        ).fetchone()

    if not linha or not check_password_hash(linha["senha_hash"], senha or ""):
        return None, "E-mail ou senha incorretos."
    if not linha["email_verificado"]:
        return None, "email_nao_confirmado"
    return {
        "id": linha["id"], "email": linha["email"],
        "tipo_perfil": linha["tipo_perfil"], "nome_usuario": linha["nome_usuario"],
    }, None


def buscar_por_id(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, tipo_perfil, nome_usuario FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
    return dict(linha) if linha else None


def listar_usuarios():
    """Todas as contas cadastradas, mais recentes primeiro — usado no
    painel administrativo de usuários."""
    with _conn() as conn:
        linhas = conn.execute(
            "SELECT id, email, tipo_perfil, nome_usuario, criado_em FROM usuarios ORDER BY criado_em DESC"
        ).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_por_email(email):
    email = (email or "").strip().lower()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, tipo_perfil, nome_usuario, email_verificado FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
    return dict(linha) if linha else None


def nome_usuario_valido(nome_usuario):
    return bool(nome_usuario) and bool(_NOME_USUARIO_REGEX.match(nome_usuario))


def buscar_por_nome_usuario(nome_usuario):
    nome_usuario = (nome_usuario or "").strip().lower()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, tipo_perfil, nome_usuario FROM usuarios WHERE nome_usuario = ?", (nome_usuario,)
        ).fetchone()
    return dict(linha) if linha else None


def definir_nome_usuario(usuario_id, nome_usuario):
    """Retorna (ok, erro). Formato: letras minúsculas, números e
    underscore, 3 a 20 caracteres — igual a um @ de rede social."""
    nome_usuario = (nome_usuario or "").strip().lower()
    if not nome_usuario_valido(nome_usuario):
        return False, "nome de usuário deve ter 3 a 20 caracteres: letras minúsculas, números ou _"
    try:
        with _conn() as conn:
            conn.execute("UPDATE usuarios SET nome_usuario = ? WHERE id = ?", (nome_usuario, usuario_id))
    except sqlite3.IntegrityError:
        return False, "esse nome de usuário já está em uso"
    return True, None


def criar_token_reset(usuario_id):
    """Gera um token de redefinição de senha, válido por VALIDADE_TOKEN_RESET."""
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.utcnow() + VALIDADE_TOKEN_RESET).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO reset_senha (token, usuario_id, expira_em) VALUES (?, ?, ?)",
            (token, usuario_id, expira_em),
        )
    return token


def _token_valido(linha):
    if not linha or linha["usado"]:
        return False
    return datetime.utcnow() <= datetime.fromisoformat(linha["expira_em"])


def redefinir_senha(token, nova_senha):
    """Retorna (ok, erro). Em caso de sucesso, erro é None."""
    if not nova_senha or len(nova_senha) < 8:
        return False, "A senha precisa ter pelo menos 8 caracteres."

    with _conn() as conn:
        linha = conn.execute(
            "SELECT usuario_id, expira_em, usado FROM reset_senha WHERE token = ?", (token,)
        ).fetchone()
        if not _token_valido(linha):
            return False, "Link inválido ou expirado. Peça um novo."

        senha_hash = generate_password_hash(nova_senha)
        conn.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (senha_hash, linha["usuario_id"]))
        conn.execute("UPDATE reset_senha SET usado = 1 WHERE token = ?", (token,))
    return True, None


def criar_token_verificacao(usuario_id):
    """Gera um token de confirmação de e-mail, válido por
    VALIDADE_TOKEN_VERIFICACAO."""
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.utcnow() + VALIDADE_TOKEN_VERIFICACAO).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO verificacao_email (token, usuario_id, expira_em) VALUES (?, ?, ?)",
            (token, usuario_id, expira_em),
        )
    return token


def confirmar_email(token):
    """Retorna (ok, erro). Marca o e-mail como confirmado e libera o
    login."""
    with _conn() as conn:
        linha = conn.execute(
            "SELECT usuario_id, expira_em, usado FROM verificacao_email WHERE token = ?", (token,)
        ).fetchone()
        if not _token_valido(linha):
            return False, "Link inválido ou expirado. Peça um novo."

        conn.execute("UPDATE usuarios SET email_verificado = 1 WHERE id = ?", (linha["usuario_id"],))
        conn.execute("UPDATE verificacao_email SET usado = 1 WHERE token = ?", (token,))
    return True, None


def salvar_filtro_padrao(usuario_id, filtro):
    """Guarda o filtro (dict) usado no Radar de Atletas como padrão do
    usuário, pra ser aplicado automaticamente na próxima visita à página."""
    with _conn() as conn:
        conn.execute(
            "UPDATE usuarios SET filtro_padrao_busca = ? WHERE id = ?",
            (json.dumps(filtro), usuario_id),
        )


def obter_filtro_padrao(usuario_id):
    """Retorna o filtro padrão salvo (dict) ou None se o usuário nunca
    salvou um."""
    with _conn() as conn:
        linha = conn.execute(
            "SELECT filtro_padrao_busca FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
    if not linha or not linha["filtro_padrao_busca"]:
        return None
    try:
        return json.loads(linha["filtro_padrao_busca"])
    except (TypeError, ValueError):
        return None
