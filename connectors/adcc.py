"""Conector ADCC (Smoothcomp) — diferente dos outros, não faz scraping ao
vivo: o Smoothcomp bloqueia requisições automatizadas via Cloudflare. Em vez
disso, lê competições e atletas importados manualmente pela tela
/importar-adcc — o usuário salva a página do evento e a página "Athletes" do
Smoothcomp (já tendo passado pela verificação no próprio navegador) e envia
esse HTML pra cá. Os dados extraídos ficam guardados em dados_adcc/."""
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from . import datas as datas_mod

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent))
DIR_DADOS = DATA_DIR / "dados_adcc"
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


def buscar_atletas(evento_id, filtros):
    arquivo = DIR_ATLETAS / f"{evento_id}.json"
    if not arquivo.exists():
        return []
    return json.loads(arquivo.read_text(encoding="utf-8"))


def _extrair_id_evento(html):
    m = re.search(r"smoothcomp\.com/[a-z_]*/event/(\d+)", html)
    return m.group(1) if m else None


_SUFIXOS_TITULO = re.compile(r"\s*[|\-–]\s*Smoothcomp\s*$", re.I)


def _extrair_nome(soup):
    titulo = soup.find("title")
    if titulo and titulo.text:
        bruto = titulo.text
        anterior = None
        while anterior != bruto:
            anterior = bruto
            bruto = _SUFIXOS_TITULO.sub("", bruto)
        nome = re.sub(r"\s+", " ", bruto).strip()
        if nome:
            return nome
    h2 = soup.select_one(".event-cms-page h2")
    return h2.get_text(strip=True) if h2 else "Evento ADCC"


# Fallback pro card "Location" não achar nada — seja porque a página foi
# salva antes do card terminar de carregar (é preenchido via JS/XHR, então
# salvar rápido demais no navegador perde essa parte), seja porque o
# evento não tem esse card. Os eventos ADCC Brazil Open seguem o padrão
# "ADCC Brazil Open - Cidade" — o local vem como sufixo depois do último
# hífen no próprio nome do evento.
_SUFIXO_GENERICO = re.compile(r"^(GI(\s*&\s*NO-?GI)?|NO-?GI|\d{4}(\s*-\s*\d{4})?)$", re.I)


def _extrair_local_do_nome(nome):
    partes = nome.rsplit(" - ", 1)
    if len(partes) == 2 and partes[1].strip() and not _SUFIXO_GENERICO.match(partes[1].strip()):
        return partes[1].strip().title()
    return ""


def _extrair_local(soup, nome_evento):
    for card in soup.select(".sc-card"):
        header = card.select_one(".sc-card-header h3")
        if header and header.get_text(strip=True).lower() == "location":
            spans = [s.get_text(strip=True) for s in card.select(".sc-list-item-text span")]
            partes = [s for s in spans if s and s != "Brazil"]
            if partes:
                return ", ".join(partes[:2])
    return _extrair_local_do_nome(nome_evento)


def _data_inicio_json_ld(soup):
    """A página do evento (smoothcomp.com) traz um bloco JSON-LD
    (schema.org/SportsEvent) com startDate em ISO 8601 — mais confiável do
    que procurar a data no texto visível da tabela SCHEDULE."""
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
    """Acha a data de início da competição. Prioriza o JSON-LD; se não
    tiver, cai pra tabela SCHEDULE (linha "Start of Matches"). O ano usado
    nesse fallback é o mais frequente entre todas as linhas da tabela —
    vimos casos de linha isolada com ano digitado errado na própria fonte,
    então a moda entre as outras datas é mais confiável que pegar o ano
    dessa linha específica."""
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
    nome_evento = _extrair_nome(soup)
    return {
        "id": f"adcc-{evento_id}",
        "nome": nome_evento,
        "data": _extrair_data(soup, data_inicio),
        "local": _extrair_local(soup, nome_evento),
        "prazo_inscricao": prazo_inscricao.isoformat() if prazo_inscricao else None,
    }


def _genero_pt(genero_raw):
    g = genero_raw.strip().lower()
    if g.startswith("women") or g == "girls":
        return "feminino"
    if g.startswith("men") or g == "boys":
        return "masculino"
    return genero_raw


