"""Conversão de peso (kg) para a categoria de peso exata de cada federação.

As faixas de peso variam por federação, idade (cada ano de idade tem sua
própria tabela nas categorias de base/kids) e gênero (a partir do Juvenil).
Aqui usamos sempre a idade exata do atleta (não o rótulo da categoria etária)
para evitar ambiguidade — em algumas federações (ex: CBJJD) uma mesma
categoria etária ("Mirim") cobre várias idades com tabelas de peso diferentes.

Fontes oficiais (tabelas de peso vigentes, 2026):
- CBJJ / FJJRio: "Tabela de Pesos" 2026 da FJJRio (fjjrio.com.br), que segue
  o padrão IBJJF/CBJJ — conferido também contra dados reais de atletas do
  CBJJ (categorias e pesos batem).
- CBJJD: tabela de peso oficial CBJJD/ISBJJA (cbjjd.com.br), edição jan/2026.
- CBJJO: tabela de peso oficial CBJJO válida a partir de 2026
  (cbjjo.com.br). Não cobrimos a categoria "Ligeiro" (uma subdivisão rara
  abaixo de Galo, disponível só para Infantil 1 e Juvenil Masculino).
- CBJJE: "Tabela de Peso Com Kimono 2026" oficial (cbjje.com.br/?p=tabela-de-peso).
- FPJJ: tabelas oficiais publicadas em fpjjcompetidor.com.br (kids até 15
  anos, e Juvenil/Adulto/Master). As categorias de base da FPJJ têm até 9
  subdivisões extras de "Pesadíssimo" (Pesadíssimo A, B, C...) para crianças
  fora da curva — não cobrimos essas subdivisões raras, ficam todas dentro
  de "Pesadíssimo" (aberto). Nem toda categoria de peso existe em toda idade
  (ex: não tem "Galo" para Mirim) — nesse caso o peso mais leve disponível
  absorve os atletas mais leves.

- CBJJC: "Tabela de Peso Com Kimono" oficial (cbjjc.com.br/tabela-de-peso-
  com-kimono, imagem lida manualmente em 18/08/2026). Categorias em faixas
  de 2 anos (não uma tabela por idade exata como as outras), com peso
  diferente por gênero desde a categoria de base (Pré-Mirim) — por isso usa
  o mesmo esquema de tabela explícita da CBJJE/FPJJ em vez do helper
  unissex `_tabela()`. "Pesadíssimo" tem limite fechado nas categorias de
  base (kids/juvenil) e um "Extra pesadíssimo" aberto acima dele — nas
  outras federações essas duas viram uma coisa só (o pesadíssimo já é
  aberto). Adulto feminino não tem categoria "Galo" (a mais leve é Pluma).

Master sempre usa a mesma tabela de peso do Adulto (todas as federações).
"""

# nome da categoria de peso -> limite máximo em kg (None = sem limite / Pesadíssimo)
_ORDEM_PESO = [
    "Galo", "Pluma", "Pena", "Leve", "Médio",
    "Meio-Pesado", "Pesado", "Super-Pesado", "Pesadíssimo",
]


def _tabela(galo, pluma, pena, leve, medio, meio_pesado, pesado, super_pesado, sem_pesadissimo=False):
    limites = [galo, pluma, pena, leve, medio, meio_pesado, pesado, super_pesado]
    pares = list(zip(_ORDEM_PESO, limites))
    if sem_pesadissimo:
        pares.append(("Super-Pesado", None))  # quem passa do super-pesado ainda é "Super-Pesado" (sem limite)
    else:
        pares.append(("Pesadíssimo", None))
    return pares


