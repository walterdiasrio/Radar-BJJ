"""Conector AJP (Smoothcomp) — mesmo esquema do ADCC: não faz scraping ao
vivo, porque o Smoothcomp bloqueia requisições automatizadas via Cloudflare.
Lê competições e atletas importados manualmente pela tela /importar-ajp — o
usuário salva a página do evento e a página "Athletes" do Smoothcomp (já
tendo passado pela verificação no próprio navegador) e envia esse HTML pra
cá. Os dados extraídos ficam guardados em dados_ajp/.

A mecânica de extração (mesma plataforma Smoothcomp) é idêntica à do ADCC —
ver connectors/adcc.py pros comentários detalhados de cada função."""
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from . import datas as datas_mod
from . import soucompetidor

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent))
DIR_DADOS = DATA_DIR / "dados_ajp"
ARQUIVO_EVENTOS = DIR_DADOS / "eventos.json"
DIR_ATLETAS = DIR_DADOS / "atletas"

_MESES_EN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _garantir_diretorios():
    DIR_ATLETAS.mkdir(parents=True, exist_ok=True)


def _ler_eventos():
    if not ARQUIVO_EVENTOS.exists():
        return []
    return json.loads(ARQUIVO_EVENTOS.read_text(encoding="utf-8"))


def _salvar_eventos(eventos):
    _garantir_diretorios()
    ARQUIVO_EVENTOS.write_text(json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")


def listar_eventos():
    # inscricoes_abertas é calculado aqui (não gravado no JSON) pra
    # continuar correto com o passar do tempo sem precisar reimportar —
    # só o prazo em si (capturado na importação) fica salvo.
    eventos = []
    for evento in _ler_eventos():
        evento = dict(evento)
        prazo = evento.get("prazo_inscricao")
        evento["inscricoes_abertas"] = date.today() <= date.fromisoformat(prazo) if prazo else None
        eventos.append(evento)
    return eventos


def _chave_dedup(texto):
    return re.sub(r"\s+", " ", (texto or "").strip().lower())


def buscar_atletas(evento_id, filtros):
    arquivo = DIR_ATLETAS / f"{evento_id}.json"
    atletas = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else []

    # Soma os atletas inscritos pelo SouCompetidor (ver connectors/
    # soucompetidor.py) — best-effort: se a busca ao vivo falhar (site fora
    # do ar, evento não encontrado lá, etc.), a busca continua funcionando
    # só com o que já tem do Smoothcomp em vez de quebrar de vez.
    evento = next((e for e in _ler_eventos() if e["id"] == evento_id), None)
    if evento:
        try:
            extras = soucompetidor.atletas_do_evento(evento.get("nome", ""), evento.get("local", ""))
        except Exception:
            extras = []
        if extras:
            vistos = {(_chave_dedup(a["nome"]), _chave_dedup(a.get("equipe"))) for a in atletas}
            for extra in extras:
                chave = (_chave_dedup(extra["nome"]), _chave_dedup(extra.get("equipe")))
                if chave in vistos:
                    continue
                vistos.add(chave)
                atletas.append(extra)

    return atletas


def _extrair_id_evento(html):
    # A AJP usa domínio próprio (ajptour.com), não smoothcomp.com direto —
    # mesma plataforma por trás, mas white-label, então o link do evento
    # tem cara de "ajptour.com/en/event/1560" em vez de
    # "smoothcomp.com/.../event/1560" (só a ADCC usa o domínio direto).
    m = re.search(r"(?:smoothcomp\.com|ajptour\.com)/[a-z_]*/event/(\d+)", html)
    return m.group(1) if m else None


def _extrair_nome(soup):
    titulo = soup.find("title")
    if titulo and titulo.text:
        bruto = re.split(r"\s*[|\-–]\s*Smoothcomp", titulo.text, flags=re.I)[0]
        nome = re.sub(r"\s+", " ", bruto).strip()
        if nome:
            return nome
    h2 = soup.select_one(".event-cms-page h2")
    return h2.get_text(strip=True) if h2 else "Evento AJP"


def _extrair_local(soup):
    for card in soup.select(".sc-card"):
        header = card.select_one(".sc-card-header h3")
        if header and header.get_text(strip=True).lower() == "location":
            spans = [s.get_text(strip=True) for s in card.select(".sc-list-item-text span")]
            partes = [s for s in spans if s and s != "Brazil"]
            return ", ".join(partes[:2])
    return ""


def _data_inicio_json_ld(soup):
    """A página do evento AJP (ajptour.com) traz um bloco JSON-LD
    (schema.org/SportsEvent) com startDate em ISO 8601 — bem mais
    confiável do que procurar a data no texto visível, porque o AJP
    mostra as datas sem ano ali ("12 Sep - 13 Sep", ano só aparece em
    outro lugar da página)."""
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            dados = json.loads(script.string)
        except ValueError:
            continue
        inicio = dados.get("startDate") if isinstance(dados, dict) else None
        if inicio:
            try:
                return date.fromisoformat(inicio[:10])
            except ValueError:
                continue
    return None


def _extrair_data(soup, data_inicio_json_ld):
    if data_inicio_json_ld:
        return data_inicio_json_ld.strftime("%d/%m/%Y")

    texto = soup.get_text(" ", strip=True)
    padrao = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4})")
    ocorrencias = padrao.findall(texto)
    if not ocorrencias:
        return ""

    ano_mais_comum = Counter(int(ano) for _, _, ano in ocorrencias).most_common(1)[0][0]

    m_matches = re.search(
        r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4}).{0,40}?Start of Matches",
        texto, re.I,
    )
    mes_txt, dia, _ = m_matches.groups() if m_matches else ocorrencias[0]

    mes = _MESES_EN.get(mes_txt.strip().lower()[:3])
    if not mes:
        return ""
    return f"{int(dia):02d}/{mes:02d}/{ano_mais_comum}"


