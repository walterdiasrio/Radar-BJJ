"""Conector FJJPA (Federação de Jiu-Jitsu do Pará).

listar_eventos() lê a home (fjjpa.app.br) — a seção "Próximos Eventos"
(div .entry3, conferido ao vivo: são só os 14 eventos futuros, a seção
separada "Eventos Passados" logo abaixo usa outra marcação e não entra
no seletor) já traz nome, data por extenso (com dia da semana, tipo
"domingo, 20 de setembro de 2026" — connectors/datas.py já entende esse
formato) e local (span com ícone de mapa) prontos. Não existe uma
página de calendário utilizável — a única "Calendário 2026" do site é
uma imagem/pôster, sem texto nenhum pra ler.

Local costuma vir sem cidade OU sem UF (ex: "Ginásio do Premem", "Arena
Guilherme Paraense (Mangueirinho)") — mas a FJJPA é uma federação
ESTADUAL (todas as competições são no Pará, confirmado pelo usuário),
então "fjjpa" entra em connectors/__init__.py::_UF_FIXA_POR_FEDERACAO
com "PA": mesmo quando não dá pra achar o município no texto,
_simplifica_local ainda consegue colar a UF certa.

status_inscricao() lê a própria página do evento (evento.php?id=<id>)
— tem um botão que já diz "As inscrições para esse evento estão
abertas."/"...estão encerradas." (usado em vez de comparar com a data
de hoje) e um bloco "Datas Importantes" com 4 datas (Início da
Inscrição / Término da Inscrição / Data limite pra pagamento / Data
limite pra edição) — usamos "Término da Inscrição" como prazo_inscricao
(é o fechamento de verdade pra quem ainda não se inscreveu; as outras
duas datas de "pagamento"/"edição" são só pra quem já está inscrito).

buscar_atletas() usa a "Checagem Pública" (checagem.php?id=<id>), que
carrega a lista via uma tabela DataTables server-side — precisa buscar
essa página primeiro só pra pegar o "checagem_token" (muda a cada
carregamento, mas não parece amarrado a sessão — qualquer token recém
gerado funciona) e o id numérico interno do evento (id_evento, diferente
do id codificado da URL), e então faz o POST de verdade pra
app/paginas/listaDeInscricoes.php. Peço "length" bem alto (9999) pra já
trazer todo mundo de uma vez em vez de paginar (conferido ao vivo:
1166 inscritos em um único evento grande, veio tudo certo).

Cada linha retornada tem, além do nome/equipe/idade/sexo/peso/faixa, um
"Sit" (status de pagamento, ignorado aqui) e às vezes uma nota extra no
próprio nome tipo "<br><span>Absoluto - Leve</span>" quando a pessoa
também está inscrita no Absoluto daquele peso — isso NÃO vira uma linha
separada (diferente da CBJJC, que trata absoluto como inscrição própria
com peso="Absoluto"): aqui é só uma anotação dentro da MESMA inscrição
já contada com o peso normal, então só limpamos do nome e ignoramos.

Idade: nomes de categoria vêm em MAIÚSCULO e os Masters vêm AGRUPADOS
EM PARES ("MASTER 1 / MASTER 2", "MASTER 3 / MASTER 4", "MASTER 5 /
MASTER 6") em vez de individuais — mas cada linha também traz a idade
literal da pessoa (ex: "MASTER 3 / MASTER 4 - 42 anos"), e as faixas
etárias da FJJPA batem exatamente com connectors/idade.py::_CBJJE
(Pré-Mirim 4-5, Mirim 6-7, Infantil A/B 8-9/10-11, Infanto Juvenil A/B
12-13/14-15, Juvenil 16-17, Adulto 18-29, Master 1-6 de 5 em 5 anos —
conferido ao vivo: idade 42 cai em Master 3 na _CBJJE, que é exatamente
o que a FJJPA quis dizer com "MASTER 3 / MASTER 4 - 42 anos"). Por isso
usamos a idade literal pra resolver qual Master exato dentro do par, em
vez de inventar uma tabela nova só pra guardar o par ambíguo.

Não há tabela oficial de peso→kg da FJJPA disponível publicamente (só
os nomes das faixas de peso), então essa federação não entra em
connectors/peso.py — igual à FJJPR."""
import re

from bs4 import BeautifulSoup

from . import datas as datas_mod
from .http import get, post

SITE = "https://www.fjjpa.app.br"

_DATAS_IMPORTANTES_RE = re.compile(r"<li><i><b>([^<]+)</b></i><br>([^<]+)</li>")

_IDADE_NORMALIZADA = {
    "pré mirim": "Pré-Mirim",
    "mirim": "Mirim",
    "infantil - a": "Infantil A",
    "infantil - b": "Infantil B",
    "infanto juvenil - a": "Infanto Juvenil A",
    "infanto juvenil - b": "Infanto Juvenil B",
    "juvenil": "Juvenil",
    "adulto": "Adulto",
}

