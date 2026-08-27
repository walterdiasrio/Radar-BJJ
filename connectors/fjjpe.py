"""Conector FJJPE (Federação de Jiu-Jitsu do Estado de Pernambuco).

Inscrições rodam na plataforma Camp Fácil (campfacil.com.br), num
subdomínio próprio por evento (site.campfacil.com.br/<slug-do-evento>).

listar_eventos() lê a home do site institucional (site.fjjpe.com.br), seção
"Eventos FJJPE" — cada card ali linka pro subdomínio Camp Fácil do evento
correspondente. Não tem "listagem de todos os eventos" à parte: só os
atualmente em cartaz aparecem na home, igual o padrão adotado pra CBJJC
(cbjjc.com.br/campeonatos).

buscar_atletas() lê a checagem geral de cada evento
(.../checageralfjjpefinal.php?sexo=MASCULINO|FEMININO), uma tabela HTML
"soup" antiga (sem framework) onde cada categoria é um bloco
"CATEGORIA | <idade> | <faixa> | <peso>" seguido das linhas de atletas.

Nomes de categoria de idade/peso no site vêm em CAIXA ALTA e sem acento
("PRE MIRIM 1", "MEIO PESADO") — normalizados aqui pros rótulos padrão
(acentuados/hifenizados) que o resto do buscador usa (ver idade.py/peso.py),
já que a FJJPE segue a "TABELA OFICIAL CBJJ/IBJJF" (rótulo do próprio PDF
de peso da federação, fjjpe.com.br) — mesmas faixas de idade/peso da
CBJJ/FJJRio.
Data de cada evento: a home não traz data em texto (só no cartaz/imagem do
evento, ilegível por scraping) — mas a FJJPE mantém um post de notícia
"Calendário <ano> FJJPE" com a agenda do ano inteiro em texto corrido (um
resumo por mês, cada linha "DD[ e DD][/MM] - Nome do evento - ..."). Casamos
cada evento descoberto na home com a linha desse calendário que compartilha
uma palavra distintiva do nome (ex: "Estima", "Derval") — impreciso pra
nomes genéricos, mas essas etapas sempre carregam o nome de um mestre
homenageado, o suficiente pra achar a linha certa.

Local: não aparece em texto em lugar nenhum do site (só no cartaz/imagem) —
usamos o local mais recente confirmado manualmente (ver _LOCAL_PADRAO
abaixo), igual à tabela de peso da CBJJC (também lida de uma imagem por
falta de fonte em texto).
"""
import re
import unicodedata
from datetime import date
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .http import get

SITE = "https://site.fjjpe.com.br"
DOMINIO_EVENTOS = "https://site.campfacil.com.br"

# Lido do cartaz oficial (imagem) do "Campeonato Pernambucano 2026 — NoGi -
# Etapa Bráulio Estima", conferido em 27/08/2026. Sem fonte em texto no
# site pra confirmar automaticamente — pode ficar desatualizado se a FJJPE
# trocar de local numa próxima etapa.
_LOCAL_PADRAO = "Secretaria de Educação do Estado de Pernambuco, Recife-PE"

_PALAVRAS_IGNORADAS = {
    "campeonato", "campeonatos", "pernambucano", "pernambuco", "fjjpe",
    "etapa", "estadual", "nogi", "camp", "kids", "juvenil", "masters",
    "adulto", "master", "de", "do", "da", "dos", "das",
}


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _palavras_distintas(texto):
    palavras = re.findall(r"[a-zà-ú]+", _sem_acento(texto))
    return {p for p in palavras if len(p) > 3 and p not in _PALAVRAS_IGNORADAS}


def _entradas_calendario():
    """Lê o post de notícia "Calendário <ano> FJJPE" da home e devolve uma
    lista de (dia, mes, ano, texto_da_linha). Retorna [] se o post não
    existir ou não achar nada reconhecível (ex: mudou de formato)."""
    try:
        resp = get(f"{SITE}/")
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "lxml")

    botao = soup.select_one('[data-titulo*="Calendário"]')
    if not botao:
        return []

    titulo = botao.get("data-titulo") or ""
    descricao = botao.get("data-descricao") or ""
    m_ano = re.search(r"\b(20\d{2})\b", titulo)
    if not m_ano or not descricao:
        return []
    ano = int(m_ano.group(1))

    entradas = []
    for linha in descricao.split("\n"):
        linha = linha.strip()
        m = re.match(r"^(\d{1,2})\b.*?/(\d{1,2})\s*-\s*(.+)$", linha)
        if not m:
            continue
        dia, mes, resto = int(m.group(1)), int(m.group(2)), m.group(3)
        entradas.append((dia, mes, ano, resto))
    return entradas


def _data_do_evento(nome_evento, entradas_calendario):
    palavras_evento = _palavras_distintas(nome_evento)
    if not palavras_evento:
        return ""
    for dia, mes, ano, texto in entradas_calendario:
        if palavras_distintas := (_palavras_distintas(texto) & palavras_evento):
            return f"{dia:02d}/{mes:02d}/{ano}"
    return ""


def _caminho_do_evento(url):
    return urlparse(url).path.strip("/")


