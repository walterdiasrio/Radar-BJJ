"""Conector CBJJE (cbjje.com.br).

As inscrições da CBJJE rodam na plataforma meucombate.com.br. O site é uma
SPA (WeWeb) mas os dados vêm de uma API JSON pública e sem bloqueio por
trás dela (Xano): `https://xnso-sxc0-yiuf.b2.xano.io/api:uxixvP46`.

- organizations_id da CBJJE = 16 (resolvido via /organization/me?organizations_slug=cbjje).
- Lista de eventos: GET /events?organizations_id=16&page=N
- Atletas de um evento: GET /event/athletes?event_id=N&page=N — paginado,
  cada item já é uma categoria completa (idade/peso/faixa/gênero) com a
  lista de atletas dentro dela.

Prazo de inscrição (pedido do usuário 11/09/2026: "está em Inscrições e
lotes, data final do último lote"): a página do evento em si (endpoint
"informations") não traz isso — é texto livre dentro de uma aba de
conteúdo (CMS por evento). Achado via rede do browser (a chamada real não
aparece com hostname "xano.io" e sim pelo domínio próprio
"api.meucombate.com.br", mesmo backend): primeiro GET
/event/{id}/information/tabs?event_id=N lista as abas (id + título); a
aba com título "INSCRIÇÃO E LOTE" tem id DIFERENTE por evento (não dá pra
fixar), por isso é achada pelo título. O conteúdo de TODAS as abas (já
com o id de cada uma) vem de uma vez só em
GET /event/{id}/information/tabs/data?events_id=N — "{id}" é literal na
URL (bug do próprio front-end da MeuCombate: não interpola o path param),
mas funciona porque o endpoint na prática só olha pra query "events_id".

O texto de cada lote não segue um formato único (é CMS livre por
organizador/evento, varia até dentro do mesmo evento) — visto ao vivo:
"LOTE 6: Data Fim: 15/09/2026 às 23h59", "LOTE 4</h3><em>(Até 23/09/2026
às 18h)</em>", "Lote 2 Até 12/10 às 18h" (SEM ano) e "LOTE 3; Data Fim:
30/11/26" (ano com 2 dígitos). Em vez de tentar casar um template exato,
pega a primeira data logo após cada ocorrência da palavra "LOTE" (até 200
caracteres à frente, ano opcional/2 ou 4 dígitos) e usa a MAIOR
encontrada — assume que os lotes sempre aparecem em ordem cronológica
crescente, então a última data é o prazo final. Ancorar em "LOTE" evita
pegar datas de outras partes do texto sem relação (ex: numa nota de
suporte ao atleta) que por coincidência batem com a data de um lote —
conferido ao vivo em vários eventos reais que isso não acontece dentro da
janela de 200 caracteres. Data sem ano usa a mesma regra de inferência de
connectors/datas.py::_ano_inferido (ano corrente, só avança pro seguinte
se a data já ficou >30 dias pra trás) — duplicada aqui em vez de
importada por ser função privada do módulo (mesma escolha já feita em
connectors/cbjjc.py para o mesmo problema).
"""
import re
from datetime import date, datetime, timedelta, timezone

from .http import get

API = "https://xnso-sxc0-yiuf.b2.xano.io/api:uxixvP46"
ORGANIZATIONS_ID = 16

GENERO_PT = {"masc": "Masculino", "fem": "Feminino"}

_LOTE_DATA_RE = re.compile(r"LOTE.{0,200}?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", re.I | re.S)


def _inferir_ano(mes, dia):
    hoje = date.today()
    ano = hoje.year
    try:
        candidata = date(ano, mes, dia)
    except ValueError:
        candidata = date(ano, mes, 1)
    if candidata < hoje - timedelta(days=30):
        ano += 1
    return ano


def _prazo_inscricao(evento_id):
    try:
        resp = get(f"{API}/event/%7Bid%7D/information/tabs/data", params={"events_id": evento_id})
        abas = resp.json()
    except Exception:
        return None

    datas = []
    for aba in abas:
        titulo = (aba.get("title") or "").lower()
        if "inscri" not in titulo or "lote" not in titulo:
            continue
        for m in _LOTE_DATA_RE.finditer(aba.get("body") or ""):
            dia, mes, ano_texto = int(m.group(1)), int(m.group(2)), m.group(3)
            if ano_texto is None:
                ano = _inferir_ano(mes, dia)
            elif len(ano_texto) == 2:
                ano = 2000 + int(ano_texto)
            else:
                ano = int(ano_texto)
            try:
                datas.append(date(ano, mes, dia))
            except ValueError:
                continue
    return max(datas) if datas else None


def listar_eventos():
    eventos = []
    pagina = 1
    while True:
        resp = get(f"{API}/events", params={"organizations_id": ORGANIZATIONS_ID, "page": pagina})
        dados = resp.json()
        for item in dados.get("items", []):
            data_texto = ""
            epoch_ini = item.get("events_first_day")
            epoch_fim = item.get("events_days_last_day") or epoch_ini
            if epoch_ini:
                ini = datetime.fromtimestamp(epoch_ini / 1000, tz=timezone.utc).strftime("%d/%m/%Y")
                fim = datetime.fromtimestamp(epoch_fim / 1000, tz=timezone.utc).strftime("%d/%m/%Y")
                data_texto = ini if fim == ini else f"{ini} a {fim}"
            local = ", ".join(p for p in (item.get("cities_name"), item.get("states_acronym")) if p)
            nome = item.get("name", "")
            if local:
                nome = f"{nome} — {local}"
            prazo = _prazo_inscricao(item["id"])
            eventos.append({
                "id": str(item["id"]),
                "nome": nome,
                "url": f"https://www.meucombate.com.br/cbjje/evento/{item['id']}/informacoes/",
                "data": data_texto,
                "local": local,
                "inscricoes_abertas": bool(item.get("events_inscriptions_opened")),
                "prazo_inscricao": prazo.isoformat() if prazo else None,
            })
        if not dados.get("nextPage"):
            break
        pagina = dados["nextPage"]
    return eventos


def buscar_atletas(evento_id, filtros):
    resultados = []
    pagina = 1
    while True:
        resp = get(f"{API}/event/athletes", params={"event_id": evento_id, "page": pagina})
        dados = resp.json()
        if "items" not in dados:
            break

        for categoria in dados["items"]:
            genero = GENERO_PT.get(categoria.get("gender", ""), categoria.get("gender", ""))
            faixa = " / ".join(b.get("belts_name", "") for b in categoria.get("belts", []))
            idade_info = (categoria.get("_categories_ages") or [{}])[0]
            nome_idade = idade_info.get("ages_name", "")
            de_ate = ""
            if idade_info.get("from_age") is not None:
                de_ate = f" ({idade_info['from_age']} a {idade_info['to_age']} anos)"
            categoria_idade = f"{nome_idade}{de_ate}"

            peso_nome = categoria.get("weight_name", "")
            peso_max = categoria.get("to_weight")
            peso = f"{peso_nome} (até {peso_max}kg)" if peso_max else peso_nome

            for atleta in categoria.get("_athletes_of_events_categories", []):
                resultados.append({
                    "federacao": "CBJJE",
                    "nome": atleta.get("user_name", ""),
                    "equipe": atleta.get("academies_name") or atleta.get("teams_name") or "",
                    "categoria_idade": categoria_idade,
                    "genero": genero,
                    "peso": peso,
                    "faixa": faixa,
                })

        if not dados.get("nextPage"):
            break
        pagina = dados["nextPage"]

    return resultados
