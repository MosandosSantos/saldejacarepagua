"""Geração de orçamento/proposta em PDF (reportlab) a partir de um negócio.

A proposta usa apenas fontes padrão do reportlab (Helvetica), que suportam
Latin-1 — todos os textos passam por `_txt` para nunca quebrar o encoding.
"""

import io
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN
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
ESTILO_NUMERO = ParagraphStyle('numero', fontName='Helvetica-Bold', fontSize=11,
                               textColor=colors.HexColor('#7fe3c4'), alignment=TA_RIGHT, leading=14)
ESTILO_ROTULO = ParagraphStyle('rotulo', fontName='Helvetica-Bold', fontSize=7.5,
                               textColor=colors.white, leading=10)
ESTILO_TITULO_SECAO = ParagraphStyle('titulo_secao', fontName='Helvetica-Bold', fontSize=10.5,
                                     textColor=COR_PRIMARIA_ESC, spaceAfter=4, leading=14)
ESTILO_LABEL = ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=8,
                              textColor=COR_MUTA, leading=11)
ESTILO_VALOR_CAMPO = ParagraphStyle('valor_campo', fontName='Helvetica', fontSize=10,
                                    textColor=COR_TEXTO, leading=13)
ESTILO_TEXTO = ParagraphStyle('texto', fontName='Helvetica', fontSize=9.5,
                              textColor=COR_TEXTO, leading=13)
ESTILO_TEXTO_CLARO = ParagraphStyle('texto_claro', fontName='Helvetica', fontSize=9,
                                    textColor=colors.HexColor('#5b6e75'), leading=12.5)


def _txt(s):
    """Sanitiza string para o encoding Latin-1 das fontes padrão do reportlab."""
    return (s or '').encode('latin-1', 'replace').decode('latin-1')


def _p(s):
    """Texto de usuário seguro para Paragraph: encoding Latin-1 + escape XML.

    O Paragraph do reportlab interpreta o conteúdo como XML — um `&` ou `<`
    vindo da ficha quebraria o parse e derrubaria o download do orçamento.
    """
    return _xml_escape(_txt(s))


def _brl(n):
    """'R$ 1.500,00' a partir de Decimal/float/int."""
    return 'R$ {:,.2f}'.format(float(n)).replace(',', 'X').replace('.', ',').replace('X', '.')


def _parcelas(valor, max_n=3):
    """Opções de pagamento: (nº de parcelas, parcela regular, última parcela).

    A última parcela de cada opção absorve o arredondamento para fechar o total.
    """
    v = Decimal(str(valor or 0))
    if v <= 0:
        return []
    opcoes = []
    for n in range(1, max_n + 1):
        base = (v / n).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        ultima = v - base * (n - 1)
        opcoes.append((n, base, ultima))
    return opcoes


def _rodape(canvas, doc):
    """Rodapé padrão desenhado em todas as páginas."""
    canvas.saveState()
    canvas.setStrokeColor(COR_LINHA)
    canvas.setLineWidth(0.6)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(COR_MUTA)
    canvas.drawString(18 * mm, 9.5 * mm, _txt(
        f'Documento gerado por CronosCRM em {date.today().strftime("%d/%m/%Y")}'
    ))
    canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, 'Proposta válida por 7 dias')
    canvas.restoreState()