# ---------------------------------------------------------------------------
# CBJJ / FJJRio (padrão IBJJF/CBJJ)
# ---------------------------------------------------------------------------
_CBJJ_FJJRIO_UNISSEX_POR_IDADE = {
    4: _tabela(12.0, 14.7, 18.0, 21.0, 24.0, 27.0, 30.0, 33.0),
    5: _tabela(14.7, 17.9, 20.0, 24.0, 26.0, 29.0, 32.0, 35.0),
    6: _tabela(17.9, 18.9, 22.0, 25.0, 28.0, 31.2, 34.2, 37.2),
    7: _tabela(18.2, 21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3),
    8: _tabela(21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3),
    9: _tabela(24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3),
    10: _tabela(27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3),
    11: _tabela(30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3, 51.5),
    12: _tabela(32.2, 36.2, 40.3, 44.3, 48.3, 52.5, 56.5, 60.5),
    13: _tabela(36.2, 40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0),
    14: _tabela(40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0),
    15: _tabela(44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0, 73.0),
}

_CBJJ_FJJRIO_JUVENIL_MASC = {
    16: _tabela(48.5, 53.5, 58.5, 64.0, 69.0, 74.0, 79.3, 84.3),
    17: _tabela(53.5, 58.5, 64.0, 69.0, 74.0, 79.3, 84.3, 89.3),
}
_CBJJ_FJJRIO_JUVENIL_FEM = _tabela(44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0, None, sem_pesadissimo=True)
_CBJJ_FJJRIO_ADULTO_MASC = _tabela(57.5, 64.0, 70.0, 76.0, 82.3, 88.3, 94.3, 100.5)
_CBJJ_FJJRIO_ADULTO_FEM = _tabela(48.5, 53.5, 58.5, 64.0, 69.0, 74.0, 79.3, None, sem_pesadissimo=True)


def _cbjj_fjjrio(idade, genero):
    if idade <= 15:
        return _CBJJ_FJJRIO_UNISSEX_POR_IDADE.get(min(idade, 15) if idade >= 4 else 4)
    if idade in (16, 17):
        return _CBJJ_FJJRIO_JUVENIL_FEM if genero == "feminino" else _CBJJ_FJJRIO_JUVENIL_MASC[idade]
    return _CBJJ_FJJRIO_ADULTO_FEM if genero == "feminino" else _CBJJ_FJJRIO_ADULTO_MASC


# Tabela de peso Sem Kimono (No-Gi) pra idade de base/kids — bem mais leve
# que a tabela Com Kimono acima (ex: "Pesado" do Mirim 3 vai até 40,90kg
# aqui, contra 42,3kg na tabela de Kimono), confirmada em 23/08/2026 lendo
# ao vivo as categorias do Campeonato Brasileiro de Jiu-Jitsu Sem Kimono
# (idade 04 a 15 anos) 2026 (cbjj.com.br/events/3368/athletes-list-by-
# divisions) — igual à tabela de Kimono, kids são unissex (só a partir do
# Juvenil o peso passa a diferenciar por gênero). Idade 7-15 tem cobertura
# real; os poucos valores sem nenhum atleta inscrito nesse evento foram
# preenchidos batendo com o valor equivalente numa idade vizinha (o
# "Pesado" de uma idade é sempre igual ao "Super-Pesado" da idade anterior,
# um padrão confirmado em toda a tabela onde os dois existiam) — marcados
# abaixo com # inferido. Sem dado nenhum pra Pré-Mirim (4-6 anos, poucos
# inscritos nesse evento pra confirmar) nem pra Juvenil/Adulto Sem Kimono —
# essas idades continuam caindo na tabela de Kimono (ver _cbjj_fjjrio_sem_kimono).
_CBJJ_FJJRIO_SEM_KIMONO_POR_IDADE = {
    7: _tabela(17.7, 19.7, 22.7, 25.7, 28.8, 31.8, 34.8, 37.9),  # Pesado inferido
    8: _tabela(19.7, 22.7, 25.7, 28.8, 31.8, 34.8, 37.9, 40.9),  # Super-Pesado inferido
    9: _tabela(22.7, 25.7, 28.8, 31.8, 34.8, 37.9, 40.9, 43.9),  # Super-Pesado inferido
    10: _tabela(25.7, 28.8, 31.8, 34.8, 37.9, 40.9, 43.9, 46.9),  # Galo inferido
    11: _tabela(28.8, 31.8, 34.8, 37.9, 40.9, 43.9, 46.9, 50.0),
    12: _tabela(30.8, 34.8, 38.9, 42.9, 46.9, 51.0, 55.0, 59.0),
    13: _tabela(34.8, 38.9, 42.9, 46.9, 51.0, 55.0, 59.0, 63.0),
    14: _tabela(38.9, 42.9, 46.9, 51.0, 55.0, 59.0, 63.0, 67.0),
    15: _tabela(42.9, 46.9, 51.0, 55.0, 59.0, 63.0, 67.0, 71.0),
}


