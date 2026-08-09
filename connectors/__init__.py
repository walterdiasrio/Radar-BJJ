import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from . import cbjj, fjjrio, cbjjd, cbjjo, cbjje, fpjj, adcc, idade as idade_mod, peso as peso_mod, datas as datas_mod

FEDERACOES = {
    "cbjj": {"label": "CBJJ", "module": cbjj},
    "fjjrio": {"label": "FJJRio", "module": fjjrio},
    "cbjjd": {"label": "CBJJD", "module": cbjjd},
    "cbjjo": {"label": "CBJJO", "module": cbjjo},
    "cbjje": {"label": "CBJJE", "module": cbjje},
    "fpjj": {"label": "FPJJ", "module": fpjj},
    "adcc": {"label": "ADCC", "module": adcc},
}
_ORDEM_FEDERACAO = {fid: i for i, fid in enumerate(FEDERACOES)}

TODAS = "todas"


def _combina(texto, termo):
    if not termo:
        return True
    return termo.strip().lower() in (texto or "").lower()


def _rotulo(texto):
    """Extrai só o nome da categoria de um texto que pode vir com informação
    extra colada (ex: "JUVENIL 1 - 16 anos", "MIRIM 1 (6 E 7 ANOS)", "Pena
    (58,50kg)") e normaliza (minúsculas, hífen vira espaço, espaços
    colapsados) para permitir comparação exata."""
    texto = texto or ""
    cortes = [i for i in (texto.find("("), texto.find(" - ")) if i != -1]
    if cortes:
        texto = texto[:min(cortes)]
    texto = texto.lower().replace("-", " ")
    return re.sub(r"\s+", " ", texto).strip()


def _combina_exata(texto, termo):
    """Como _combina, mas por igualdade do rótulo da categoria (não
    substring) — usada para valores que a gente mesmo calculou (categoria
    etária, categoria de peso). Substring falha aqui: "Pesado" é substring
    de "Meio Pesado" e "Super Pesado"; "Mirim 3" é substring de "Pré-Mirim
    3". Comparando o rótulo inteiro e normalizado evita esses falsos
    positivos."""
    if not termo:
        return True
    return _rotulo(texto) == _rotulo(termo)


def _atleta_combina(atleta, filtros_fed):
    combina_faixa = (
        adcc.faixa_combina(atleta, filtros_fed.get("faixa"))
        if atleta.get("federacao") == "ADCC"
        else _combina(atleta.get("faixa"), filtros_fed.get("faixa"))
    )
    return (
        _combina(atleta.get("nome"), filtros_fed.get("nome"))
        and _combina(atleta.get("equipe"), filtros_fed.get("equipe"))
        and _combina_exata(atleta.get("categoria_idade"), filtros_fed.get("categoria_idade"))
        and _combina(atleta.get("genero"), filtros_fed.get("genero"))
        and _combina_exata(atleta.get("peso"), filtros_fed.get("peso_categoria"))
        and combina_faixa
    )


_NOME_FALLBACK = re.compile(r"^evento\s*\d+$", re.I)


def listar_eventos(federacao):
    modulo = FEDERACOES[federacao]["module"]
    eventos = modulo.listar_eventos()
    return _apenas_futuros(_sem_bugs(eventos))


def _apenas_futuros(eventos):
    """Descarta competições cuja data já passou (antes de hoje). Eventos
    cuja data não deu para interpretar são mantidos — preferimos mostrar
    a mais do que esconder uma competição válida por falha de parsing."""
    hoje = date.today()
    resultado = []
    for evento in eventos:
        data_evento = datas_mod.extrair_data(evento.get("data", ""))
        if data_evento is not None and data_evento < hoje:
            continue
        resultado.append(evento)
    return resultado


