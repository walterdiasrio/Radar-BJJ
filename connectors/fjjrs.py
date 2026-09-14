"""Conector FJJ-RS (Federação de Jiu-Jitsu do Estado do Rio Grande do Sul).

listar_eventos() lê o calendário público em fjjrs.com.br ("Circuito
Estadual") — cada card do calendário só traz nome e link pra um "iframe"
de detalhe (fjjrs.com.br/modulos/agenda/eventos.php?b=<id>) com o resto
(data, local, prazos de inscrição). Eventos futuros sem inscrição aberta
ainda mostram só "Em Breve" nesse iframe (conferido ao vivo: 8ª e 9ª
Etapa 2026) — sem link pra inscrição, sem como buscar atleta neles
mesmo, então ficam de fora.

O link de inscrição de cada evento aponta direto pro SouCompetidor
(soucompetidor.com.br) — a FJJ-RS não roda checagem própria, usa esse
portal como back-end de inscrição/checagem (confirmado no próprio edital
em PDF do evento: "Checagem Geral: Será realizada on-line no site
www.soucompetidor.com.br"). buscar_atletas() por isso reaproveita
connectors/soucompetidor.py::_linhas_checagem (mesmo mecanismo que a AJP
já usa como complemento — ver soucompetidor.py) em vez de duplicar o
scraping; só a tradução de categoria é diferente (mantém em português,
não traduz pro vocabulário em inglês da AJP).

O prazo de inscrição de verdade é o do ÚLTIMO lote (o edital tem vários
lotes com desconto progressivo, tipo "1º Lote até 06/09", "4º Lote até
23/09" — depois disso não aceita mais inscrição nova) — pega sempre a
maior data de "Até dia DD/MM/YY" encontrada no texto, não importa quantos
lotes o evento tiver.

O próprio edital declara "Este evento seguirá rigorosamente as regras da
CONFEDERAÇÃO BRASILEIRA DE JIU-JITSU" — por isso entra em
connectors/peso.py reaproveitando _cbjj_fjjrio (mesma tabela oficial).
Faixas etárias na checagem real, porém, vêm em bandas de 2 anos
("PRE-MIRIM", "INF-JUV A/B"...) que batem com connectors/idade.py::
_CBJJE, não com o padrão ano-a-ano da CBJJ/FJJRio (mesmo caso já visto em
FJJPR/FJJPA) — normalizadas aqui antes de chegar em idade.py.

Divisões "NOGI" (o evento tem uma parte com kimono e outra sem, mesmo
como a AJP trata isso pro seu complemento SouCompetidor) e "ABS"
(absoluto, categorias combinadas tipo "MASTER 1+2 ABS") ficam de fora —
sem tabela de peso Sem Kimono nem um jeito limpo de representar bracket
combinado no formato usado aqui."""
import html as html_mod
import re
from datetime import date

from . import datas as datas_mod
from . import soucompetidor
from .http import get

SITE = "https://www.fjjrs.com.br"

_SLUG_SOUCOMPETIDOR_RE = re.compile(r"soucompetidor\.com\.br/pt-br/eventos/todos-os-eventos/(p\d+-[a-z0-9-]+)/", re.I)
_LOTE_DATA_RE = re.compile(r"Até dia (\d{1,2})/(\d{1,2})/(\d{2,4})", re.I)

# Prefixo (não igualdade exata) porque a checagem real tem sub-bandas com
# letra solta não previstas na _CBJJE (ex: "PRE-MIRIM B") — cai pro rótulo
# _CBJJE mesmo assim, só ignora a letra. Master fica de fora daqui (já sai
# certo do título "MASTER N", inclusive combinados tipo "MASTER 4+5+6").
_PREFIXOS_IDADE = [
    ("pre-mirim", "Pré-Mirim"),
    ("mirim", "Mirim"),
    ("infantil a", "Infantil A"),
    ("infantil b", "Infantil B"),
    ("infanto-juvenil a", "Infanto Juvenil A"),
    ("infanto-juvenil b", "Infanto Juvenil B"),
    ("infanto juvenil a", "Infanto Juvenil A"),
    ("infanto juvenil b", "Infanto Juvenil B"),
    ("juvenil", "Juvenil"),
    ("adulto", "Adulto"),
]