def gerar_orcamento_pdf(tenant, contato, negocio) -> bytes:
    """Monta o PDF da proposta comercial do negócio; devolve os bytes do arquivo."""
    nome_clinica = _txt(tenant.nome) if tenant is not None else 'CronosCRM'
    hoje = date.today()
    validade = hoje + timedelta(days=7)

    story = []

    # ---------- Cabeçalho ----------
    cabecalho = Table(
        [[Paragraph(nome_clinica, ESTILO_EMPRESA),
          Paragraph(f'ORÇAMENTO Nº {negocio.id}', ESTILO_NUMERO)]],
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

    dados_linha = Table(
        [[Paragraph('EMITIDO EM', ESTILO_ROTULO),
          Paragraph(hoje.strftime('%d/%m/%Y'), ESTILO_ROTULO),
          Paragraph('VALIDADE', ESTILO_ROTULO),
          Paragraph(validade.strftime('%d/%m/%Y'), ESTILO_ROTULO)]],
        colWidths=[24 * mm, 30 * mm, 24 * mm, 30 * mm],
    )
    dados_linha.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COR_PRIMARIA_ESC),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(dados_linha)
    story.append(Spacer(1, 8 * mm))

    # ---------- Para / cliente ----------
    story.append(Paragraph('PARA', ESTILO_TITULO_SECAO))
    info_cliente = [
        Paragraph('<b>' + _p(contato.nome) + '</b>', ESTILO_VALOR_CAMPO),
    ]
    extras = []
    if contato.empresa and contato.empresa != '—':
        extras.append(_p(f'Empresa: {contato.empresa}'))
    if contato.email and contato.email != '—':
        extras.append(_p(f'E-mail: {contato.email}'))
    if contato.tel and contato.tel != '—':
        extras.append(_p(f'Telefone: {contato.tel}'))
    if contato.cidade or contato.bairro:
        extras.append(_p(f'{contato.cidade}{" · " if contato.cidade and contato.bairro else ""}{contato.bairro}'))
    if extras:
        info_cliente.append(Paragraph('<br/>'.join(extras), ESTILO_TEXTO_CLARO))
    if contato.procedimento and contato.procedimento != '—':
        info_cliente.append(Paragraph(_p(f'Procedimento de interesse: {contato.procedimento}'), ESTILO_TEXTO_CLARO))
    cliente = Table([[info_cliente]], colWidths=[172 * mm])
    cliente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COR_FUNDO),
        ('BOX', (0, 0), (-1, -1), 0.6, COR_LINHA),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(cliente)
    story.append(Spacer(1, 8 * mm))

    # ---------- Descrição ----------
    story.append(Paragraph('DESCRIÇÃO DO SERVIÇO', ESTILO_TITULO_SECAO))
    story.append(Paragraph(_p(negocio.titulo or contato.nome), ESTILO_TEXTO))
    story.append(Spacer(1, 6 * mm))

    # ---------- Tabela de valores ----------
    cab = [Paragraph('DESCRIÇÃO', ParagraphStyle('th_d', fontName='Helvetica-Bold', fontSize=8,
                                                 textColor=colors.white, leading=11)),
           Paragraph('VALOR', ParagraphStyle('th_v', fontName='Helvetica-Bold', fontSize=8,
                                             textColor=colors.white, alignment=TA_RIGHT, leading=11))]
    linha_item = [Paragraph(_p(negocio.titulo or contato.nome), ESTILO_TEXTO),
                  Paragraph(_brl(negocio.valor), ParagraphStyle(
                      'it_v', fontName='Helvetica', fontSize=9.5, textColor=COR_TEXTO,
                      alignment=TA_RIGHT, leading=13))]
    total = [Paragraph('TOTAL', ParagraphStyle('tt', fontName='Helvetica-Bold', fontSize=10,
                                               textColor=colors.white, leading=14)),
             Paragraph(_brl(negocio.valor), ParagraphStyle(
                 'tv', fontName='Helvetica-Bold', fontSize=11, textColor=colors.white,
                 alignment=TA_RIGHT, leading=14))]

    valores = Table([cab, linha_item, total], colWidths=[132 * mm, 40 * mm])
    valores.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA),
        ('BACKGROUND', (0, 2), (-1, 2), COR_PRIMARIA_ESC),
        ('GRID', (0, 1), (-1, 1), 0.5, COR_LINHA),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(valores)
    story.append(Spacer(1, 7 * mm))

    # ---------- Condições de pagamento ----------
    opcoes = _parcelas(negocio.valor)
    if opcoes:
        story.append(Paragraph('CONDIÇÕES DE PAGAMENTO', ESTILO_TITULO_SECAO))
        linhas_pag = []
        for n, base, ultima in opcoes:
            if n == 1:
                desc = f'À vista (1x) — {_brl(ultima)}'
            else:
                desc = f'Em {n}x de {_brl(base)}'
            linhas_pag.append([Paragraph(desc, ESTILO_TEXTO)])
        pag = Table([[linhas_pag]], colWidths=[172 * mm])
        pag.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COR_FUNDO),
            ('BOX', (0, 0), (-1, -1), 0.6, COR_LINHA),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(pag)
        story.append(Spacer(1, 7 * mm))

    # ---------- Observações ----------
    observacoes = (
        '• Valores e condições válidos por 7 dias a partir da data de emissão.\n'
        '• O orçamento será confirmado após a avaliação do profissional responsável.'
    )
    if contato.observacoes:
        observacoes += f'\n• {contato.observacoes}'
    obs = Table(
        [[Paragraph('OBSERVAÇÕES', ESTILO_ROTULO)],
         [Paragraph(_p(observacoes), ESTILO_TEXTO_CLARO)]],
        colWidths=[172 * mm],
    )
    obs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COR_PRIMARIA_ESC),
        ('BOX', (0, 0), (-1, -1), 0.6, COR_LINHA),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(obs)
    story.append(Spacer(1, 14 * mm))

    # ---------- Assinaturas ----------
    ass = Table(
        [[Paragraph('__________________________________', ESTILO_TEXTO),
          Paragraph('__________________________________', ESTILO_TEXTO)],
         [Paragraph('Assinatura do cliente', ESTILO_LABEL),
          Paragraph('Assinatura da empresa', ESTILO_LABEL)]],
        colWidths=[86 * mm, 86 * mm],
    )
    ass.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(ass)

    # ---------- Monta o PDF ----------
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=f'Orçamento {negocio.id}',
        author=nome_clinica,
    )
    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
