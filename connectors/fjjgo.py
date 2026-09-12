"""Conector FJJGO (Federação de Jiu-Jitsu de Goiás) via SouCompetidor.

Diferente da maioria das federações brasileiras (site institucional próprio
com lista de eventos e checagem geral), a FJJGO — e outros organizadores do
Centro-Oeste, como o "Campeonato Centro-Oeste Brasileiro de Jiu-Jitsu" —
rodam as inscrições na mesma plataforma pública do SouCompetidor
(soucompetidor.com.br) já usada em connectors/soucompetidor.py como
complemento da AJP. Aqui o SouCompetidor É a fonte principal, não um
complemento.

Não existe filtro de organizador/federação na busca do SouCompetidor (só
"eventos" por substring do nome, testado ao vivo em 09/09/2026: buscar por
"FJJGO" não retorna nada — o evento oficial da federação nem leva a sigla no
título). A única forma confiável de achar os eventos é varrer a listagem
"novos eventos" (mesma que _buscar_candidatos usa) e filtrar pelos que
acontecem em Goiás (local termina em "- GO"). A listagem pagina via
"page=N", mas depois do fim do conteúdo real ela volta a repetir a primeira
página em vez de ficar vazia (confirmado ao vivo) — por isso paramos assim
que uma página inteira não traz nenhum slug novo, em vez de confiar em
"página vazia" como sinal de fim.

O nome do evento no card da listagem (<h6>) vem truncado com "…" pra títulos
longos (é assim no HTML, não só visual) — o nome completo só existe no atributo
alt da imagem do card ("P<id>-<NOME> <edição>"), por isso extraído de lá.

Os rótulos de categoria (idade/peso/faixa) já vêm em português no formato
"GENERO/IDADE/FAIXA/PESO" — igual ao formato lido por soucompetidor.py, mas
os valores em si (ex: "JUVENIL" sem separar 1/2, "INF-JUV 1" abreviado) não
batem com o vocabulário em inglês que soucompetidor._traduzir_idade/_peso
produzem para a AJP (aquele é o vocabulário Smoothcomp). Por isso esse
conector traduz os rótulos por conta própria, pro mesmo vocabulário em
português usado pela tabela idade.py/peso.py "fjjgo" (que segue o padrão
CBJJ/FJJRio, com a única diferença de não separar Juvenil 1/2 — ver
connectors/idade.py)."""
import re
from datetime import date

from bs4 import BeautifulSoup

from .http import get
from .soucompetidor import BASE, _linhas_checagem

_MAX_PAGINAS_LISTAGEM = 10

_SLUG_RE = re.compile(r"/pt-br/eventos/todos-os-eventos/(p\d+-[a-z0-9-]+)/", re.I)


def _nome_completo(card):
    """O <h6> do card é truncado com "…" para nomes longos — o nome
    completo (sem a truncagem) só existe no atributo alt da imagem, no
    formato "P<id>-<NOME> <edição>"; removemos o prefixo do id e o sufixo
    de edição (repetido à parte em .text-edicao) pra sobrar só o nome."""
    img = card.select_one("img.card-img-top")
    alt = (img.get("alt") if img else "") or ""
    nome = re.sub(r"^P\d+-", "", alt).strip()
    edicao_el = card.select_one(".text-edicao")
    edicao = edicao_el.get_text(strip=True) if edicao_el else ""
    if edicao and nome.endswith(edicao):
        nome = nome[: -len(edicao)].strip()
    if nome:
        return nome
    h6 = card.select_one("h6")
    return h6.get_text(strip=True) if h6 else ""


def _eventos_da_pagina(html):
    """Devolve TODOS os eventos da página (não só os de Goiás) — usado por
    listar_eventos() pra detectar o fim real da paginação (ver ali). O
    filtro por "- GO" fica pra depois, em listar_eventos()."""
    soup = BeautifulSoup(html, "lxml")
    eventos = []
    for card in soup.select("div.card.h-100"):
        link = card.select_one("a[href*='todos-os-eventos/p']")
        if not link:
            continue
        m = _SLUG_RE.search(link.get("href") or "")
        if not m:
            continue
        locais = card.select(".card-title small")
        local = locais[1].get_text(strip=True) if len(locais) > 1 else ""
        data_el = card.select_one(".date-badge-card")
        data_bruta = data_el.get_text(" ", strip=True) if data_el else ""
        eventos.append({
            "id": m.group(1),
            "nome": _nome_completo(card),
            "url": f"{BASE}/pt-br/eventos/todos-os-eventos/{m.group(1)}/",
            "data": re.sub(r"\s+", " ", data_bruta),
            "local": local,
        })
    return eventos


def listar_eventos():
    vistos = set()
    eventos_go = []
    pagina = 1
    while pagina <= _MAX_PAGINAS_LISTAGEM:
        params = {} if pagina == 1 else {"page": pagina}
        html = get(f"{BASE}/pt-br/eventos/todos-os-eventos/novos/", params=params).text
        # A paginação (page=N) não fica vazia no fim do conteúdo real — ela
        # volta a repetir a primeira página (confirmado ao vivo em
        # 09/09/2026) — por isso o critério de parada é "página inteira já
        # vista", contando TODOS os eventos da página, não só os de Goiás
        # (senão qualquer página sem evento de GO no meio da listagem real
        # pararia a busca cedo demais).
        novos = 0
        for evento in _eventos_da_pagina(html):
            if evento["id"] in vistos:
                continue
            vistos.add(evento["id"])
            novos += 1
            if re.search(r"-\s*GO$", evento["local"]):
                eventos_go.append(evento)
        if novos == 0 and pagina > 1:
            break
        pagina += 1
    return eventos_go


