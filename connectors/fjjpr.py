"""Conector FJJPR (Federação de Jiu-Jitsu do Paraná).

listar_eventos() lê o calendário público em fjjpr.com/calendario.php —
cada card (.fjjpr-card) já traz nome, data (sem ano) e local ("Cidade-PR",
sem tratamento extra necessário — connectors/__init__.py::_simplifica_local
já entende esse formato) prontos, além do id numérico usado tanto na
página de detalhe (fjjpr.com/ver-campeonato.php?id=N) quanto direto na
busca de atletas (mesmo id, conferido ao vivo). Eventos sem link "Saber
mais" (mais distantes no calendário, inscrição ainda não aberta) não têm
esse id e são ignorados — não tem como buscar atleta neles mesmo.

A data do card não tem ano ("14 E 15 DE MAR") — quando o próprio nome do
evento já traz o ano ("2ª Etapa 2026", maioria dos casos), usamos esse
ano explícito em vez de deixar connectors/datas.py inferir: o calendário
lista o ANO INTEIRO de uma vez (inclusive etapas que já aconteceram meses
atrás), e a inferência (pensada pra "data solta, assume a mais próxima no
futuro") erraria essas pro ano seguinte.

buscar_atletas() lê app.fjjpr.com/lista_por_grupos.php?id=<id> — uma
página só com TODOS os atletas de TODAS as categorias já agrupados em
acordeões (o parâmetro nome_comp da URL é só cosmético pro título da
página, confirmado ao vivo: mesmo resultado com ou sem ele). Cada grupo
tem um "Categoria: X • Sexo: Y • Peso: Z • Faixa: W" (span .subline) e
uma tabelinha Nome/Academia.

Nomes de categoria de idade vêm sem acento e "Pre Mirim" sem hífen —
normalizados aqui pros mesmos rótulos já usados por connectors/idade.py::
_CBJJE (mesmas faixas etárias, conferido ao vivo contra a checagem real:
Pré-Mirim 4-5, Mirim 6-7, Infantil A/B 8-9/10-11, Infanto Juvenil A/B
12-13/14-15, Juvenil 16-17, Adulto, Master 1-6 — idêntico). Peso também
sem acento ("Medio", "Pesadissimo") — normalizado pro vocabulário padrão
(Médio, Meio Pesado, Super Pesado, Pesadíssimo) só por consistência
visual; não temos tabela de peso→limite em kg oficial da FJJPR, então
essa federação não entra em connectors/peso.py — o calculador automático
de peso simplesmente não sugere nada aqui, sem quebrar nada (ver
categoria_peso_para, que já degrada bem pra federação desconhecida).

Categorias infantis/adulto aparecem misturadas no mesmo evento, com
nomes de evento genéricos ("1ª Etapa 2026", sem palavra kids/adulto no
nome) — por isso "fjjpr" entra em connectors/__init__.py::
_FEDERACOES_SEM_SEPARACAO_POR_NOME (mesmo caso já resolvido pra
FJJGO/FCOJJ), senão o filtro "Kids" nunca acharia nada aqui."""
import re

from bs4 import BeautifulSoup

from . import datas as datas_mod
from .http import get

SITE = "https://fjjpr.com"
APP = "https://app.fjjpr.com"

_IDADE_NORMALIZADA = {
    "pre mirim": "Pré-Mirim",
    "mirim": "Mirim",
    "infantil a": "Infantil A",
    "infantil b": "Infantil B",
    "infanto juvenil a": "Infanto Juvenil A",
    "infanto juvenil b": "Infanto Juvenil B",
    "juvenil": "Juvenil",
    "adulto": "Adulto",
    "master 1": "Master 1",
    "master 2": "Master 2",
    "master 3": "Master 3",
    "master 4": "Master 4",
    "master 5": "Master 5",
    "master 6": "Master 6",
}

_PESO_NORMALIZADO = {
    "galo": "Galo",
    "pluma": "Pluma",
    "pena": "Pena",
    "leve": "Leve",
    "medio": "Médio",
    "meio pesado": "Meio Pesado",
    "pesado": "Pesado",
    "super pesado": "Super Pesado",
    "pesadissimo": "Pesadíssimo",
}


def _normalizar(valor, tabela):
    return tabela.get(valor.strip().lower(), valor.strip())


def _campo(rotulo, texto):
    m = re.search(rf"{rotulo}:\s*([^•]+)", texto)
    return m.group(1).strip() if m else ""


def listar_eventos():
    resp = get(f"{SITE}/calendario.php")
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select(".fjjpr-card"):
        link = card.select_one('a[href*="ver-campeonato.php"]')
        if not link:
            continue
        m = re.search(r"id=(\d+)", link["href"])
        if not m:
            continue
        evento_id = m.group(1)

        titulo_el = card.select_one(".fjjpr-card__title")
        nome = titulo_el.get_text(strip=True) if titulo_el else ""
        if not nome:
            continue

        pill = card.select_one(".fjjpr-pill")
        data_bruta = pill.get_text(strip=True) if pill else ""
        m_ano = re.search(r"\b(20\d{2})\b", nome)
        data_texto = f"{data_bruta} {m_ano.group(1)}" if m_ano else data_bruta

        metas = card.select(".fjjpr-card__meta .fjjpr-meta-row")
        local = metas[0].get_text(" ", strip=True) if metas else ""

        eventos.append({
            "id": evento_id,
            "nome": nome,
            "url": f"{SITE}/ver-campeonato.php?id={evento_id}",
            "data": datas_mod.formatar(data_texto),
            "local": local,
        })
    return eventos


def buscar_atletas(evento_id, filtros):
    resp = get(f"{APP}/lista_por_grupos.php", params={"id": evento_id})
    soup = BeautifulSoup(resp.text, "lxml")

    resultados = []
    for item in soup.select(".accordion-item"):
        subline = item.select_one(".subline")
        if not subline:
            continue
        texto = subline.get_text(" ", strip=True)

        categoria_idade = _normalizar(_campo("Categoria", texto), _IDADE_NORMALIZADA)
        genero = _campo("Sexo", texto)
        peso = _normalizar(_campo("Peso", texto), _PESO_NORMALIZADO)
        faixa = _campo("Faixa", texto)

        for tr in item.select("table tbody tr"):
            tds = tr.select("td")
            if len(tds) < 2:
                continue
            resultados.append({
                "federacao": "FJJPR",
                "nome": tds[0].get_text(strip=True),
                "equipe": tds[1].get_text(strip=True),
                "categoria_idade": categoria_idade,
                "genero": genero,
                "peso": peso,
                "faixa": faixa,
            })
    return resultados
