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

inscricoes_abertas: a página do evento no iLutas nunca expõe um indicador
explícito de aberta/encerrada (nem texto tipo "inscrições encerradas" nem
classe CSS — conferido ao vivo em 11/09/2026 varrendo o texto inteiro da
página) — só a lista de lotes com data. Por isso é inferida a partir do
prazo (mesma regra do fallback usado em fjjemg.py): aberta se ainda não
passou do prazo do último lote, ou True (assume aberta) se não deu pra
achar prazo nenhum.

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
from datetime import date, timedelta

from bs4 import BeautifulSoup

from .http import get

SITE = "https://cbjjc.com.br"
ILUTAS = "https://www.ilutas.com.br"

_EVENTO_ID_RE = re.compile(r"ilutas\.com\.br/Evento/Index\.php\?event=([a-f0-9]+)", re.I)
_LOTE_DATA_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")


def _inferir_ano(mes, dia):
    """As datas de lote da iLutas vêm sem ano ("26/08") — mesma regra do
    fallback de connectors/datas.py::extrair_data: assume o ano corrente,
    só avança pro seguinte se a data já ficou bem pra trás (30 dias de
    folga, pra não pular um ano por causa de virada de mês)."""
    hoje = date.today()
    ano = hoje.year
    try:
        candidata = date(ano, mes, dia)
    except ValueError:
        candidata = date(ano, mes, 1)
    if candidata < hoje - timedelta(days=30):
        ano += 1
    return ano


def _prazo_inscricao(soup):
    """A página do evento pode ter mais de uma tabela de preço (ex: uma só
    GI, outra GI+NOGI) — cada uma com seus próprios "1°/2°/3° Lote até
    <strong>DD/MM ou "final"</strong>" (ver .evento-item .lote, cada
    <span> desses). "até final" (sem data — o lote fica aberto até o fim
    das inscrições, sem um corte fixo à parte) é comum quando a organização
    não quer travar um preço final; ignoramos esses e ficamos com o maior
    prazo REAL encontrado em qualquer uma das tabelas da página — na
    prática, o prazo mais tardio já visto costuma ser o prazo final de
    verdade, mesmo quando outra tabela da mesma página não fecha uma data."""
    # Infere o ano UMA VEZ só, pro par (mês, dia) mais tardio — não pra
    # cada data separadamente. Um lote isolado que já passou há pouco mais
    # de 30 dias (ex: 1º Lote "20/07" com hoje em 10/09) rolaria sozinho
    # pro ANO QUE VEM, enquanto um lote mais tardio da mesma tabela (ex: 2º
    # Lote "08/09", só 2 dias atrás) ficaria no ano corrente — os dois são
    # do mesmo evento/temporada, então comparar as datas resultantes com
    # anos diferentes já dava um "prazo final" mais cedo que o penúltimo
    # lote. Comparando (mês, dia) primeiro e só inferindo o ano no final,
    # pro maior par, evita essa inversão.
    pares = []
    for texto_no in soup.find_all(string=lambda s: s and "Lote até" in s):
        span = texto_no.parent
        forte = span.find("strong") if span else None
        if not forte:
            continue
        m = _LOTE_DATA_RE.match(forte.get_text(strip=True))
        if not m:
            continue  # "final" ou outro texto sem data
        pares.append((int(m.group(2)), int(m.group(1))))  # (mês, dia)
    if not pares:
        return None
    mes, dia = max(pares)
    try:
        return date(_inferir_ano(mes, dia), mes, dia)
    except ValueError:
        return None


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

    prazo = _prazo_inscricao(soup)
    return {
        "id": f"cbjjc-{evento_id_bruto}",
        "nome": nome,
        "url": f"{ILUTAS}/Evento/Index.php?event={evento_id_bruto}",
        "data": data,
        "local": local,
        "inscricoes_abertas": (date.today() <= prazo) if prazo else True,
        "prazo_inscricao": prazo.isoformat() if prazo else None,
    }


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


_FAIXAS_COLORIDAS = {"cinza", "amarela", "laranja", "verde"}


def _faixa_normalizada(faixa_bruta):
    # Cinza/Amarela/Laranja/Verde são as faixas infantis intermediárias — a
    # própria CBJJC já usa "Colorida" pra agrupar essas faixas em algumas
    # categorias (mistura com faixas soltas em outras); normaliza aqui pra
    # sempre virar "Colorida" e a busca/filtro tratar igual dos dois jeitos.
    if faixa_bruta.strip().lower() in _FAIXAS_COLORIDAS:
        return "Colorida"
    return faixa_bruta


def faixa_combina(atleta, termo_busca):
    """Como o dado já vem normalizado pra "Colorida" (ver
    _faixa_normalizada), buscar por "Cinza"/"Amarela"/"Laranja"/"Verde"
    também precisa achar esses atletas — sem isso, a busca por substring
    simples (_combina) não bate "cinza" contra "colorida" e some com eles."""
    if not termo_busca:
        return True
    termo = termo_busca.strip().lower()
    faixa_atleta = (atleta.get("faixa") or "").strip().lower()
    if termo in _FAIXAS_COLORIDAS:
        termo = "colorida"
    return termo in faixa_atleta


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
        "faixa": _faixa_normalizada(faixa),
    }


def buscar_atletas(evento_id, filtros):
    evento_id_bruto = evento_id.split("-", 1)[1] if evento_id.startswith("cbjjc-") else evento_id
    atletas = []
    for linha in _linhas_checagem(evento_id_bruto):
        atleta = _monta_atleta(linha)
        if atleta:
            atletas.append(atleta)
    return atletas
