"""Assinaturas pagas via Stripe Checkout (mode=subscription para cartão,
mode=payment para PIX).

Dois planos (atleta/mestre), cada um mensal ou anual, com 7 dias de teste
grátis (só no cartão — PIX não tem teste grátis, ver criar_sessao_checkout_
pix). O Stripe é a fonte da verdade sobre cobrança de cartão — aqui a
gente só guarda um espelho local (assinaturas.db) atualizado pelos
webhooks, pra não precisar bater na API do Stripe a cada requisição só
pra saber se o usuário tem acesso.

PIX é diferente: não existe "assinatura PIX" de verdade — PIX é uma
transferência instantânea sem cartão salvo, então o Stripe não permite
cobrança recorrente automática por PIX (só mode=payment, pagamento
avulso). Por isso quem paga por PIX compra o PERÍODO (mês ou ano) de uma
vez, e a gente mesmo controla localmente quando isso vence
(forma_pagamento="pix" + periodo_atual_fim calculado aqui, não vindo do
Stripe) — sem renovação automática, com lembrete por e-mail perto do
vencimento (ver verificar_pix() e app.py, chamado no loop periódico já
existente pros alertas)."""
import os
import sqlite3
import time
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
    ("atleta", "mensal"): os.environ.get("STRIPE_PRICE_ATLETA_MENSAL", ""),
    ("atleta", "anual"): os.environ.get("STRIPE_PRICE_ATLETA_ANUAL", ""),
    ("mestre", "mensal"): os.environ.get("STRIPE_PRICE_MESTRE_MENSAL", ""),
    ("mestre", "anual"): os.environ.get("STRIPE_PRICE_MESTRE_ANUAL", ""),
}

# Preços AVULSOS (não recorrentes) pro checkout com PIX — precisam ser
# Prices diferentes dos de cima no Stripe (esses são "one time", os de
# cima são "recurring"), mesmo cobrando o mesmo valor.
PRECOS_PIX = {
    ("atleta", "mensal"): os.environ.get("STRIPE_PRICE_PIX_ATLETA_MENSAL", ""),
    ("atleta", "anual"): os.environ.get("STRIPE_PRICE_PIX_ATLETA_ANUAL", ""),
    ("mestre", "mensal"): os.environ.get("STRIPE_PRICE_PIX_MESTRE_MENSAL", ""),
    ("mestre", "anual"): os.environ.get("STRIPE_PRICE_PIX_MESTRE_ANUAL", ""),
}

# Quantos dias um período pago por PIX dura, por periodicidade — usado
# pra calcular periodo_atual_fim localmente (o Stripe não sabe disso,
# porque pra ele é só um pagamento avulso, sem noção de "assinatura").
DIAS_PIX = {"mensal": 30, "anual": 365}

# Quantos dias antes do vencimento o lembrete de renovação por PIX é
# mandado (ver verificar_pix() / app.py).
DIAS_LEMBRETE_PIX = 3

# Status do Stripe (ou, pro PIX, status que a gente mesmo controla) que
# contam como "acesso liberado".
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
        # Migrações pra bancos criados antes desses campos existirem.
        colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(assinaturas)")}
        if "forma_pagamento" not in colunas:
            conn.execute("ALTER TABLE assinaturas ADD COLUMN forma_pagamento TEXT NOT NULL DEFAULT 'stripe'")
        if "pix_lembrete_enviado_em" not in colunas:
            conn.execute("ALTER TABLE assinaturas ADD COLUMN pix_lembrete_enviado_em TEXT")


def plano_valido(plano, periodicidade):
    return (plano, periodicidade) in PRECOS and bool(PRECOS[(plano, periodicidade)])


def plano_valido_pix(plano, periodicidade):
    return (plano, periodicidade) in PRECOS_PIX and bool(PRECOS_PIX[(plano, periodicidade)])


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
        "success_url": f"{URL_SITE}/assinatura/sucesso?plano={plano}&periodicidade={periodicidade}",
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