def _cbjj_fjjrio_sem_kimono(idade, genero):
    return _CBJJ_FJJRIO_SEM_KIMONO_POR_IDADE.get(idade) or _cbjj_fjjrio(idade, genero)


# ---------------------------------------------------------------------------
# CBJJD
# ---------------------------------------------------------------------------
_CBJJD_UNISSEX_POR_IDADE = {
    6: _tabela(16.0, 18.9, 22.0, 25.0, 28.0, 31.2, 34.2, 37.2),
    7: _tabela(18.0, 21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3),
    8: _tabela(21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3),
    9: _tabela(24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3),
    10: _tabela(27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3),
    11: _tabela(30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3, 51.5),
    12: _tabela(33.2, 36.2, 40.3, 44.3, 48.3, 52.5, 56.5, 60.5),
    13: _tabela(36.2, 40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0),
    14: _tabela(40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0),
    15: _tabela(44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0, 73.0),
}
_CBJJD_JUVENIL_MASC = _tabela(53.0, 58.0, 64.0, 69.0, 74.0, 79.0, 84.0, 89.0)
_CBJJD_JUVENIL_FEM = _tabela(44.0, 48.0, 52.0, 56.0, 60.0, 65.0, 69.0, 73.0)
_CBJJD_ADULTO_MASC = _tabela(57.0, 64.0, 70.0, 76.0, 82.0, 88.0, 94.0, 102.0)
_CBJJD_ADULTO_FEM = _tabela(48.0, 53.0, 58.0, 64.0, 69.0, 74.0, 79.0, 84.0)


def _cbjjd(idade, genero):
    if idade <= 15:
        return _CBJJD_UNISSEX_POR_IDADE.get(min(idade, 15) if idade >= 6 else 6)
    if idade in (16, 17):
        return _CBJJD_JUVENIL_FEM if genero == "feminino" else _CBJJD_JUVENIL_MASC
    return _CBJJD_ADULTO_FEM if genero == "feminino" else _CBJJD_ADULTO_MASC


# ---------------------------------------------------------------------------
# CBJJO
# ---------------------------------------------------------------------------
_CBJJO_POR_IDADE_UNISSEX = {
    4: _tabela(14.7, 17.9, 20.0, 24.0, 26.0, 29.0, 32.0, 35.0),
    5: _tabela(14.7, 17.9, 20.0, 24.0, 26.0, 29.0, 32.0, 35.0),
    6: _tabela(18.9, 21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3),
    7: _tabela(18.9, 21.0, 24.0, 27.0, 30.2, 33.2, 36.2, 39.3),
    8: _tabela(24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3),
    9: _tabela(24.0, 27.0, 30.2, 33.2, 36.2, 39.3, 42.3, 45.3),
    10: _tabela(30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3, 51.5),
    11: _tabela(30.2, 33.2, 36.2, 39.3, 42.3, 45.3, 48.3, 51.5),
    12: _tabela(32.2, 36.2, 39.3, 42.3, 45.3, 48.3, 52.5, 56.5),
    13: _tabela(36.2, 40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0),
    14: _tabela(40.3, 44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0),
    15: _tabela(44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0, 73.0),
}
_CBJJO_JUVENIL_FEM = _tabela(44.3, 48.3, 52.5, 56.5, 60.5, 65.0, 69.0, 73.0)
_CBJJO_JUVENIL_MASC = _tabela(53.5, 58.5, 64.0, 69.0, 74.0, 79.3, 84.3, 89.3)
_CBJJO_ADULTO_MASC = _tabela(57.5, 64.0, 70.0, 76.0, 82.3, 88.3, 94.3, 100.5)
_CBJJO_ADULTO_FEM = _tabela(48.5, 53.5, 58.5, 64.0, 69.0, 74.0, 79.3, 84.3)


