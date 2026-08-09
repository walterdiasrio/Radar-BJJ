"""Cadastro e login de usuários, com senha em hash e sessão do Flask.

Guardado num SQLite local (usuarios.db). Sem verificação de e-mail por
enquanto — isso exige um serviço de envio (SMTP/SendGrid) ainda não
configurado. Quando isso for definido, o campo email_verificado já está
pronto pra ser usado como gate de "só e-mail confirmado recebe alerta".
"""
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reset_senha (
                token TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                expira_em TEXT NOT NULL,
                usado INTEGER NOT NULL DEFAULT 0
            )
        """)


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
    """Retorna (usuario, erro). usuario é um dict se sucesso."""
    email = (email or "").strip().lower()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, senha_hash, tipo_perfil, nome_usuario FROM usuarios WHERE email = ?", (email,)
        ).fetchone()

    if not linha or not check_password_hash(linha["senha_hash"], senha or ""):
        return None, "E-mail ou senha incorretos."
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
            "SELECT id, email, tipo_perfil, nome_usuario FROM usuarios WHERE email = ?", (email,)
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