def _sem_bugs(eventos):
    """Descarta competições onde a própria fonte falhou ao gerar a página
    (ex: erro PHP vazando pro texto, ou nosso conector caindo no nome
    genérico de reserva "Evento 123" por não ter achado o título real)."""
    resultado = []
    for evento in eventos:
        nome = (evento.get("nome") or "").strip()
        data_texto = evento.get("data") or ""
        if not nome or _NOME_FALLBACK.match(nome):
            continue
        if "warning" in data_texto.lower() or "warning" in nome.lower():
            continue
        resultado.append(evento)
    return resultado


def buscar_atletas(federacao, evento_id, filtros):
    modulo = FEDERACOES[federacao]["module"]
    return modulo.buscar_atletas(evento_id, filtros)


def _filtros_para_federacao(fed, filtros, evento_id=None):
    """Calcula, para essa federação específica, a categoria etária exata e a
    categoria de peso exata. A maioria das federações usa ano de nascimento
    (tabela própria por federação); o ADCC é diferente — categoriza pela
    idade exata (dia/mês/ano) NO DIA DA COMPETIÇÃO, então usa a data de
    nascimento completa e as categorias que já existem na competição
    escolhida (só dá pra calcular isso com precisão quando uma competição
    específica do ADCC foi selecionada, não em "todas")."""
    filtros_fed = dict(filtros)
    avisos = []

    if fed == "adcc":
        data_nascimento_iso = filtros.get("data_nascimento")
        if not data_nascimento_iso:
            return filtros_fed, avisos
        try:
            data_nascimento = date.fromisoformat(data_nascimento_iso)
        except ValueError:
            return filtros_fed, [f"{FEDERACOES[fed]['label']}: data de nascimento inválida"]

        if not evento_id or evento_id == TODAS:
            avisos.append(
                f"{FEDERACOES[fed]['label']}: selecione uma competição específica para filtrar por "
                "idade exata (a categoria depende da data de cada evento)"
            )
            return filtros_fed, avisos

        data_referencia = adcc.data_referencia_evento(evento_id)
        idade_exata = adcc.idade_exata(data_nascimento, data_referencia)
        categoria = adcc.categoria_exata_para_idade(evento_id, idade_exata)
        if not categoria:
            avisos.append(f"{FEDERACOES[fed]['label']}: não há categoria dessa idade nessa competição")
            return filtros_fed, avisos
        filtros_fed["categoria_idade"] = categoria

        peso_sem_kimono = filtros.get("peso_sem_kimono")
        if peso_sem_kimono:
            try:
                peso_sem_kimono = float(str(peso_sem_kimono).replace(",", "."))
            except (TypeError, ValueError):
                avisos.append(f"{FEDERACOES[fed]['label']}: peso inválido")
                return filtros_fed, avisos
            if not filtros.get("genero"):
                avisos.append(f"{FEDERACOES[fed]['label']}: selecione o gênero para calcular a categoria de peso")
            else:
                categoria_peso = adcc.categoria_peso_exata(evento_id, categoria, filtros.get("genero"), peso_sem_kimono)
                if categoria_peso:
                    filtros_fed["peso_categoria"] = categoria_peso
                else:
                    avisos.append(f"{FEDERACOES[fed]['label']}: não há categoria de peso pra esse valor nessa competição")
        return filtros_fed, avisos

    idade = None
    ano_nascimento = filtros.get("ano_nascimento")
    if ano_nascimento:
        try:
            ano_nascimento = int(ano_nascimento)
        except (TypeError, ValueError):
            return filtros_fed, [f"{FEDERACOES[fed]['label']}: ano de nascimento inválido"]

        idade = idade_mod.idade_a_partir_do_ano(ano_nascimento)
        categoria = idade_mod.categoria_para(fed, ano_nascimento)
        if categoria:
            filtros_fed["categoria_idade"] = categoria
        else:
            avisos.append(f"{FEDERACOES[fed]['label']}: não há categoria para esse ano de nascimento")

    peso_kg = filtros.get("peso_kg")
    if peso_kg:
        try:
            peso_kg = float(str(peso_kg).replace(",", "."))
        except (TypeError, ValueError):
            avisos.append(f"{FEDERACOES[fed]['label']}: peso inválido")
            peso_kg = None

        if peso_kg is not None:
            if idade is None:
                avisos.append(
                    f"{FEDERACOES[fed]['label']}: informe também o ano de nascimento para calcular a categoria de peso"
                )
            elif idade >= 16 and not filtros.get("genero"):
                avisos.append(
                    f"{FEDERACOES[fed]['label']}: selecione o gênero para calcular a categoria de peso "
                    "(a partir do Juvenil, o limite de peso muda entre masculino e feminino)"
                )
            else:
                categoria_peso = peso_mod.categoria_peso_para(fed, idade, peso_kg, filtros.get("genero", ""))
                if categoria_peso:
                    filtros_fed["peso_categoria"] = categoria_peso
                else:
                    avisos.append(f"{FEDERACOES[fed]['label']}: não há categoria de peso para esses dados")

    return filtros_fed, avisos


