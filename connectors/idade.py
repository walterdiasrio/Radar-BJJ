"""Conversão de ano de nascimento para a categoria etária exata de cada
federação. As faixas de idade variam por federação, então uma mesma pessoa
pode cair em categorias com nomes diferentes dependendo de onde compete.

Todas usam a mesma fórmula ("idade do atleta" = ano da competição - ano de
nascimento, sem considerar o dia/mês exato) — é assim que essas federações
calculam a idade oficialmente.

Fontes (tabelas de peso/idade oficiais, 2026):
- CBJJ / FJJRio: seguem o padrão IBJJF/CBJJ. Tabela de peso 2026 da FJJRio
  (fjjrio.com.br, "Tabela de Pesos") traz o ano de nascimento por categoria;
  convertido aqui para faixas de idade (equivalente e independente do ano).
- CBJJD: tabela de peso oficial CBJJD/ISBJJA (cbjjd.com.br), edição jan/2026.
- CBJJO: tabela de peso oficial CBJJO válida a partir de 2026
  (cbjjo.com.br). Essa tabela não detalha subdivisões de Master para
  adultos — usamos a mesma convenção padrão (Master 1 a 6) por ser a
  praticada em todo o jiu-jitsu brasileiro; trate como aproximado até
  confirmar com uma checagem real aberta.
- CBJJC: "Tabela de Peso Com Kimono" oficial (cbjjc.com.br/tabela-de-peso-
  com-kimono, imagem lida manualmente em 18/08/2026 — sem link de texto/PDF
  disponível). Rótulos conferidos contra uma checagem real aberta (Brasileiro
  de Jiu-Jitsu 2026): batem exatamente, inclusive o hífen de "Infanto
  Juvenil-A/B" (a checagem usa espaço em vez de hífen, mas a comparação de
  categoria no site ignora essa diferença).
"""
from datetime import date

# Cada federação: lista de (idade_min, idade_max, "rótulo da categoria")
# em ordem crescente de idade. idade_max=None significa "sem limite superior".

