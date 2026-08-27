"""Conector FJJEMG (Federação de Jiu-Jitsu do Estado de Minas Gerais —
até dez/2025 era a LMJJ, Liga Mineira de Jiu-Jitsu, que "virou federação"
sem trocar de sistema).

Dois sites: fjjemg.com.br (institucional) e fjjemg.adm.br (inscrição e
checagem, sistema próprio em ASP, cada etapa num caminho
/campeonatos/<ano>/<etapa>/...).

listar_eventos() lê a home (fjjemg.com.br/calendario/, seção de cards de
evento) — só os cards com link (inscrição já aberta) viram evento aqui, os
demais são só cartazes informativos sem página própria ainda (mesma
limitação da CBJJC/FJJPE). Data e local já vêm em texto limpo direto no
card (".event-date"/".event-location") — essa federação não precisa do
hack de calendário nem de imagem que a FJJPE precisou. O nome do evento não
está no card (só um logo/imagem) — busca na página de checagem da própria
etapa (".titulo").

buscar_atletas() lê a "Checagem Geral de Atletas" (masculino/feminino, só
GI por enquanto — ver abaixo), tabela HTML limpa e previsível: um
".categoria" por bloco ("FAIXA: BRANCA/CINZA | MIRIM A (6/7 anos) |
- 24,000 KGS | Área 0") seguido de linhas com campos <input readonly>
(Qtd/Nome/Número/Academia/ABS/Observação).

A categoria de peso na checagem vem como o limite em KG ("- 24,000 KGS"),
não um nome ("Pluma") — convertido pro nome oficial comparando contra a
mesma tabela de peso.py usada pro lado do filtro (ver _nome_peso), garante
que as duas pontas sempre usam exatamente os mesmos números.

Só as divisões DE KIMONO (Categorias GI, masculino e feminino) — igual à
CBJJC, a FJJEMG é tratada como sempre-Gi pro cálculo de categoria de peso
(ver evento_sem_kimono em connectors/__init__.py), e cada evento daqui tem
GI e NOGI juntos (não dá pra usar o nome do evento pra saber qual é qual).
NOGI, Absoluto e "Desafio Kids" (formato à parte, com faixas de idade
próprias) ficam de fora por enquanto.
"""
import re

from bs4 import BeautifulSoup

from . import peso as peso_mod
from .http import get

SITE = "https://fjjemg.com.br"
DOMINIO_EVENTOS = "https://fjjemg.adm.br"

_EVENTO_URL_RE = re.compile(r"/campeonatos/(\d{4})/(\d+)/")


def _nome_evento(ano, etapa):
    try:
        resp = get(f"{DOMINIO_EVENTOS}/campeonatos/{ano}/{etapa}/checagem_geral_masculino_gi.asp")
    except Exception:
        return ""
    soup = BeautifulSoup(resp.text, "lxml")
    titulo = soup.select_one(".titulo")
    return titulo.get_text(strip=True) if titulo else ""


def listar_eventos():
    resp = get(f"{SITE}/calendario/")
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select(".event-card"):
        link = card.select_one("a.event-link-overlay[href]")
        if not link:
            continue  # sem inscrição aberta ainda, sem página própria pra ler
        m = _EVENTO_URL_RE.search(link.get("href") or "")
        if not m:
            continue
        ano, etapa = m.group(1), m.group(2)

        nome = _nome_evento(ano, etapa)
        if not nome:
            continue

        data_el = card.select_one(".event-date")
        local_el = card.select_one(".event-location")
        # ".event-location" começa com um pin de localização (emoji 📍 solto
        # no texto, não uma imagem — o WordPress só troca por <img> no
        # navegador via JS, o HTML puro que a gente lê tem o emoji mesmo).
        local_texto = local_el.get_text(strip=True).lstrip("📍 ") if local_el else ""
        eventos.append({
            "id": f"fjjemg-{ano}-{etapa}",
            "nome": nome,
            "data": data_el.get_text(strip=True) if data_el else "",
            "local": local_texto,
            "inscricoes_abertas": True,  # só chega aqui quem tem o card com link/tag "Inscrições Abertas"
        })
    return eventos