_SCHEDULE_ITEM_INTERVALO = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\s*-\s*(\d{1,2})\s+([A-Za-z]{3,9})")


def _extrair_prazo_inscricao(soup, ano_evento):
    """As fases de inscrição ("Normal registration", "Late registration")
    aparecem como .schedule-item na página do evento, com intervalo de
    datas sem ano (ex: "25 Aug - 08 Sep 18:00") — usa o ano do evento
    (já resolvido via JSON-LD) pra montar a data completa. Quando há mais
    de uma fase, o prazo final de inscrição é o fim da fase mais tardia
    (normalmente "Late registration"). Sem ano do evento, não dá pra
    montar a data com segurança (o intervalo pode virar o ano)."""
    if not ano_evento:
        return None
    prazos = []
    for item in soup.select(".schedule-item"):
        titulo_el = item.select_one(".title")
        info_el = item.select_one(".info")
        if not titulo_el or not info_el:
            continue
        if "registration" not in titulo_el.get_text(strip=True).lower():
            continue
        m = _SCHEDULE_ITEM_INTERVALO.search(info_el.get_text(" ", strip=True))
        if not m:
            continue
        _dia_ini, _mes_ini, dia_fim, mes_fim_txt = m.groups()
        mes_fim = _MESES_EN.get(mes_fim_txt.strip().lower()[:3])
        if not mes_fim:
            continue
        try:
            prazos.append(date(ano_evento, mes_fim, int(dia_fim)))
        except ValueError:
            continue
    return max(prazos) if prazos else None


_TABELA_IDADE_COORTE = re.compile(r"^(\d{4})\s+and\s+(\d{4})\s*/\s*([^/]+?)\s*/\s*.+$", re.I)
_TABELA_IDADE_CORTE = re.compile(r"^(\d{4})\s+and\s+before\s*/\s*([^/]+?)\s*/\s*.+$", re.I)
_DIVISOES_SEM_IDADE_PROPRIA = {"amateur", "professional"}