def _cbjjo(idade, genero):
    if idade <= 15:
        return _CBJJO_POR_IDADE_UNISSEX.get(min(idade, 15) if idade >= 4 else 4)
    if idade in (16, 17):
        return _CBJJO_JUVENIL_FEM if genero == "feminino" else _CBJJO_JUVENIL_MASC
    return _CBJJO_ADULTO_FEM if genero == "feminino" else _CBJJO_ADULTO_MASC



# ---------------------------------------------------------------------------
# CBJJE — vai até "Extra Pesadíssimo 3" nas categorias de base (kids), então
# usa sua própria função de tabela em vez de _tabela() (que só cobre até
# Pesadíssimo).
# ---------------------------------------------------------------------------
def _tabela_cbjje(*pares):
    """pares = nome, limite, nome, limite, ..., último limite deve ser None."""
    return list(zip(pares[0::2], pares[1::2]))


_CBJJE_POR_IDADE = {
    4: {
        "masculino": _tabela_cbjje("Galo", 17, "Pluma", 19, "Pena", 22, "Leve", 25, "Médio", 28.3,
                                    "Meio Pesado", 31.3, "Pesado", 34.5, "Super Pesado", 37.5,
                                    "Pesadíssimo", 42.5, "Extra Pesadíssimo", 45,
                                    "Extra Pesadíssimo 2", 49, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 15, "Pluma", 17, "Pena", 20, "Leve", 23, "Médio", 26,
                                   "Meio Pesado", 29.5, "Pesado", 32.3, "Super Pesado", 35.3,
                                   "Pesadíssimo", 38.5, "Extra Pesadíssimo", 43,
                                   "Extra Pesadíssimo 2", 47, "Extra Pesadíssimo 3", None),
    },
    6: {
        "masculino": _tabela_cbjje("Galo", 18, "Pluma", 20, "Pena", 23, "Leve", 26, "Médio", 29.3,
                                    "Meio Pesado", 32.3, "Pesado", 35.5, "Super Pesado", 38.5,
                                    "Pesadíssimo", 44, "Extra Pesadíssimo", 50,
                                    "Extra Pesadíssimo 2", 56, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 16, "Pluma", 18, "Pena", 21, "Leve", 24, "Médio", 27,
                                   "Meio Pesado", 30.5, "Pesado", 33.3, "Super Pesado", 36.3,
                                   "Pesadíssimo", 40, "Extra Pesadíssimo", 44,
                                   "Extra Pesadíssimo 2", 48, "Extra Pesadíssimo 3", None),
    },
    8: {
        "masculino": _tabela_cbjje("Galo", 23, "Pluma", 26, "Pena", 29.3, "Leve", 32.3, "Médio", 35.5,
                                    "Meio Pesado", 38.5, "Pesado", 41.7, "Super Pesado", 44.7,
                                    "Pesadíssimo", 50, "Extra Pesadíssimo", 57,
                                    "Extra Pesadíssimo 2", 64, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 18, "Pluma", 20, "Pena", 23, "Leve", 26, "Médio", 29.3,
                                   "Meio Pesado", 32.3, "Pesado", 35.5, "Super Pesado", 38.5,
                                   "Pesadíssimo", 42.5, "Extra Pesadíssimo", 46.5,
                                   "Extra Pesadíssimo 2", 52, "Extra Pesadíssimo 3", None),
    },
    10: {
        "masculino": _tabela_cbjje("Galo", 29.3, "Pluma", 32.3, "Pena", 35.5, "Leve", 38.5, "Médio", 41.7,
                                    "Meio Pesado", 44.7, "Pesado", 47.7, "Super Pesado", 51,
                                    "Pesadíssimo", 55, "Extra Pesadíssimo", 60,
                                    "Extra Pesadíssimo 2", 67, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 23, "Pluma", 26, "Pena", 29.3, "Leve", 32.3, "Médio", 35.5,
                                   "Meio Pesado", 38.5, "Pesado", 41.7, "Super Pesado", 44.7,
                                   "Pesadíssimo", 48, "Extra Pesadíssimo", 53,
                                   "Extra Pesadíssimo 2", 60, "Extra Pesadíssimo 3", None),
    },
    12: {
        "masculino": _tabela_cbjje("Galo", 34.5, "Pluma", 38.5, "Pena", 42.7, "Leve", 46.7, "Médio", 51,
                                    "Meio Pesado", 55.5, "Pesado", 59.5, "Super Pesado", 63.5,
                                    "Pesadíssimo", 67.5, "Extra Pesadíssimo", 71,
                                    "Extra Pesadíssimo 2", 78, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 29.3, "Pluma", 32.3, "Pena", 35.5, "Leve", 38.5, "Médio", 41.7,
                                   "Meio Pesado", 44.7, "Pesado", 47.7, "Super Pesado", 51,
                                   "Pesadíssimo", 55, "Extra Pesadíssimo", 59,
                                   "Extra Pesadíssimo 2", 65, "Extra Pesadíssimo 3", None),
    },
    14: {
        "masculino": _tabela_cbjje("Galo", 44, "Pluma", 48, "Pena", 52.5, "Leve", 56.5, "Médio", 60.5,
                                    "Meio Pesado", 64.5, "Pesado", 69, "Super Pesado", 73,
                                    "Pesadíssimo", 77, "Extra Pesadíssimo", 82,
                                    "Extra Pesadíssimo 2", 90, "Extra Pesadíssimo 3", None),
        "feminino": _tabela_cbjje("Galo", 35.5, "Pluma", 39.5, "Pena", 43.7, "Leve", 48, "Médio", 52.5,
                                   "Meio Pesado", 56.5, "Pesado", 60.5, "Super Pesado", 65,
                                   "Pesadíssimo", 69, "Extra Pesadíssimo", 73,
                                   "Extra Pesadíssimo 2", 79, "Extra Pesadíssimo 3", None),
    },
    16: {
        "masculino": _tabela_cbjje("Pluma", 58.5, "Pena", 64, "Leve", 69, "Médio", 74, "Meio Pesado", 79.3,
                                    "Pesado", 84.3, "Super Pesado", 89.3, "Pesadíssimo", None),
        "feminino": _tabela_cbjje("Galo", 43.7, "Pluma", 48, "Pena", 52.5, "Leve", 56.5, "Médio", 60.5,
                                   "Meio Pesado", 65, "Pesado", 69, "Super Pesado", 73, "Pesadíssimo", None),
    },
}

