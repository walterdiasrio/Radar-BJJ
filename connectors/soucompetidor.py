"""Conector SouCompetidor (soucompetidor.com.br) — complementa a AJP.

Parte dos atletas da AJP se inscreve pelo Smoothcomp (ver connectors/ajp.py,
importado manualmente/via Drive), mas outra parte se inscreve por um portal
à parte, o SouCompetidor — atletas que não aparecem em nenhum lugar se só
lermos o Smoothcomp. Esse conector busca esses atletas AO VIVO (página
pública "Checagem Geral", sem bloqueio, sem precisar de login) e devolve
pra ajp.buscar_atletas somar com o que já veio do Smoothcomp.

Não existe um ID de evento em comum entre as duas plataformas — o casamento
do evento AJP (Smoothcomp) com o evento correspondente no SouCompetidor é
automático, por nome (ver _melhor_slug): busca todos os eventos com "AJP" no
nome no SouCompetidor e escolhe o que tem mais palavras em comum com o nome/
local do evento já importado. É heurística (não há garantia de acerto), mas
como os eventos AJP Tour são sempre nomeados "AJP TOUR <CIDADE> ..." nas duas
plataformas, a cidade sozinha já costuma bastar.

Os campos da categoria vêm em português e num formato de rótulos diferente
do Smoothcomp (ex: "MASCULINO/MASTER 1/ROXA/ATE 62KG") — são traduzidos pro
mesmo vocabulário em inglês que a AJP já usa (ver _traduzir_idade/_faixa/
_peso), pra continuar combinando com os filtros de busca existentes. Como
não há uma tabela oficial de tradução, isso também é best-effort: rótulos
não reconhecidos passam direto (Title Case) em vez de quebrar a busca.

Divisões marcadas "NOGI" (categoria No-Gi dentro de um evento que é Gi) são
descartadas — a AJP é tratada como sempre-Gi em todo o resto do site (ver
FEDERACOES_SMOOTHCOMP_SEM_KIMONO em connectors/__init__.py), então misturar
essas divisões classificaria peso/categoria errado pros filtros de busca.
"""
import os
import re
import threading
import time
import unicodedata

from bs4 import BeautifulSoup

from .http import get

BASE = "https://soucompetidor.com.br"

# Buscas ao vivo no SouCompetidor são bem mais lentas que ler o JSON local
# do Smoothcomp (várias páginas HTML por evento) — cacheia separado do
# resto da AJP pra não deixar toda busca lenta. TTL do casamento
# evento->slug é mais longo (o vínculo não muda) que o dos atletas em si
# (inscrições mudam com mais frequência).
CACHE_TTL_SLUG_SEGUNDOS = int(os.environ.get("CACHE_TTL_SOUCOMPETIDOR_SLUG_SEGUNDOS", 1800))
CACHE_TTL_ATLETAS_SEGUNDOS = int(os.environ.get("CACHE_TTL_SOUCOMPETIDOR_ATLETAS_SEGUNDOS", 300))
_MAX_PAGINAS = 50

_cache_slug = {}
_cache_slug_lock = threading.Lock()
_cache_atletas = {}
_cache_atletas_lock = threading.Lock()


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


_PALAVRAS_IGNORADAS = {
    "ajp", "tour", "international", "internacional", "championship",
    "campeonato", "jiu", "jitsu", "open", "edicao", "copa", "gi", "nogi",
    "the", "and",
}


def _tokens(texto):
    normalizado = re.sub(r"[^a-z0-9\s]", " ", _normalizar(texto))
    return {
        palavra for palavra in normalizado.split()
        if len(palavra) >= 4 and not palavra.isdigit() and palavra not in _PALAVRAS_IGNORADAS
    }


_SLUG_RE = re.compile(r"/pt-br/eventos/todos-os-eventos/(p\d+-[a-z0-9-]+)/", re.I)


def _buscar_candidatos(termo):
    resp = get(f"{BASE}/pt-br/eventos/todos-os-eventos/novos/", params={"eventos": termo})
    slugs = {m.group(1) for m in _SLUG_RE.finditer(resp.text)}
    candidatos = []
    for slug in slugs:
        _, _, resto = slug.partition("-")
        candidatos.append((slug, resto.replace("-", " ")))
    return candidatos


def _melhor_slug(nome_evento_ajp, local_evento_ajp):
    alvo = _tokens(f"{local_evento_ajp or ''} {nome_evento_ajp or ''}")
    if not alvo:
        return None
    candidatos = _buscar_candidatos("AJP")
    melhor_slug, melhor_pontos = None, 0
    for slug, nome_pela_url in candidatos:
        pontos = len(alvo & _tokens(nome_pela_url))
        if pontos > melhor_pontos:
            melhor_slug, melhor_pontos = slug, pontos
    return melhor_slug


def _slug_evento(nome_evento_ajp, local_evento_ajp):
    chave = (nome_evento_ajp or "", local_evento_ajp or "")
    with _cache_slug_lock:
        entrada = _cache_slug.get(chave)
        if entrada and time.time() - entrada[0] < CACHE_TTL_SLUG_SEGUNDOS:
            return entrada[1]

    slug = _melhor_slug(nome_evento_ajp, local_evento_ajp)

    with _cache_slug_lock:
        _cache_slug[chave] = (time.time(), slug)
    return slug


