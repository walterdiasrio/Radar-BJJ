"""Conector Meu Combate (meucombate.com.br) — federação "avulsa" própria,
igual ao SouCompetidor: uma plataforma que hospeda vários organizadores
independentes, não uma federação só.

O site é uma SPA (Vue/WeWeb) sem nada de útil no HTML puro (confirmado ao
vivo: o HTML bruto não tem nenhum evento, tudo é montado por JavaScript
depois) — mas por trás roda uma API REST pública, sem autenticação,
descoberta inspecionando as chamadas reais que o navegador faz:

- listar_eventos() usa GET /api:0VrKOQzz/events/events?page=N&filter_
  status_events=active — é o catálogo de verdade (14 eventos ativos no
  total em 14/09/2026, sem paginação de verdade porque já cabe tudo numa
  página: itemsReceived=14, nextPage=null). ATENÇÃO: existe um segundo
  endpoint parecido, /api:0VrKOQzz/home/events, que parece paginado
  (aceita ?page=N) mas SEMPRE devolve os mesmos 8 itens não importa a
  página pedida (nextPage sempre volta "2" — looping infinito se você
  seguir o nextPage cegamente, foi assim que essa investigação travou a
  primeira vez). Esse é só a vitrine de destaques da home, não o catálogo
  — usar sempre /events/events.
- buscar_atletas() usa GET /api:uxixvP46/event/athletes?event_id=N&page=N
  (API diferente da de listar_eventos — "api:uxixvP46", não "api:0VrKOQzz"
  — confirmado ao vivo, a outra dá 404) — devolve grupos de categoria
  (peso/gênero/gi-nogi/faixa/faixa etária) já com a lista de atletas
  daquele grupo dentro (_athletes_of_events_categories).

Maioria dos eventos ativos (11 de 14, em 14/09/2026) são organizados pela
própria CBJJE (organizations_slug="cbjje") — que já tem conector próprio
(connectors/cbjje.py, lendo o site oficial da CBJJE) — por isso
listar_eventos() filtra esse slug fora, senão duplicaria a competição na
busca (a mesma competição apareceria em "CBJJE" e em "Meu Combate" ao
mesmo tempo). "fjje-mt" (uma etapa estadual de Mato Grosso) fica DENTRO —
parece uma federação regional própria por trás (mesmo padrão de
FJJEMG/FJJPR/FJJPA, já tratadas como entidades separadas da CBJJ/CBJJE
nacional aqui no Radar), não uma duplicata confirmada da CBJJE.

Cada organizador no Meu Combate define seu próprio vocabulário de
categoria de idade (um usa "PRE-MIRIM"/"MIRIM"/"INFANTIL A"..., outro usa
"FESTIVAL (4 a 9 anos)"/"ADULTO (18 a 29 anos)"... — nomes bem diferentes
pra idades parecidas) — diferente das federações "de verdade" daqui, que
têm uma tabela oficial e fixa. Por isso esse conector NÃO tenta encaixar
a categoria em nenhuma tabela de connectors/idade.py — só devolve o
rótulo que o próprio organizador publicou (Title Case), sem cálculo de
categoria por ano de nascimento (igual à ADCC/AJP quando não há uma
competição específica escolhida)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from . import datas as datas_mod
from .http import get

API_EVENTOS = "https://api.meucombate.com.br/api:0VrKOQzz"
API_ATLETAS = "https://api.meucombate.com.br/api:uxixvP46"

# organizations_slug já cobertos por conector próprio — ver docstring.
_ORGANIZACOES_EXCLUIDAS = {"cbjje"}

_MAX_PAGINAS = 20


def _data_do_evento(item):
    inicio_ms = item.get("events_first_day")
    if not inicio_ms:
        return ""
    fuso = ZoneInfo(item.get("timezones") or "America/Sao_Paulo")
    inicio = datetime.fromtimestamp(inicio_ms / 1000, tz=fuso).date()
    fim_ms = item.get("events_last_day") or inicio_ms
    fim = datetime.fromtimestamp(fim_ms / 1000, tz=fuso).date()
    texto = inicio.strftime("%d/%m/%Y")
    if fim != inicio:
        texto += f" a {fim.strftime('%d/%m/%Y')}"
    return datas_mod.formatar(texto)


def listar_eventos():
    eventos = []
    pagina = 1
    while pagina <= _MAX_PAGINAS:
        resp = get(f"{API_EVENTOS}/events/events", params={"page": pagina, "filter_status_events": "active"})
        dados = resp.json()
        for item in dados.get("items", []):
            if item.get("organizations_slug") in _ORGANIZACOES_EXCLUIDAS:
                continue
            nome = (item.get("events_name") or "").strip()
            if not nome:
                continue
            cidade = (item.get("cities_name") or "").strip()
            uf = (item.get("states_acronym") or "").strip()
            local = f"{cidade}, {uf}" if cidade and uf else (cidade or uf)
            eventos.append({
                "id": str(item["events_id"]),
                "nome": nome,
                "url": f"https://www.meucombate.com.br/{item.get('organizations_slug', '')}/evento/{item['events_id']}/informacoes/",
                "data": _data_do_evento(item),
                "local": local,
            })
        if not dados.get("nextPage"):
            break
        pagina = dados["nextPage"]
    return eventos


_GENERO_PT = {"masc": "masculino", "fem": "feminino"}


def _titulo_pt(texto):
    """Como str.title(), mas mantém "e" minúsculo (conjunção) — pras
    faixas combinadas (ex: "Cinza e Amarela")."""
    saida = []
    for palavra in texto.strip().split():
        saida.append("e" if palavra.lower() == "e" else palavra.capitalize())
    return " ".join(saida)


def _nome_faixas(belts):
    nomes = [b["belts_name"] for b in belts if b.get("belts_name")]
    if not nomes:
        return ""
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def buscar_atletas(evento_id, filtros):
    resultados = []
    pagina = 1
    while pagina <= _MAX_PAGINAS:
        resp = get(f"{API_ATLETAS}/event/athletes", params={"event_id": evento_id, "page": pagina, "search_athletes_id": ""})
        try:
            dados = resp.json()
        except ValueError:
            break
        itens = dados.get("items", [])
        if not itens:
            break

        for grupo in itens:
            idades = grupo.get("_categories_ages") or []
            categoria_idade = _titulo_pt(idades[0]["ages_name"]) if idades else ""
            genero = _GENERO_PT.get(grupo.get("gender"), grupo.get("gender") or "")
            peso = _titulo_pt(grupo.get("weight_name") or "")
            faixa = _nome_faixas(grupo.get("belts") or [])

            for atleta in grupo.get("_athletes_of_events_categories") or []:
                nome = (atleta.get("user_name") or "").strip()
                if not nome:
                    continue
                resultados.append({
                    "federacao": "MEUCOMBATE",
                    "nome": nome,
                    "equipe": (atleta.get("academias_name") or atleta.get("academies_name") or "").strip(),
                    "categoria_idade": categoria_idade,
                    "genero": genero,
                    "peso": peso,
                    "faixa": faixa,
                })

        if not dados.get("nextPage"):
            break
        pagina = dados["nextPage"]
    return resultados
