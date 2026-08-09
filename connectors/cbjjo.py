"""Conector CBJJO (cbjjo.com.br / portalsamurai.com).

O sistema de eventos roda em cbjjo.beta.portalsamurai.com, identificado por
um ID_EVENTO numérico. Duas páginas nos interessam:
  - views/checagem/checagem_atleta.php?ID_EVENTO=N  → lista de inscritos,
    só acessível enquanto a checagem do evento está aberta.
  - views/evento/evento_apuracao_categoria.php?ID_EVENTO=N → atletas por
    categoria pós-evento (sempre disponível depois que o evento acontece).
Ambas têm o mesmo formato: um rótulo de categoria (".apur-cat-label" ou
equivalente) seguido de uma tabela com ATLETA / EQUIPE.
"""
import re
from datetime import date
from bs4 import BeautifulSoup

from .http import get
from . import datas as datas_mod

CBJJO_SITE = "https://www.cbjjo.com.br"
PORTAL = "https://cbjjo.beta.portalsamurai.com"


def listar_eventos():
    resp = get(f"{CBJJO_SITE}/site/eventos/calendario")
    soup = BeautifulSoup(resp.text, "lxml")
    eventos = []
    seen = set()
    for a in soup.select("a[href*='ID_EVENTO=']"):
        href = a.get("href", "")
        m = re.search(r"ID_EVENTO=(\d+)", href)
        if not m:
            continue
        evento_id = m.group(1)
        if evento_id in seen:
            continue
        seen.add(evento_id)
        detalhes = _detalhes_evento(evento_id)
        eventos.append({"id": evento_id, "url": href, **detalhes})
    return eventos


def _detalhes_evento(evento_id):
    try:
        resp = get(f"{PORTAL}/views/evento/Evento.php?ID_EVENTO={evento_id}")
        soup = BeautifulSoup(resp.text, "lxml")

        titulo_el = soup.select_one("h1, h2")
        texto = titulo_el.get_text(strip=True) if titulo_el else ""
        if not texto and soup.title:
            texto = soup.title.get_text(strip=True)
        titulo = texto if texto and "Warning" not in texto else f"Evento {evento_id}"

        campos = {}
        for linha in soup.select(".evc-info-row"):
            rotulo_el = linha.select_one(".evc-info-label")
            valor_el = linha.select_one(".evc-info-value")
            if rotulo_el and valor_el:
                campos[rotulo_el.get_text(strip=True).lower()] = valor_el.get_text(strip=True)

        data_texto = campos.get("data", "")
        local_texto = campos.get("local", "")

        inscricoes_abertas = None
        prazo_texto = campos.get("inscrições", "")
        prazo = datas_mod.extrair_data(prazo_texto)
        if prazo is not None:
            inscricoes_abertas = date.today() <= prazo

        return {
            "nome": titulo,
            "data": data_texto,
            "local": local_texto,
            "inscricoes_abertas": inscricoes_abertas,
        }
    except Exception:
        return {"nome": f"Evento {evento_id}", "data": "", "local": "", "inscricoes_abertas": None}


def buscar_atletas(evento_id, filtros):
    checagem_url = f"{PORTAL}/views/checagem/checagem_atleta.php?ID_EVENTO={evento_id}"
    resp = get(checagem_url, allow_redirects=True)
    resultados = _parsear_categoria(resp.text, "CBJJO")
    if resultados:
        return resultados

    # Checagem fechada (evento ainda não abriu ou já terminou) — tenta o
    # resultado por categoria, que fica disponível após o evento.
    apuracao_url = f"{PORTAL}/views/evento/evento_apuracao_categoria.php?ID_EVENTO={evento_id}"
    resp2 = get(apuracao_url, allow_redirects=True)
    return _parsear_categoria(resp2.text, "CBJJO")


def _parsear_categoria(html, federacao):
    soup = BeautifulSoup(html, "lxml")
    resultados = []

    labels = soup.select(".apur-cat-label") or soup.select("[class*='cat-label']")
    for label in labels:
        categoria_texto = re.sub(r"\s+", " ", label.get_text(" ", strip=True))
        tabela = label.find_next("table")
        if not tabela:
            continue

        genero = "MASCULINO" if "MASCULINO" in categoria_texto.upper() else (
            "FEMININO" if "FEMININO" in categoria_texto.upper() else "")
        m_faixa = re.search(
            r"BRANCA|CINZA|AMARELA|LARANJA|VERDE|AZUL|ROXA|MARROM|PRETA",
            categoria_texto.upper(),
        )
        faixa = m_faixa.group(0) if m_faixa else ""
        categoria_idade = categoria_texto.split(genero)[0].strip() if genero else categoria_texto

        for linha in tabela.select("tbody tr"):
            cols = [c.get_text(strip=True) for c in linha.find_all("td")]
            if len(cols) < 2:
                continue
            resultados.append({
                "federacao": federacao,
                "nome": cols[0],
                "equipe": cols[1],
                "categoria_idade": categoria_idade,
                "genero": genero,
                "peso": "",
                "faixa": faixa,
            })
    return resultados