def _federacoes_alvo(federacao):
    """federacao pode ser TODAS, um único id, ou uma lista de ids (seleção
    múltipla) — sempre devolve a lista de ids a percorrer."""
    if federacao == TODAS:
        return list(FEDERACOES.keys())
    if isinstance(federacao, (list, tuple, set)):
        return [f for f in federacao if f in FEDERACOES]
    return [federacao]


def buscar_atletas_agregado(federacao, evento_id, filtros):
    """Busca atletas podendo abranger uma, várias ou todas as federações,
    e todas as competições de uma vez, disparando as buscas em paralelo."""
    federacoes_alvo = _federacoes_alvo(federacao)
    federacao_unica = len(federacoes_alvo) == 1

    tarefas = []  # (federacao, evento, filtros_fed)
    erros = []
    avisos_ja_mostrados = set()
    for fed in federacoes_alvo:
        try:
            eventos = listar_eventos(fed)
        except Exception as exc:
            erros.append(f"{FEDERACOES[fed]['label']}: não foi possível carregar competições ({exc})")
            continue

        if evento_id != TODAS and federacao_unica:
            eventos = [e for e in eventos if e["id"] == evento_id]

        if fed == "adcc":
            # A categoria do ADCC depende da data de CADA competição (idade
            # exata no dia do evento), então precisa calcular por evento —
            # diferente das outras federações, onde a categoria não muda
            # conforme a competição escolhida.
            for evento in eventos:
                filtros_fed, avisos = _filtros_para_federacao(fed, filtros, evento["id"])
                for aviso in avisos:
                    if aviso not in avisos_ja_mostrados:
                        avisos_ja_mostrados.add(aviso)
                        erros.append(aviso)
                tarefas.append((fed, evento, filtros_fed))
            continue

        filtros_fed, avisos = _filtros_para_federacao(fed, filtros)
        erros.extend(avisos)
        for evento in eventos:
            tarefas.append((fed, evento, filtros_fed))

    resultados = []
    with ThreadPoolExecutor(max_workers=24) as executor:
        futuros = {
            executor.submit(buscar_atletas, fed, evento["id"], filtros_fed): (fed, evento, filtros_fed)
            for fed, evento, filtros_fed in tarefas
        }
        for futuro in as_completed(futuros):
            fed, evento, filtros_fed = futuros[futuro]
            try:
                atletas = futuro.result()
            except Exception as exc:
                erros.append(
                    f"{FEDERACOES[fed]['label']} — {evento['nome']}: erro na busca ({exc})"
                )
                continue
            data_ordenacao = datas_mod.extrair_data(evento.get("data", ""))
            for atleta in atletas:
                if not _atleta_combina(atleta, filtros_fed):
                    continue
                atleta["evento"] = evento["nome"]
                atleta["data"] = datas_mod.formatar(evento.get("data", ""))
                resultados.append((_ORDEM_FEDERACAO.get(fed, 99), data_ordenacao or date.max, atleta))

    resultados.sort(key=lambda item: (item[0], item[1]))
    return [atleta for _, _, atleta in resultados], erros, len(tarefas)