_CBJJE_ADULTO_MASTER = {
    "masculino": _tabela_cbjje("Galo", 58, "Pluma", 64, "Pena", 70, "Leve", 76, "Médio", 82.3,
                                "Meio Pesado", 88.3, "Pesado", 94.3, "Super Pesado", 100.5, "Pesadíssimo", None),
    "feminino": _tabela_cbjje("Pluma", 53.5, "Pena", 58.5, "Leve", 64, "Médio", 69,
                               "Meio Pesado", 74, "Pesado", 80, "Super Pesado", 85, "Pesadíssimo", None),
}


def _cbjje(idade, genero):
    genero_chave = "feminino" if genero == "feminino" else "masculino"
    if idade >= 18:
        return _CBJJE_ADULTO_MASTER[genero_chave]
    chaves_validas = [k for k in _CBJJE_POR_IDADE if k <= idade]
    if not chaves_validas:
        return None
    return _CBJJE_POR_IDADE[max(chaves_validas)][genero_chave]



# ---------------------------------------------------------------------------
# FPJJ — nem toda idade tem todas as categorias de peso (ex: sem "Galo" até
# os 13 anos), então cada tabela só lista as classes que realmente existem.
# ---------------------------------------------------------------------------
def _tabela_fpjj(*pares):
    return list(zip(pares[0::2], pares[1::2]))


