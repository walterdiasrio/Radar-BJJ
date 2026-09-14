"""Conector FSMJJ (Federação Sul-Mato-Grossense de Jiu-Jitsu, MS).

Dois sites: fsmjj.com.br (institucional, calendário) e fsmjj.adm.br
(inscrição/checagem, sistema próprio em ASP clássico, mesma família de
sistema já usada pela FJJEMG — ver connectors/fjjemg.py — cada evento num
caminho /campeonatos<ano>/<numero>/...).

listar_eventos() lê o calendário (fsmjj.com.br/calendario2026/, cards
".fsmjj-card") — só os cards com link pra fsmjj.adm.br viram evento aqui;
cards "Encerrado" não têm link, e cards "Em Breve" também não (mesmo
tratamento dado a outras federações nessa mesma plataforma). Alguns cards
do calendário promovem evento de OUTRO organizador hospedado em domínio
diferente (ex: "Indoorzinho" em tatamebjj.com.br, mesmo sistema/mesmo
desenvolvedor, site de terceiro) — ficam de fora, só entra o que está
hospedado no próprio fsmjj.adm.br.

O "id" de cada evento é composto ("fsmjj-<ano>-<numero>", mesmo padrão de
fjjemg.py) porque o path muda a cada ano (campeonatos2026/, campeonatos
2027/...) e buscar_atletas só recebe o id, não a URL completa.

status_inscricao() lê o Edital em PDF (aberto, sem login; nome de arquivo
previsível EDITAL_CAMPEONATO_<ano>_<numero>_FSMJJ.PDF) e pega o prazo do
ÚLTIMO lote de preço ("INSCRIÇÕES GI ... ATÉ 14/09 ... ATÉ 14/10 ... ATÉ
16/11") — mesma técnica de "maior data de lote" já usada em fjjrs.py e
fjjemg.py. A frase solta "encerramento das inscrições na sexta-feira
DD/MM/AAAA" logo no início do edital NÃO é usada como fonte: conferido ao
vivo (edital da Etapa 12) que ela ficou desatualizada — parece copiada de
outro evento e não corrigida — bem antes da data real de fechamento (que
é sempre a do último lote de preço, alguns dias antes do evento).

buscar_atletas() só cobre as divisões DE KIMONO (masculino/feminino GI) —
mesma limitação já assumida em fjjemg.py: não achamos uma tabela de peso
Sem Kimono própria da FSMJJ com dados reais suficientes pra confiar (a
checagem de NoGi dos eventos abertos no momento desta implementação tem
poucos ou nenhum atleta confirmado ainda). "Absolutos" e "Festival Kids"
também ficam de fora — Absoluto duplicaria o mesmo atleta (já aparece na
categoria normal) e Festival Kids não tem chave/categoria de peso de
verdade (só recreação, conforme o próprio edital).

Cada linha de atleta na checagem vem em <input readonly> soltos dentro de
uma tabela HTML antiga e bem aninhada — faixa/idade/peso da CATEGORIA
ficam no cabeçalho da seção (<tr bgcolor="#000000">, duas linhas: uma com
"FAIXA - IDADE (x/y anos) - area de luta n. N", outra só com "ATE/ACIMA X
KGS"), não em cada atleta — _linhas_checagem varre <tr>/<input> em ordem
de documento carregando esse estado. Nome da categoria de peso ("Galo",
"Leve"...) não vem pronto, só o limite em kg — convertido comparando
contra a MESMA tabela de peso.py usada pro filtro (ver _nome_peso, igual
ao padrão já usado em fjjemg.py).

Checagem exige cookie de sessão ASP (visitar menucampeonato.asp antes,
senão a página responde "CHECAGEM DOS ATLETAS INVÁLIDA!", confirmado ao
vivo) — usa uma requests.Session() PRÓPRIA por chamada (não a sessão
global de connectors/http.py), porque o servidor amarra o cookie a um
evento específico e várias buscas rodam em paralelo em threads (ver
connectors/__init__.py) — uma sessão compartilhada arriscaria misturar o
cookie de sessão de dois eventos sendo buscados ao mesmo tempo.

Faixas etárias batem EXATAMENTE com connectors/idade.py::_CBJJE (Mirim
6/7, Infantil 1/2 8-11, Infanto-Juvenil 1/2 12-15, Juvenil 16/17, Adulto
18-29, Master 1-3 30-45 — conferido ao vivo pela checagem real de dois
eventos, cobrindo kids a Master 3). Peso bate com connectors/peso.py::
_cbjjd pra Juvenil/Adulto/Master (76/82/88/94/102 kg batem exatos, número
inteiro — não com casas decimais como a tabela CBJJ/FJJRio) — o próprio
edital cita "livro de regras CBJJD como referência" pra esse tipo de
critério. Pras idades kids (6 a 15 anos) a FSMJJ funde pares de idade da
CBJJD (ex: 8 e 9 anos) numa faixa só ("Infantil 1"), com os limites de
peso arredondados — bate quase todo, só 1 valor divergente observado (uma
faixa mostrou 40kg onde a CBJJD teria 39,3kg) — aceito por ser a melhor
aproximação disponível sem OCR da tabela de peso oficial da FSMJJ, que só
existe como imagem (tabela_pesos.asp, sem texto pra extrair)."""
import io
import re
from datetime import date