_CATEGORIA_RE = re.compile(r"^FAIXA:\s*(.+?)\s*\|\s*(.+?)\s*\|\s*([+-])\s*([\d.,]+)\s*KGS")


def _nome_peso(idade_texto, genero, sinal, valor_kg):
    """Converte o limite em kg da checagem ("- 24,000") no nome oficial da
    categoria (ex: "Galo"), usando a MESMA tabela de peso.py do lado do
    filtro — garante que as duas pontas sempre concordam. sinal "+" é
    sempre a categoria mais pesada da tabela (a checagem usa "+" pro
    último degrau em vez do "SEM PESO MÁXIMO" da tabela oficial).
    Casa pelo valor mais PRÓXIMO em vez de exigir igualdade exata: alguns
    limites na checagem ao vivo saem uns 0,2-0,5kg diferentes da imagem
    oficial da tabela (ex: "Leve" do Mirim A é 27,000 na tabela mas
    apareceu como 27,200 numa checagem real) — ainda assim é claramente a
    categoria mais próxima, exigir exatidão perderia esses casos."""
    # busca o número DENTRO dos parênteses ("(30 a 35 anos)") — não o
    # primeiro número da string inteira, que pra Master é o nível
    # ("MASTER 1 (30 a 35 anos)" começa com o "1" de "Master 1", não a idade)
    m_idade = re.search(r"\((\d+)", idade_texto)
    idade = int(m_idade.group(1)) if m_idade else 18
    tabela = peso_mod._fjjemg(idade, genero)
    if not tabela:
        return None
    if sinal == "+":
        return tabela[-1][0]
    try:
        valor = float(valor_kg.replace(",", "."))
    except ValueError:
        return None
    candidatos = [(nome, limite) for nome, limite in tabela if limite is not None]
    if not candidatos:
        return tabela[-1][0]
    return min(candidatos, key=lambda par: abs(par[1] - valor))[0]


def _linhas_checagem(ano, etapa, sexo):
    resp = get(f"{DOMINIO_EVENTOS}/campeonatos/{ano}/{etapa}/checagem_geral_{sexo}_gi.asp")
    soup = BeautifulSoup(resp.text, "lxml")

    linhas = []
    categoria_atual = None
    for el in soup.select(".categoria, .linha-atleta"):
        if "categoria" in el.get("class", []):
            categoria_atual = el.get_text(" ", strip=True)
            continue
        if not categoria_atual:
            continue
        m = _CATEGORIA_RE.match(categoria_atual)
        if not m:
            continue
        faixa, idade_texto, sinal, valor_kg = m.groups()

        tabela_row = el.select_one("table.tabela-desktop")
        inputs = tabela_row.select("input") if tabela_row else []
        if len(inputs) < 4:
            continue
        nome = (inputs[1].get("value") or "").strip()
        academia = (inputs[3].get("value") or "").strip()
        if not nome:
            continue

        linhas.append({
            "faixa": faixa,
            "idade_texto": idade_texto,
            "sinal": sinal,
            "valor_kg": valor_kg,
            "nome": nome,
            "equipe": academia,
        })
    return linhas


def buscar_atletas(evento_id, filtros):
    partes = evento_id.split("-")
    if len(partes) != 3:
        return []
    _, ano, etapa = partes

    atletas = []
    for sexo, genero in (("masculino", "masculino"), ("feminino", "feminino")):
        for linha in _linhas_checagem(ano, etapa, sexo):
            peso_nome = _nome_peso(linha["idade_texto"], genero, linha["sinal"], linha["valor_kg"])
            atletas.append({
                "federacao": "FJJEMG",
                "nome": linha["nome"],
                "equipe": linha["equipe"],
                "categoria_idade": linha["idade_texto"],
                "genero": genero,
                "peso": peso_nome or "",
                "faixa": linha["faixa"],
            })
    return atletas