def criar_sessao_checkout_pix(usuario, plano, periodicidade):
    """Retorna (url, erro). Igual criar_sessao_checkout, mas mode=payment
    (avulso) com PIX — sem teste grátis (não faz sentido cobrar de novo
    "manualmente" 7 dias depois) e sem tokenizar cliente pra cobrança
    futura (PIX não permite). A liberação do acesso acontece no webhook
    (ver processar_evento_webhook), calculando periodo_atual_fim aqui —
    não vem do Stripe porque pra ele isso não é uma assinatura."""
    if not plano_valido_pix(plano, periodicidade):
        return None, "plano inválido"

    price_id = PRECOS_PIX[(plano, periodicidade)]
    parametros = {
        "mode": "payment",
        "payment_method_types": ["pix"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "client_reference_id": str(usuario["id"]),
        "customer_email": usuario["email"],
        "metadata": {
            "usuario_id": str(usuario["id"]),
            "plano": plano,
            "periodicidade": periodicidade,
            "forma_pagamento": "pix",
        },
        "success_url": f"{URL_SITE}/assinatura/sucesso?plano={plano}&periodicidade={periodicidade}",
        "cancel_url": f"{URL_SITE}/assinatura",
    }

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
        forma_pagamento="stripe",
        pix_lembrete_enviado_em=None,
    )


def _refletir_pagamento_pix(sessao_checkout):
    """Grava localmente um pagamento avulso via PIX (checkout.session.
    completed com mode=payment) — sem subscription do Stripe pra
    espelhar, então calcula o vencimento aqui mesmo (hoje + DIAS_PIX)."""
    metadata = sessao_checkout.get("metadata") or {}
    usuario_id = sessao_checkout.get("client_reference_id") or metadata.get("usuario_id")
    plano = metadata.get("plano")
    periodicidade = metadata.get("periodicidade")
    if not usuario_id or not plano or not periodicidade:
        return
    usuario_id = int(usuario_id)

    periodo_atual_fim = int(time.time()) + DIAS_PIX.get(periodicidade, 30) * 86400

    _upsert(
        usuario_id,
        stripe_customer_id=sessao_checkout.get("customer"),
        stripe_subscription_id=None,
        plano=plano,
        periodicidade=periodicidade,
        status="active",
        trial_fim=None,
        periodo_atual_fim=str(periodo_atual_fim),
        forma_pagamento="pix",
        pix_lembrete_enviado_em=None,
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
        if dados.get("mode") == "payment":
            # PIX é um "delayed payment method" — o Stripe considera a
            # sessão "completed" assim que a pessoa gera o QR Code, ANTES
            # de cair o dinheiro de verdade. Só libera acesso aqui se já
            # veio marcado como pago (raro, mas acontece pra valores que
            # confirmam na hora); o caminho normal é o evento
            # async_payment_succeeded abaixo, que só dispara depois da
            # confirmação real do PIX.
            if dados.get("payment_status") == "paid":
                _refletir_pagamento_pix(dados)
        else:
            subscription_id = dados.get("subscription")
            usuario_id = dados.get("client_reference_id") or (dados.get("metadata") or {}).get("usuario_id")
            if subscription_id and usuario_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                _refletir_subscription(subscription, usuario_id=usuario_id)

    elif tipo == "checkout.session.async_payment_succeeded":
        _refletir_pagamento_pix(dados)

    elif tipo in ("customer.subscription.updated", "customer.subscription.created"):
        _refletir_subscription(dados)

    elif tipo == "customer.subscription.deleted":
        _refletir_subscription(dados)

    return tipo


def listar_pix_a_lembrar():
    """Assinaturas pagas por PIX, ativas, vencendo dentro de DIAS_LEMBRETE_PIX
    dias, que ainda não receberam o lembrete de renovação nesse período."""
    limite = int(time.time()) + DIAS_LEMBRETE_PIX * 86400
    with _conn() as conn:
        linhas = conn.execute(
            """SELECT * FROM assinaturas
               WHERE forma_pagamento = 'pix' AND status = 'active'
                 AND pix_lembrete_enviado_em IS NULL
                 AND CAST(periodo_atual_fim AS INTEGER) <= ?
                 AND CAST(periodo_atual_fim AS INTEGER) > ?""",
            (limite, int(time.time())),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def listar_pix_vencidos():
    """Assinaturas pagas por PIX, ainda marcadas "active", cujo período já
    passou — perdem o acesso (status vira "vencida", fora de
    STATUS_COM_ACESSO) até pagar de novo."""
    with _conn() as conn:
        linhas = conn.execute(
            """SELECT * FROM assinaturas
               WHERE forma_pagamento = 'pix' AND status = 'active'
                 AND CAST(periodo_atual_fim AS INTEGER) <= ?""",
            (int(time.time()),),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def marcar_pix_lembrete_enviado(usuario_id):
    _upsert(usuario_id, pix_lembrete_enviado_em=str(int(time.time())))


def marcar_pix_vencida(usuario_id):
    _upsert(usuario_id, status="vencida")
