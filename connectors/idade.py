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