def _normalizar_idade(bruto):
    chave = bruto.strip().lower()
    for prefixo, rotulo in _PREFIXOS_IDADE:
        if chave.startswith(prefixo):
            return rotulo
    return bruto.strip().title()


# Peso sem acento na checagem real ("MEDIO", "PESADISSIMO") — só por
# consistência visual com o resto do site (as outras federações mostram
# acentuado); as demais categorias já saem certas só com .title().
_PESO_NORMALIZADO = {"medio": "Médio", "pesadissimo": "Pesadíssimo"}


def _normalizar_peso(bruto):
    return _PESO_NORMALIZADO.get(bruto.strip().lower(), bruto.strip().title())


def _detalhe_evento(evento_id):
    resp = get(f"{SITE}/modulos/agenda/eventos.php", params={"b": evento_id})
    return html_mod.unescape(resp.text)


def listar_eventos():
    resp = get(f"{SITE}/")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select("#calendario .card"):
        titulo_el = card.select_one(".card-header b")
        link_el = card.select_one('a[href*="eventos.php"]')
        if not titulo_el or not link_el:
            continue
        m_id = re.search(r"b=(\d+)", link_el["href"])
        if not m_id:
            continue
        evento_id = m_id.group(1)

        texto = _detalhe_evento(evento_id)
        if not _SLUG_SOUCOMPETIDOR_RE.search(texto):
            continue  # "Em Breve" — sem inscrição aberta, sem como buscar atleta

        m_data = re.search(r"<strong>Data:</strong>\s*([^<]+)", texto)
        m_local = re.search(r"<strong>Local:</strong>\s*([^<]+)", texto)

        eventos.append({
            "id": evento_id,
            "nome": titulo_el.get_text(strip=True),
            "url": f"{SITE}/modulos/agenda/eventos.php?b={evento_id}",
            "data": datas_mod.formatar(m_data.group(1).strip()) if m_data else "",
            "local": m_local.group(1).strip() if m_local else "",
        })
    return eventos


def status_inscricao(evento):
    url = evento.get("url")
    if not url:
        return None, None
    try:
        texto = html_mod.unescape(get(url).text)
    except Exception:
        return None, None

    prazos = []
    for dia, mes, ano in _LOTE_DATA_RE.findall(texto):
        ano_completo = int(ano) if len(ano) == 4 else 2000 + int(ano)
        try:
            prazos.append(date(ano_completo, int(mes), int(dia)))
        except ValueError:
            continue
    if not prazos:
        return None, None
    prazo = max(prazos)
    return date.today() <= prazo, prazo.isoformat()


def buscar_atletas(evento_id, filtros):
    texto = _detalhe_evento(evento_id)
    m_slug = _SLUG_SOUCOMPETIDOR_RE.search(texto)
    if not m_slug:
        return []
    slug = m_slug.group(1)

    resultados = []
    for linha in soucompetidor._linhas_checagem(slug):
        partes = [p.strip() for p in linha["categoria"].split("/")]
        if len(partes) != 4:
            continue
        genero_raw, idade_raw, faixa_raw, peso_raw = partes
        if "nogi" in idade_raw.lower() or "abs" in idade_raw.lower():
            continue

        resultados.append({
            "federacao": "FJJRS",
            "nome": linha["nome"],
            "equipe": linha["equipe"],
            "categoria_idade": _normalizar_idade(idade_raw),
            "genero": genero_raw.strip().lower(),
            "peso": _normalizar_peso(peso_raw),
            "faixa": faixa_raw.strip().title(),
        })
    return resultados
