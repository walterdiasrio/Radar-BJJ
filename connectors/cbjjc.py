"""Conector CBJJC (cbjjc.com.br) — inscrições rodam na plataforma iLutas
(ilutas.com.br), que hospeda campeonatos de vários organizadores diferentes,
não só a CBJJC.

listar_eventos() lê a home do site institucional (cbjjc.com.br/campeonatos)
só pra descobrir OS IDs dos eventos (procurando links pro formato
".../Evento/Index.php?event=<id>") — o site em si é montado num construtor
de site (GoDaddy Website Builder), sem uma listagem estruturada confiável, e
mistura campeonatos com seminários/cursos que não têm checagem de atletas.
Nome/data/local de cada evento (e o filtro pra manter só campeonato de
verdade, via o rótulo "Campeonato de Jiu-Jitsu") vêm de volta da própria
página do evento no iLutas — essa sim estruturada e igual pra qualquer
organizador na plataforma.

buscar_atletas() lê a checagem pública (.../checagem/list-all/?event=...),
tudo numa página só, sem paginação nem bloqueio. Um mesmo atleta pode ter
mais de uma inscrição na mesma checagem (peso Gi, absoluto Gi, peso No-Gi,
absoluto No-Gi) — cada uma vira uma entrada separada aqui, igual o resto do
site trata cada inscrição. Só entram as divisões DE KIMONO (peso e absoluto
Gi): "No-Gi" fica de fora porque a CBJJC, como as outras federações
tradicionais do site, é tratada como sempre-Gi pro cálculo de categoria de
peso (ver evento_sem_kimono em connectors/__init__.py) — misturar as duas
classificaria peso errado pros filtros de busca.
"""
import re

from bs4 import BeautifulSoup

from .http import get

SITE = "https://cbjjc.com.br"
ILUTAS = "https://www.ilutas.com.br"

_EVENTO_ID_RE = re.compile(r"ilutas\.com\.br/Evento/Index\.php\?event=([a-f0-9]+)", re.I)


def _ids_dos_eventos():
    resp = get(f"{SITE}/campeonatos")
    return list(dict.fromkeys(_EVENTO_ID_RE.findall(resp.text)))


def _info_evento(evento_id_bruto):
    resp = get(f"{ILUTAS}/Evento/Index.php", params={"event": evento_id_bruto})
    soup = BeautifulSoup(resp.text, "lxml")

    tipo = soup.select_one("h2")
    if not tipo or "campeonato" not in tipo.get_text(strip=True).lower():
        return None  # seminário, curso/workshop etc. — não é competição

    item = soup.select_one(".evento-item")
    nome_el = item.select_one("h5") if item else None
    nome = nome_el.get_text(strip=True) if nome_el else ""
    if not nome:
        meta = soup.find("meta", attrs={"property": "og:title"})
        nome = (meta.get("content") or "").strip() if meta else ""
    if not nome:
        return None

    data = local = ""
    info_p = item.select_one(".evento-info p") if item else None
    if info_p:
        partes = [p.strip() for p in info_p.get_text("|", strip=True).split("|") if p.strip()]
        data = partes[0] if partes else ""
        local = partes[1] if len(partes) > 1 else ""

    return {"id": f"cbjjc-{evento_id_bruto}", "nome": nome, "data": data, "local": local}


def listar_eventos():
    eventos = []
    for evento_id_bruto in _ids_dos_eventos():
        try:
            info = _info_evento(evento_id_bruto)
        except Exception:
            continue
        if info:
            eventos.append(info)
    return eventos


_PREFIXOS_CATEGORIA = ("Peso GI - ", "Peso NO-GI - ", "Abs GI - ", "Abs NO-GI - ")


def _linhas_checagem(evento_id_bruto):
    resp = get(f"{ILUTAS}/checagem/list-all/", params={"event": evento_id_bruto})
    soup = BeautifulSoup(resp.text, "lxml")

    linhas = []
    for tr in soup.select("div.tabela-checagem table tr"):
        container = tr.select_one("div.col-lg-10")
        if not container:
            continue
        nome_el = container.find("b")
        if not nome_el:
            continue
        nome = nome_el.get_text(strip=True)

        equipe = ""
        equipe_div = container.select_one("div[style*='color:#333333']")
        if equipe_div:
            clone = BeautifulSoup(str(equipe_div), "lxml")
            for tag in clone.find_all(["a", "u"]):
                tag.extract()
            partes = [t.strip() for t in clone.get_text("\n").split("\n") if t.strip()]
            equipe = partes[0] if partes else ""

        for linha_texto in container.get_text("\n").split("\n"):
            linha_texto = linha_texto.strip()
            if linha_texto.startswith(_PREFIXOS_CATEGORIA):
                linhas.append({"nome": nome, "equipe": equipe, "categoria": linha_texto})

    return linhas


def _genero_normalizado(genero_bruto):
    # A própria checagem do CBJJC tem categorias com "Feminina" em vez de
    # "Feminino" (typo na fonte) — sem isso, esses atletas somem do filtro
    # de busca por gênero (que compara por substring exata do termo).
    g = genero_bruto.strip().lower()
    if g.startswith("femin"):
        return "feminino"
    if g.startswith("mascul"):
        return "masculino"
    return g


def _monta_atleta(linha):
    if "nogi" in linha["categoria"].lower().replace("-", "").replace(" ", ""):
        return None

    if linha["categoria"].startswith("Abs GI - "):
        partes = [p.strip() for p in linha["categoria"][len("Abs GI - "):].split(" - ")]
        if len(partes) != 3:
            return None
        idade, faixa, genero = partes
        peso = "Absoluto"
    elif linha["categoria"].startswith("Peso GI - "):
        partes = [p.strip() for p in linha["categoria"][len("Peso GI - "):].split(" - ")]
        if len(partes) != 4:
            return None
        idade, faixa, peso, genero = partes
    else:
        return None

    return {
        "federacao": "CBJJC",
        "nome": linha["nome"],
        "equipe": linha["equipe"],
        "categoria_idade": idade,
        "genero": _genero_normalizado(genero),
        "peso": peso,
        "faixa": faixa,
    }


def buscar_atletas(evento_id, filtros):
    evento_id_bruto = evento_id.split("-", 1)[1] if evento_id.startswith("cbjjc-") else evento_id
    atletas = []
    for linha in _linhas_checagem(evento_id_bruto):
        atleta = _monta_atleta(linha)
        if atleta:
            atletas.append(atleta)
    return atletas
