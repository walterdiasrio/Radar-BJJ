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
    ("checagem_geral_masculino_gi.asp", "MASCULINO"),
    ("checagem_geral_feminino_gi.asp", "FEMININO"),
    ("checagem_absoluto_masculino_gi.asp", "MASCULINO"),
    ("checagem_absoluto_feminino_gi.asp", "FEMININO"),
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
    for pagina, genero in PAGINAS_CHECAGEM:
        url = f"{ISBJJ}/{evento_id}/{pagina}"
        resp = get(url, headers={"Referer": menu_url}, allow_redirects=True)
        if not _checagem_aberta(resp.text):
            continue
        resultados.extend(_parsear_checagem(resp.text, genero))

    return resultados


def _texto_normalizado(tag):
    return " ".join(tag.get_text(" ", strip=True).split())


def _parsear_checagem(html, genero):
    """A página é uma única tabela gigante (HTML antigo, sem <table> por
    categoria): cada categoria é uma linha <tr bgcolor="#000000"> com
    "FAIXA - <faixa> - <divisão>", seguida de uma linha de cabeçalho
    <tr bgcolor="#FFFFFF"> com os rótulos das colunas ("Nome do Atleta",
    "Academia", etc — a posição varia entre página geral e absoluto) e então
    as linhas de atletas propriamente ditas. Times/idades vazios continuam
    aparecendo como linhas "molde" sem nome (é assim que o site sinaliza que
    ninguém fez checagem ainda nessa categoria) — por isso pulamos qualquer
    linha sem nome em vez de tratá-la como atleta."""
    soup = BeautifulSoup(html, "lxml")
    resultados = []
    categoria_atual = ""
    idx_nome = idx_academia = idx_peso = None

    for linha in soup.find_all("tr"):
        bg = (linha.get("bgcolor") or "").upper()
        cols = [_texto_normalizado(c) for c in linha.find_all("td", recursive=False)]

        if bg == "#000000" and cols and "FAIXA" in cols[0].upper():
            categoria_atual = cols[0]
            idx_nome = idx_academia = idx_peso = None
            continue

        if bg == "#FFFFFF" and "Nome do Atleta" in cols:
            idx_nome = cols.index("Nome do Atleta")
            idx_academia = cols.index("Academia") if "Academia" in cols else None
            idx_peso = cols.index("Peso") if "Peso" in cols else None
            continue

        if idx_nome is None or idx_nome >= len(cols):
            continue
        nome = cols[idx_nome]
        if not nome:
            continue

        m = re.match(r"FAIXA\s*-\s*([^-]+?)\s*-\s*(.+)", categoria_atual, re.I)
        resultados.append({
            "federacao": "CBJJD",
            "nome": nome,
            "equipe": cols[idx_academia] if idx_academia is not None and idx_academia < len(cols) else "",
            "categoria_idade": m.group(2) if m else categoria_atual,
            "genero": genero,
            "peso": cols[idx_peso] if idx_peso is not None and idx_peso < len(cols) else "",
            "faixa": m.group(1).strip().title() if m else "",
        })
    return resultados