def _extrair_tabela_idade(soup):
    """Cada evento AJP costuma trazer, no texto livre da própria página
    (escrito pelo organizador, não um campo estruturado do Smoothcomp),
    uma tabela "Year of Birth / Division / Belt" com o ano de nascimento
    exato de cada divisão (ex: "2011 and 2012 / Teen / ...",
    "1990 and before / Master 2 / ..."). Isso é bem mais preciso do que
    tentar adivinhar a idade de "Master 2"/"Teen"/"Kids 1" só pelo nome —
    esses rótulos não seguem um padrão numérico previsível (diferente do
    ADCC, que usa "Masters 30/35/40" — aí sim o número já É a idade).

    "Amateur"/"Professional" ficam de fora: não são faixa etária, são
    nível de habilidade (nesse mesmo evento, pessoas de anos de
    nascimento sobrepostos podem estar em qualquer um dos dois), então
    não dá pra resolver isso a partir da data de nascimento.

    Como isso vem de texto escrito à mão por cada organizador, o formato
    pode variar ou faltar em algum evento — por isso é só uma tentativa
    best-effort: se não achar nada, `categoria_exata_para_idade` cai de
    volta no heurístico genérico (ver lá)."""
    coortes = []
    cortes = []
    vistos = set()
    for p in soup.find_all("p"):
        texto = p.get_text(" ", strip=True)
        if not texto or "/" not in texto:
            continue

        m = _TABELA_IDADE_COORTE.match(texto)
        if m:
            ano1, ano2, divisao = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            if divisao.lower() in _DIVISOES_SEM_IDADE_PROPRIA:
                continue
            chave = ("coorte", divisao, ano1, ano2)
            if chave not in vistos:
                vistos.add(chave)
                coortes.append({"divisao": divisao, "ano_min": min(ano1, ano2), "ano_max": max(ano1, ano2)})
            continue

        m = _TABELA_IDADE_CORTE.match(texto)
        if m:
            ano, divisao = int(m.group(1)), m.group(2).strip()
            if divisao.lower() in _DIVISOES_SEM_IDADE_PROPRIA:
                continue
            chave = ("corte", divisao, ano)
            if chave not in vistos:
                vistos.add(chave)
                cortes.append({"divisao": divisao, "ano_max": ano})

    return {"coortes": coortes, "cortes": cortes}


def parse_evento_html(html):
    soup = BeautifulSoup(html, "lxml")
    evento_id = _extrair_id_evento(html)
    if not evento_id:
        raise ValueError(
            "não encontrei o ID do evento nessa página (procurei um link tipo "
            "smoothcomp.com/.../event/12345) — confirma que essa é a página do evento?"
        )
    data_inicio = _data_inicio_json_ld(soup)
    prazo_inscricao = _extrair_prazo_inscricao(soup, data_inicio.year if data_inicio else None)
    return {
        "id": f"ajp-{evento_id}",
        "nome": _extrair_nome(soup),
        "data": _extrair_data(soup, data_inicio),
        "local": _extrair_local(soup),
        "tabela_idade": _extrair_tabela_idade(soup),
        "prazo_inscricao": prazo_inscricao.isoformat() if prazo_inscricao else None,
    }


def _genero_pt(genero_raw):
    g = genero_raw.strip().lower()
    if g.startswith("women") or g.startswith("girls"):
        return "feminino"
    if g.startswith("men") or g.startswith("boys"):
        return "masculino"
    return genero_raw


_BELTS_EN = {"white", "grey", "gray", "yellow", "orange", "green", "blue", "purple", "brown", "black"}

# Rótulos de idade que não seguem os padrões numéricos (_KIDS_INTERVALO,
# _KIDS_ATE, _MASTERS) mas ainda assim são categoria de idade, não faixa
# nem nível — usado só pra classificar corretamente o campo na hora de
# extrair (ver _partes_categoria); categoria_exata_para_idade não sabe
# resolver esses a partir da data de nascimento (não há uma tabela oficial
# e estável de faixa etária pra eles disponível na página do evento).
_ROTULOS_IDADE_SEM_TABELA = {"teen", "junior", "youth", "juvenile", "kids"}


def _eh_rotulo_idade(token):
    token = token.strip()
    return bool(
        _KIDS_INTERVALO.match(token) or _KIDS_ATE.match(token) or _MASTERS.match(token)
        or token.lower() in _ROTULOS_IDADE_SEM_TABELA or token.lower() == "adult"
    )


def _partes_categoria(header_texto):
    """O cabeçalho de cada grupo de inscritos tem 4 campos separados por
    "/", mas a ORDEM dos dois campos do meio varia: divisões kids/teen
    vêm como "Gênero / Idade / Faixa / Peso" (ex: "Girls GI / Teen /
    Yellow / 57KG"), enquanto divisões adulto vêm como "Gênero / Faixa /
    Nível-ou-Master / Peso" (ex: "Men's GI / Blue / Amateur / 62KG",
    "Men's GI / Purple / Master 2 / 77KG") — sem token de idade quando é
    só "Amateur"/"Professional" (implicitamente Adulto). Por isso os dois
    campos do meio são classificados pelo próprio conteúdo (é idade? é
    faixa?) em vez de por posição fixa."""
    partes = [p.strip() for p in header_texto.split("/")]
    genero_raw = partes[0] if partes else ""
    peso = partes[-1] if len(partes) > 1 else ""
    meio = partes[1:-1]

    # tokens que não batem com idade nem com faixa conhecida (ex:
    # "Amateur"/"Professional") são descartados — não são faixa nem
    # idade de verdade, então não há onde guardá-los; idade e faixa,
    # quando presentes, continuam corretas de qualquer forma.
    categoria_idade = ""
    nivel = ""
    for token in meio:
        if not categoria_idade and _eh_rotulo_idade(token):
            categoria_idade = token
        elif not nivel and token.strip().lower() in _BELTS_EN:
            nivel = token
    if not categoria_idade:
        categoria_idade = "Adult"

    if not peso and "absolute" in genero_raw.lower():
        peso = "Absoluto"

    return genero_raw, categoria_idade, nivel, peso


