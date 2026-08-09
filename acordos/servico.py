"""Serviço de acordos — simulador financeiro com descontos progressivos (PRD 6.3).

O operador informa o valor original da dívida; o simulador aplica as regras de
desconto configuradas pela empresa (RegraDesconto) e devolve as opções de
pagamento (à vista e parcelado), com valor final e parcela mensal.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from acordos.models import Acordo, MODALIDADES, RegraDesconto

DOIS = Decimal('0.01')


def _brl(valor):
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _normalizar_valor(raw):
    """Converte entrada '1.234,56' / '1234.56' em Decimal (2 casas)."""
    raw = (raw or '').strip().replace('R$', '').strip()
    if not raw:
        raise ValueError('Informe o valor.')
    try:
        if ',' in raw:
            valor = Decimal(raw.replace('.', '').replace(',', '.'))
        else:
            valor = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError('Valor inválido.')
    if valor <= 0:
        raise ValueError('O valor deve ser maior que zero.')
    return valor.quantize(DOIS, rounding=ROUND_HALF_UP)


def regras_do_tenant(tenant_id):
    """Regras de desconto do tenant (fallback: padrão da casa)."""
    regras = list(RegraDesconto.objects.filter(tenant_id=tenant_id).order_by('modalidade', 'parcelas'))
    if regras:
        return regras
    # Padrão inicial quando a empresa ainda não configurou nada
    padroes = [
        ('vista', 1, Decimal('30.00')),
        ('parcelado', 2, Decimal('20.00')),
        ('parcelado', 3, Decimal('15.00')),
        ('parcelado', 6, Decimal('8.00')),
    ]
    return [RegraDesconto(modalidade=m, parcelas=p, percentual=Decimal(v), tenant_id=tenant_id)
            for m, p, v in padroes]


def simular(valor_original, tenant_id):
    """Retorna as opções de pagamento aplicando as regras do tenant.

    Cada opção: modalidade, parcelas, percentual, desconto (R$), valor final,
    parcela mensal e rótulo. À vista entra sempre como primeira opção.
    """
    regras = regras_do_tenant(tenant_id)

    def _opcao(regra):
        pct = Decimal(regra.percentual)
        desconto = (valor_original * pct / 100).quantize(DOIS, rounding=ROUND_HALF_UP)
        valor_final = (valor_original - desconto).quantize(DOIS, rounding=ROUND_HALF_UP)
        parcelas = regra.parcelas
        if parcelas <= 1:
            parcela = valor_final
        else:
            base = (valor_final / parcelas).quantize(DOIS, rounding=ROUND_HALF_UP)
            parcela = (valor_final - base * (parcelas - 1)).quantize(DOIS, rounding=ROUND_HALF_UP)
        return {
            'modalidade': regra.modalidade,
            'parcelas': parcelas,
            'percentual': pct,
            'percentual_label': str(pct).rstrip('0').rstrip('.').replace('.', ','),
            'desconto': desconto,
            'valor_final': valor_final,
            'parcela': parcela,
            'valor_final_label': _brl(valor_final),
            'desconto_label': _brl(desconto),
            'parcela_label': _brl(parcela),
            'poupanca': _brl(valor_original - valor_final),
        }

    opcoes = [_opcao(r) for r in regras if r.modalidade == 'vista']
    parcelado = [_opcao(r) for r in regras if r.modalidade == 'parcelado']
    opcoes.extend(parcelado)
    return opcoes


def registrar_acordo(contato, valor_original, modalidade, parcelas, tenant_id, chamada_id=None,
                     observacao=''):
    """Cria o Acordo a partir da opção escolhida na simulação (status 'aceito')."""
    regra = regras_do_tenant(tenant_id)
    alvo = None
    for r in regra:
        if r.modalidade == modalidade and r.parcelas == int(parcelas):
            alvo = r
            break
    if alvo is None:
        # sem regra exata, sem desconto
        alvo = RegraDesconto(modalidade=modalidade, parcelas=int(parcelas), percentual=Decimal('0'))

    pct = Decimal(alvo.percentual)
    desconto = (valor_original * pct / 100).quantize(DOIS, rounding=ROUND_HALF_UP)
    valor_final = (valor_original - desconto).quantize(DOIS, rounding=ROUND_HALF_UP)
    return Acordo.objects.create(
        contato=contato,
        chamada_id=chamada_id,
        valor_original=valor_original,
        modalidade=modalidade,
        parcelas=int(parcelas),
        percentual_desconto=pct,
        desconto=desconto,
        valor_final=valor_final,
        status='aceito',
        observacao=observacao,
        tenant_id=tenant_id,
    )