def _status_inscricao(fed, modulo, evento):
    """True = abertas, False = fechadas, None = não informado. Algumas
    federações (CBJJO, CBJJE) já trazem isso pronto na própria listagem de
    eventos; para CBJJ e FJJRio buscamos na página do evento; CBJJD não tem
    sinal confiável, fica sempre "não informado"."""
    if "inscricoes_abertas" in evento:
        return evento["inscricoes_abertas"]
    if hasattr(modulo, "status_inscricao"):
        try:
            return modulo.status_inscricao(evento)
        except Exception:
            return None
    return None


_PALAVRAS_KIDS = re.compile(r"pr[ée].?mirim|\bmirim\b|infantil|infanto|\bkids\b", re.I)
_PALAVRAS_ADULTO = re.compile(r"\bmaster\b|\badulto\b|\bjuvenil\b", re.I)

# CBJJD, CBJJO e CBJJE (na maioria dos eventos) não separam Kids num evento
# com nome próprio como CBJJ/FJJRio fazem ("... Kids International Open
# ...") — é uma competição só, com as categorias infantis inscritas junto.
# Pra essas federações, na ausência de palavra-chave no nome, o padrão é
# "ambos" (a competição pode ter categoria kids) em vez de "adulto", senão
# o filtro Kids nunca mostra nada pra elas.
_FEDERACOES_SEM_SEPARACAO_POR_NOME = {"cbjjd", "cbjjo", "cbjje"}


def _classificar_publico(nome, fed):
    """Classifica uma competição em "kids", "adulto" ou "ambos" a partir do
    nome do evento — não temos a lista de categorias de cada competição sem
    fazer uma requisição extra por evento, então isso é uma heurística
    baseada em como as federações costumam nomear edições Kids/Adulto (ex:
    "... Kids International Open ..." na CBJJ/FJJRio, ou "Pré Mirim a
    Master" na FPJJ). Categorias até Infanto-Juvenil 3 contam como kids."""
    tem_kids = bool(_PALAVRAS_KIDS.search(nome))
    tem_adulto = bool(_PALAVRAS_ADULTO.search(nome))
    if tem_kids and tem_adulto:
        return "ambos"
    if tem_kids:
        return "kids"
    if tem_adulto:
        return "adulto"
    return "ambos" if fed in _FEDERACOES_SEM_SEPARACAO_POR_NOME else "adulto"


def listar_competicoes(federacao):
    """Lista as próximas competições (com checagem aberta ou não) de uma,
    várias ou todas as federações, já com o status de inscrição resolvido."""
    federacoes_alvo = _federacoes_alvo(federacao)

    tarefas = []  # (fed, evento)
    erros = []
    for fed in federacoes_alvo:
        try:
            eventos = listar_eventos(fed)
        except Exception as exc:
            erros.append(f"{FEDERACOES[fed]['label']}: não foi possível carregar competições ({exc})")
            continue
        for evento in eventos:
            tarefas.append((fed, evento))

    resultado = []
    with ThreadPoolExecutor(max_workers=24) as executor:
        futuros = {
            executor.submit(_status_inscricao, fed, FEDERACOES[fed]["module"], evento): (fed, evento)
            for fed, evento in tarefas
        }
        for futuro in as_completed(futuros):
            fed, evento = futuros[futuro]
            try:
                inscricoes_abertas = futuro.result()
            except Exception:
                inscricoes_abertas = None
            data_ordenacao = datas_mod.extrair_data(evento.get("data", ""))
            nome = evento.get("nome", "")
            resultado.append((
                _ORDEM_FEDERACAO.get(fed, 99),
                data_ordenacao or date.max,
                {
                    "federacao": FEDERACOES[fed]["label"],
                    "nome": nome,
                    "data": datas_mod.formatar(evento.get("data", "")),
                    "mes": datas_mod.rotulo_mes(data_ordenacao),
                    "local": evento.get("local", ""),
                    "inscricoes_abertas": inscricoes_abertas,
                    "publico": _classificar_publico(nome, fed),
                },
            ))

    resultado.sort(key=lambda item: item[1])
    return [comp for _, _, comp in resultado], erros