def _inscricoes_abertas(caminho):
    """A página do evento (login/checagem) tem um card "Valores das
    inscrições" com um ou mais lotes, cada um com uma data limite
    (".lot-date", ex: "até 09/09/2026") — inscrições contam como abertas
    enquanto a data de hoje não passar do último lote. None se a página não
    tiver nenhum lote (não dá pra saber)."""
    try:
        resp = get(f"{DOMINIO_EVENTOS}/{caminho}")
    except Exception:
        return None
    soup = BeautifulSoup(resp.text, "lxml")

    limites = []
    for el in soup.select(".lot-date"):
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", el.get_text(strip=True))
        if not m:
            continue
        dia, mes, ano = (int(x) for x in m.groups())
        try:
            limites.append(date(ano, mes, dia))
        except ValueError:
            continue
    if not limites:
        return None
    return date.today() <= max(limites)


def listar_eventos():
    resp = get(f"{SITE}/")
    soup = BeautifulSoup(resp.text, "lxml")

    container = soup.select_one("div.container.events.content")
    if not container:
        return []

    entradas_calendario = _entradas_calendario()

    eventos = []
    for card in container.select(".card"):
        link = card.select_one("a[href]")
        titulo_el = card.select_one(".card-title")
        if not link or not titulo_el:
            continue
        url = (link.get("href") or "").strip()
        nome = titulo_el.get_text(strip=True)
        caminho = _caminho_do_evento(url)
        if not url or not nome or not caminho:
            continue
        eventos.append({
            "id": f"fjjpe-{caminho}",
            "nome": nome,
            "data": _data_do_evento(nome, entradas_calendario),
            "local": _LOCAL_PADRAO,
            "inscricoes_abertas": _inscricoes_abertas(caminho),
        })
    return eventos


_IDADE_LABEL_MAP = {
    "pre mirim 1": "Pré-Mirim 1", "pre mirim 2": "Pré-Mirim 2", "pre mirim 3": "Pré-Mirim 3",
    "mirim 1": "Mirim 1", "mirim 2": "Mirim 2", "mirim 3": "Mirim 3",
    "infantil 1": "Infantil 1", "infantil 2": "Infantil 2", "infantil 3": "Infantil 3",
    "infanto juvenil 1": "Infanto-Juvenil 1",
    "infanto juvenil 2": "Infanto-Juvenil 2",
    "infanto juvenil 3": "Infanto-Juvenil 3",
    "juvenil 1": "Juvenil 1", "juvenil 2": "Juvenil 2",
    "adulto": "Adulto",
    "master 1": "Master 1", "master 2": "Master 2", "master 3": "Master 3",
    "master 4": "Master 4", "master 5": "Master 5", "master 6": "Master 6",
}


def _idade_normalizada(idade_bruta):
    return _IDADE_LABEL_MAP.get(idade_bruta.strip().lower(), idade_bruta.strip().title())


_PESO_LABEL_MAP = {
    "galo": "Galo",
    "pluma": "Pluma",
    "pena": "Pena",
    "leve": "Leve",
    "medio": "Médio",
    "meio pesado": "Meio-Pesado",
    "pesado": "Pesado",
    "super pesado": "Super-Pesado",
    "pesadissimo": "Pesadíssimo",
    "absoluto": "Absoluto",
}


def _peso_normalizado(peso_bruto):
    return _PESO_LABEL_MAP.get(peso_bruto.strip().lower(), peso_bruto.strip().title())


_LINHA_ATLETA_RE = re.compile(r"^(.*?)\s*\(\d+\)\s*/\s*(.*)$")


def _linhas_checagem(caminho, sexo):
    resp = get(f"{DOMINIO_EVENTOS}/{caminho}/checageralfjjpefinal.php", params={"sexo": sexo})
    soup = BeautifulSoup(resp.text, "lxml")

    linhas = []
    categoria_atual = None
    for tr in soup.select("tr"):
        h6 = tr.select_one("h6")
        if h6:
            categoria_atual = h6.get_text(" ", strip=True)
            continue
        if not categoria_atual:
            continue
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        bruto = tds[1].get_text(" ", strip=True)
        m = _LINHA_ATLETA_RE.match(bruto)
        if not m:
            continue
        nome, status = m.groups()
        equipe = tds[2].get_text(strip=True)
        linhas.append({
            "categoria": categoria_atual,
            "nome": nome.strip(),
            "equipe": equipe,
            "status": status.strip(),
        })
    return linhas


def _monta_atleta(linha, genero):
    # "CATEGORIA |  JUVENIL 1   |  BRANCA |  PLUMA" -> rótulo, idade, faixa, peso
    partes = [p.strip() for p in linha["categoria"].split("|")]
    if len(partes) != 4:
        return None
    _rotulo, idade_bruta, faixa_bruta, peso_bruto = partes

    return {
        "federacao": "FJJPE",
        "nome": linha["nome"],
        "equipe": linha["equipe"],
        "categoria_idade": _idade_normalizada(idade_bruta),
        "genero": genero,
        "peso": _peso_normalizado(peso_bruto),
        "faixa": faixa_bruta.title(),
        "pagamento": "Confirmado" if linha["status"].upper() == "CONFIRMADO" else linha["status"].title(),
    }


def buscar_atletas(evento_id, filtros):
    caminho = evento_id.split("-", 1)[1] if evento_id.startswith("fjjpe-") else evento_id
    atletas = []
    for sexo, genero in (("MASCULINO", "masculino"), ("FEMININO", "feminino")):
        for linha in _linhas_checagem(caminho, sexo):
            atleta = _monta_atleta(linha, genero)
            if atleta:
                atletas.append(atleta)
    return atletas
