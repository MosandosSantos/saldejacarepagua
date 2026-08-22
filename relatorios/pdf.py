"""Geração do relatório gerencial em PDF (reportlab) — PRD S7 (7.3.2).

Usa apenas fontes padrão do reportlab (Helvetica, Latin-1) — mesmos cuidados de
`contatos/orcamento.py` (sanitização de texto e escape XML).
"""

import io
from datetime import date
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

COR_PRIMARIA = colors.HexColor('#0b6f74')
COR_PRIMARIA_ESC = colors.HexColor('#075b60')
COR_TEXTO = colors.HexColor('#1c2b30')
COR_MUTA = colors.HexColor('#6f8a93')
COR_LINHA = colors.HexColor('#d3e2e6')
COR_FUNDO = colors.HexColor('#f4fafb')

ESTILO_EMPRESA = ParagraphStyle('empresa', fontName='Helvetica-Bold', fontSize=17,
                                textColor=colors.white, leading=21)
ESTILO_NUMERO = ParagraphStyle('numero', fontName='Helvetica-Bold', fontSize=10.5,
                               textColor=colors.HexColor('#7fe3c4'), alignment=TA_RIGHT, leading=14)
ESTILO_ROTULO = ParagraphStyle('rotulo', fontName='Helvetica-Bold', fontSize=7.5,
                               textColor=colors.white, leading=10)
ESTILO_TITULO_SECAO = ParagraphStyle('titulo_secao', fontName='Helvetica-Bold', fontSize=10.5,
                                     textColor=COR_PRIMARIA_ESC, spaceAfter=4, leading=14)
ESTILO_TEXTO = ParagraphStyle('texto', fontName='Helvetica', fontSize=9.5,
                              textColor=COR_TEXTO, leading=13)
ESTILO_TEXTO_CLARO = ParagraphStyle('texto_claro', fontName='Helvetica', fontSize=9,
                                    textColor=colors.HexColor('#5b6e75'), leading=12.5)


def _txt(s):
    """Sanitiza string para o encoding Latin-1 das fontes padrão do reportlab."""
    return (s or '').encode('latin-1', 'replace').decode('latin-1')


def _p(s):
    """Texto seguro para Paragraph: Latin-1 + escape XML."""
    return _xml_escape(_txt(s))


def _kpi_cell(rotulo, valor, valor_cor=COR_PRIMARIA_ESC):
    """Célula de KPI: rótulo pequeno em cima, valor em baixo."""
    return [
        Paragraph(_txt(rotulo), ParagraphStyle(
            'k', fontName='Helvetica-Bold', fontSize=7.5, textColor=COR_MUTA, leading=10)),
        Paragraph(_txt(valor), ParagraphStyle(
            'v', fontName='Helvetica-Bold', fontSize=12.5, textColor=valor_cor, leading=16)),
    ]


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(COR_LINHA)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(COR_MUTA)
    canvas.drawString(18 * mm, 9.5 * mm, _txt(
        f'Documento gerado por CRMCronos.Cloud em {date.today().strftime("%d/%m/%Y")}'
    ))
    canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, 'Relatório gerencial')
    canvas.restoreState()


def gerar_relatorio_pdf(tenant, periodo_label, kpis, produtividade, operador_nome=None) -> bytes:
    """Monta o PDF do relatório gerencial (KPIs + produtividade por operador).

    `operador_nome` (opcional) identifica o operador quando o relatório foi
    filtrado por `?operador=` — exibido na faixa de contexto do cabeçalho.
    """
    nome_empresa = _txt(tenant.nome) if tenant is not None else 'CRMCronos.Cloud'
    story = []

    # ---------- Cabeçalho ----------
    cabecalho = Table(
        [[Paragraph(nome_empresa, ESTILO_EMPRESA),
          Paragraph(f'RELATÓRIO GERENCIAL', ESTILO_NUMERO)]],
        colWidths=[120 * mm, 52 * mm],
    )
    cabecalho.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COR_PRIMARIA),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(cabecalho)

    contexto_extra = f' · Operador: {_txt(operador_nome)}' if operador_nome else ''
    linha = Table(
        [[Paragraph('PERÍODO', ESTILO_ROTULO),
          Paragraph(_txt(periodo_label) + contexto_extra, ESTILO_ROTULO),
          Paragraph('EMITIDO EM', ESTILO_ROTULO),
          Paragraph(date.today().strftime('%d/%m/%Y'), ESTILO_ROTULO)]],
        colWidths=[24 * mm, 82 * mm, 24 * mm, 30 * mm],
    )
    linha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COR_PRIMARIA_ESC),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(linha)
    story.append(Spacer(1, 8 * mm))

    # ---------- KPIs ----------
    story.append(Paragraph('INDICADORES', ESTILO_TITULO_SECAO))
    kpi_rows = [
        [_kpi_cell('Base em cobrança', kpis['base_label']),
         _kpi_cell('Contatos úteis (CPC)', kpis['cpc_label']),
         _kpi_cell('Retornos agendados', kpis['retornos_label']),
         _kpi_cell('Chamadas', kpis['chamadas_label'])],
    ]
    kpi_tbl = Table(kpi_rows, colWidths=[43 * mm] * 4)
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COR_FUNDO),
        ('BOX', (0, 0), (-1, -1), 0.6, COR_LINHA),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, COR_LINHA),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 8 * mm))

    # ---------- Produtividade ----------
    story.append(Paragraph('PRODUTIVIDADE POR OPERADOR', ESTILO_TITULO_SECAO))
    cab = [Paragraph(_txt(c), ParagraphStyle(
        'th', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, leading=10))
        for c in ['Operador', 'Chamadas', 'Realizadas', 'Retornos']]
    linhas = []
    for p in produtividade:
        linhas.append([
            Paragraph(_p(p['nome']), ESTILO_TEXTO),
            Paragraph(str(p['chamadas']), ParagraphStyle(
                'c', fontName='Helvetica', fontSize=9.5, textColor=COR_TEXTO, alignment=TA_CENTER, leading=13)),
            Paragraph(str(p['realizadas']), ParagraphStyle(
                'c2', fontName='Helvetica', fontSize=9.5, textColor=COR_TEXTO, alignment=TA_CENTER, leading=13)),
            Paragraph(str(p['retornos']), ParagraphStyle(
                'c3', fontName='Helvetica', fontSize=9.5, textColor=COR_TEXTO, alignment=TA_CENTER, leading=13)),
        ])
    if not linhas:
        linhas = [[Paragraph('—', ESTILO_TEXTO_CLARO), '', '', '']]
    dados = [cab] + linhas
    prod_tbl = Table(dados, colWidths=[58 * mm, 30 * mm, 30 * mm, 30 * mm])
    prod_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA),
        ('GRID', (0, 0), (-1, -1), 0.4, COR_LINHA),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COR_FUNDO]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(prod_tbl)
    story.append(Spacer(1, 6 * mm))

    # ---------- Monta o PDF ----------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title='Relatório gerencial',
        author=nome_empresa,
    )
    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