# Faixas etárias do Master na _CBJJE (idade.py) — usadas aqui só pra
# resolver o par ambíguo "MASTER X / MASTER Y" a partir da idade literal.
_MASTER_FAIXAS = [
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

_IDADE_RE = re.compile(r"^(.*?)\s*-\s*<span[^>]*><b>(\d+)</b>\s*anos</span>", re.I)


def _master_exato(idade):
    for minimo, maximo, rotulo in _MASTER_FAIXAS:
        if idade >= minimo and (maximo is None or idade <= maximo):
            return rotulo
    return None


def _normalizar_idade(campo_html):
    m = _IDADE_RE.match(campo_html.strip())
    if not m:
        return campo_html.strip().title()
    bruto, idade_texto = m.group(1).strip(), m.group(2)
    chave = bruto.lower()
    if chave in _IDADE_NORMALIZADA:
        return _IDADE_NORMALIZADA[chave]
    if chave.startswith("master"):
        return _master_exato(int(idade_texto)) or bruto.title()
    return bruto.title()


def _titulo_pt(texto):
    """Como str.title(), mas mantém "e" minúsculo (conjunção) — precisa pra
    faixas compostas tipo "AMARELA, LARANJA E VERDE" -> "Amarela, Laranja e
    Verde" (str.title() puro deixaria "E" maiúsculo no meio)."""
    saida = []
    for palavra in texto.strip().split():
        sufixo = "," if palavra.endswith(",") else ""
        base = palavra.rstrip(",")
        saida.append(("e" if base.lower() == "e" else base.capitalize()) + sufixo)
    return " ".join(saida)


def listar_eventos():
    resp = get(SITE + "/")
    soup = BeautifulSoup(resp.text, "lxml")

    eventos = []
    for card in soup.select(".entry3"):
        link = card.select_one("h2 a")
        if not link or not link.get("href"):
            continue
        m = re.search(r"id=([^&]+)", link["href"])
        if not m:
            continue
        evento_id = m.group(1)

        metas = card.select(".post-meta")
        data_texto = metas[0].get_text(" ", strip=True) if metas else ""
        local_el = card.select_one(".post-meta .icon-map-marker")
        local = local_el.parent.get_text(" ", strip=True) if local_el else ""
        local = re.sub(r"^\s*", "", local)

        eventos.append({
            "id": evento_id,
            "nome": link.get_text(strip=True),
            "url": f"{SITE}/evento.php?id={evento_id}",
            "data": datas_mod.formatar(data_texto),
            "local": local,
        })
    return eventos


def status_inscricao(evento):
    url = evento.get("url")
    if not url:
        return None, None
    try:
        resp = get(url)
    except Exception:
        return None, None
    html = resp.text

    datas = {rotulo.strip(): valor.strip() for rotulo, valor in _DATAS_IMPORTANTES_RE.findall(html)}
    prazo_inscricao = None
    termino = datas.get("Término da Inscrição")
    if termino:
        prazo_inscricao = datas_mod.extrair_data(termino)
        prazo_inscricao = prazo_inscricao.isoformat() if prazo_inscricao else None

    inscricoes_abertas = None
    if "estão abertas" in html:
        inscricoes_abertas = True
    elif "estão encerradas" in html:
        inscricoes_abertas = False

    return inscricoes_abertas, prazo_inscricao


def buscar_atletas(evento_id, filtros):
    resp = get(f"{SITE}/checagem.php", params={"id": evento_id})
    html = resp.text
    m_id = re.search(r"d\.id_evento = (\d+)", html)
    m_token = re.search(r'checagem_token = "([a-f0-9]+)"', html)
    if not m_id or not m_token:
        return []

    dados = {
        "draw": "1", "start": "0", "length": "9999",
        "search[value]": "", "search[regex]": "false",
        "order[0][column]": "0", "order[0][dir]": "asc",
        "id_evento": m_id.group(1), "checagem_token": m_token.group(1),
        "nome": "", "academia": "0", "idade": "", "sexo": "", "peso": "", "faixa": "", "chave": "",
    }
    for i, nome_coluna in enumerate(
        ["chave", "competidor", "academia", "idade", "sexo", "peso", "faixa", "sit"]
    ):
        dados[f"columns[{i}][data]"] = str(i)
        dados[f"columns[{i}][name]"] = nome_coluna
        dados[f"columns[{i}][searchable]"] = "true"
        dados[f"columns[{i}][orderable]"] = "true"
        dados[f"columns[{i}][search][value]"] = ""
        dados[f"columns[{i}][search][regex]"] = "false"

    resp2 = post(f"{SITE}/app/paginas/listaDeInscricoes.php", data=dados)
    try:
        linhas = resp2.json().get("data", [])
    except ValueError:
        return []

    resultados = []
    for linha in linhas:
        if len(linha) < 7:
            continue
        chave, competidor, academia, idade_html, sexo, peso, faixa = linha[:7]
        nome = competidor.split("<br>")[0].strip()
        resultados.append({
            "federacao": "FJJPA",
            "nome": nome,
            "equipe": academia.strip(),
            "categoria_idade": _normalizar_idade(idade_html),
            "genero": sexo.strip(),
            "peso": _titulo_pt(peso),
            "faixa": _titulo_pt(faixa),
        })
    return resultados
