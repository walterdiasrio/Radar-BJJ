"""Assinaturas pagas via Stripe Checkout (mode=subscription, cartão/boleto)
+ PIX via Asaas (cobrança avulsa, sem renovação automática — PIX não tem
cartão salvo pra debitar sozinho depois).

Dois planos (atleta/mestre), cada um mensal ou anual, com 7 dias de teste
grátis. O Stripe é a fonte da verdade pra cobrança de cartão — aqui a
gente só guarda um espelho local (assinaturas.db) atualizado pelos
webhooks, pra não precisar bater na API a cada requisição só pra saber se
o usuário tem acesso. PIX via Asaas segue o mesmo espelho local, só que
SEM subscription de verdade por trás: quem paga por PIX compra o
PERÍODO (mês ou ano) de uma vez, e a gente mesmo controla quando isso
vence (forma_pagamento="pix" + periodo_atual_fim calculado aqui) — sem
renovação automática, com lembrete por e-mail perto do vencimento (ver
listar_pix_a_lembrar/listar_assinaturas_sem_renovacao_vencidas, já
usados há tempos pra "cortesia" e reaproveitados agora pro PIX de
verdade, ver conceder_teste_gratis_pix/criar_cobranca_pix).

PIX já tinha sido tentado antes via Stripe, mas o Stripe exige 60 dias de
conta antes de liberar PIX como forma de pagamento — por isso a troca
pro Asaas (pedido do usuário, 07/10/2026), que libera PIX na hora."""
import os
import sqlite3
import time
from datetime import date
from pathlib import Path

import requests
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

# Quantos dias um período pago por PIX dura, por periodicidade — usado
# pra calcular periodo_atual_fim localmente (nem Stripe nem Asaas sabem
# disso, porque pra eles é só um pagamento avulso, sem noção de "assinatura").
DIAS_PIX = {"mensal": 30, "anual": 365}

# Quantos dias antes do vencimento o lembrete de renovação por PIX é
# mandado (ver verificar_pix() / app.py).
DIAS_LEMBRETE_PIX = 3

# Status do Stripe (ou, pro PIX, status que a gente mesmo controla) que
# contam como "acesso liberado".
STATUS_COM_ACESSO = {"trialing", "active"}

# --- Asaas (PIX) --------------------------------------------------------
# A chave de sandbox começa com $aact_hmlg_, a de produção com $aact_prod_
# — detecta sozinho qual API usar a partir da própria chave, sem precisar
# de uma variável de ambiente extra só pra isso (ver docs.asaas.com/docs/
# sandbox-2). Sem chave configurada, criar_cobranca_pix já recusa antes
# de tentar qualquer request (mesmo padrão do RESEND_API_KEY ausente em
# alertas.py — não trava o site, só avisa que a função não está pronta).
ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "")
ASAAS_BASE_URL = (
    "https://api-sandbox.asaas.com/v3" if ASAAS_API_KEY.startswith("$aact_hmlg_")
    else "https://api.asaas.com/v3"
)
# Token separado da API key (a própria Asaas recomenda não reaproveitar a
# API key aqui) — configurado na hora de cadastrar o webhook no painel do
# Asaas, e conferido em processar_webhook_asaas via header
# "asaas-access-token" (ver docs.asaas.com/docs/sobre-os-webhooks).
ASAAS_WEBHOOK_TOKEN = os.environ.get("ASAAS_WEBHOOK_TOKEN", "")

# Preço avulso (R$) por plano/periodicidade — Asaas não tem um catálogo de
# Prices pra referenciar por id como o Stripe; cada cobrança já leva o
# valor direto. Mesmos valores mostrados em /planos.
PRECOS_PIX = {
    ("atleta", "mensal"): 9.90,
    ("atleta", "anual"): 99.90,
    ("mestre", "mensal"): 19.90,
    ("mestre", "anual"): 199.90,
}


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
        if "asaas_customer_id" not in colunas:
            conn.execute("ALTER TABLE assinaturas ADD COLUMN asaas_customer_id TEXT")


def plano_valido(plano, periodicidade):
    return (plano, periodicidade) in PRECOS and bool(PRECOS[(plano, periodicidade)])


def plano_valido_pix(plano, periodicidade):
    return (plano, periodicidade) in PRECOS_PIX


def obter_assinatura(usuario_id):
    with _conn() as conn:
        linha = conn.execute(
            "SELECT * FROM assinaturas WHERE usuario_id = ?", (usuario_id,)
        ).fetchone()
    return dict(linha) if linha else None


def usuario_tem_acesso(usuario_id):
    assinatura = obter_assinatura(usuario_id)
    return bool(assinatura) and assinatura["status"] in STATUS_COM_ACESSO


