"""Conector CBJJD (cbjjd.com.br / isbjj.com).

O sistema de inscrições roda em isbjj.com. A checagem pública de atletas só
fica acessível quando a checagem do evento está aberta; fora desse período o
site redireciona para "checagem_abrir_invalida.asp". Quando aberta, cada
categoria (masculino/feminino gi) tem sua própria página de checagem.
"""
import re
from bs4 import BeautifulSoup

from .http import get

CBJJD_SITE = "https://cbjjd.com.br"
ISBJJ = "https://isbjj.com"

PAGINAS_CHECAGEM = [
    "checagem_geral_masculino_gi.asp",
    "checagem_geral_feminino_gi.asp",
    "checagem_absoluto_masculino_gi.asp",
    "checagem_absoluto_feminino_gi.asp",
]


def listar_eventos():
    resp = get(f"{CBJJD_SITE}/eventos/")
    soup = BeautifulSoup(resp.text, "lxml")
    eventos = []
    seen = set()
    for a in soup.select("a[href*='menucampeonato.asp']"):
        href = a.get("href", "")
        m = re.search(r"isbjj\.com/campeonatos/(\d+)/(\d+)/menucampeonato\.asp", href)
        if not m:
            continue
        path = f"campeonatos/{m.group(1)}/{m.group(2)}"
        if path in seen:
            continue
        seen.add(path)
        nome_el = a.select_one(".post-des p")
        data_el = a.select_one(".post-date span")
        local_el = a.select_one(".post-location span")
        titulo = nome_el.get_text(strip=True) if nome_el else (a.get_text(strip=True) or path)
        eventos.append({
            "id": path,
            "nome": titulo,
            "url": href,
            "data": data_el.get_text(strip=True) if data_el else "",
            "local": local_el.get_text(strip=True) if local_el else "",
        })
    return eventos


def _checagem_aberta(html):
    return "checagem_abrir_invalida" not in html and "INVÁLIDA" not in html.upper()


def buscar_atletas(evento_id, filtros):
    menu_url = f"{ISBJJ}/{evento_id}/menucampeonato.asp"
    resp_menu = get(menu_url)
    if resp_menu.status_code != 200:
        return []

    resultados = []
    for pagina in PAGINAS_CHECAGEM:
        url = f"{ISBJJ}/{evento_id}/{pagina}"
        resp = get(url, headers={"Referer": menu_url}, allow_redirects=True)
        if not _checagem_aberta(resp.text):
            continue
        resultados.extend(_parsear_checagem(resp.text))

    if not resultados:
        # Sinaliza para a camada de busca que a checagem não está aberta agora
        return []
    return resultados


def _parsear_checagem(html):
    soup = BeautifulSoup(html, "lxml")
    resultados = []

    # A checagem costuma ter um cabeçalho de categoria seguido de uma tabela
    # de atletas (mesmo padrão usado pela CBJJ/CBJJO). Procuramos qualquer
    # elemento que pareça um título de categoria e a tabela mais próxima depois dele.
    candidatos_categoria = soup.find_all(
        lambda tag: tag.name in ("h3", "h4", "div", "strong")
        and tag.get_text(strip=True)
        and re.search(r"MASCULINO|FEMININO", tag.get_text(strip=True).upper())
    )

    for header in candidatos_categoria:
        categoria_texto = header.get_text(strip=True)
        tabela = header.find_next("table")
        if not tabela:
            continue
        linhas = tabela.find_all("tr")
        for linha in linhas:
            cols = [c.get_text(strip=True) for c in linha.find_all("td")]
            if len(cols) < 2:
                continue
            resultados.append({
                "federacao": "CBJJD",
                "nome": cols[1] if len(cols) > 1 else cols[0],
                "equipe": cols[2] if len(cols) > 2 else "",
                "categoria_idade": categoria_texto,
                "genero": "MASCULINO" if "MASCULINO" in categoria_texto.upper() else "FEMININO",
                "peso": "",
                "faixa": "",
            })
    return resultados
