"""Conector CBJJ (cbjj.com.br) — mesma plataforma do IBJJF, só que em domínio/idioma BR.

Lista de eventos: API JSON `/api/v1/events/upcomings.json` (exige header Referer,
senão responde {"error":"Denied"}). O ID numérico do evento — usado depois para
buscar os atletas — vem embutido na URL do logo (".../Championship/Logo/3347").

Atletas: página pública `/events/{id}/athletes-list-by-divisions`, HTML estático
com uma seção <section class='category-set'> por categoria (idade/gênero/faixa/peso)
e uma tabela de atletas dentro de cada uma.
"""
import re
from bs4 import BeautifulSoup

from .http import get

BASE = "https://cbjj.com.br"

FAIXAS_PT = {
    "white": "Branca",
    "grey": "Cinza",
    "yellow": "Amarela",
    "orange": "Laranja",
    "green": "Verde",
    "blue": "Azul",
    "purple": "Roxa",
    "brown": "Marrom",
    "black": "Preta",
}


def listar_eventos():
    resp = get(
        f"{BASE}/api/v1/events/upcomings.json",
        headers={
            "Referer": f"{BASE}/events/championships",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    dados = resp.json()
    eventos = []
    for item in dados.get("championships", []):
        m = re.search(r"/Logo/(\d+)", item.get("urlLogo", ""))
        if not m:
            continue
        eventos.append({
            "id": m.group(1),
            "nome": item.get("name", ""),
            "url": f"{BASE}/events/{item.get('slug', '')}",
            "data": item.get("eventIntervalDays", ""),
            "local": ", ".join(p for p in (item.get("city"), item.get("state")) if p),
        })
    return eventos


def status_inscricao(evento):
    """True = inscrições abertas, False = fechadas, None = não deu pra saber.
    A página do evento tem um botão em '.registration-button a': quando as
    inscrições estão abertas ele é um link de verdade pra plataforma de
    inscrição ("Inscreva-se agora"); quando fecham (por prazo ou por atingir
    o limite de vagas) ele vira um botão desabilitado com texto avisando
    disso. (Versão antiga do site tinha um texto fixo "AS INSCRIÇÕES ESTÃO
    ABERTAS/FECHADAS" que não é mais usado — mantido como fallback abaixo
    caso a página volte a mudar.)"""
    url = evento.get("url")
    if not url:
        return None
    resp = get(url)
    soup = BeautifulSoup(resp.text, "lxml")

    botao = soup.select_one(".registration-button a")
    if botao:
        texto_botao = botao.get_text(strip=True).lower()
        if "fechad" in texto_botao or "limite" in texto_botao or "encerr" in texto_botao:
            return False
        if "inscreva" in texto_botao or "inscrição" in texto_botao or "inscricao" in texto_botao:
            return True

    texto = resp.text.upper()
    if "INSCRIÇÕES PARA ESSE EVENTO ESTÃO ABERTAS" in texto:
        return True
    if "INSCRIÇÕES PARA ESSE EVENTO ESTÃO FECHADAS" in texto:
        return False
    return None


def buscar_atletas(evento_id, filtros):
    resp = get(f"{BASE}/events/{evento_id}/athletes-list-by-divisions")
    soup = BeautifulSoup(resp.text, "lxml")

    resultados = []
    for section in soup.select("section.category-set"):
        header = section.select_one(".category-name")
        if not header:
            continue
        categoria_texto = header.get_text(strip=True)
        # formato: "Adulto / Masculino / Galo (57,50kg)"
        partes = [p.strip() for p in categoria_texto.split("/")]
        categoria_idade = partes[0] if len(partes) > 0 else ""
        genero = partes[1] if len(partes) > 1 else section.get("data-gender", "")
        peso = partes[2] if len(partes) > 2 else ""
        faixa_raw = section.get("data-belt-group", "")
        faixa = FAIXAS_PT.get(faixa_raw, faixa_raw)

        for row in section.select("table.registrations-table tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            equipe = cols[0].get_text(strip=True)
            atleta = cols[1].get_text(strip=True)
            resultados.append({
                "federacao": "CBJJ",
                "nome": atleta,
                "equipe": equipe,
                "categoria_idade": categoria_idade,
                "genero": genero,
                "peso": peso,
                "faixa": faixa,
            })
    return resultados