def _partes_categoria(header_texto):
    """O cabeçalho de cada grupo vem em dois formatos diferentes:
    adulto/master: "Women / Adult / Beginner / -55,0 kg" (gênero, categoria
    etária, nível e peso em segmentos separados); kids: "Boys [15-17 years]
    / Intermediate / -75,0 kg" (gênero e categoria etária colados no mesmo
    segmento, sem segmento de categoria etária separado)."""
    partes = [p.strip() for p in header_texto.split("/")]
    primeiro = partes[0] if partes else ""

    m_kids = re.match(r"(.+?)\s*\[(.*?)\]\s*$", primeiro)
    if m_kids:
        genero_raw, categoria_idade = m_kids.group(1).strip(), m_kids.group(2).strip()
        nivel = partes[1] if len(partes) > 1 else ""
        peso = partes[2] if len(partes) > 2 else ""
    else:
        genero_raw = primeiro
        categoria_idade = partes[1] if len(partes) > 1 else ""
        nivel = partes[2] if len(partes) > 2 else ""
        peso = partes[3] if len(partes) > 3 else ""

    if not peso and "absolute" in genero_raw.lower():
        peso = "Absoluto"

    return genero_raw, categoria_idade, nivel, peso


_ANO_NASCIMENTO = re.compile(r"\d{4}")


def _ano_nascimento_do_card(card):
    """A Smoothcomp parou de marcar essa célula com uma classe própria —
    agora só dá pra achar pelo rótulo "Chave" na tabela de detalhes do
    card (que também tem Age/Rank/Weight, sem classe que distinga uma
    linha da outra). Texto vem como "1996 (30 anos)"; ficamos só com o
    ano."""
    for th in card.select(".sc-card-footer th"):
        if th.get_text(strip=True) == "Chave":
            td = th.find_next_sibling("td")
            if td:
                m = _ANO_NASCIMENTO.search(td.get_text(strip=True))
                if m:
                    return m.group()
    return ""