import pdfplumber
import requests
from bs4 import BeautifulSoup

from . import peso as peso_mod
from .http import get

SITE = "https://fsmjj.com.br"
ADM = "https://fsmjj.adm.br"

_EVENTO_URL_RE = re.compile(r"/campeonatos(\d{4})/(\d+)/")
_LOTE_DATA_RE = re.compile(r"\bAT[ÉE]\s+(\d{1,2})/(\d{1,2})\b", re.I)


def listar_eventos():
    resp = get(f"{SITE}/calendario2026/")
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select(".fsmjj-card"):
        link = card.select_one('a.fsmjj-btn[href*="fsmjj.adm.br"]')
        if not link:
            continue  # encerrado (sem link) ou hospedado no site de outro organizador
        m = _EVENTO_URL_RE.search(link.get("href", ""))
        if not m:
            continue
        ano, numero = m.group(1), m.group(2)

        etapa_el = card.select_one(".fsmjj-etapa")
        titulo_el = card.select_one(".fsmjj-title")
        partes_nome = [el.get_text(strip=True) for el in (etapa_el, titulo_el) if el]
        nome = " - ".join(partes_nome) if partes_nome else "Campeonato FSMJJ"

        data_el = card.select_one(".fsmjj-date")
        cidade_el = card.select_one(".fsmjj-city")

        # ".fsmjj-date" é só "DD/MM" (sem ano) — datas_mod.extrair_data só
        # reconhece "DD/MM/YYYY" (ano explícito) ou nome de mês por extenso,
        # nenhum dos dois casa com "DD/MM" puro. Já sabemos o ano de verdade
        # (vem no path da URL do evento, ao contrário da maioria das outras
        # federações que não tem ano nenhum na fonte) — monta "DD/MM/YYYY"
        # aqui em vez de deixar pro _ano_inferido genérico adivinhar.
        data_bruta = data_el.get_text(strip=True) if data_el else ""
        m_data = re.match(r"^(\d{1,2})/(\d{1,2})$", data_bruta)
        data_com_ano = f"{m_data.group(1)}/{m_data.group(2)}/{ano}" if m_data else data_bruta

        eventos.append({
            "id": f"fsmjj-{ano}-{numero}",
            "nome": nome,
            "url": f"{ADM}/campeonatos{ano}/{numero}/menucampeonato.asp",
            "data": data_com_ano,
            "local": cidade_el.get_text(strip=True) if cidade_el else "",
        })
    return eventos


