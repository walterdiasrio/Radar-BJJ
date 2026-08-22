"""Gera o PDF do Planner Mensal de Aulas, no estilo do template visual
(calendário do mês com o conteúdo de cada dia de aula, mais Objetivos do
Mês e Anotações) — ver turmas.gerar_planner_mensal pro conteúdo.

reportlab é puro Python (sem dependência de sistema como Cairo/Pango),
o que importa pra rodar sem drama num buildpack simples como o do Render.
"""
import calendar
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, NextPageTemplate, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)

_AZUL = colors.HexColor("#093093")
_AZUL_MENU = colors.HexColor("#1f4392")
_DOURADO = colors.HexColor("#c9a227")
_CINZA_CLARO = colors.HexColor("#eef2f6")
_CINZA_BORDA = colors.HexColor("#d7dde3")

_MESES_LABEL = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
_DIAS_SEMANA_LABEL = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]


def _estilos():
    return {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=20, textColor=_AZUL, leading=24),
        "subtitulo": ParagraphStyle("subtitulo", fontName="Helvetica-Bold", fontSize=12, textColor=_DOURADO, leading=15),
        "mes": ParagraphStyle("mes", fontName="Helvetica-Bold", fontSize=12, textColor=_AZUL),
        "dia_numero": ParagraphStyle("dia_numero", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white),
        "dia_conteudo": ParagraphStyle("dia_conteudo", fontName="Helvetica", fontSize=6.6, leading=8, textColor=colors.HexColor("#1c2733")),
        "caixa_titulo": ParagraphStyle("caixa_titulo", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white),
        "caixa_texto": ParagraphStyle("caixa_texto", fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#1c2733")),
        "rodape": ParagraphStyle("rodape", fontName="Helvetica", fontSize=7, textColor=colors.HexColor("#7c8894")),
    }


def _texto_do_dia(dia):
    """Posições em negrito + observação normal, no mini-markup do
    reportlab (Paragraph entende <b> nativamente) — não é HTML de verdade,
    então dá pra usar mesmo com o texto vindo de input do usuário."""
    from xml.sax.saxutils import escape

    posicoes = ", ".join(dia.get("posicoes") or [])
    observacao = (dia.get("observacao") or "").strip()
    partes = []
    if posicoes:
        partes.append(f"<b>{escape(posicoes)}</b>")
    if observacao:
        partes.append(escape(observacao))
    return "<br/>".join(partes)


def _tabela_calendario(mes, ano, dias_planner, estilos):
    conteudo_por_data = {d["data"]: _texto_do_dia(d) for d in dias_planner}
    semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(ano, mes)

    cabecalho = [Paragraph(d, ParagraphStyle("cab", fontName="Helvetica-Bold", fontSize=8, textColor=colors.white)) for d in _DIAS_SEMANA_LABEL]
    linhas = [cabecalho]

    for semana in semanas:
        linha = []
        for dia in semana:
            if dia == 0:
                linha.append("")
                continue
            data_iso = f"{ano:04d}-{mes:02d}-{dia:02d}"
            conteudo = conteudo_por_data.get(data_iso, "")
            partes = [Paragraph(str(dia), estilos["dia_numero"])]
            if conteudo:
                partes.append(Spacer(1, 2))
                partes.append(Paragraph(conteudo, estilos["dia_conteudo"]))
            celula = Table([[p] for p in partes], colWidths=[24 * mm])
            celula.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("BACKGROUND", (0, 0), (0, 0), _AZUL if conteudo else _AZUL_MENU),
            ]))
            linha.append(celula)
        linhas.append(linha)

    largura_col = 24 * mm
    tabela = Table(linhas, colWidths=[largura_col] * 7, rowHeights=[7 * mm] + [None] * len(semanas))
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, _CINZA_BORDA),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
        ("LEFTPADDING", (0, 1), (-1, -1), 0),
        ("RIGHTPADDING", (0, 1), (-1, -1), 0),
    ]
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _caixa_texto(titulo, texto, estilos, largura):
    conteudo = texto.strip() if texto else "—"
    tabela = Table(
        [
            [Paragraph(titulo, estilos["caixa_titulo"])],
            [Paragraph(conteudo.replace("\n", "<br/>"), estilos["caixa_texto"])],
        ],
        colWidths=[largura],
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), _AZUL),
        ("BACKGROUND", (0, 1), (0, 1), colors.white),
        ("BOX", (0, 0), (-1, -1), 1, _DOURADO),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 1), (-1, 1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
    ]))
    return tabela


def gerar_pdf(turma, planner):
    """Retorna os bytes do PDF do planner mensal de uma turma."""
    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="corpo")
    doc.addPageTemplates([PageTemplate(id="planner", frames=[frame])])

    estilos = _estilos()
    mes, ano = planner["mes"], planner["ano"]
    nome_turma = turma.get("nome") or turma.get("categoria", "")

    elementos = [
        Paragraph("PLANNER MENSAL DE AULAS", estilos["titulo"]),
        Paragraph("JIU-JITSU", estilos["subtitulo"]),
        Spacer(1, 6),
        Paragraph(f"Turma: {nome_turma} ({turma.get('categoria', '')})", estilos["mes"]),
        Paragraph(f"Mês: {_MESES_LABEL[mes - 1]} de {ano}", estilos["mes"]),
        Spacer(1, 10),
        _tabela_calendario(mes, ano, planner.get("dias", []), estilos),
        Spacer(1, 14),
    ]

    largura_caixa = (doc.width - 8 * mm) / 2
    caixas = Table(
        [[
            _caixa_texto("OBJETIVOS DO MÊS", planner.get("objetivos", ""), estilos, largura_caixa),
            _caixa_texto("ANOTAÇÕES", planner.get("anotacoes", ""), estilos, largura_caixa),
        ]],
        colWidths=[largura_caixa, largura_caixa],
        spaceBefore=0,
    )
    caixas.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (1, 0), (1, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 8 * mm)]))
    elementos.append(caixas)
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("Gerado pelo Radar BJJ — www.radarbjj.com", estilos["rodape"]))

    doc.build(elementos)
    return buffer.getvalue()