_PERIODO_INSCRICAO_RE = re.compile(
    # Sem ":" logo após "inscrição" — achado ao vivo em 11/09/2026 (Circuito
    # de Lutas Casadas Team Jackin) que o texto entre o rótulo e o ":" varia
    # por evento: "inscrição: (podendo ser antecipado...)" num evento,
    # "inscrição (podendo ser antecipado...): Até:..." noutro (mesma
    # federação, digitado à mão por evento). Exigir ":" logo em seguida
    # perdia esse segundo formato inteiro (nenhuma data extraída).
    r"Per[íi]odo de inscri[cç][ãa]o\b.*?(?=Per[íi]odo\s+de\s+CHECAGEM|$)", re.I | re.S
)
_DATA_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def status_inscricao(evento):
    """(inscricoes_abertas, prazo_inscricao). A página do evento tem uma
    seção "AGENDA / SCHEDULE" > "Período de inscrição" com uma ou mais
    datas "Até: DD/MM/YYYY" (uma por forma de pagamento — boleto fecha
    antes de cartão/PIX, por exemplo) antes da seção seguinte, "Período de
    CHECAGEM". Usamos a maior dessas datas — é sempre a última forma de
    pagamento ainda aceita, ou seja, o prazo final de verdade."""
    url = evento.get("url")
    if not url:
        return None, None
    try:
        resp = get(url)
    except Exception:
        return None, None
    soup = BeautifulSoup(resp.text, "lxml")
    texto = soup.get_text(" ", strip=True)

    secao = _PERIODO_INSCRICAO_RE.search(texto)
    if not secao:
        return None, None
    prazos = []
    for m in _DATA_RE.finditer(secao.group()):
        dia, mes, ano = (int(x) for x in m.groups())
        try:
            prazos.append(date(ano, mes, dia))
        except ValueError:
            continue
    if not prazos:
        return None, None
    prazo = max(prazos)
    return date.today() <= prazo, prazo.isoformat()


# Rótulos exatamente como aparecem na checagem geral real (conferido ao vivo
# em 09/09/2026 contra o Campeonato Centro-Oeste Brasileiro de Jiu-Jitsu
# 2026) — ver connectors/idade.py::_FJJGO pro porquê de cada um.
_IDADE_MAP = {
    "pre-mirim 1": "Pré-Mirim 1", "pre-mirim 2": "Pré-Mirim 2", "pre-mirim 3": "Pré-Mirim 3",
    "mirim 1": "Mirim 1", "mirim 2": "Mirim 2", "mirim 3": "Mirim 3",
    "infantil 1": "Infantil 1", "infantil 2": "Infantil 2", "infantil 3": "Infantil 3",
    "inf-juv 1": "Infanto-Juvenil 1", "inf-juv 2": "Infanto-Juvenil 2", "inf-juv 3": "Infanto-Juvenil 3",
    "juvenil": "Juvenil", "juvenil 1": "Juvenil", "juvenil 2": "Juvenil",
    "adulto": "Adulto",
    "master 1": "Master 1", "master 2": "Master 2", "master 3": "Master 3",
    "master 4": "Master 4", "master 5": "Master 5", "master 6": "Master 6",
}


def _traduzir_idade(idade_pt):
    return _IDADE_MAP.get(idade_pt.strip().lower(), idade_pt.strip().title())


# Nomes de categoria de peso batem com a tabela CBJJ/FJJRio (ver peso.py),
# só sem acento na checagem real ("MEDIO", "PESADISSIMO") — recolocado aqui
# pra combinar com o rótulo acentuado que peso.categoria_peso_para devolve.
_PESO_MAP = {
    "galo": "Galo", "pluma": "Pluma", "pena": "Pena", "leve": "Leve",
    "medio": "Médio", "meio-pesado": "Meio-Pesado", "pesado": "Pesado",
    "super-pesado": "Super-Pesado", "pesadissimo": "Pesadíssimo",
    "absoluto": "Absoluto",
}


def _traduzir_peso(peso_pt):
    return _PESO_MAP.get(peso_pt.strip().lower(), peso_pt.strip().title())


def _atletas_das_linhas(linhas):
    # Não reaproveita soucompetidor._atletas_das_linhas aqui de propósito:
    # aquela função traduz idade/peso pro vocabulário em INGLÊS da AJP
    # (Smoothcomp) — a FJJGO precisa dos rótulos em português da tabela
    # idade.py/peso.py "fjjgo" (ver _traduzir_idade/_traduzir_peso acima).
    atletas = []
    for linha in linhas:
        partes = [p.strip() for p in linha["categoria"].split("/")]
        if len(partes) != 4:
            continue
        genero_raw, idade_raw, faixa_raw, peso_raw = partes
        if "nogi" in idade_raw.lower():
            continue
        atletas.append({
            "federacao": "FJJGO",
            "nome": linha["nome"],
            "equipe": linha["equipe"],
            "categoria_idade": _traduzir_idade(idade_raw),
            "genero": genero_raw.strip().lower(),
            "peso": _traduzir_peso(peso_raw),
            "faixa": faixa_raw.title(),
            "pagamento": "Confirmado",
        })
    return atletas


def buscar_atletas(evento_id, filtros):
    return _atletas_das_linhas(_linhas_checagem(evento_id))