def status_inscricao(evento):
    m = _EVENTO_URL_RE.search(evento.get("url", ""))
    if not m:
        return None, None
    ano, numero = m.group(1), m.group(2)
    url_edital = f"{ADM}/campeonatos{ano}/{numero}/EDITAL_CAMPEONATO_{ano}_{numero}_FSMJJ.PDF"

    try:
        resp = get(url_edital)
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
    except Exception:
        return None, None

    prazos = []
    for dia, mes in _LOTE_DATA_RE.findall(texto):
        try:
            prazos.append(date(int(ano), int(mes), int(dia)))
        except ValueError:
            continue
    if not prazos:
        return None, None
    prazo = max(prazos)
    return date.today() <= prazo, prazo.isoformat()


_CATEGORIA_RE = re.compile(r"^([A-ZÀ-Ú/\s]+?)\s*-\s*(.+?)\s*-\s*area", re.I)
_PESO_RAW_RE = re.compile(r"^(ATE|ACIMA)\s+([\d.,]+)\s*KGS?$", re.I)

_ORDEM_CHECAGEM = [
    ("checagem_geral_masculino_gi.asp", "masculino"),
    ("checagem_geral_feminino_gi.asp", "feminino"),
]


def _nome_peso(idade_texto, genero, peso_raw):
    m_peso = _PESO_RAW_RE.match((peso_raw or "").strip())
    if not m_peso:
        return None
    sinal, valor_texto = m_peso.groups()

    m_idade = re.search(r"\((\d+)", idade_texto or "")
    idade = int(m_idade.group(1)) if m_idade else 18
    tabela = peso_mod._cbjjd(idade, genero)
    if not tabela:
        return None

    if sinal.upper() == "ACIMA":
        return tabela[-1][0]
    try:
        valor = float(valor_texto.replace(",", "."))
    except ValueError:
        return None
    candidatos = [(nome, limite) for nome, limite in tabela if limite is not None]
    if not candidatos:
        return tabela[-1][0]
    return min(candidatos, key=lambda par: abs(par[1] - valor))[0]


def _linhas_checagem(sessao, ano, numero, pagina):
    resp = sessao.get(f"{ADM}/campeonatos{ano}/{numero}/{pagina}", timeout=18)
    soup = BeautifulSoup(resp.text, "lxml")

    faixa_atual = idade_atual = peso_atual = None
    atleta_atual = {}
    linhas = []
    for el in soup.find_all(["tr", "input"]):
        if el.name == "tr" and (el.get("bgcolor") or "").upper() == "#000000":
            texto = el.get_text(" ", strip=True)
            if re.match(r"^(ATE|ACIMA)\s", texto.upper()):
                peso_atual = texto.strip()
            else:
                m = _CATEGORIA_RE.match(texto)
                if m:
                    faixa_atual, idade_atual = m.group(1).strip(), m.group(2).strip()
            continue

        nome_campo = el.get("name", "")
        valor = (el.get("value") or "").strip()
        if nome_campo == "m_numero_sequencia":
            atleta_atual = {}
        atleta_atual[nome_campo] = valor
        if nome_campo == "m_pagamento" and atleta_atual.get("m_nomeatleta"):
            linhas.append({
                "faixa": faixa_atual,
                "idade": idade_atual,
                "peso": peso_atual,
                "nome": atleta_atual.get("m_nomeatleta", ""),
                "equipe": atleta_atual.get("m_nomeacademia", ""),
            })
    return linhas


def buscar_atletas(evento_id, filtros):
    partes = evento_id.split("-")
    if len(partes) != 3:
        return []
    _, ano, numero = partes

    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
    try:
        sessao.get(f"{ADM}/campeonatos{ano}/{numero}/menucampeonato.asp", timeout=18)
    except Exception:
        return []

    atletas = []
    for pagina, genero in _ORDEM_CHECAGEM:
        try:
            linhas = _linhas_checagem(sessao, ano, numero, pagina)
        except Exception:
            continue
        for linha in linhas:
            if not linha["nome"] or not linha["idade"]:
                continue
            atletas.append({
                "federacao": "FSMJJ",
                "nome": linha["nome"],
                "equipe": linha["equipe"],
                "categoria_idade": linha["idade"].title(),
                "genero": genero,
                "peso": _nome_peso(linha["idade"], genero, linha["peso"]) or "",
                "faixa": (linha["faixa"] or "").title(),
            })
    return atletas
