"""Cadastro e login de usuários, com senha em hash e sessão do Flask.

Guardado num SQLite local (usuarios.db). Sem verificação de e-mail por
enquanto — isso exige um serviço de envio (SMTP/SendGrid) ainda não
configurado. Quando isso for definido, o campo email_verificado já está
pronto pra ser usado como gate de "só e-mail confirmado recebe alerta".
"""
import os
import re
import sqlite3
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "usuarios.db"

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
                criado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def email_valido(email):
    return bool(email) and bool(_EMAIL_REGEX.match(email.strip()))


def cadastrar(email, senha):
    """Retorna (usuario_id, erro). Em caso de sucesso, erro é None."""
    email = (email or "").strip().lower()
    if not email_valido(email):
        return None, "E-mail inválido."
    if not senha or len(senha) < 8:
        return None, "A senha precisa ter pelo menos 8 caracteres."

    senha_hash = generate_password_hash(senha)
    try:
        with _conn() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (email, senha_hash) VALUES (?, ?)",
                (email, senha_hash),
            )
            return cursor.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "Esse e-mail já está cadastrado."


def autenticar(email, senha):
    """Retorna (usuario, erro). usuario é um dict {id, email} se sucesso."""
    email = (email or "").strip().lower()
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email, senha_hash FROM usuarios WHERE email = ?", (email,)
        ).fetchone()

    if not linha or not check_password_hash(linha["senha_hash"], senha or ""):
        return None, "E-mail ou senha incorretos."
    return {"id": linha["id"], "email": linha["email"]}, None


def buscar_por_id(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT id, email FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
    return {"id": linha["id"], "email": linha["email"]} if linha else None
