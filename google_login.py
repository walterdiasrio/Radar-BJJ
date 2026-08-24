"""Login com Google (OAuth2/OpenID Connect) — alternativa ao cadastro por
e-mail/senha, não substitui ele. Sem GOOGLE_OAUTH_CLIENT_ID/SECRET
configuradas, os botões "Continuar com Google" simplesmente erram com uma
mensagem clara (ver login_google_callback em app.py), sem derrubar o resto
do site."""
import os

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def configurado():
    return bool(CLIENT_ID and CLIENT_SECRET)


def montar_url_autorizacao(redirect_uri, state):
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
    return f"{AUTH_URL}?{query}"


def obter_email_e_nome(code, redirect_uri):
    """Troca o code do OAuth pelo e-mail/nome da conta Google. Retorna
    (email, nome, erro)."""
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        return None, None, f"falha de rede ao falar com o Google: {exc}"

    if resp.status_code >= 300:
        return None, None, f"Google recusou o login: {resp.text}"

    id_token_bruto = resp.json().get("id_token")
    if not id_token_bruto:
        return None, None, "resposta do Google sem id_token"

    try:
        # Verifica a assinatura do token e o client_id — garante que o
        # token é mesmo do Google e foi emitido pra este app, não algo
        # forjado tentando se passar por login (ver docs do google-auth).
        claims = google_id_token.verify_oauth2_token(id_token_bruto, google_requests.Request(), CLIENT_ID)
    except ValueError as exc:
        return None, None, f"token do Google inválido: {exc}"

    if not claims.get("email_verified", False):
        return None, None, "e-mail da conta Google não verificado"

    return claims.get("email"), claims.get("name"), None
