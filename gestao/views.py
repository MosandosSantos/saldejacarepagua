"""Views do Dashboard de Inscricoes (GEOD-CEOD) e do Modulo de Comunicacao."""
import json
from datetime import timedelta
from collections import defaultdict

from django.conf import settings
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from acesso.decorators import pode_editar, web_login_required
from core.utils import brl as _brl, brl_curto as _brl_curto
from gestao.comunicacao import (
    disparar_async,
    listar_lojas,
    listar_prefeituras,
    montar_destinatarios,
)
from gestao.models import (
    Campanha, Capitulo, Congressista, Inscricao, Pagamento, TipoInscricao,
)
from gestao.whatsapp import obter_qr_code, verificar_conexao


def _evento_atual():
    """Retorna o evento mais recente (placeholder — por enquanto usa todos)."""
    return None


# _brl, _brl_curto → importados de core.utils


@web_login_required
def dashboard(request):
    """Dashboard principal de inscricoes (GEOD-CEOD)."""
    hoje = timezone.now().date()
    inicio_6meses = hoje - timedelta(days=180)

    # ================================================================
    # KPIs
    # ================================================================
    ano_corrente = hoje.year

    # IAS Ativas (Inscricoes ativas)
    ias_ativas = Inscricao.objects.filter(
        status__in=Inscricao.STATUS_ATIVOS
    ).count()

    # Membros ativos (congressistas vinculados a inscricoes ativas)
    membros_ativos = Congressista.objects.filter(
        inscricao__status__in=Inscricao.STATUS_ATIVOS
    ).count()

    # Sessoes no ano (inscricoes criadas no ano corrente)
    sessoes_ano = Inscricao.objects.filter(
        criado_em__year=ano_corrente
    ).count()

    # Caixa (total arrecadado — pagamentos confirmados/sistema)
    caixa = Pagamento.objects.filter(
        status__in=['confirmado', 'sistema']
    ).aggregate(total=Sum('valor'))['total'] or 0

    # Novos no ano corrente (congressistas criados no ano corrente)
    novos_ano = Congressista.objects.filter(
        created_at__year=ano_corrente
    ).count()

    # ================================================================
    # Grafico 1: Inscricoes e cancelamentos por mes (ultimos 6 meses)
    # ================================================================
    inscricoes_por_mes = (
        Inscricao.objects.filter(criado_em__date__gte=inicio_6meses)
        .annotate(mes=TruncMonth('criado_em'))
        .values('mes')
        .annotate(
            total=Count('id'),
            canceladas=Count('id', filter=Q(status='cancelada')),
        )
        .order_by('mes')
    )
    meses_labels = []
    meses_inscritos = []
    meses_cancelados = []
    for item in inscricoes_por_mes:
        meses_labels.append(item['mes'].strftime('%b/%Y'))
        meses_inscritos.append(item['total'] - item['canceladas'])
        meses_cancelados.append(item['canceladas'])

    # ================================================================
    # Grafico 2: Funil de conversao (horizontal)
    # ================================================================
    fluxo_labels = {
        'emitiu_boleto': 'Emitiu Boleto',
        'aguardando_aprovacao': 'Aguard. Aprovacao',
        'aguardando_documentos': 'Aguard. Documentos',
        'aprovado': 'Aprovado',
        'hospedado': 'Hospedado',
        'nao_compareceu': 'Nao Compareceu',
    }
    fluxo_valores = []
    fluxo_nomes = []
    for status in Inscricao.FLUXO_KANBAN:
        # Acumulado: cada etapa soma a si + posteriores
        count = Inscricao.objects.filter(
            status__in=Inscricao.FLUXO_KANBAN[Inscricao.FLUXO_KANBAN.index(status):]
        ).count()
        fluxo_valores.append(count)
        fluxo_nomes.append(fluxo_labels.get(status, status))

    # ================================================================
    # Grafico 3: Tipos de inscricao (donut)
    # ================================================================
    tipos_data = (
        Inscricao.objects.filter(status__in=Inscricao.STATUS_ATIVOS)
        .exclude(tipo__isnull=True)
        .values('tipo__nome')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    tipos_labels = [t['tipo__nome'] for t in tipos_data]
    tipos_valores = [t['total'] for t in tipos_data]

    # ================================================================
    # Grafico 4: Categorias (barras horizontais)
    # ================================================================
    categorias_data = (
        Congressista.objects.filter(inscricao__status__in=Inscricao.STATUS_ATIVOS)
        .values('categoria')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    cat_map = dict(Congressista.CATEGORIAS)
    cat_labels = [cat_map.get(c['categoria'], c['categoria']) for c in categorias_data]
    cat_valores = [c['total'] for c in categorias_data]

    # ================================================================
    # Grafico 5: Forma de pagamento (barras horizontais)
    # ================================================================
    pagamentos_data = (
        Pagamento.objects.filter(status__in=['confirmado', 'sistema'])
        .values('forma')
        .annotate(total=Count('id'), valor_total=Sum('valor'))
        .order_by('-total')
    )
    forma_map = dict(Pagamento.FORMA_CHOICES)
    # Mapear CREDIT_CARD para CARTAO
    pag_labels = [forma_map.get(p['forma'], p['forma']).replace('Cartao de Credito', 'CARTAO') for p in pagamentos_data]
    pag_valores = [p['total'] for p in pagamentos_data]

    # ================================================================
    # Grafico 6: McDia Feliz por capitulo (barras verticais, amarelas)
    # ================================================================
    mcdia_data = (
        Congressista.objects.filter(
            mc_lanche=True,
            inscricao__status__in=Inscricao.STATUS_ATIVOS,
            capitulo__isnull=False,
        )
        .values('capitulo__nome')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    mcdia_labels = [c['capitulo__nome'] for c in mcdia_data]
    mcdia_valores = [c['total'] for c in mcdia_data]

    # ================================================================
    # Grafico 7: Camisas por tamanho (barras verticais, azuis)
    # ================================================================
    camisas_data = (
        Congressista.objects.filter(
            inscricao__status__in=Inscricao.STATUS_ATIVOS,
        )
        .exclude(tamanho_camisa='')
        .exclude(tamanho_camisa='OUTRO')
        .values('tamanho_camisa')
        .annotate(total=Count('id'))
        .order_by('tamanho_camisa')
    )
    camisas_labels = [c['tamanho_camisa'] for c in camisas_data]
    camisas_valores = [c['total'] for c in camisas_data]

    # ================================================================
    # Grafico 8: Congressistas por capitulo (barras horizontais)
    # ================================================================
    capitulo_data = (
        Congressista.objects.filter(
            inscricao__status__in=Inscricao.STATUS_ATIVOS,
            capitulo__isnull=False,
        )
        .values('capitulo__nome')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    cap_labels = [c['capitulo__nome'] for c in capitulo_data]
    cap_valores = [c['total'] for c in capitulo_data]

    # ================================================================
    # Cores do tema GEOD-CEOD
    # ================================================================
    cores = {
        'primary': '#1a5fb4',
        'accent': '#5b8def',
        'accent_bright': '#93b8f7',
        'success': '#4ade80',
        'danger': '#ef4444',
        'warning': '#fbbf24',
        'blue': '#5b8def',
        'yellow': '#fbbf24',
    }

    return render(request, 'gestao/dashboard.html', {
        # KPIs
        'ias_ativas': ias_ativas,
        'membros_ativos': membros_ativos,
        'sessoes_ano': sessoes_ano,
        'caixa': _brl(caixa),
        'caixa_valor': float(caixa),
        'novos_ano': novos_ano,
        'ano_corrente': ano_corrente,
        # Dados para Chart.js (via json_script — NUNCA |safe)
        'chart_meses_labels': json.dumps(meses_labels),
        'chart_meses_inscritos': json.dumps(meses_inscritos),
        'chart_meses_cancelados': json.dumps(meses_cancelados),
        'chart_fluxo_labels': json.dumps(fluxo_nomes),
        'chart_fluxo_valores': json.dumps(fluxo_valores),
        'chart_tipos_labels': json.dumps(tipos_labels),
        'chart_tipos_valores': json.dumps(tipos_valores),
        'chart_cat_labels': json.dumps(cat_labels),
        'chart_cat_valores': json.dumps(cat_valores),
        'chart_pag_labels': json.dumps(pag_labels),
        'chart_pag_valores': json.dumps(pag_valores),
        'chart_mcdia_labels': json.dumps(mcdia_labels),
        'chart_mcdia_valores': json.dumps(mcdia_valores),
        'chart_camisas_labels': json.dumps(camisas_labels),
        'chart_camisas_valores': json.dumps(camisas_valores),
        'chart_cap_labels': json.dumps(cap_labels),
        'chart_cap_valores': json.dumps(cap_valores),
        # Cores
        'cores': cores,
    })


@web_login_required
def comunicacoes(request):
    """Painel unico de comunicacao (PRD_comunicacao): form de envio + historico.

    Destinatarios por Prefeitura/Loja do GPRB: Prefeitura (ou Todas) envia para
    o Prefeito; Loja envia para o Deputado Mestre da loja.
    """
    erros = []
    sucesso = None

    if request.method == 'POST':
        if not pode_editar(request):
            erros.append('Você não tem permissão para enviar comunicações — peça ao admin.')
        else:
            canal = request.POST.get('canal', '').strip().upper()
            origem = request.POST.get('origem', '').strip()
            corpo = request.POST.get('corpo', '').strip()
            assunto = request.POST.get('assunto', '').strip()

            canais_validos = [c[0] for c in Campanha.CANAIS]
            origens_validas = [o[0] for o in Campanha.ORIGENS]
            if canal not in canais_validos:
                erros.append('Escolha um canal de envio (E-mail ou WhatsApp).')
            if origem not in origens_validas:
                erros.append('Escolha uma origem de destinatários.')
            if not corpo:
                erros.append('Informe o corpo da mensagem.')
            if canal == 'EMAIL' and not assunto:
                erros.append('Informe o assunto (obrigatório para e-mail).')

            if not erros:
                destinatarios = montar_destinatarios(origem, canal, request, erros)
                if not destinatarios:
                    erros.append('Nenhum destinatário válido — verifique os filtros/lista.')

            if not erros:
                filtros = {}
                if origem == 'prefeituras':
                    filtros = {
                        'prefeitura': request.POST.get('filtro_prefeitura', '').strip(),
                        'loja': request.POST.get('filtro_loja', '').strip(),
                    }
                campanha = Campanha.objects.create(
                    canal=canal,
                    assunto=assunto,
                    corpo=corpo,
                    origem=origem,
                    filtros=filtros,
                    destinatarios=destinatarios,
                    criado_por=getattr(request, 'usuario_logado', None),
                )
                disparar_async(campanha.id)
                sucesso = (
                    f'Campanha criada para {len(destinatarios)} destinatário(s) — '
                    'o envio roda em segundo plano e o histórico é atualizado.'
                )

    origem_selecionada = request.POST.get('origem', 'prefeituras').strip()
    prefeitura_selecionada = request.POST.get('filtro_prefeitura', '').strip()
    loja_selecionada = request.POST.get('filtro_loja', '').strip()

    return render(request, 'gestao/comunicacoes.html', {
        'erros': erros,
        'sucesso': sucesso,
        'canais': Campanha.CANAIS,
        'origens': Campanha.ORIGENS,
        'origem': origem_selecionada,
        'prefeituras': listar_prefeituras(),
        'prefeitura_selecionada': prefeitura_selecionada,
        'lojas_da_prefeitura': listar_lojas(prefeitura_selecionada) if prefeitura_selecionada else [],
        'loja_selecionada': loja_selecionada,
        'historico': Campanha.objects.all()[:30],
        'email_configurado': settings.EMAIL_CONFIGURADO,
    })


@web_login_required
def zap_status(request):
    """JSON com o status da conexao WhatsApp (PRD §8)."""
    return JsonResponse(verificar_conexao())


@web_login_required
def zap_qrcode(request):
    """JSON com o QR code base64 (ou logado=True) para pareamento (PRD §8)."""
    return JsonResponse(obter_qr_code())