def _parse_pagina(html):
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.select_one("table")
    if not tabela:
        return [], 1

    cabecalhos = [th.get_text(strip=True).upper() for th in tabela.select("thead th")]
    linhas = []
    for tr in tabela.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) != len(cabecalhos):
            continue
        campos = dict(zip(cabecalhos, tds))
        nome_td = campos.get("NOME DO ATLETA")
        categoria_td = campos.get("CATEGORIA")
        if nome_td is None or categoria_td is None:
            continue
        equipe_td = campos.get("EQUIPE")
        linhas.append({
            "nome": nome_td.get_text(strip=True),
            "equipe": equipe_td.get_text(strip=True) if equipe_td else "",
            "categoria": categoria_td.get_text(strip=True),
        })

    ultima_pagina = 1
    for m in re.finditer(r"page=(\d+)", html):
        ultima_pagina = max(ultima_pagina, int(m.group(1)))
    return linhas, ultima_pagina


def _linhas_checagem(slug):
    url = f"{BASE}/pt-br/eventos/checagem-geral/{slug}/"
    linhas, ultima_pagina = _parse_pagina(get(url).text)
    todas = list(linhas)
    for pagina in range(2, min(ultima_pagina, _MAX_PAGINAS) + 1):
        linhas_pagina, _ = _parse_pagina(get(url, params={"page": pagina}).text)
        todas.extend(linhas_pagina)
    return todas


# Mesmas siglas de faixa do connectors/ajp.py (_FAIXA_PT_PARA_EN) — duplicado
# aqui de propósito, pra não criar import circular entre os dois módulos.
_FAIXA_PT_PARA_EN = {
    "branca": "white", "cinza": "grey", "cinzenta": "grey",
    "amarela": "yellow", "laranja": "orange", "verde": "green",
    "azul": "blue", "roxa": "purple", "marrom": "brown", "preta": "black",
}


def _traduzir_faixa(faixa_pt):
    partes = [_FAIXA_PT_PARA_EN.get(p.strip().lower(), p.strip().lower()) for p in faixa_pt.split("+")]
    return "+".join(p.capitalize() for p in partes if p)


_MASTER_RE = re.compile(r"^master\s*(\d+)$", re.I)
_KIDS_RE = re.compile(r"^kids\s*(\d+)$", re.I)

_IDADE_PT_PARA_EN = {
    "teen": "Teen",
    "junior": "Junior",
    "juvenil (youth)": "Youth",
    "juvenil": "Youth",
    "infantil": "Infantil",
    "adulto": "Adult",
    "amateur (adulto)": "Adult",
    "professional (adulto)": "Adult",
    "amateur (acima de 18 anos)": "Adult",
    "professional (acima de 18 anos)": "Adult",
}


def _traduzir_idade(idade_pt):
    chave = idade_pt.strip().lower()
    if chave in _IDADE_PT_PARA_EN:
        return _IDADE_PT_PARA_EN[chave]
    m = _MASTER_RE.match(idade_pt.strip())
    if m:
        return f"Master {m.group(1)}"
    m = _KIDS_RE.match(idade_pt.strip())
    if m:
        return f"Kids {m.group(1)}"
    return idade_pt.strip().title()


_PESO_ATE_RE = re.compile(r"^ATE\s+(\d+(?:[.,]\d+)?)\s*KG$", re.I)
_PESO_ACIMA_RE = re.compile(r"^ACIMA\s+DE\s+(\d+(?:[.,]\d+)?)\s*KG$", re.I)


def _traduzir_peso(peso_pt):
    peso_pt = peso_pt.strip()
    m = _PESO_ATE_RE.match(peso_pt)
    if m:
        return f"-{m.group(1)}KG"
    m = _PESO_ACIMA_RE.match(peso_pt)
    if m:
        return f"+{m.group(1)}KG"
    if "absolut" in peso_pt.lower():
        return "Absoluto"
    return peso_pt


def _genero_pt(genero_raw):
    g = genero_raw.strip().lower()
    return g if g in ("masculino", "feminino") else g


def _atletas_das_linhas(linhas):
    atletas = []
    for linha in linhas:
        partes = [p.strip() for p in linha["categoria"].split("/")]
        if len(partes) != 4:
            continue
        genero_raw, idade_raw, faixa_raw, peso_raw = partes
        if "nogi" in idade_raw.lower():
            continue
        atletas.append({
            "federacao": "AJP",
            "nome": linha["nome"],
            "equipe": linha["equipe"],
            "categoria_idade": _traduzir_idade(idade_raw),
            "genero": _genero_pt(genero_raw),
            "peso": _traduzir_peso(peso_raw),
            "faixa": _traduzir_faixa(faixa_raw),
            "pais": "",
            "ano_nascimento": "",
            "pagamento": "Confirmado",
        })
    return atletas


def atletas_do_evento(nome_evento_ajp, local_evento_ajp):
    """Atletas AJP inscritos pelo SouCompetidor pro evento correspondente
    (casado por nome/local — ver _melhor_slug) ao de `nome_evento_ajp`, já
    traduzidos pro vocabulário da AJP. Lista vazia se não achar o evento
    correspondente ou se o SouCompetidor não tiver ninguém inscrito lá."""
    slug = _slug_evento(nome_evento_ajp, local_evento_ajp)
    if not slug:
        return []

    with _cache_atletas_lock:
        entrada = _cache_atletas.get(slug)
        if entrada and time.time() - entrada[0] < CACHE_TTL_ATLETAS_SEGUNDOS:
            return entrada[1]

    atletas = _atletas_das_linhas(_linhas_checagem(slug))

    with _cache_atletas_lock:
        _cache_atletas[slug] = (time.time(), atletas)
    return atletas