def plano_atual(usuario_id):
    """Plano ATIVO agora ('atleta'/'mestre') ou None — fonte única de
    verdade pra saber o "papel" de alguém (ver app.py::_usuario_eh_mestre e
    /api/sessao). Não existe mais tipo_perfil independente: o papel é
    sempre derivado da assinatura de verdade, calculado a cada request, pra
    nunca dessincronizar (era exatamente isso que dava pra acontecer antes:
    o webhook do Stripe atualiza assinaturas, mas nunca atualizava
    usuarios.tipo_perfil)."""
    assinatura = obter_assinatura(usuario_id)
    if not assinatura or assinatura["status"] not in STATUS_COM_ACESSO:
        return None
    return assinatura["plano"]


def usuario_eh_mestre(usuario_id):
    return plano_atual(usuario_id) == "mestre"


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


def _asaas_request(metodo, caminho, **kwargs):
    """POST/GET genérico pra API do Asaas — centraliza header de
    autenticação e o erro de chave ausente (mesmo padrão do RESEND_API_KEY
    em alertas.py: não derruba o site, só devolve um erro claro pra quem
    chamou tratar)."""
    if not ASAAS_API_KEY:
        raise RuntimeError("ASAAS_API_KEY não configurada")
    resposta = requests.request(
        metodo, f"{ASAAS_BASE_URL}{caminho}",
        headers={"access_token": ASAAS_API_KEY, "Content-Type": "application/json"},
        timeout=20, **kwargs,
    )
    resposta.raise_for_status()
    return resposta.json()


def _asaas_obter_ou_criar_cliente(usuario, cpf, nome):
    """Retorna (customer_id, erro). Reaproveita o cliente já criado no
    Asaas pra esse usuário (guardado em assinaturas.asaas_customer_id) se
    existir — senão cria um novo. cpfCnpj é obrigatório na API do Asaas
    pra criar cliente (CPF/CNPJ não é um dado que o Radar BJJ coleta no
    cadastro normal, então é pedido na hora de pagar por PIX, ver
    api_checkout_pix em app.py)."""
    assinatura = obter_assinatura(usuario["id"])
    if assinatura and assinatura.get("asaas_customer_id"):
        return assinatura["asaas_customer_id"], None

    cpf = (cpf or "").strip()
    if not cpf:
        return None, "CPF é obrigatório pra gerar cobrança PIX"

    try:
        cliente = _asaas_request("POST", "/customers", json={
            "name": nome or usuario["email"],
            "cpfCnpj": cpf,
            "email": usuario["email"],
            "externalReference": str(usuario["id"]),
        })
    except (RuntimeError, requests.RequestException) as exc:
        return None, f"erro ao criar cliente no Asaas: {exc}"
    return cliente["id"], None


def criar_cobranca_pix(usuario, plano, periodicidade, cpf, nome):
    """Retorna (url, erro). Cria (ou reaproveita) o cliente no Asaas e gera
    uma cobrança PIX avulsa — pagamento no cartão usa assinatura de
    verdade (criar_sessao_checkout, renovação automática pelo Stripe);
    PIX não tem cartão salvo, então é sempre um pagamento avulso por
    período (ver DIAS_PIX) que a pessoa precisa repetir manualmente pra
    continuar. O acesso só é liberado de verdade quando o webhook
    confirma o pagamento (ver processar_webhook_asaas) — isso aqui só
    gera o link de pagamento, igual ao Stripe Checkout fazia."""
    if not plano_valido_pix(plano, periodicidade):
        return None, "plano inválido"

    customer_id, erro = _asaas_obter_ou_criar_cliente(usuario, cpf, nome)
    if erro:
        return None, erro

    valor = PRECOS_PIX[(plano, periodicidade)]
    try:
        cobranca = _asaas_request("POST", "/payments", json={
            "customer": customer_id,
            "billingType": "PIX",
            "value": valor,
            "dueDate": date.today().isoformat(),
            "description": f"Radar BJJ — Plano {plano.capitalize()} PRO ({periodicidade})",
            "externalReference": f"{usuario['id']}:{plano}:{periodicidade}",
        })
    except (RuntimeError, requests.RequestException) as exc:
        return None, f"erro ao criar cobrança no Asaas: {exc}"

    # Guarda o cliente (pra reaproveitar na próxima cobrança, sem pedir
    # CPF de novo) mesmo antes do pagamento confirmar — não mexe em
    # status/plano/periodo_atual_fim, que só mudam de verdade com o
    # webhook (ver processar_webhook_asaas).
    _upsert(usuario["id"], asaas_customer_id=customer_id)
    return cobranca.get("invoiceUrl"), None


