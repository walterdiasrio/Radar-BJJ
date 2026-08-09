"""Conector FPJJ (Federação Paulista de Jiu-Jitsu).

Duas frentes do mesmo grupo:
- fpjjcompetidor.com.br: site institucional, com a página de cada evento em
  `/campeonato/?codigo=N` (nome, data, local, texto "INSCRIÇÕES ABERTAS/ENCERRADAS").
- am.fpjjcompetidor.com.br: sistema de inscrições. A lista de inscritos de
  cada campeonato vem de um POST simples e público em
  `checagem_inscricoes.php` (campo `campeonato_id`), sem exigir login.
"""
import html as html_mod
import re
from bs4 import BeautifulSoup

from .http import get, post

SITE = "https://www.fpjjcompetidor.com.br"
AM = "https://am.fpjjcompetidor.com.br"


def listar_eventos():
    resp = get(f"{AM}/checagem_inscricoes.php")
    soup = BeautifulSoup(resp.text, "lxml")
    select = soup.find("select", {"name": "campeonato_id"})
    if not select:
        return []

    eventos = []
    for option in select.find_all("option"):
        codigo = (option.get("value") or "").strip()
        if not codigo:
            continue
        eventos.append({"id": codigo, "nome": option.get_text(strip=True)})

    for evento in eventos:
        evento.update(_detalhes_evento(evento["id"]))
    return eventos


def _detalhes_evento(codigo):
    try:
        resp = get(f"{SITE}/campeonato/", params={"codigo": codigo})
        html = resp.text

        titulo_el = BeautifulSoup(html, "lxml").select_one("h1")
        nome = titulo_el.get_text(strip=True) if titulo_el else ""

        m_data = re.search(r"Data:</strong>\s*([^<]+)", html)
        m_local = re.search(r"Local:</strong>\s*([^<]+)", html)
        data_texto = html_mod.unescape(m_data.group(1).strip()) if m_data else ""
        local_texto = html_mod.unescape(m_local.group(1).strip()) if m_local else ""

        inscricoes_abertas = None
        texto_upper = html.upper()
        if "INSCRIÇÕES ABERTAS" in texto_upper:
            inscricoes_abertas = True
        elif "INSCRIÇÕES ENCERRADAS" in texto_upper or "CAPACIDADE MÁXIMA" in texto_upper:
            inscricoes_abertas = False

        return {
            "nome": nome,
            "data": data_texto,
            "local": local_texto,
            "inscricoes_abertas": inscricoes_abertas,
        }
    except Exception:
        return {"data": "", "local": "", "inscricoes_abertas": None}


def buscar_atletas(evento_id, filtros):
    resp = post(f"{AM}/checagem_inscricoes.php", data={"campeonato_id": evento_id})
    soup = BeautifulSoup(resp.text, "lxml")

    resultados = []
    for item in soup.select(".registration-item"):
        card = item.select_one(".registration-card")
        if not card:
            continue

        nome_el = card.select_one(".athlete-name")
        nome = nome_el.get_text(strip=True) if nome_el else ""

        academia = ""
        for info in card.select(".info-item"):
            rotulo = info.select_one(".info-label")
            valor = info.select_one(".info-value")
            if rotulo and valor and "academia" in rotulo.get_text(strip=True).lower():
                academia = valor.get_text(strip=True)
                break

        classes_card = card.get("class", [])
        confirmado = "invalida" not in classes_card and not card.select_one(".status-badge")

        resultados.append({
            "federacao": "FPJJ",
            "nome": nome,
            "equipe": academia,
            "categoria_idade": (item.get("data-categoria") or "").strip(),
            "genero": (item.get("data-sexo") or "").strip(),
            "peso": (item.get("data-peso") or "").strip(),
            "faixa": (item.get("data-faixa") or "").strip(),
            "pagamento": "Confirmado" if confirmado else "Não confirmado",
        })
    return resultados