def parse_atletas_html(html):
    soup = BeautifulSoup(html, "lxml")
    atletas = []
    for grupo in soup.select(".participant-group"):
        header = grupo.select_one(".group-name")
        if not header:
            continue
        genero_raw, categoria_idade, nivel, peso = _partes_categoria(header.get_text(strip=True))
        genero = _genero_pt(genero_raw)

        # ".profile-card" virou ".sc-card" numa atualização da Smoothcomp
        # (as classes internas, tipo ".profile-card-name", continuam as
        # mesmas) — aceita as duas por segurança, caso algum evento ainda
        # esteja na versão antiga.
        for card in grupo.select(".sc-card, .profile-card"):
            nome_el = card.select_one(".profile-card-name a span")
            if not nome_el:
                continue
            equipe_el = card.select_one(".sc-card-body-club a, .participant-td-club a")
            pais_el = card.select_one(".country-name span")
            aprovado = "unapproved" not in (card.get("class") or [])

            atletas.append({
                "federacao": "ADCC",
                "nome": nome_el.get_text(strip=True),
                "equipe": equipe_el.get_text(strip=True) if equipe_el else "",
                "categoria_idade": categoria_idade,
                "genero": genero,
                "peso": peso,
                "faixa": nivel,
                "pais": pais_el.get_text(strip=True) if pais_el else "",
                "ano_nascimento": _ano_nascimento_do_card(card),
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
    """Data da competição (pra calcular idade exata nela) — hoje se o
    evento não foi encontrado."""
    for evento in _ler_eventos():
        if evento["id"] == evento_id:
            data_evento = datas_mod.extrair_data(evento.get("data", ""))
            if data_evento:
                return data_evento
            break
    return date.today()


def idade_exata(data_nascimento, data_referencia):
    """Idade completa (anos) em data_referencia — diferente da idade "por
    ano" usada nas federações brasileiras, o ADCC categoriza pela idade
    exata no dia da competição (conta mês/dia de nascimento, não só o ano)."""
    anos = data_referencia.year - data_nascimento.year
    if (data_referencia.month, data_referencia.day) < (data_nascimento.month, data_nascimento.day):
        anos -= 1
    return anos


_KIDS_INTERVALO = re.compile(r"^(\d+)-(\d+)\s*years$", re.I)
_KIDS_ATE = re.compile(r"^(\d+)\s*and under$", re.I)
_MASTERS = re.compile(r"^Masters\s*(\d+)$", re.I)


_FAIXA_PT_PARA_EN = {
    "branca": "white", "cinza": "grey", "cinzenta": "grey",
    "amarela": "yellow", "laranja": "orange", "verde": "green",
    "azul": "blue", "roxa": "purple", "marrom": "brown", "preta": "black",
}

_NIVEIS_ADCC = {"beginner", "intermediate", "advanced"}

# Regras oficiais do ADCC (página "Divisions" do evento) — o corte de faixa
# pra cada nível muda por faixa etária: crianças (4-12), adolescentes
# (13-17) e adultos/masters (18+) têm cortes de faixa diferentes.
_REGRAS_FAIXA_ADCC = {
    "kids": {
        "beginner": {"white"},
        "intermediate": {"grey"},
        "advanced": {"yellow", "orange", "green", "blue", "purple", "brown", "black"},
    },
    "teen": {
        "beginner": {"white"},
        "intermediate": {"grey", "yellow"},
        "advanced": {"orange", "green", "blue", "purple", "brown", "black"},
    },
    "adulto": {
        "beginner": {"white"},
        "intermediate": {"blue", "purple"},
        "advanced": {"brown", "black"},
    },
}


def _faixa_etaria_regras(categoria_idade):
    """Em qual das 3 tabelas de corte de faixa (kids/teen/adulto) esse
    "categoria_idade" (ex: "9-10 years", "15-17 years", "Adult", "Masters
    35") se encaixa."""
    texto = (categoria_idade or "").strip()
    if texto.lower() == "adult" or _MASTERS.match(texto):
        return "adulto"

    m = _KIDS_INTERVALO.match(texto)
    if m:
        maximo = int(m.group(2))
    else:
        m2 = _KIDS_ATE.match(texto)
        maximo = int(m2.group(1)) if m2 else None

    if maximo is None:
        return None
    return "kids" if maximo <= 12 else "teen"


def faixa_combina(atleta, termo_busca):
    """Compara a faixa buscada (nome da faixa em PT/EN, ou o próprio nível
    Beginner/Intermediate/Advanced) com o nível em que o atleta está
    inscrito, usando a tabela de corte oficial do ADCC pra idade DELE — a
    mesma faixa de cor pode cair num nível diferente dependendo se é
    criança, adolescente ou adulto."""
    if not termo_busca:
        return True
    termo = termo_busca.strip().lower()
    nivel_atleta = (atleta.get("faixa") or "").strip().lower()

    if termo in _NIVEIS_ADCC:
        return nivel_atleta == termo

    faixa_en = _FAIXA_PT_PARA_EN.get(termo, termo)
    grupo_etario = _faixa_etaria_regras(atleta.get("categoria_idade"))
    if grupo_etario is None:
        return False

    for nivel, faixas in _REGRAS_FAIXA_ADCC[grupo_etario].items():
        if faixa_en in faixas:
            return nivel_atleta == nivel
    return False


def categoria_exata_para_idade(evento_id, idade, data_nascimento=None):
    """Descobre a categoria etária certa pra essa idade dentro das
    categorias que JÁ EXISTEM nessa competição especificamente (em vez de
    supor uma tabela fixa de regras do ADCC, que muda de evento pra
    evento) — usa os rótulos que o próprio Smoothcomp criou pros grupos
    dessa competição na hora da importação. `data_nascimento` não é usado
    aqui (existe só pra manter a mesma assinatura do conector AJP, que
    precisa do ano de nascimento exato pra resolver categorias tipo
    "Master N"/"Teen" a partir da tabela de idade da página do evento —
    o ADCC não tem esse problema porque usa "Masters 30/35/40", onde o
    número já é a própria idade)."""
    rotulos = {a["categoria_idade"] for a in buscar_atletas(evento_id, {}) if a.get("categoria_idade")}

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
    """Mesma lógica de categoria_exata_para_idade, só que pro peso: acha a
    faixa certa comparando com os pesos que já existem nessa competição
    pra esse gênero+categoria etária específicos (o ADCC é NO-GI, então o
    peso considerado é o peso real do atleta, sem kimono)."""
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