_FPJJ_POR_IDADE = {
    4: {
        "masculino": _tabela_fpjj("Pluma", 14, "Leve", 18, "Meio-Pesado", 22, "Super-Pesado", 26, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Pluma", 14, "Leve", 18, "Meio-Pesado", 22, "Super-Pesado", 26, "Pesadissimo", None),
    },
    6: {
        "masculino": _tabela_fpjj("Pluma", 22, "Pena", 24, "Leve", 26, "Medio", 28.5, "Meio-Pesado", 30,
                                   "Pesado", 32.5, "Super-Pesado", 34, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Pluma", 20, "Leve", 24, "Meio-Pesado", 28, "Super-Pesado", 32, "Pesadissimo", None),
    },
    8: {
        "masculino": _tabela_fpjj("Pluma", 28, "Pena", 30.5, "Leve", 33, "Medio", 35.5, "Meio-Pesado", 38,
                                   "Pesado", 41.5, "Super-Pesado", 43, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Pluma", 24, "Leve", 29, "Meio-Pesado", 33, "Super-Pesado", 38, "Pesadissimo", None),
    },
    10: {
        "masculino": _tabela_fpjj("Pluma", 34, "Pena", 37, "Leve", 39, "Medio", 41.5, "Meio-Pesado", 44,
                                   "Pesado", 46.5, "Super-Pesado", 49, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Pluma", 28, "Leve", 33, "Meio-Pesado", 38, "Super-Pesado", 43, "Pesadissimo", None),
    },
    12: {
        "masculino": _tabela_fpjj("Pluma", 40, "Pena", 42.5, "Leve", 45, "Medio", 47.5, "Meio-Pesado", 50,
                                   "Pesado", 52.5, "Super-Pesado", 55, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Pluma", 33, "Leve", 38, "Meio-Pesado", 43, "Super-Pesado", 48, "Pesadissimo", None),
    },
    14: {
        "masculino": _tabela_fpjj("Galo", 44, "Pluma", 48, "Pena", 52, "Leve", 56, "Medio", 60,
                                   "Meio-Pesado", 64, "Pesado", 68, "Super-Pesado", 72.5, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Galo", 35, "Pluma", 39, "Pena", 43, "Leve", 47, "Medio", 51,
                                  "Meio-Pesado", 55, "Pesado", 59, "Super-Pesado", 63.5, "Pesadissimo", None),
    },
    16: {
        "masculino": _tabela_fpjj("Galo", 53.5, "Pluma", 59, "Pena", 64, "Leve", 69, "Medio", 74.3,
                                   "Meio-Pesado", 79.3, "Pesado", 84.3, "Super-Pesado", 89.5, "Pesadissimo", None),
        "feminino": _tabela_fpjj("Galo", 44, "Pluma", 48, "Pena", 52, "Leve", 56, "Medio", 60,
                                  "Meio-Pesado", 64, "Pesado", 68, "Super-Pesado", 72.5, "Pesadissimo", None),
    },
}

_FPJJ_ADULTO_MASTER = {
    "masculino": _tabela_fpjj("Galo", 57.5, "Pluma", 64, "Pena", 70, "Leve", 76, "Medio", 82.3,
                               "Meio-Pesado", 88.3, "Pesado", 94.3, "Super-Pesado", 100.5, "Pesadissimo", None),
    "feminino": _tabela_fpjj("Galo", 48.5, "Pluma", 53.5, "Pena", 58.5, "Leve", 64, "Medio", 69,
                              "Meio-Pesado", 74, "Pesado", 79.3, "Super-Pesado", 84.3, "Pesadissimo", None),
}


def _fpjj(idade, genero):
    genero_chave = "feminino" if genero == "feminino" else "masculino"
    if idade >= 18:
        return _FPJJ_ADULTO_MASTER[genero_chave]
    chaves_validas = [k for k in _FPJJ_POR_IDADE if k <= idade]
    if not chaves_validas:
        return None
    return _FPJJ_POR_IDADE[max(chaves_validas)][genero_chave]


# ---------------------------------------------------------------------------
# CBJJC
# ---------------------------------------------------------------------------
def _tabela_cbjjc(*pares):
    return list(zip(pares[0::2], pares[1::2]))


_CBJJC_POR_IDADE = {
    4: {
        "masculino": _tabela_cbjjc("Galo", 17, "Pluma", 19, "Pena", 22, "Leve", 25, "Médio", 28.3,
                                    "Meio Pesado", 31.3, "Pesado", 34.5, "Super Pesado", 37.5,
                                    "Pesadíssimo", 42.5, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 15, "Pluma", 17, "Pena", 20, "Leve", 23, "Médio", 26,
                                   "Meio Pesado", 29.5, "Pesado", 32.3, "Super Pesado", 35.3,
                                   "Pesadíssimo", 38.5, "Extra Pesadíssimo", None),
    },
    6: {
        "masculino": _tabela_cbjjc("Galo", 18, "Pluma", 20, "Pena", 23, "Leve", 26, "Médio", 29.3,
                                    "Meio Pesado", 32.3, "Pesado", 35.5, "Super Pesado", 38.5,
                                    "Pesadíssimo", 44, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 16, "Pluma", 18, "Pena", 21, "Leve", 24, "Médio", 27,
                                   "Meio Pesado", 30.5, "Pesado", 33.3, "Super Pesado", 36.3,
                                   "Pesadíssimo", 40, "Extra Pesadíssimo", None),
    },
    8: {
        "masculino": _tabela_cbjjc("Galo", 23, "Pluma", 26, "Pena", 29.3, "Leve", 32.3, "Médio", 35.5,
                                    "Meio Pesado", 38.5, "Pesado", 41.7, "Super Pesado", 44.7,
                                    "Pesadíssimo", 48, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 18, "Pluma", 20, "Pena", 23, "Leve", 26, "Médio", 29.3,
                                   "Meio Pesado", 32.3, "Pesado", 35.5, "Super Pesado", 38.5,
                                   "Pesadíssimo", 44, "Extra Pesadíssimo", None),
    },
    10: {
        "masculino": _tabela_cbjjc("Galo", 29.3, "Pluma", 32.3, "Pena", 35.5, "Leve", 38.5, "Médio", 41.7,
                                    "Meio Pesado", 44.7, "Pesado", 47.7, "Super Pesado", 51,
                                    "Pesadíssimo", 55, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 23, "Pluma", 26, "Pena", 29.3, "Leve", 32.3, "Médio", 35.5,
                                   "Meio Pesado", 38.5, "Pesado", 41.7, "Super Pesado", 44.7,
                                   "Pesadíssimo", 48, "Extra Pesadíssimo", None),
    },
    12: {
        "masculino": _tabela_cbjjc("Galo", 34.5, "Pluma", 38.5, "Pena", 42.7, "Leve", 46.7, "Médio", 51,
                                    "Meio Pesado", 55.5, "Pesado", 59.5, "Super Pesado", 63.5,
                                    "Pesadíssimo", 67.5, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 29.3, "Pluma", 32.3, "Pena", 35.5, "Leve", 38.5, "Médio", 41.7,
                                   "Meio Pesado", 44.7, "Pesado", 47.7, "Super Pesado", 51,
                                   "Pesadíssimo", 55, "Extra Pesadíssimo", None),
    },
    14: {
        "masculino": _tabela_cbjjc("Galo", 44, "Pluma", 48, "Pena", 52.5, "Leve", 56.5, "Médio", 60.5,
                                    "Meio Pesado", 64.5, "Pesado", 69, "Super Pesado", 73,
                                    "Pesadíssimo", 77, "Extra Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 35.5, "Pluma", 39.5, "Pena", 43.7, "Leve", 48, "Médio", 52.5,
                                   "Meio Pesado", 56.5, "Pesado", 60.5, "Super Pesado", 65,
                                   "Pesadíssimo", 69, "Extra Pesadíssimo", None),
    },
    16: {
        "masculino": _tabela_cbjjc("Galo", 53.5, "Pluma", 58.5, "Pena", 64, "Leve", 69, "Médio", 74,
                                    "Meio Pesado", 79.3, "Pesado", 84.3, "Super Pesado", 89.3,
                                    "Pesadíssimo", None),
        "feminino": _tabela_cbjjc("Galo", 43.7, "Pluma", 48, "Pena", 52.5, "Leve", 56.5, "Médio", 60.5,
                                   "Meio Pesado", 65, "Pesado", 69, "Super Pesado", 73,
                                   "Pesadíssimo", None),
    },
}

_CBJJC_ADULTO_MASTER = {
    "masculino": _tabela_cbjjc("Galo", 58, "Pluma", 64, "Pena", 70, "Leve", 76, "Médio", 82.3,
                                "Meio Pesado", 88.3, "Pesado", 94.3, "Super Pesado", 100.5,
                                "Pesadíssimo", None),
    "feminino": _tabela_cbjjc("Pluma", 53.5, "Pena", 58.5, "Leve", 64, "Médio", 69,
                               "Meio Pesado", 74, "Pesado", 80, "Super Pesado", 85,
                               "Pesadíssimo", None),
}


def _cbjjc(idade, genero):
    genero_chave = "feminino" if genero == "feminino" else "masculino"
    if idade >= 18:
        return _CBJJC_ADULTO_MASTER[genero_chave]
    chaves_validas = [k for k in _CBJJC_POR_IDADE if k <= idade]
    if not chaves_validas:
        return None
    return _CBJJC_POR_IDADE[max(chaves_validas)][genero_chave]


_FUNCOES = {
    "cbjj": _cbjj_fjjrio,
    "fjjrio": _cbjj_fjjrio,
    "cbjjd": _cbjjd,
    "cbjjo": _cbjjo,
    "cbjje": _cbjje,
    "fpjj": _fpjj,
    "cbjjc": _cbjjc,
    # FJJPE segue a "TABELA OFICIAL CBJJ/IBJJF" (rótulo do próprio PDF de
    # peso da federação) — reaproveita a mesma tabela da CBJJ/FJJRio.
    "fjjpe": _cbjj_fjjrio,
}

# Federações onde já confirmamos que a competição Sem Kimono usa uma tabela
# de peso diferente da de Kimono (ver _cbjj_fjjrio_sem_kimono) — as demais
# não têm essa tabela levantada ainda, então continuam usando a de Kimono
# mesmo em evento Sem Kimono (mesmo comportamento de antes, não piora nada;
# só corrige o que já foi confirmado).
_FUNCOES_SEM_KIMONO = {
    "cbjj": _cbjj_fjjrio_sem_kimono,
    "fjjrio": _cbjj_fjjrio_sem_kimono,
    "fjjpe": _cbjj_fjjrio_sem_kimono,
}


def categoria_peso_para(federacao, idade, peso_kg, genero="", sem_kimono=False):
    """Retorna o nome da categoria de peso (ex: "Leve") para o peso (kg)
    informado, dada a idade exata do atleta e seu gênero. genero deve ser
    "masculino" ou "feminino" (para idade >= 16); se vazio, assume masculino.
    sem_kimono=True usa a tabela de peso Sem Kimono da federação, se já
    tivermos uma cadastrada (ver _FUNCOES_SEM_KIMONO)."""
    funcao = (_FUNCOES_SEM_KIMONO.get(federacao) if sem_kimono else None) or _FUNCOES.get(federacao)
    if not funcao:
        return None

    genero_norm = (genero or "").strip().lower()
    tabela = funcao(idade, genero_norm or "masculino")
    if not tabela:
        return None

    for nome, limite in tabela:
        if limite is None or peso_kg <= limite:
            return nome
    return tabela[-1][0]
