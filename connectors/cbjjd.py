"""Conector CBJJD (cbjjd.com.br / isbjj.com).

O sistema de inscrições roda em isbjj.com. A checagem pública de atletas só
fica acessível quando a checagem do evento está aberta; fora desse período o
site redireciona para "checagem_abrir_invalida.asp". Quando aberta, cada
categoria (masculino/feminino gi) tem sua própria página de checagem.
"""
import re
from datetime import date

from bs4 import BeautifulSoup

from . import idade as idade_mod
from . import peso as peso_mod
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


def _partes_categoria(bloco):
    """O cabeçalho de cada categoria (ex: "FAIXA: BRANCA | PRE-MIRIM 3 (6
    anos) | - 22,000") vem logo no começo do bloco, antes da primeira tag
    <font> (que abre o trecho de "Área 0"/horário — puro ruído, sem <font>
    fechando antes dele por causa das dezenas de tags aninhadas nunca
    fechadas). Faixa, divisão e peso vêm separados por "|"; na página
    "absoluto" o terceiro campo é o texto "TODOS OS PESOS" em vez de um
    peso numérico."""
    m = re.search(r"^(.*?)<font", bloco, re.S)
    if not m:
        return "", "", ""
    bruto = re.sub(r"<[^>]+>", " ", m.group(1))
    partes = [" ".join(p.split()) for p in bruto.split("|")]
    partes = [p for p in partes if p]
    faixa = partes[0].lstrip(":").strip() if len(partes) > 0 else ""
    divisao = partes[1] if len(partes) > 1 else ""
    peso_bruto = partes[2] if len(partes) > 2 else ""
    return faixa, divisao, peso_bruto


def _idade_da_divisao(divisao):
    m = re.search(r"\((\d+)", divisao)
    return int(m.group(1)) if m else None


def _categoria_idade_padrao(idade):
    """O texto da divisão raspado da página (ex: "PRE-MIRIM 3 (6 anos)",
    "INFANTO-JUVENIL 1 (13 anos)") é bem mais granular do que a categoria
    etária que o filtro de busca calcula pra CBJJD (connectors/idade.py usa
    faixas mais largas, tipo "Pré-Mirim" pra 4-6 anos, "Mirim" pra 7-9). Sem
    converter pro mesmo rótulo, o filtro por idade nunca bate com o que a
    gente devolve aqui — por isso usamos a idade extraída da divisão pra
    calcular o mesmo rótulo que o filtro usaria."""
    if idade is None:
        return ""
    ano_referencia = date.today().year
    return idade_mod.categoria_para("cbjjd", ano_referencia - idade, ano_referencia) or ""


def _nome_peso(divisao, genero, bruto):
    """Converte o peso bruto raspado da página (ex: "- 22,000" ou "+ 45,300")
    pro nome oficial da categoria de peso (ex: "Pena"), usando a mesma tabela
    oficial CBJJD que o filtro de busca usa (connectors/peso.py) — sem isso,
    o filtro por peso nunca bate com o que a gente devolve aqui, porque o
    filtro compara pelo nome da categoria, não pelo número em kg."""
    m = re.match(r"([+-])\s*([\d.,]+)", (bruto or "").strip())
    if not m:
        return ""
    sinal, numero_str = m.groups()
    idade = _idade_da_divisao(divisao)
    if idade is None:
        return ""
    try:
        numero = float(numero_str.replace(",", "."))
    except ValueError:
        return ""
    if sinal == "+":
        numero += 0.05  # "acima de X" — empurra pra categoria seguinte da tabela
    return peso_mod.categoria_peso_para("cbjjd", idade, numero, genero) or ""


_LINHA_ATLETA = re.compile(r'<div class="linha-atleta">(.*?)<!-- MOBILE -->', re.S)
_VALUE = re.compile(r'value="([^"]*)"')


def _parsear_checagem(html, genero):
    """A página é HTML muito antigo, com tags nunca fechadas (ex: dezenas de
    <font> aninhados sem par) — isso quebra qualquer parser de árvore DOM,
    que acaba enfiando o documento inteiro dentro do primeiro <td>. Por isso
    trabalhamos direto no texto bruto: cada categoria começa com a palavra
    "FAIXA", então dividimos o HTML por ela; dentro de cada bloco, cada
    atleta vem num <div class="linha-atleta"> com uma tabela de <input
    readonly value="..."> SEM atributo "name" (o site abandonou os names
    antigos numa reforma visual) — só dá pra saber o que é cada campo pela
    ORDEM: Qtd, Nome, Número, Academia, ABS, Observação. Cortamos o bloco no
    comentário "<!-- MOBILE -->" pra não recontar os mesmos dados que se
    repetem em texto simples no card mobile logo depois. Categorias sem
    ninguém marcado continuam aparecendo como linhas "molde" com o <input>
    vazio — por isso pulamos qualquer nome vazio em vez de tratá-lo como
    atleta."""
    resultados = []
    for bloco in html.split("FAIXA")[1:]:
        faixa, divisao, peso_bruto = _partes_categoria(bloco)
        idade = _idade_da_divisao(divisao or faixa)

        for linha in _LINHA_ATLETA.findall(bloco):
            valores = _VALUE.findall(linha)
            if len(valores) < 4:
                continue
            nome = valores[1].strip()
            if not nome:
                continue
            resultados.append({
                "federacao": "CBJJD",
                "nome": nome,
                "equipe": valores[3].strip(),
                "categoria_idade": _categoria_idade_padrao(idade) or divisao or faixa,
                "genero": genero,
                "peso": _nome_peso(divisao or faixa, genero, peso_bruto),
                "faixa": faixa.strip().title(),
            })
    return resultados
