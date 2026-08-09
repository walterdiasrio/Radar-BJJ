"""Extrai uma data (para ordenação) a partir dos textos de data soltos que
cada federação usa nos seus próprios formatos (ex: "8 ago até 9 ago",
"sábado, 15 de agosto de 2026", "22 e 23 AGOSTO", "25, 26 e 27 SETEMBRO",
"DE: 07/03/2026 ATÉ 07/03/2026"). Sempre pegamos o PRIMEIRO dia do evento
(primeiro número e primeiro mês citados no texto). Quando não há ano
explícito no texto, assumimos o ano corrente, avançando para o ano seguinte
se o mês já tiver passado (evento futuro)."""
import re
from datetime import date

_MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
_MESES_REGEX = "|".join(_MESES)


def _mes_de(token):
    return _MESES.get(token.strip().lower()[:3])


def _ano_inferido(mes, dia, hoje=None):
    hoje = hoje or date.today()
    ano = hoje.year
    try:
        candidata = date(ano, mes, dia)
    except ValueError:
        candidata = date(ano, mes, 1)
    if candidata < hoje.replace(day=1):
        ano += 1
    return ano


def extrair_data(texto):
    """Retorna um date (primeiro dia do evento) ou None se não conseguir
    interpretar o texto."""
    if not texto:
        return None
    texto = texto.strip()

    # dd/mm/yyyy (CBJJO: "DE: 07/03/2026 ATÉ 07/03/2026") ou dd-mm-yyyy (FPJJ)
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", texto)
    if m:
        dia, mes, ano = (int(x) for x in m.groups())
        try:
            return date(ano, mes, dia)
        except ValueError:
            return None

    # fallback genérico: primeiro número = primeiro dia; primeiro nome de
    # mês citado = mês do evento; ano explícito no texto (se houver) ou
    # inferido a partir de hoje.
    m_dia = re.search(r"\d{1,2}", texto)
    m_mes = re.search(_MESES_REGEX, texto, re.I)
    if not m_dia or not m_mes:
        return None

    dia = int(m_dia.group())
    mes = _mes_de(m_mes.group())
    if not mes:
        return None

    m_ano = re.search(r"\b(20\d{2})\b", texto)
    ano = int(m_ano.group(1)) if m_ano else _ano_inferido(mes, dia)

    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


_MESES_LABEL = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def rotulo_mes(data_obj):
    """"Agosto 2026" a partir de um date, ou "Data não informada" se None."""
    if data_obj is None:
        return "Data não informada"
    return f"{_MESES_LABEL[data_obj.month - 1]} {data_obj.year}"


def extrair_intervalo(texto):
    """Retorna (data_inicio, data_fim) — ambos `date`, fim igual a início
    quando o evento é de um dia só — ou None se não deu pra interpretar."""
    if not texto:
        return None
    texto = texto.strip()

    # duas datas completas dd/mm/yyyy ou dd-mm-yyyy (CBJJO, FPJJ multi-dia)
    datas_completas = re.findall(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", texto)
    if datas_completas:
        try:
            convertidas = [date(int(a), int(m), int(d)) for d, m, a in datas_completas]
        except ValueError:
            return None
        return (convertidas[0], convertidas[-1])

    # fallback genérico: um mês só, uma ou mais dias soltos ao redor dele
    # (ex: "8 ago até 9 ago", "15 e 16 de agosto 2026", "25, 26 e 27 SETEMBRO")
    m_mes = re.search(_MESES_REGEX, texto, re.I)
    if not m_mes:
        return None
    mes = _mes_de(m_mes.group())
    if not mes:
        return None

    m_ano = re.search(r"\b(20\d{2})\b", texto)
    texto_sem_ano = texto[:m_ano.start()] + texto[m_ano.end():] if m_ano else texto

    dias = [int(d) for d in re.findall(r"\b\d{1,2}\b", texto_sem_ano)]
    dias = [d for d in dias if 1 <= d <= 31]
    if not dias:
        return None

    ano = int(m_ano.group(1)) if m_ano else _ano_inferido(mes, min(dias))

    try:
        inicio = date(ano, mes, min(dias))
        fim = date(ano, mes, max(dias))
    except ValueError:
        return None
    return (inicio, fim)


def formatar(texto):
    """"02 de janeiro de 2026" (um dia) ou "07 a 08 de janeiro de 2026"
    (intervalo) a partir do texto de data solto de qualquer federação.
    Retorna o texto original se não conseguir interpretar."""
    intervalo = extrair_intervalo(texto)
    if intervalo is None:
        return texto or ""

    inicio, fim = intervalo
    if inicio == fim:
        return f"{inicio.day:02d} de {_MESES_LABEL[inicio.month - 1].lower()} de {inicio.year}"

    if inicio.month == fim.month and inicio.year == fim.year:
        return (
            f"{inicio.day:02d} a {fim.day:02d} de "
            f"{_MESES_LABEL[inicio.month - 1].lower()} de {inicio.year}"
        )

    def _por_extenso(d):
        return f"{d.day:02d} de {_MESES_LABEL[d.month - 1].lower()} de {d.year}"

    return f"{_por_extenso(inicio)} a {_por_extenso(fim)}"
