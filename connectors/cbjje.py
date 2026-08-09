"""Conector CBJJE (cbjje.com.br).

As inscrições da CBJJE rodam na plataforma meucombate.com.br. O site é uma
SPA (WeWeb) mas os dados vêm de uma API JSON pública e sem bloqueio por
trás dela (Xano): `https://xnso-sxc0-yiuf.b2.xano.io/api:uxixvP46`.

- organizations_id da CBJJE = 16 (resolvido via /organization/me?organizations_slug=cbjje).
- Lista de eventos: GET /events?organizations_id=16&page=N
- Atletas de um evento: GET /event/athletes?event_id=N&page=N — paginado,
  cada item já é uma categoria completa (idade/peso/faixa/gênero) com a
  lista de atletas dentro dela.
"""
from datetime import datetime, timezone

from .http import get

API = "https://xnso-sxc0-yiuf.b2.xano.io/api:uxixvP46"
ORGANIZATIONS_ID = 16

GENERO_PT = {"masc": "Masculino", "fem": "Feminino"}


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
            eventos.append({
                "id": str(item["id"]),
                "nome": nome,
                "data": data_texto,
                "local": local,
                "inscricoes_abertas": bool(item.get("events_inscriptions_opened")),
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
