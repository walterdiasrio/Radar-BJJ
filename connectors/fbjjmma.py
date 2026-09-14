"""Conector FBJJMMA (Federação Baiana de Jiu-Jitsu e MMA, fbjjmma.com.br).

listar_eventos() lê a home — a seção "#eventos" já vem pronta no HTML
puro (sem JavaScript nenhum, conferido ao vivo), com um card por evento
marcado por data-tipo (0=Jiu-Jitsu, 1=MuayThai, 2=Kickboxing, 3=Cursos)
— só entram os data-tipo="0": a federação também organiza outras
modalidades de luta debaixo do mesmo guarda-chuva, mas o Radar só busca
Jiu-Jitsu.

buscar_atletas() lê /evento/checagem/<uuid> — página também 100%
server-side (sem precisar de navegador), um bloco <div
class="card-checagem"> por grupo de categoria (cabeçalho tipo "Feminino
| INFANTIL A (8 E 9 ANOS) | BRANCA/COLORIDA"), cada um com uma
tabelinha Nome/Peso/Equipe. Faixas etárias batem exatamente com
connectors/idade.py::_CBJJE — a própria checagem já mostra o intervalo
de idade entre parênteses, conferido ao vivo (Infantil A 8-9, Master 3
41-45 anos etc. — idêntico). Peso vem com o nome da categoria E o
limite em kg junto (ex: "PLUMA 26 KG (26,0 KG)") — os números batem
exatamente com a tabela oficial CBJJ/FJJRio já cadastrada em
connectors/peso.py, inclusive pro Adulto Masculino (57.5/64/70/76/
82.3/88.3/94.3/100.5kg) — por isso entra em peso.py reaproveitando
_cbjj_fjjrio direto, com mais confiança que a suposição usada pra
FJJPE/FJJGO/FJJPR (lá só os NOMES batiam; aqui os KG batem exatamente).

status_inscricao() é melhor esforço: o prazo de inscrição é texto livre
por evento, escrito à mão na descrição — alguns dizem "as inscrições
serão encerradas definitivamente em <data>", outros só "encerram ao
atingir o limite de X atletas" (sem data nenhuma). Só extrai quando o
organizador escreveu no primeiro formato; os outros ficam "não
informado" em vez de tentar adivinhar uma data que não existe.
"""
import re
from datetime import date

from bs4 import BeautifulSoup

from . import datas as datas_mod
from .http import get

SITE = "https://fbjjmma.com.br"

# Nome da categoria de peso, sem o "ACIMA (DE) X KG" nem o limite em kg
# que vem junto no mesmo texto (ex: "PLUMA 26 KG (26,0 KG)" -> "PLUMA";
# "PESADÍSSIMO ACIMA DE 100.5KG (200,0 KG)" -> "PESADÍSSIMO"). Sem dígito
# na classe de propósito (diferente de _IDADE_RE) — aqui um número
# sempre marca o início do peso em kg, nunca faz parte do nome.
_PESO_RE = re.compile(r"^((?:(?!ACIMA)[A-ZÀ-ÜÇ]+\s*)+)")
# Nome da categoria de idade, sem o intervalo de anos entre parênteses
# (ex: "INFANTIL A (8 E 9 ANOS)" -> "INFANTIL A"; "MASTER 3 (41 A 45
# ANOS)" -> "MASTER 3" — precisa incluir dígito no meio do nome).
_IDADE_RE = re.compile(r"^([A-ZÀ-ÜÇ0-9 ]+)")

# Prazo de inscrição é texto livre por evento, escrito à mão na descrição
# — um evento diz "as inscrições serão encerradas definitivamente em 18
# de setembro de 2026, às 23h59"; outro só diz "encerram ao atingir o
# limite de X atletas", sem data nenhuma. Só dá pra extrair quando o
# organizador escreveu no primeiro formato — melhor esforço: os outros
# ficam "não informado" (mesmo fallback que outras federações sem essa
# informação estruturada já usam), em vez de tentar adivinhar uma data
# que não existe.
_PRAZO_RE = re.compile(r"encerradas?[^<]{0,60}em\s*<strong>(\d{1,2}) de (\w+) de (\d{4})", re.I)


def status_inscricao(evento):
    url = evento.get("url")
    if not url:
        return None, None
    try:
        html = get(url).text
    except Exception:
        return None, None

    m = _PRAZO_RE.search(html)
    if not m:
        return None, None
    prazo = datas_mod.extrair_data(f"{m.group(1)} de {m.group(2)} de {m.group(3)}")
    if not prazo:
        return None, None
    return date.today() <= prazo, prazo.isoformat()


def listar_eventos():
    resp = get(f"{SITE}/")
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select("#eventos-proximos .evento-card"):
        if card.get("data-tipo") != "0":
            continue
        link = card.select_one("a")
        if not link or not link.get("href"):
            continue
        m = re.search(r"/evento/([0-9a-f-]+)", link["href"])
        if not m:
            continue
        evento_id = m.group(1)

        titulos = card.select(".member-info-content h4")
        if len(titulos) < 2:
            continue
        nome = titulos[0].get_text(strip=True)
        data_texto = titulos[1].get_text(strip=True)
        local_el = card.select_one(".member-info-content span")
        local = local_el.get_text(strip=True) if local_el else ""

        eventos.append({
            "id": evento_id,
            "nome": nome,
            "url": f"{SITE}/evento/{evento_id}",
            "data": datas_mod.formatar(data_texto),
            "local": local,
        })
    return eventos


def buscar_atletas(evento_id, filtros):
    resp = get(f"{SITE}/evento/checagem/{evento_id}")
    soup = BeautifulSoup(resp.text, "lxml")

    resultados = []
    for card in soup.select(".card-checagem"):
        h3 = card.select_one("h3")
        if not h3:
            continue
        partes = [p.strip() for p in h3.get_text(strip=True).split("|")]
        if len(partes) != 3:
            continue
        genero_raw, idade_raw, faixa_raw = partes
        m_idade = _IDADE_RE.match(idade_raw)
        categoria_idade = (m_idade.group(1) if m_idade else idade_raw).strip().title()

        for tr in card.select("table tbody tr"):
            tds = tr.select("td")
            if len(tds) < 4:
                continue
            nome = tds[1].get_text(strip=True)
            peso_raw = tds[2].get_text(strip=True)
            equipe = tds[3].get_text(strip=True)
            m_peso = _PESO_RE.match(peso_raw)
            peso = (m_peso.group(1) if m_peso else peso_raw).strip().title()

            resultados.append({
                "federacao": "FBJJMMA",
                "nome": nome,
                "equipe": equipe,
                "categoria_idade": categoria_idade,
                "genero": genero_raw.strip().lower(),
                "peso": peso,
                "faixa": faixa_raw.strip().title(),
            })
    return resultados
