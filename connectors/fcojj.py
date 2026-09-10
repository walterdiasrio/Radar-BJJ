"""Conector FCOJJ (Federação Centro-Oeste de Jiu-Jitsu e Artes Marciais),
sediada em Brasília/DF.

Diferente de toda outra federação do site, a FCOJJ não centraliza inscrições
numa única plataforma: o site institucional (fcojj.com.br/eventos) lista os
eventos oficiais da federação, mas cada um pode apontar pra uma plataforma
de inscrição diferente (ou nenhuma, se for só um registro histórico com link
pra álbum de fotos no Facebook). Conferido ao vivo em 09/09/2026: dos 20
eventos listados, só o mais recente aberto (Campeonato Brasiliense de
Jiu-Jitsu, 13/09/2026) tinha inscrição rodando de verdade, e é na
MartialMatch (martialmatch.com) — plataforma que nenhum outro conector daqui
usa ainda. A federação também tem uma filiação cadastrada no SouCompetidor,
mas isso é só carteirinha de atleta, não achamos nenhum evento dela rodando
lá.

listar_eventos() varre a página de eventos do site institucional e mantém
só os que têm link pra um evento MartialMatch (com id numérico na URL) — os
demais (Facebook, sem link) não têm como buscar atleta nenhum. Se um dia a
FCOJJ passar a usar outra plataforma pros próximos eventos, dá pra estender
esse filtro.

buscar_atletas() lê a "Lista de inscritos" pública da MartialMatch, uma API
JSON sem login (`/api/events/<id>/starting-lists/public`) — confirmado que
funciona direto via requests, sem bloqueio de Cloudflare (a página HTML em
volta tem challenge JS, mas o endpoint da API não). A categoria vem separada
por ";" (não "/", como no padrão SouCompetidor/AJP) e o número de campos
varia: 4 campos pra a maioria ("GENERO; IDADE; FAIXA; PESO"), 5 quando a
idade tem subdivisão numérica ("GENERO; IDADE; NIVEL; FAIXA; PESO", ex:
"MASCULINO; MASTER; 1+2; BRANCA; ATE 56KG"), e 2 pra categoria PCD (sem
faixa/peso, categoria aberta).

Os nomes de categoria etária da FCOJJ (Kids 1/2/3, Infantil, Júnior,
Adolescente, Juvenil, Adulto, Master 1-4) são um sistema próprio da
federação, diferente da tabela CBJJ/IBJJF (Mirim/Infantil/Infanto-Juvenil)
usada pela maioria das outras — a tabela de ano de nascimento -> categoria
está registrada em connectors/idade.py::_FCOJJ, extraída do edital oficial
do Campeonato Brasiliense de Jiu-Jitsu 2026 (Cláusula Terceira), então o
filtro de "ano de nascimento" já funciona. O de peso (kg), não: o edital diz
que os limites seguem "os parâmetros da AJP" mas remete a uma tabela em
"formato visual anexo" que não veio no PDF do edital — sem os números,
connectors/peso.py não tem entrada pra "fcojj" (mesmo comportamento de
qualquer federação fora de lá: mostra aviso, não filtra por peso). Nome,
equipe, gênero e faixa buscam normalmente.

Limitação conhecida do filtro por ano de nascimento: quando o organizador
junta dois brackets de Master adjacentes por falta de inscritos (ex:
"Master 1+2" em vez de "Master 1" e "Master 2" separados — visto ao vivo
nesse mesmo evento), o rótulo calculado a partir do ano de nascimento
("Master 1") não bate com o rótulo composto da inscrição real — ver
_idade_e_peso_e_faixa mais abaixo.
"""
import re

from bs4 import BeautifulSoup

from .http import get

SITE = "https://fcojj.com.br"
MARTIALMATCH_BASE = "https://martialmatch.com"

_LINK_MARTIALMATCH_RE = re.compile(r"martialmatch\.com/pt/events/(\d+)-[a-z0-9-]+", re.I)

_MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
_DATA_CARD_RE = re.compile(r"([a-zçãéô]+)\s+(\d{1,2})\s*,\s*(\d{4})", re.I)


def _data_do_card(elemento_data):
    if not elemento_data:
        return ""
    m = _DATA_CARD_RE.match(elemento_data.get_text(" ", strip=True))
    if not m:
        return ""
    mes = _MESES_PT.get(m.group(1).strip().lower())
    if not mes:
        return ""
    return f"{int(m.group(2)):02d}/{mes:02d}/{m.group(3)}"


