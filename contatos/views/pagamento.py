"""Simulação de pagamento de graus (Asaas fake — nenhuma cobrança real).

Fluxo: detalhe do membro → "Ir para pagamento" → seleção de graus
→ página fake do Asaas → confirmação simulada. Regras de negócio:
- Grau 9 exige o 4; Grau 14 exige 9 + 4 (cadeia automática);
- "Todos" é exclusivo (R$ 900 em vez de 3 × R$ 350).
"""
import base64
import io

import qrcode
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from acesso.decorators import web_login_required
from contatos.views.gprb_membros import _membro_do_papel, _para_contexto_membro
from core.utils import brl as _brl

ITENS = (
    ('4', 'Grau 4', 350),
    ('9', 'Grau 9', 350),
    ('14', 'Grau 14', 350),
    ('todos', 'Todos os graus (4 + 9 + 14)', 900),
)
PRECO = {codigo: preco for codigo, _rotulo, preco in ITENS}
METODOS = (('pix', 'Pix'), ('boleto', 'Boleto'), ('cartao', 'Cartão'))


def normalizar_itens(marcados):
    """Aplica cadeia (9→4, 14→9+4) e exclusividade do 'todos'.

    Devolve (lista_de_codigos, total). Seleção vazia → ([], 0).
    """
    sel = [c for c in (marcados or []) if c in PRECO]
    if 'todos' in sel:
        return ['todos'], PRECO['todos']
    out = []
    for codigo in ('4', '9', '14'):
        if codigo in sel and codigo not in out:
            out.append(codigo)
    if '14' in out and '9' not in out:
        out.append('9')
    if '9' in out and '4' not in out:
        out.append('4')
    ordem = {'4': 0, '9': 1, '14': 2}
    out.sort(key=ordem.get)
    return out, PRECO['4'] * len(out)


def _resolver_membro(request, pk):
    """(membro, vale, contexto) ou None quando fora do papel do usuário."""
    resolvido = _membro_do_papel(request, pk)
    if resolvido is None:
        return None
    membro, vale = resolvido
    return membro, vale, _para_contexto_membro(membro, vale)


def _payload_sessao(request, membro):
    dados = request.session.get('pagamento') or {}
    # 'membro_pk', 'itens' e 'total' sao chaves obrigatorias do payload: se
    # faltarem, o payload e de outra sessao/membro e nao deve ser reaproveitado.
    if 'membro_pk' not in dados or 'itens' not in dados or 'total' not in dados:
        return None
    if str(dados['membro_pk']) != str(membro.pk):
        return None
    itens, total = normalizar_itens(dados['itens'])
    if not itens or total != dados['total']:
        return None
    return {'itens': itens, 'total': total}


@web_login_required
def membro_pagamento(request, pk):
    """Seleção de graus a pagar (GET) → grava na sessão e vai ao Asaas (POST)."""
    resolvido = _resolver_membro(request, pk)
    if resolvido is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar membros.')
    membro, _vale, contexto = resolvido

    erro = None
    if request.method == 'POST':
        itens, total = normalizar_itens(request.POST.getlist('itens'))
        if not itens:
            erro = 'Selecione ao menos um grau.'
        else:
            request.session['pagamento'] = {
                'membro_pk': membro.pk, 'itens': itens, 'total': total,
            }
            return redirect('membros:pagamento_asaas', pk=membro.pk)

    return render(request, 'contatos/pagamento.html', {
        'membro': contexto,
        'itens': [
            {'codigo': codigo, 'rotulo': rotulo, 'preco': preco, 'preco_brl': _brl(preco)}
            for codigo, rotulo, preco in ITENS
        ],
        'erro': erro,
    })


def _qr_fake_pix(total):
    """QRCode ilustrativo do Pix (conteúdo fictício, só para a simulação)."""
    img = qrcode.make(f'SIMULACAO-ASAAS|valor={total:.2f}|nao-cobrar')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@web_login_required
def membro_pagamento_asaas(request, pk):
    """Checkout fake do Asaas (GET) + confirmação simulada (POST)."""
    resolvido = _resolver_membro(request, pk)
    if resolvido is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar membros.')
    membro, _vale, contexto = resolvido

    payload = _payload_sessao(request, membro)
    if payload is None:
        return redirect('membros:pagamento', pk=membro.pk)

    rotulos = {codigo: rotulo for codigo, rotulo, _preco in ITENS}
    itens_ctx = [
        {'rotulo': rotulos[c], 'preco_brl': _brl(PRECO[c])} for c in payload['itens']
    ]

    if request.method == 'POST':
        metodo = request.POST.get('metodo', '')
        if metodo not in dict(METODOS):
            return render(request, 'contatos/pagamento_asaas.html', {
                'membro': contexto, 'itens': itens_ctx,
                'total_brl': _brl(payload['total']),
                'metodos': METODOS, 'metodo': metodo,
                'qr_pix': _qr_fake_pix(payload['total']),
                'boleto_linha': '23793.38128 60007.827136 95000.063305 9 99110000090000',
                'erro': 'Escolha a forma de pagamento.',
                'pago': False,
            })
        request.session.pop('pagamento', None)
        return render(request, 'contatos/pagamento_asaas.html', {
            'membro': contexto, 'itens': itens_ctx,
            'total_brl': _brl(payload['total']),
            'metodo_label': dict(METODOS)[metodo],
            'pago': True,
        })

    return render(request, 'contatos/pagamento_asaas.html', {
        'membro': contexto, 'itens': itens_ctx,
        'total_brl': _brl(payload['total']),
        'metodos': METODOS, 'metodo': 'pix',
        'qr_pix': _qr_fake_pix(payload['total']),
        'boleto_linha': '23793.38128 60007.827136 95000.063305 9 99110000090000',
        'erro': None, 'pago': False,
    })