_CBJJ_FJJRIO = [
    (4, 4, "Pré-Mirim 1"),
    (5, 5, "Pré-Mirim 2"),
    (6, 6, "Pré-Mirim 3"),
    (7, 7, "Mirim 1"),
    (8, 8, "Mirim 2"),
    (9, 9, "Mirim 3"),
    (10, 10, "Infantil 1"),
    (11, 11, "Infantil 2"),
    (12, 12, "Infantil 3"),
    (13, 13, "Infanto-Juvenil 1"),
    (14, 14, "Infanto-Juvenil 2"),
    (15, 15, "Infanto-Juvenil 3"),
    (16, 16, "Juvenil 1"),
    (17, 17, "Juvenil 2"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

_CBJJD = [
    (4, 4, "Pré-Mirim 1"),
    (5, 5, "Pré-Mirim 2"),
    (6, 6, "Pré-Mirim 3"),
    (7, 7, "Mirim 1"),
    (8, 8, "Mirim 2"),
    (9, 9, "Mirim 3"),
    (10, 10, "Infantil 1"),
    (11, 11, "Infantil 2"),
    (12, 12, "Infantil 3"),
    (13, 13, "Infanto 1"),
    (14, 14, "Infanto 2"),
    (15, 15, "Infanto 3"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

_CBJJO = [
    (4, 5, "Pré-Mirim"),
    (6, 7, "Mirim 1"),
    (8, 9, "Mirim 2"),
    (10, 11, "Infantil 1"),
    (12, 12, "Infantil 2"),
    (13, 13, "Infanto Juv 1"),
    (14, 14, "Infanto Juv 2"),
    (15, 15, "Infanto Juv 3"),
    (16, 17, "Juvenil"),
    # A tabela oficial de peso da CBJJO não detalha Master 1-6 para adultos;
    # usamos a convenção padrão do jiu-jitsu brasileiro como aproximação.
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]


# ---------------------------------------------------------------------------
# CBJJE — extraída ao vivo dos próprios dados de eventos (a API retorna
# from_age/to_age por categoria), não de uma tabela publicada; nomes e
# faixas conferidos em 3 eventos reais.
# ---------------------------------------------------------------------------
_CBJJE = [
    (4, 5, "Pré-Mirim"),
    (6, 7, "Mirim"),
    (8, 9, "Infantil A"),
    (10, 11, "Infantil B"),
    (12, 13, "Infanto Juvenil A"),
    (14, 15, "Infanto Juvenil B"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]


# ---------------------------------------------------------------------------
# FPJJ — nomes das categorias exatamente como aparecem nos dados reais dos
# inscritos (sem acento em "Pre Mirim", "Infanto A/B" ao invés de "Infanto
# Juvenil A/B"). FPJJ segue as regras da CBJJ, então as faixas de idade do
# Master seguem o mesmo padrão (30-35, 36-40, ...).
# ---------------------------------------------------------------------------
_FPJJ = [
    (4, 5, "Pre Mirim"),
    (6, 7, "Mirim"),
    (8, 9, "Infantil A"),
    (10, 11, "Infantil B"),
    (12, 13, "Infanto A"),
    (14, 15, "Infanto B"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

_CBJJC = [
    (4, 5, "Pré-Mirim"),
    (6, 7, "Mirim"),
    (8, 9, "Infantil-A"),
    (10, 11, "Infantil-B"),
    (12, 13, "Infanto Juvenil-A"),
    (14, 15, "Infanto Juvenil-B"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

# ---------------------------------------------------------------------------
# FJJEMG — rótulos exatamente como aparecem na checagem real (fjjemg.adm.br,
# ".categoria": "FAIXA: X | MIRIM A (6/7 anos) | ..."), incluindo "Pre-Mirim"
# sem acento (é assim que o próprio site escreve — "Pré-Mirim" não bateria,
# _combina_exata não ignora acento). Faixas em bandas de 2 anos (A/B pros
# grupos intermediários) até o Juvenil; do Adulto em diante segue o mesmo
# padrão Master 1-6 de 5 em 5 anos comum a todas as federações daqui
# (conferido contra a checagem real de um evento: Adulto 18-29, Master 1
# 30-35 ... Master 5 51-55 aparecem exatamente assim).
# ---------------------------------------------------------------------------
_FJJEMG = [
    (4, 5, "Pre-Mirim"),
    (6, 7, "Mirim A"),
    (8, 9, "Mirim B"),
    (10, 11, "Infantil"),
    (12, 13, "Infanto-Juvenil A"),
    (14, 15, "Infanto-Juvenil B"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

# ---------------------------------------------------------------------------
# FJJGO — rótulos exatamente como aparecem na checagem geral do
# SouCompetidor (soucompetidor.com.br) pro Campeonato Centro-Oeste
# Brasileiro de Jiu-Jitsu 2026: "MIRIM 2/3", "INFANTIL 1/2/3", "INF-JUV
# 1/2/3" (traduzido pra Infanto-Juvenil, ver fjjgo._traduzir_idade),
# "JUVENIL" sem separar 1/2 (diferente da CBJJ/FJJRio, que divide em Juvenil
# 1 e 2), "ADULTO", "MASTER 1" a "MASTER 5" (conferido ao vivo em
# 09/09/2026 — sem ninguém inscrito em Master 6 nesse evento pra confirmar,
# mas mantido pelo padrão comum a toda federação brasileira). Faixas de
# Pré-Mirim (4-6 anos) sem confirmação direta (poucos inscritos nessa idade
# no evento lido) — mantidas iguais à CBJJ/FJJRio por ser o padrão mais comum.
# ---------------------------------------------------------------------------
_FJJGO = [
    (4, 4, "Pré-Mirim 1"),
    (5, 5, "Pré-Mirim 2"),
    (6, 6, "Pré-Mirim 3"),
    (7, 7, "Mirim 1"),
    (8, 8, "Mirim 2"),
    (9, 9, "Mirim 3"),
    (10, 10, "Infantil 1"),
    (11, 11, "Infantil 2"),
    (12, 12, "Infantil 3"),
    (13, 13, "Infanto-Juvenil 1"),
    (14, 14, "Infanto-Juvenil 2"),
    (15, 15, "Infanto-Juvenil 3"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, 50, "Master 4"),
    (51, 55, "Master 5"),
    (56, None, "Master 6"),
]

# ---------------------------------------------------------------------------
# FCOJJ — tabela oficial do edital do Campeonato Brasiliense de Jiu-Jitsu
# 2026 (fcojj.com.br), Cláusula Terceira: ano de nascimento -> categoria por
# idade, calculado sobre 2026 (mesma fórmula usada aqui: idade = ano
# referência - ano nascimento). Segue o padrão AJP (o próprio edital diz
# seguir "os parâmetros estabelecidos pela AJP") — mas com faixas etárias
# nomeadas diferente: Kids 1/2/3 (não "Kids N" corrido), Infantil/Júnior/
# Adolescente/Juvenil (uma faixa cada, sem subdivisão numérica) e só até
# Master 4 (46 anos+, sem limite superior definido no edital — diferente do
# Master 6 comum nas federações CBJJ). "Júnior" com acento porque
# fcojj._IDADE_LABEL (que traduz o rótulo bruto da API MartialMatch)
# usa a mesma grafia.
# ---------------------------------------------------------------------------
_FCOJJ = [
    (4, 5, "Kids 1"),
    (6, 7, "Kids 2"),
    (8, 9, "Kids 3"),
    (10, 11, "Infantil"),
    (12, 13, "Júnior"),
    (14, 15, "Adolescente"),
    (16, 17, "Juvenil"),
    (18, 29, "Adulto"),
    (30, 35, "Master 1"),
    (36, 40, "Master 2"),
    (41, 45, "Master 3"),
    (46, None, "Master 4"),
]

TABELAS = {
    "cbjj": _CBJJ_FJJRIO,
    "fjjrio": _CBJJ_FJJRIO,
    "cbjjd": _CBJJD,
    "cbjjo": _CBJJO,
    "cbjje": _CBJJE,
    "fpjj": _FPJJ,
    "cbjjc": _CBJJC,
    # FJJPE: o próprio PDF de tabela de peso da federação (fjjpe.com.br)
    # se identifica como "TABELA OFICIAL CBJJ/IBJJF" — mesmas faixas de
    # idade e nomes de categoria da CBJJ/FJJRio (conferido contra a
    # checagem real de dois eventos: Juvenil 1/2, Adulto, Master 1-6 no
    # masculino adulto; Pré-Mirim a Infanto-Juvenil nos kids — batem
    # exatamente). O conector normaliza o texto sem acento do site
    # ("PRE MIRIM 1") para esses rótulos (ver fjjpe._idade_normalizada).
    "fjjpe": _CBJJ_FJJRIO,
    "fjjemg": _FJJEMG,
    "fjjgo": _FJJGO,
    "fcojj": _FCOJJ,
    # FJJPR: faixas etárias idênticas à CBJJE (Pré-Mirim 4-5, Mirim 6-7,
    # Infantil A/B 8-9/10-11, Infanto Juvenil A/B 12-13/14-15, Juvenil
    # 16-17, Adulto, Master 1-6 — conferido ao vivo contra a lista real de
    # atletas). O site usa os mesmos nomes sem acento ("Pre Mirim"),
    # normalizados pro conector antes de chegar aqui (ver
    # connectors/fjjpr.py::_IDADE_NORMALIZADA).
    "fjjpr": _CBJJE,
    # FJJPA: faixas etárias idênticas à CBJJE (Pré-Mirim 4-5, Mirim 6-7,
    # Infantil A/B 8-9/10-11, Infanto Juvenil A/B 12-13/14-15, Juvenil
    # 16-17, Adulto, Master 1-6 — conferido ao vivo: idade 42 caiu em
    # "MASTER 3 / MASTER 4" na checagem real, que bate com Master 3 na
    # _CBJJE). O site agrupa os Masters em pares ("Master 1 / Master 2"),
    # normalizado pro rótulo individual exato dentro do conector antes de
    # chegar aqui (ver connectors/fjjpa.py::_master_exato).
    "fjjpa": _CBJJE,
    # FJJ-RS: checagem real usa bandas de 2 anos (Pré-Mirim, Mirim,
    # Infantil A/B, Infanto Juvenil A/B, Juvenil, Adulto, Master 1-6) —
    # mesmas faixas da _CBJJE, apesar do edital citar as regras da CBJJ
    # nacional pro resto (peso, regulamento). Normalizado no conector
    # antes de chegar aqui (ver connectors/fjjrs.py::_normalizar_idade).
    "fjjrs": _CBJJE,
    # FBJJMMA: a própria checagem real já mostra o intervalo de idade
    # entre parênteses (ex: "INFANTIL A (8 E 9 ANOS)", "MASTER 3 (41 A 45
    # ANOS)") — conferido ao vivo, bate exatamente com as faixas da
    # _CBJJE, sem precisar supor nada.
    "fbjjmma": _CBJJE,
}


def idade_a_partir_do_ano(ano_nascimento, ano_referencia=None):
    ano_referencia = ano_referencia or date.today().year
    return ano_referencia - ano_nascimento


def categoria_para(federacao, ano_nascimento, ano_referencia=None):
    """Retorna o nome da categoria etária (para usar como filtro de texto)
    correspondente ao ano de nascimento informado, segundo as regras da
    federação. Retorna None se a idade não se encaixa em nenhuma faixa
    conhecida (ex: ano de nascimento inválido)."""
    tabela = TABELAS.get(federacao)
    if not tabela:
        return None
    idade = idade_a_partir_do_ano(ano_nascimento, ano_referencia)
    for idade_min, idade_max, rotulo in tabela:
        if idade < idade_min:
            continue
        if idade_max is None or idade <= idade_max:
            return rotulo
    return None