def listar_eventos():
    resp = get(f"{SITE}/eventos")
    # O servidor declara ISO-8859-1 no header, mas serve o HTML em UTF-8 de
    # verdade — sem isso, todo acento vira caractere corrompido.
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for linha in soup.select(".kv-ee-row.kv-ee-event"):
        link = linha.select_one(".kv-ee-venue a[href]")
        if not link:
            continue
        m = _LINK_MARTIALMATCH_RE.search(link.get("href") or "")
        if not m:
            continue
        local_el = linha.select_one(".kv-ee-location")
        eventos.append({
            "id": f"martialmatch-{m.group(1)}",
            "nome": link.get_text(strip=True),
            "data": _data_do_card(linha.select_one(".kv-ee-date")),
            "local": local_el.get_text(" ", strip=True) if local_el else "",
        })
    return eventos


_IDADE_LABEL = {
    "kids": "Kids", "infantil": "Infantil", "junior": "Júnior",
    "adolescente": "Adolescente", "juvenil": "Juvenil", "adulto": "Adulto",
    "master": "Master", "pcd": "PCD",
}

_PESO_ATE_RE = re.compile(r"^ATE\s+(\d+(?:[.,]\d+)?)\s*KG$", re.I)
_PESO_ACIMA_RE = re.compile(r"^ACIMA\s+(\d+(?:[.,]\d+)?)\s*KG$", re.I)


def _traduzir_peso(peso_bruto):
    peso_bruto = peso_bruto.strip()
    m = _PESO_ATE_RE.match(peso_bruto)
    if m:
        return f"-{m.group(1)}KG"
    m = _PESO_ACIMA_RE.match(peso_bruto)
    if m:
        return f"+{m.group(1)}KG"
    return peso_bruto.title()


def _idade_e_peso_e_faixa(categoria_bruta):
    """Retorna (categoria_idade, faixa, peso) a partir do texto bruto da
    categoria MartialMatch (ver formatos no docstring do módulo). O gênero
    já vem separado antes de chamar esta função (é sempre o 1º campo).

    Quando o nível vem composto (ex: "MASTER; 1+2", o organizador juntou
    dois brackets adjacentes por falta de inscritos pra abrir os dois
    separados — conferido ao vivo em 09/09/2026 nesse mesmo evento), o
    rótulo final também fica composto ("Master 1+2"). Isso é reportado como
    está: os conectores devolvem sempre a MESMA lista de atletas
    independente do filtro (ver comentário sobre cache em
    connectors/__init__.py::buscar_atletas) — não dá pra decidir "Master 1"
    vs "Master 2" aqui sem arriscar cache incorreto pra buscas futuras.
    Na prática, filtrar por ano de nascimento não encontra atletas nesses
    brackets combinados (o rótulo calculado não bate com o composto); busca
    por nome/equipe/gênero/faixa funciona normalmente."""
    partes = [p.strip() for p in categoria_bruta.split(";")]
    if len(partes) == 2:
        _genero, idade = partes
        rotulo = _IDADE_LABEL.get(idade.strip().lower(), idade.strip().title())
        return rotulo, "", ""
    if len(partes) == 4:
        _genero, idade, faixa, peso = partes
        rotulo = _IDADE_LABEL.get(idade.strip().lower(), idade.strip().title())
        return rotulo, faixa.title(), _traduzir_peso(peso)
    if len(partes) == 5:
        _genero, idade, nivel, faixa, peso = partes
        rotulo_base = _IDADE_LABEL.get(idade.strip().lower(), idade.strip().title())
        return f"{rotulo_base} {nivel.strip()}", faixa.title(), _traduzir_peso(peso)
    return categoria_bruta.strip().title(), "", ""


def buscar_atletas(evento_id, filtros):
    if not evento_id.startswith("martialmatch-"):
        return []
    id_numerico = evento_id.split("-", 1)[1]
    resp = get(f"{MARTIALMATCH_BASE}/api/events/{id_numerico}/starting-lists/public")
    dados = resp.json()

    atletas = []
    for categoria in dados.get("categories", []):
        genero_bruto = categoria["category"].split(";", 1)[0].strip().lower()
        categoria_idade, faixa, peso = _idade_e_peso_e_faixa(categoria["category"])
        for competidor in categoria.get("competitors", []):
            nome = f"{competidor.get('firstName', '')} {competidor.get('lastName', '')}".strip()
            atletas.append({
                "federacao": "FCOJJ",
                "nome": nome,
                "equipe": competidor.get("academy", ""),
                "categoria_idade": categoria_idade,
                "genero": genero_bruto,
                "peso": peso,
                "faixa": faixa,
                "pagamento": "Pendente" if competidor.get("isDisqualifiedForNoPayment") else "Confirmado",
            })
    return atletas
