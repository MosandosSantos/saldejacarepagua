"""Views do app 'acordos' — simulação financeira, acordos e PIX (PRD Sprint 6).

O operador simula o acordo com o valor da dívida, escolhe a opção e registra;
o detalhe gera o BR Code (copia-e-cola + QR Code) com os dados PIX da empresa
e permite enviar pelo canal e marcar como pago.
"""

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from acesso.decorators import (
    filtro_tenant,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from acordos.models import Acordo, MODALIDADES, STATUS_ACORDO
from acordos.pix import montar_payload_pix, qrcode_svg
from acordos.servico import _normalizar_valor, _brl, registrar_acordo
from acordos.servico import simular as simular_opcoes
from contatos.models import Contato

_TAB = {'proposta': 'Proposta', 'aceito': 'Aceito', 'pix_gerado': 'PIX gerado',
        'enviado': 'Enviado', 'pago': 'Pago', 'recusado': 'Recusado'}


def _acordos_scope(request):
    qs = Acordo.objects.all()
    tid = tenant_id_da_sessao(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _dados_acordo(a, contato_nome=None):
    return {
        'id': a.id,
        'contato_id': a.contato_id,
        'contato_nome': contato_nome or a.contato.nome,
        'valor_original': _brl(a.valor_original),
        'modalidade': a.get_modalidade_display(),
        'modalidade_key': a.modalidade,
        'parcelas': a.parcelas,
        'percentual': a.percentual_desconto,
        'desconto': _brl(a.desconto),
        'valor_final': _brl(a.valor_final),
        'valor_parcela': _brl(a.valor_parcela),
        'status': a.status,
        'status_label': a.get_status_display(),
        'observacao': a.observacao,
        'pago_em': a.pago_em,
        'created_at': a.created_at,
        'tem_pix': bool(a.pix_payload),
    }


@web_login_required
def lista(request):
    """Lista os acordos do tenant, com filtro por status (6.3.8 / histórico)."""
    status = request.GET.get('status', '')
    qs = _acordos_scope(request).select_related('contato')
    if status in dict(STATUS_ACORDO):
        qs = qs.filter(status=status)
    itens = [_dados_acordo(a) for a in qs[:200]]
    contagem = {s: _acordos_scope(request).filter(status=s).count() for s, _ in STATUS_ACORDO}
    return render(request, 'acordos/lista.html', {
        'itens': itens,
        'status_atual': status,
        'status_opcoes': STATUS_ACORDO,
        'contagem': contagem,
    })


@web_login_required
@web_requer_edicao
def simular(request, contato_id=None):
    """Formulário de simulação (6.3.1–6.3.7): valor original → opções de pagamento."""
    contatos = filtro_tenant(request, Contato.objects.all())
    contato = get_object_or_404(contatos, pk=contato_id) if contato_id else None
    erros = []
    opcoes = []
    valor_original = None

    if request.method == 'POST':
        if not contato:
            contato_id = request.POST.get('contato_id', '0')
            contato = get_object_or_404(contatos, pk=int(contato_id) if contato_id.isdigit() else 0)
        try:
            valor_original = _normalizar_valor(request.POST.get('valor_original'))
            opcoes = simular_opcoes(valor_original, tenant_id_da_sessao(request))
        except ValueError as e:
            erros.append(str(e))

    return render(request, 'acordos/simular.html', {
        'contato': contato,
        'contatos': contatos.order_by('nome')[:200],
        'erros': erros,
        'opcoes': opcoes,
        'valor_original': valor_original,
        'valor_original_label': _brl(valor_original) if valor_original else '',
        'pode_registrar': bool(opcoes),
    })


@web_login_required
@web_requer_edicao
@require_POST
def registrar(request, contato_id):
    """Registra o acordo a partir da opção escolhida (6.3.8) — status 'aceito'."""
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=contato_id)
    modalidade = request.POST.get('modalidade', '')
    parcelas = request.POST.get('parcelas', '1')
    if modalidade not in dict(MODALIDADES) or not parcelas.isdigit() or int(parcelas) < 1:
        return redirect('acordos:simular', contato_id=contato.id)
    try:
        valor = _normalizar_valor(request.POST.get('valor_original'))
    except ValueError:
        return redirect('acordos:simular', contato_id=contato.id)
    chamada_id = request.POST.get('chamada_id', '')
    acordo = registrar_acordo(
        contato, valor, modalidade, int(parcelas), tenant_id_da_sessao(request),
        chamada_id=int(chamada_id) if chamada_id.isdigit() else None,
        observacao=(request.POST.get('observacao') or '').strip(),
    )
    return redirect('acordos:detalhe', pk=acordo.id)


@web_login_required
def detalhe(request, pk):
    """Detalhe do acordo — valores, BR Code copia-e-cola, QR Code e ações (6.4)."""
    acordo = get_object_or_404(_acordos_scope(request).select_related('contato', 'tenant'), pk=pk)
    tenant = acordo.tenant

    pix_gerar = request.GET.get('gerar_pix') == '1' and tenant and tenant.pix_chave
    if pix_gerar and not acordo.pix_payload:
        acordo.pix_payload = montar_payload_pix(
            tenant.pix_chave, tenant.pix_recebedor, tenant.pix_cidade, acordo.valor_final,
        )
        acordo.status = 'pix_gerado'
        acordo.save(update_fields=['pix_payload', 'status', 'updated_at'])

    qr_svg = ''
    if acordo.pix_payload:
        qr_svg = qrcode_svg(acordo.pix_payload)

    wa_link = ''
    if acordo.contato.tel_normalizado:
        wa_link = 'https://wa.me/55' + acordo.contato.tel_normalizado

    return render(request, 'acordos/detalhe.html', {
        'acordo': _dados_acordo(acordo),
        'pix_payload': acordo.pix_payload,
        'qr_svg': qr_svg,
        'wa_link': wa_link,
        'pix_configurado': bool(tenant and tenant.pix_chave),
        'contato': {'id': acordo.contato_id, 'nome': acordo.contato.nome},
    })


@web_login_required
@web_requer_edicao
@require_POST
def marcar_pago(request, pk):
    """Marca o acordo como pago (6.4.8 — registra o estado da operação)."""
    acordo = get_object_or_404(_acordos_scope(request), pk=pk)
    acordo.status = 'pago'
    acordo.pago_em = timezone.now()
    acordo.save(update_fields=['status', 'pago_em', 'updated_at'])
    return redirect('acordos:detalhe', pk=acordo.id)


@web_login_required
@web_requer_edicao
@require_POST
def recusar(request, pk):
    """Registra recusa do acordo."""
    acordo = get_object_or_404(_acordos_scope(request), pk=pk)
    acordo.status = 'recusado'
    acordo.save(update_fields=['status', 'updated_at'])
    return redirect('acordos:detalhe', pk=acordo.id)
