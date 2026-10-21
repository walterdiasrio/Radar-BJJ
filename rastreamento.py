"""Conversão confirmada por PIX pro Meta Ads e Google Ads/GA4 — via
servidor, não pelo navegador.

Por quê: o Meta Pixel/gtag do navegador (ver static/assinatura.js,
static/assinatura-sucesso.html) só sabe disparar um evento se a PESSOA
estiver com o site aberto no momento. Isso funciona pra quem paga no
cartão (o Stripe redireciona de volta pro nosso /assinatura/sucesso), mas
quem paga por PIX nunca volta: o pagamento acontece na página hospedada
da Asaas, e a confirmação chega só pelo webhook (ver
pagamentos.processar_webhook_asaas), sem navegador nenhum aberto. Sem
isso, toda conversão por PIX ficava invisível pro Meta/Google — rodar
tráfego pago otimizando só com os dados do cartão enviesaria o algoritmo
contra quem prefere PIX (pedido do usuário, 21/10/2026).

Sem as chaves configuradas (META_CAPI_ACCESS_TOKEN / GA4_API_SECRET),
cada função aqui não faz nada — mesmo padrão do RESEND_API_KEY ausente em
alertas.py: não trava o site, só deixa de reportar.
"""
import hashlib
import os
import time

import requests

META_PIXEL_ID = os.environ.get("META_PIXEL_ID", "28254694314126516")
META_CAPI_ACCESS_TOKEN = os.environ.get("META_CAPI_ACCESS_TOKEN", "")

GA4_MEASUREMENT_ID = os.environ.get("GA4_MEASUREMENT_ID", "G-DDSBFFHD2F")
GA4_API_SECRET = os.environ.get("GA4_API_SECRET", "")


def _sha256(valor):
    return hashlib.sha256(valor.strip().lower().encode()).hexdigest()


def _reportar_meta_capi(email, valor, fbp):
    if not META_CAPI_ACCESS_TOKEN:
        return
    user_data = {"em": [_sha256(email)]}
    if fbp:
        user_data["fbp"] = fbp
    try:
        requests.post(
            f"https://graph.facebook.com/v21.0/{META_PIXEL_ID}/events",
            params={"access_token": META_CAPI_ACCESS_TOKEN},
            json={"data": [{
                "event_name": "Subscribe",
                "event_time": int(time.time()),
                "action_source": "website",
                "user_data": user_data,
                "custom_data": {"value": valor, "currency": "BRL"},
            }]},
            timeout=10,
        )
    except requests.RequestException:
        pass  # conversão de ad tracking não pode derrubar o webhook de pagamento


def _reportar_ga4(client_id, plano, periodicidade, valor):
    if not GA4_API_SECRET or not client_id:
        return
    try:
        requests.post(
            "https://www.google-analytics.com/mp/collect",
            params={"measurement_id": GA4_MEASUREMENT_ID, "api_secret": GA4_API_SECRET},
            json={
                "client_id": client_id,
                "events": [{
                    "name": "purchase",
                    "params": {
                        "value": valor,
                        "currency": "BRL",
                        "items": [{"item_name": f"{plano}_{periodicidade}"}],
                    },
                }],
            },
            timeout=10,
        )
    except requests.RequestException:
        pass


def reportar_conversao_pix(email, plano, periodicidade, valor, ga_client_id, fbp):
    """Chamado só quando o webhook da Asaas confirma o pagamento de
    verdade (ver pagamentos.processar_webhook_asaas) — nunca na criação
    da cobrança, que a pessoa pode gerar e nunca pagar."""
    _reportar_meta_capi(email, valor, fbp)
    _reportar_ga4(ga_client_id, plano, periodicidade, valor)
