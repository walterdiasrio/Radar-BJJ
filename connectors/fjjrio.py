"""Conector FJJRio (fjjrio.com.br).

Fonte: endpoint JSON público `app/paginas/listaDeInscricoes.php`, usado pelo
DataTable de "Checagem Pública" de cada evento. Não exige login.
"""
import re
from bs4 import BeautifulSoup

from . import datas as datas_mod
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
    """(inscricoes_abertas, prazo_inscricao) — a página do evento traz uma
    lista "Início/Término da Inscrição/Data limite para pagamento/edição"
    (ver <li><b>Término da Inscrição</b></li>) — usamos o "Término", que é
    o prazo final de verdade (a edição segue aberta um pouco depois, mas
    sem poder mais competir se não tiver se inscrito antes).

    Achado ao vivo em 11/09/2026 (REI DO RIO 2026 e ROLLS GRACIE 2026,
    ambos com "Início da Inscrição" ainda no futuro): existe uma TERCEIRA
    frase de status além de aberta/encerrada — "Em breve as inscrições
    serão abertas." — pro período em que o evento já está no site mas a
    inscrição ainda nem começou. Sem esse caso, `aberta` ficava None
    (nem aberta nem encerrada) só porque nenhuma das duas frases batia."""
    url = evento.get("url")
    if not url:
        return None, None
    resp = get(url)
    texto = resp.text.lower()

    aberta = None
    if "inscrições para esse evento estão abertas" in texto:
        aberta = True
    elif "inscrições para esse evento estão" in texto and "encerrada" in texto:
        aberta = False
    elif "as inscrições serão abertas" in texto:
        aberta = False

    prazo = None
    soup = BeautifulSoup(resp.text, "lxml")
    rotulo = soup.find("b", string=lambda s: s and "Término da Inscrição" in s)
    if rotulo and rotulo.parent and rotulo.parent.parent:
        texto_data = rotulo.parent.parent.get_text(" ", strip=True).replace("Término da Inscrição", "")
        data_obj = datas_mod.extrair_data(texto_data)
        prazo = data_obj.isoformat() if data_obj else None

    return aberta, prazo


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