def parse_atletas_html(html):
    soup = BeautifulSoup(html, "lxml")
    atletas = []
    for grupo in soup.select(".participant-group"):
        header = grupo.select_one(".group-name")
        if not header:
            continue
        genero_raw, categoria_idade, nivel, peso = _partes_categoria(header.get_text(strip=True))
        genero = _genero_pt(genero_raw)

        for card in grupo.select(".profile-card"):
            nome_el = card.select_one(".profile-card-name a span")
            if not nome_el:
                continue
            equipe_el = card.select_one(".participant-td-club a")
            pais_el = card.select_one(".country-name span")
            nascimento_container = card.select_one(".participant-td-birth")
            nascimento_div = nascimento_container.find("div") if nascimento_container else None
            aprovado = "unapproved" not in (card.get("class") or [])

            atletas.append({
                "federacao": "AJP",
                "nome": nome_el.get_text(strip=True),
                "equipe": equipe_el.get_text(strip=True) if equipe_el else "",
                "categoria_idade": categoria_idade,
                "genero": genero,
                "peso": peso,
                "faixa": nivel,
                "pais": pais_el.get_text(strip=True) if pais_el else "",
                "ano_nascimento": nascimento_div.get_text(strip=True) if nascimento_div else "",
                "pagamento": "Confirmado" if aprovado else "Não confirmado",
            })
    return atletas


def salvar_evento(evento):
    eventos = [e for e in _ler_eventos() if e["id"] != evento["id"]]
    eventos.append(evento)
    _salvar_eventos(eventos)


