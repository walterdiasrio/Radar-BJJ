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


_CAMPO_NOME = re.compile(r'name="m_nomeatleta"[^>]*value="([^"]*)"')
_CAMPO_ACADEMIA = re.compile(r'name="m_nomeacademia"[^>]*value="([^"]*)"')
_CAMPO_PESO = re.compile(r'name="m_peso"[^>]*value="([^"]*)"')


def _texto_categoria(bloco):
    # O texto da categoria (ex: "BRANCA - PRE-MIRIM 3 (6 anos)") vem logo no
    # começo do bloco, antes da primeira tag </font> que fecha o cabeçalho.
    m = re.search(r"^(.*?)</font>", bloco, re.S)
    if not m:
        return ""
    bruto = re.sub(r"<[^>]+>", " ", m.group(1))
    return " ".join(bruto.split()).lstrip("- ").strip()


def _parsear_checagem(html, genero):
    """A página é HTML muito antigo, com tags nunca fechadas (ex: dezenas de
    <font> aninhados sem par) — isso quebra qualquer parser de árvore DOM,
    que acaba enfiando o documento inteiro dentro do primeiro <td>. Por isso
    trabalhamos direto no texto bruto: cada categoria começa com a palavra
    "FAIXA", então dividimos o HTML por ela; dentro de cada bloco, os dados
    do atleta não estão em texto de célula, e sim em <input readonly
    value="..."> (name="m_nomeatleta", "m_nomeacademia", "m_peso" — só existe
    na página de absoluto). Categorias sem ninguém marcado continuam
    aparecendo como linhas "molde" com o <input> vazio — por isso pulamos
    qualquer nome vazio em vez de tratá-lo como atleta."""
    resultados = []
    for bloco in html.split("FAIXA")[1:]:
        categoria = _texto_categoria(bloco)
        faixa, _, divisao = categoria.partition(" - ")
        nomes = _CAMPO_NOME.findall(bloco)
        academias = _CAMPO_ACADEMIA.findall(bloco)
        pesos = _CAMPO_PESO.findall(bloco)

        for i, nome in enumerate(nomes):
            nome = nome.strip()
            if not nome:
                continue
            resultados.append({
                "federacao": "CBJJD",
                "nome": nome,
                "equipe": academias[i].strip() if i < len(academias) else "",
                "categoria_idade": divisao or categoria,
                "genero": genero,
                "peso": pesos[i].strip() if i < len(pesos) else "",
                "faixa": faixa.strip().title(),
            })
    return resultados