def conceder_teste_gratis_pix(usuario_id, plano):
    """"Testar grátis" pra quem vai pagar por PIX — libera acesso imediato
    por DIAS_TESTE_GRATIS dias SEM cobrar nada ainda (diferente do
    cartão: aqui não tem como debitar sozinho depois do teste acabar, já
    que PIX não guarda cartão — ver criar_cobranca_pix). A pessoa
    continua tendo que voltar e pagar de verdade antes do teste vencer
    (mesmo lembrete/corte automático que já existe hoje pra "cortesia",
    ver listar_pix_a_lembrar/listar_assinaturas_sem_renovacao_vencidas —
    forma_pagamento="pix" já é tratado igual lá). Só funciona uma vez por
    conta (ninguém com assinatura/teste registrado ainda) — senão dava
    pra repetir o teste grátis pra sempre só clicando de novo."""
    if obter_assinatura(usuario_id):
        return False, "você já usou o teste grátis (ou já tem uma assinatura)"
    periodo_atual_fim = int(time.time()) + DIAS_TESTE_GRATIS * 86400
    _upsert(
        usuario_id,
        stripe_customer_id=None, stripe_subscription_id=None,
        plano=plano, periodicidade=None, status="active", trial_fim=None,
        periodo_atual_fim=str(periodo_atual_fim),
        forma_pagamento="pix", pix_lembrete_enviado_em=None,
    )
    return True, None


def processar_webhook_asaas(payload, token_recebido):
    """Confere o token do webhook (header asaas-access-token, configurado
    na hora de cadastrar o webhook no painel do Asaas — NUNCA a API key,
    ver docs.asaas.com/docs/sobre-os-webhooks) e aplica o evento. Levanta
    ValueError se o token não bater (chamador deve responder 401/403).
    Retorna o nome do evento processado, ou None se não era um evento que
    a gente trata (ex: cobrança criada, mas ainda não paga)."""
    if not ASAAS_WEBHOOK_TOKEN or token_recebido != ASAAS_WEBHOOK_TOKEN:
        raise ValueError("token do webhook inválido")

    evento = payload.get("event")
    if evento not in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"):
        return None

    pagamento = payload.get("payment") or {}
    referencia = pagamento.get("externalReference") or ""
    partes = referencia.split(":")
    if len(partes) != 3:
        return evento
    usuario_id_str, plano, periodicidade = partes
    try:
        usuario_id = int(usuario_id_str)
    except ValueError:
        return evento

    periodo_atual_fim = int(time.time()) + DIAS_PIX.get(periodicidade, 30) * 86400
    _upsert(
        usuario_id,
        stripe_customer_id=None, stripe_subscription_id=None,
        asaas_customer_id=pagamento.get("customer"),
        plano=plano, periodicidade=periodicidade, status="active", trial_fim=None,
        periodo_atual_fim=str(periodo_atual_fim),
        forma_pagamento="pix", pix_lembrete_enviado_em=None,
    )
    return evento


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


def conceder_cortesia(usuario_id, plano, dias=None):
    """Libera o Plano PRO manualmente pra alguém, sem passar pelo Stripe —
    usado pelo admin em Gerenciar Usuários (ex: parceria, cortesia,
    compensar um problema). `dias=None` é sem validade (só sai revogando
    na mão); com `dias`, expira sozinho depois (ver listar_assinaturas_sem_
    renovacao_vencidas, que trata "cortesia" igual a "pix" pra isso — os dois
    são formas de pagamento que não avisam a gente quando renovam)."""
    periodo_atual_fim = int(time.time()) + dias * 86400 if dias else None
    _upsert(
        usuario_id,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        plano=plano,
        periodicidade=None,
        status="active",
        trial_fim=None,
        periodo_atual_fim=str(periodo_atual_fim) if periodo_atual_fim else None,
        forma_pagamento="cortesia",
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


def listar_assinaturas_sem_renovacao_vencidas():
    """Assinaturas que NINGUÉM renova sozinho — PIX (sem cartão salvo) e
    cortesia (concedida na mão, ver conceder_cortesia) — ainda marcadas
    "active", cujo período já passou. Perdem o acesso (status vira
    "vencida", fora de STATUS_COM_ACESSO) até pagar/receber de novo.
    Diferente do Stripe, que já se corrige sozinho via webhook."""
    with _conn() as conn:
        linhas = conn.execute(
            """SELECT * FROM assinaturas
               WHERE forma_pagamento IN ('pix', 'cortesia') AND status = 'active'
                 AND CAST(periodo_atual_fim AS INTEGER) <= ?""",
            (int(time.time()),),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def marcar_pix_lembrete_enviado(usuario_id):
    _upsert(usuario_id, pix_lembrete_enviado_em=str(int(time.time())))


def marcar_assinatura_vencida(usuario_id):
    _upsert(usuario_id, status="vencida")