def salvar_atletas(evento_id, atletas):
    _garantir_diretorios()
    (DIR_ATLETAS / f"{evento_id}.json").write_text(
        json.dumps(atletas, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def remover_evento(evento_id):
    eventos = [e for e in _ler_eventos() if e["id"] != evento_id]
    _salvar_eventos(eventos)
    arquivo = DIR_ATLETAS / f"{evento_id}.json"
    if arquivo.exists():
        arquivo.unlink()


def data_referencia_evento(evento_id):
    for evento in _ler_eventos():
        if evento["id"] == evento_id:
            data_evento = datas_mod.extrair_data(evento.get("data", ""))
            if data_evento:
                return data_evento
            break
    return date.today()


def idade_exata(data_nascimento, data_referencia):
    anos = data_referencia.year - data_nascimento.year
    if (data_referencia.month, data_referencia.day) < (data_nascimento.month, data_nascimento.day):
        anos -= 1
    return anos


_KIDS_INTERVALO = re.compile(r"^(\d+)-(\d+)\s*years$", re.I)
_KIDS_ATE = re.compile(r"^(\d+)\s*and under$", re.I)
_MASTERS = re.compile(r"^Masters?\s*(\d+)$", re.I)


_FAIXA_PT_PARA_EN = {
    "branca": "white", "cinza": "grey", "cinzenta": "grey",
    "amarela": "yellow", "laranja": "orange", "verde": "green",
    "azul": "blue", "roxa": "purple", "marrom": "brown", "preta": "black",
}


def faixa_combina(atleta, termo_busca):
    """Diferente do ADCC (que categoriza por nível de habilidade autodeclarado
    — Beginner/Intermediate/Advanced), a AJP usa o nome da faixa direto no
    rótulo da categoria (ex: "Purple"), igual às federações brasileiras — só
    que em inglês. Aceita o termo em português (traduzido) ou já em inglês."""
    if not termo_busca:
        return True
    termo = termo_busca.strip().lower()
    faixa_atleta = (atleta.get("faixa") or "").strip().lower()
    faixa_en = _FAIXA_PT_PARA_EN.get(termo, termo)
    return faixa_atleta == faixa_en or faixa_atleta == termo


def _categoria_por_ano_nascimento(tabela_idade, ano_nascimento):
    """Resolve a divisão certa usando a tabela "ano de nascimento -> divisão"
    extraída da página do evento (ver _extrair_tabela_idade). Coortes
    (2 anos exatos, tipo kids/teen/youth) são checadas primeiro, por
    serem mais específicas; cortes tipo "Master N: X e antes" são
    cumulativos — o corte mais recente (maior ano) que ainda contém o
    ano de nascimento é o mais específico (ex: nascido em 1988: bate em
    "1990 and before" E "1996 and before", mas 1990 é o mais restrito
    dos dois que ainda vale, então é esse)."""
    if not tabela_idade:
        return None

    for coorte in tabela_idade.get("coortes", []):
        if coorte["ano_min"] <= ano_nascimento <= coorte["ano_max"]:
            return coorte["divisao"]

    cortes = sorted(tabela_idade.get("cortes", []), key=lambda c: c["ano_max"])
    for corte in cortes:
        if ano_nascimento <= corte["ano_max"]:
            return corte["divisao"]

    return None


def categoria_exata_para_idade(evento_id, idade, data_nascimento=None):
    rotulos = {a["categoria_idade"] for a in buscar_atletas(evento_id, {}) if a.get("categoria_idade")}

    if data_nascimento is not None:
        tabela_idade = None
        for evento in _ler_eventos():
            if evento["id"] == evento_id:
                tabela_idade = evento.get("tabela_idade")
                break
        if tabela_idade and (tabela_idade.get("coortes") or tabela_idade.get("cortes")):
            categoria = _categoria_por_ano_nascimento(tabela_idade, data_nascimento.year)
            if categoria:
                return categoria
            # não bateu com nenhuma divisão específica da tabela (kids,
            # teen, master...) — é um adulto "comum" (não master). NÃO
            # cai no heurístico genérico abaixo pra esse caso: ele trata
            # o número de "Master N" como se fosse idade, o que daria
            # resposta errada aqui (ex: classificaria um adulto de 26
            # anos como "Master 4").
            return "Adult" if "adult" in {r.strip().lower() for r in rotulos} else None

    kids = []
    masters = []
    tem_adult = False
    for rotulo in rotulos:
        m_intervalo = _KIDS_INTERVALO.match(rotulo)
        m_ate = _KIDS_ATE.match(rotulo)
        m_masters = _MASTERS.match(rotulo)
        if m_intervalo:
            kids.append((int(m_intervalo.group(1)), int(m_intervalo.group(2)), rotulo))
        elif m_ate:
            kids.append((0, int(m_ate.group(1)), rotulo))
        elif m_masters:
            masters.append((int(m_masters.group(1)), rotulo))
        elif rotulo.strip().lower() == "adult":
            tem_adult = True

    for minimo, maximo, rotulo in sorted(kids):
        if minimo <= idade <= maximo:
            return rotulo

    masters.sort()
    if masters:
        if tem_adult and 18 <= idade < masters[0][0]:
            return "Adult"
        for i, (numero, rotulo) in enumerate(masters):
            proximo = masters[i + 1][0] if i + 1 < len(masters) else None
            if idade >= numero and (proximo is None or idade < proximo):
                return rotulo
    elif tem_adult and idade >= 18:
        return "Adult"

    return None


_PESO_BRACKET = re.compile(r"^([+-])\s*(\d+(?:[.,]\d+)?)\s*kg$", re.I)


def categoria_peso_exata(evento_id, categoria_idade, genero, peso_kg):
    faixas = set()
    for atleta in buscar_atletas(evento_id, {}):
        if atleta.get("categoria_idade") != categoria_idade:
            continue
        if genero and atleta.get("genero") != genero:
            continue
        m = _PESO_BRACKET.match((atleta.get("peso") or "").strip())
        if m:
            sinal, numero = m.groups()
            faixas.add((float(numero.replace(",", ".")), sinal, atleta["peso"]))

    if not faixas:
        return None

    abaixo = sorted((limite, rotulo) for limite, sinal, rotulo in faixas if sinal == "-")
    for limite, rotulo in abaixo:
        if peso_kg <= limite:
            return rotulo

    acima = sorted((limite, rotulo) for limite, sinal, rotulo in faixas if sinal == "+")
    return acima[-1][1] if acima else None
