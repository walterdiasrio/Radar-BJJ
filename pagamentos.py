"""Assinaturas pagas via Stripe Checkout (mode=subscription).

Dois planos (aluno/mestre), cada um mensal ou anual, com 7 dias de teste
grátis. O Stripe é a fonte da verdade sobre cobrança — aqui a gente só
guarda um espelho local (assinaturas.db) atualizado pelos webhooks, pra
não precisar bater na API do Stripe a cada requisição só pra saber se o
usuário tem acesso.
"""
import os
import sqlite3
from pathlib import Path

import stripe

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "assinaturas.db"

URL_SITE = os.environ.get("URL_SITE", "http://localhost:5050")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

DIAS_TESTE_GRATIS = 7

# id do Price configurado no Stripe pra cada combinação de plano/periodicidade.
PRECOS = {
    ("aluno", "mensal"): os.environ.get("STRIPE_PRICE_ALUNO_MENSAL", ""),
    ("aluno", "anual"): os.environ.get("STRIPE_PRICE_ALUNO_ANUAL", ""),
    ("mestre", "mensal"): os.environ.get("STRIPE_PRICE_MESTRE_MENSAL", ""),
    ("mestre", "anual"): os.environ.get("STRIPE_PRICE_MESTRE_ANUAL", ""),
}

# Status do Stripe que contam como "acesso liberado".
STATUS_COM_ACESSO = {"trialing", "active"}


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assinaturas (
                usuario_id INTEGER PRIMARY KEY,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                plano TEXT,
                periodicidade TEXT,
                status TEXT,
                trial_fim TEXT,
                periodo_atual_fim TEXT,
                criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def plano_valido(plano, periodicidade):
    return (plano, periodicidade) in PRECOS and bool(PRECOS[(plano, periodicidade)])


def obter_assinatura(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT * FROM assinaturas WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    return dict(linha) if linha else None


def usuario_tem_acesso(usuario_id):
    assinatura = obter_assinatura(usuario_id)
    return bool(assinatura) and assinatura["status"] in STATUS_COM_ACESSO


def _upsert(usuario_id, **campos):
    with _conn() as conn:
        existente = conn.execute(
            "SELECT usuario_id FROM assinaturas WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
        if existente:
            set_clause = ", ".join(f"{k} = ?" for k in campos) + ", atualizado_em = datetime('now')"
            conn.execute(
                f"UPDATE assinaturas SET {set_clause} WHERE usuario_id = ?",
                (*campos.values(), usuario_id),
            )
        else:
            colunas_nomes = ["usuario_id", *campos.keys()]
            marcadores = ", ".join("?" for _ in colunas_nomes)
            conn.execute(
                f"INSERT INTO assinaturas ({', '.join(colunas_nomes)}) VALUES ({marcadores})",
                (usuario_id, *campos.values()),
            )


def criar_sessao_checkout(usuario, plano, periodicidade):
    """Retorna (url, erro). Cria a sessão do Stripe Checkout hospedado —
    o cartão nunca passa pelo nosso servidor."""
    if not plano_valido(plano, periodicidade):
        return None, "plano inválido"

    price_id = PRECOS[(plano, periodicidade)]
    assinatura_existente = obter_assinatura(usuario["id"])
    customer_id = assinatura_existente["stripe_customer_id"] if assinatura_existente else None

    parametros = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "subscription_data": {
            "trial_period_days": DIAS_TESTE_GRATIS,
            "metadata": {"usuario_id": str(usuario["id"]), "plano": plano, "periodicidade": periodicidade},
        },
        "client_reference_id": str(usuario["id"]),
        "metadata": {"usuario_id": str(usuario["id"]), "plano": plano, "periodicidade": periodicidade},
        "success_url": f"{URL_SITE}/assinatura/sucesso",
        "cancel_url": f"{URL_SITE}/assinatura",
        "allow_promotion_codes": True,
    }
    if customer_id:
        parametros["customer"] = customer_id
    else:
        parametros["customer_email"] = usuario["email"]

    try:
        sessao = stripe.checkout.Session.create(**parametros)
    except stripe.error.StripeError as exc:
        return None, str(exc)
    return sessao.url, None


def criar_sessao_portal(usuario):
    """Retorna (url, erro). Portal do Stripe pra gerenciar/cancelar a
    assinatura — trocar cartão, ver faturas, cancelar."""
    assinatura = obter_assinatura(usuario["id"])
    if not assinatura or not assinatura["stripe_customer_id"]:
        return None, "nenhuma assinatura encontrada"
    try:
        sessao = stripe.billing_portal.Session.create(
            customer=assinatura["stripe_customer_id"],
            return_url=f"{URL_SITE}/assinatura",
        )
    except stripe.error.StripeError as exc:
        return None, str(exc)
    return sessao.url, None


def _refletir_subscription(subscription, usuario_id=None):
    """Grava localmente o estado atual de uma subscription do Stripe."""
    metadata = subscription.get("metadata") or {}
    usuario_id = usuario_id or metadata.get("usuario_id")
    if not usuario_id:
        return
    usuario_id = int(usuario_id)

    item = subscription["items"]["data"][0] if subscription.get("items", {}).get("data") else None
    price_id = item["price"]["id"] if item else None
    plano = metadata.get("plano")
    periodicidade = metadata.get("periodicidade")
    if not plano or not periodicidade:
        for (p, per), pid in PRECOS.items():
            if pid == price_id:
                plano, periodicidade = p, per
                break

    trial_fim = subscription.get("trial_end")
    periodo_atual_fim = subscription.get("current_period_end")

    _upsert(
        usuario_id,
        stripe_customer_id=subscription.get("customer"),
        stripe_subscription_id=subscription.get("id"),
        plano=plano,
        periodicidade=periodicidade,
        status=subscription.get("status"),
        trial_fim=str(trial_fim) if trial_fim else None,
        periodo_atual_fim=str(periodo_atual_fim) if periodo_atual_fim else None,
    )


def processar_evento_webhook(payload, assinatura_header):
    """Verifica a assinatura do webhook e aplica o evento. Levanta
    ValueError se a assinatura for inválida (chamador deve responder 400)."""
    try:
        evento = stripe.Webhook.construct_event(payload, assinatura_header, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise ValueError(str(exc))

    tipo = evento["type"]
    dados = evento["data"]["object"]

    if tipo == "checkout.session.completed":
        subscription_id = dados.get("subscription")
        usuario_id = dados.get("client_reference_id") or (dados.get("metadata") or {}).get("usuario_id")
        if subscription_id and usuario_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            _refletir_subscription(subscription, usuario_id=usuario_id)

    elif tipo in ("customer.subscription.updated", "customer.subscription.created"):
        _refletir_subscription(dados)

    elif tipo == "customer.subscription.deleted":
        _refletir_subscription(dados)

    return tipo
