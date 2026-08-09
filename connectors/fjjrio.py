"""Conector FJJRio (fjjrio.com.br).

Fonte: endpoint JSON público `app/paginas/listaDeInscricoes.php`, usado pelo
DataTable de "Checagem Pública" de cada evento. Não exige login.
"""
import re
from bs4 import BeautifulSoup

from .http import get, post

BASE = "https://fjjrio.com.br"


def listar_eventos():
    resp = get(BASE)
    soup = BeautifulSoup(resp.text, "lxml")
    eventos = []
    seen = set()
    for a in soup.select("a[href^='evento.php?id=']"):
        href = a.get("href", "")
        if href in seen:
            continue
        titulo = a.get_text(strip=True)
        if not titulo:
            continue
        cartao = a.find_parent(class_="entry3") or a.find_parent(class_="event-card") or a.parent.parent
        rotulo = cartao.get_text(" ", strip=True) if cartao else ""
        if "curso" in rotulo.lower().split(titulo.lower())[0][-40:]:
            continue
        seen.add(href)
        base64_id = href.split("id=")[-1]
        data_el = cartao.select_one(".post-meta") if cartao else None
        local_el = cartao.select_one(".post-meta.mb-3") if cartao else None
        eventos.append({
            "id": base64_id,
            "nome": titulo,
            "url": f"{BASE}/{href}",
            "data": data_el.get_text(strip=True) if data_el else "",
            "local": local_el.get_text(strip=True) if local_el else "",
        })
    return eventos


def status_inscricao(evento):
    """True = inscrições abertas, False = encerradas, None = não deu pra saber."""
    url = evento.get("url")
    if not url:
        return None
    resp = get(url)
    texto = resp.text.lower()
    if "inscrições para esse evento estão abertas" in texto:
        return True
    if "inscrições para esse evento estão" in texto and "encerrada" in texto:
        return False
    return None


def _resolver_id_evento(base64_id):
    """A checagem pública usa um id numérico interno (id_evento), diferente do
    id em base64 da URL. Ele vem embutido no <script> da página de checagem."""
    resp = get(f"{BASE}/checagem.php?id={base64_id}")
    m = re.search(r"d\.id_evento\s*=\s*(\d+)", resp.text)
    if not m:
        return None
    return m.group(1)


def _datatables_payload(id_evento, filtros):
    colunas = ["id", "nome", "academia", "idade", "sexo", "peso", "faixa"]
    payload = {"draw": "1", "start": "0", "length": "100000"}
    for i, nome_col in enumerate(colunas):
        payload[f"columns[{i}][data]"] = str(i)
        payload[f"columns[{i}][name]"] = ""
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "true"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"
    payload["order[0][column]"] = "0"
    payload["order[0][dir]"] = "asc"
    payload["search[value]"] = ""
    payload["search[regex]"] = "false"
    payload["id_evento"] = id_evento
    payload["nome"] = filtros.get("nome", "") or ""
    payload["academia"] = "0"
    payload["idade"] = "0"
    payload["sexo"] = "0"
    payload["peso"] = "0"
    payload["faixa"] = "0"
    payload["chave"] = "0"
    return payload


def buscar_atletas(evento_id, filtros):
    id_evento = _resolver_id_evento(evento_id)
    if not id_evento:
        return []

    resp = post(
        f"{BASE}/app/paginas/listaDeInscricoes.php",
        data=_datatables_payload(id_evento, filtros),
    )
    try:
        dados = resp.json()
    except ValueError:
        return []

    resultados = []
    for linha in dados.get("data", []):
        if len(linha) < 7:
            continue
        _id, nome, academia, categoria_html, sexo, peso, faixa = linha[:7]
        status_pagamento = linha[7] if len(linha) > 7 else ""
        categoria_idade = re.sub(r"<[^>]+>", "", categoria_html or "").strip()
        categoria_idade = re.sub(r"\s+", " ", categoria_idade)
        resultados.append({
            "federacao": "FJJRio",
            "nome": (nome or "").strip(),
            "equipe": (academia or "").strip(),
            "categoria_idade": categoria_idade,
            "genero": (sexo or "").strip(),
            "peso": (peso or "").strip(),
            "faixa": (faixa or "").strip(),
            "pagamento": "Pago" if (status_pagamento or "").strip().upper() == "PAGO" else "Não pago",
        })
    return resultados
