"""Views do app 'discador' — Nation Dialer (PRD Sprint 5).

Tela do operador (5.1.5): escolhe a fila, vê os contatos (nome, empresa, cargo e
telefone) com prioridade, inicia a chamada com uma ação única (5.2.2) e registra
o resultado (5.2.5). O script da operação é exibido durante a chamada (5.3.3).
Filas e scripts são geridos pelo admin da empresa.
"""

import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from acesso.decorators import (
    filtro_tenant,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_admin,
    web_requer_edicao,
)
from contatos.models import Contato
from core.dominio import STAGE_MAP
from discador.models import Chamada, Fila, Script
from discador.softphone import uri_chamada


def _filas_scope(request):
    qs = Fila.objects.all()
    tid = tenant_id_da_sessao(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _scripts_scope(request):
    qs = Script.objects.all()
    tid = tenant_id_da_sessao(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _chamadas_scope(request):
    qs = Chamada.objects.all()
    tid = tenant_id_da_sessao(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _dados_contato(contato, ultima_chamada=None):
    """Dict com os dados do contato para a fila (5.1.4 — exibir dados do contato)."""
    negocio = contato.negocio
    stage = STAGE_MAP.get(negocio.stage, {}) if negocio else {}
    return {
        'id': contato.id,
        'nome': contato.nome,
        'empresa': contato.empresa,
        'cargo': contato.cargo,
        'tel': contato.tel,
        'tel_normalizado': contato.tel_normalizado,
        'score': contato.lead_score,
        'score_nivel': ('quente' if contato.lead_score >= 40
                        else 'morno' if contato.lead_score >= 20 else 'frio'),
        'etapa': stage.get('name', '—'),
        'etapa_cor': stage.get('color', '#94a3b8'),
        'uri': uri_chamada(contato, contato.tenant),
        'ultima_chamada': ultima_chamada,
    }


def _ultima_chamada_por_contato(contato_ids):
    """Última chamada de cada contato (mapa id → dict), sem N+1."""
    mapa = {}
    for c in Chamada.objects.filter(contato_id__in=contato_ids).order_by('-created_at'):
        if c.contato_id not in mapa:
            mapa[c.contato_id] = {
                'id': c.id,
                'status': c.status,
                'status_label': c.get_status_display(),
                'observacao': c.observacao,
                'retorno_em': c.retorno_em,
            }
    return mapa


@web_login_required
def operador(request):
    """Tela do operador — fila, contatos, script e ação de chamada (5.1.5)."""
    filas = _filas_scope(request)
    fila_id = request.GET.get('fila', '')
    fila = None
    if fila_id.isdigit():
        fila = filas.filter(pk=int(fila_id)).first()
    if fila is None:
        fila = filas.filter(ativa=True).first() or filas.first()

    contatos = []
    if fila is not None:
        qs = fila.contatos()
        # Ordem configurada preservada + sem N+1 (negocios prefetched, tenant/carteira select_related)
        objetos = list(qs.select_related('tenant', 'carteira').prefetch_related('negocios')[:200])
        mapa = _ultima_chamada_por_contato([c.id for c in objetos])
        contatos = [_dados_contato(c, mapa.get(c.id)) for c in objetos]

    script = fila.script_ativo() if fila is not None else None
    script_passos = []
    if script is not None:
        for linha in script.conteudo.splitlines():
            linha = linha.strip()
            if linha:
                script_passos.append(linha.removeprefix('- '))

    return render(request, 'discador/operador.html', {
        'filas': filas,
        'fila': fila,
        'fila_selecionada': fila.id if fila else None,
        'contatos': contatos,
        'script': script,
        'script_passos': script_passos,
        'status_opcoes': Chamada.STATUS,
        'total_fila': len(contatos),
    })


@require_POST
@web_login_required
@web_requer_edicao
def chamar(request, fila_id):
    """Inicia a chamada com ação única: registra a Chamada (discada) e devolve a URI.

    O JavaScript abre a URI (sip:/tel:) — o softphone (MicroSIP) é disparado pelo
    navegador. Retorna JSON.
    """
    fila = get_object_or_404(_filas_scope(request), pk=fila_id)
    try:
        dados = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido.'}, status=400)
    raw_id = dados.get('contato_id', 0)
    if not str(raw_id).isdigit():
        return JsonResponse({'ok': False, 'erro': 'Contato inválido.'}, status=400)
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()),
        pk=int(raw_id),
    )
    if not contato.tel_normalizado:
        return JsonResponse({'ok': False, 'erro': 'Contato sem telefone válido.'}, status=400)
    chamada = Chamada.objects.create(
        fila=fila,
        contato=contato,
        operador_id=request.session.get('usuario_id'),
        tenant_id=tenant_id_da_sessao(request),
    )
    return JsonResponse({
        'ok': True,
        'chamada_id': chamada.id,
        'uri': uri_chamada(contato, contato.tenant),
    })


@require_POST
@web_login_required
@web_requer_edicao
def registrar_resultado(request, pk):
    """Registra o resultado da chamada (5.2.5). Retorna JSON.

    Quando o resultado é "Retornar depois" com data, cria automaticamente uma
    Tarefa de follow-up (S6 — 6.2): responsável = operador, vencimento = retorno.
    """
    chamada = get_object_or_404(_chamadas_scope(request), pk=pk)
    try:
        dados = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido.'}, status=400)
    status = dados.get('status', '')
    if status not in dict(Chamada.STATUS):
        return JsonResponse({'ok': False, 'erro': 'Status inválido.'}, status=400)
    chamada.status = status
    chamada.observacao = (dados.get('observacao') or '').strip()
    retorno = dados.get('retorno_em') or ''
    chamada.retorno_em = retorno or None
    chamada.save(update_fields=['status', 'observacao', 'retorno_em', 'updated_at'])

    followup = None
    if status == 'retornar':
        from tarefas.models import Tarefa

        retorno_date = None
        if retorno:
            try:
                retorno_date = date.fromisoformat(str(retorno)[:10])
            except ValueError:
                retorno_date = None
        if retorno_date and chamada.tenant_id is not None:
            # Tarefa exige tenant (null=False) — sem tenant (admin_saas) não cria follow-up
            followup = Tarefa.objects.create(
                tenant_id=chamada.tenant_id,
                titulo=f'Retornar ligação — {chamada.contato.nome}',
                descricao=chamada.observacao or 'Retorno da chamada registrado no discador',
                contato=chamada.contato,
                responsavel_id=request.session.get('usuario_id'),
                criado_por_id=request.session.get('usuario_id'),
                vencimento=retorno_date,
                prioridade='alta',
            )

    return JsonResponse({'ok': True, 'status_label': chamada.get_status_display(),
                         'followup': bool(followup)})


@web_login_required
@web_requer_admin
def filas(request):
    """Lista as filas da operação (gestão — admin da empresa)."""
    itens = []
    for f in _filas_scope(request).prefetch_related('chamadas'):
        total = f.contatos().count()
        chamadas = f.chamadas.all()
        itens.append({
            'id': f.id,
            'nome': f.nome,
            'descricao': f.descricao,
            'carteira': f.carteira.nome if f.carteira_id else 'Todos os contatos',
            'ordem': f.get_ordem_display(),
            'ativa': f.ativa,
            'script': f.script.nome if f.script_id else None,
            'total_contatos': total,
            'total_chamadas': chamadas.count(),
        })
    return render(request, 'discador/filas.html', {'itens': itens})


@web_login_required
@web_requer_admin
def fila_form(request, pk=None):
    """Cria/edita uma fila (admin)."""
    fila = get_object_or_404(_filas_scope(request), pk=pk) if pk else None
    erros = []
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            erros.append('Informe o nome da fila.')
        elif _filas_scope(request).filter(nome__iexact=nome).exclude(pk=fila.pk if fila else None).exists():
            erros.append(f'Já existe uma fila chamada "{nome}".')
        if not erros:
            if fila is None:
                fila = Fila(tenant_id=tenant_id_da_sessao(request))
            fila.nome = nome
            fila.descricao = (request.POST.get('descricao') or '').strip()
            fila.ordem = request.POST.get('ordem', 'score')
            fila.ativa = request.POST.get('ativa') == 'on'
            carteira_id = request.POST.get('carteira_id', '')
            fila.carteira_id = int(carteira_id) if carteira_id.isdigit() else None
            script_id = request.POST.get('script_id', '')
            fila.script_id = int(script_id) if script_id.isdigit() else None
            fila.save()
            return redirect('discador:filas')

    carteiras = filtro_tenant(request, Contato.carteira.field.related_model.objects.all())
    scripts = _scripts_scope(request)
    return render(request, 'discador/fila_form.html', {
        'fila': fila,
        'titulo_form': 'Editar fila' if fila else 'Nova fila',
        'erros': erros,
        'carteiras': carteiras,
        'scripts': scripts,
        'ordens': Fila.ORDENS,
        'nome': request.POST.get('nome', fila.nome if fila else ''),
        'descricao': request.POST.get('descricao', fila.descricao if fila else ''),
        'ordem': request.POST.get('ordem', fila.ordem if fila else 'score'),
        'ativa': (fila.ativa if fila else True) or request.POST.get('ativa') == 'on',
        'carteira_selecionada': request.POST.get('carteira_id', str(fila.carteira_id) if fila and fila.carteira_id else ''),
        'script_selecionado': request.POST.get('script_id', str(fila.script_id) if fila and fila.script_id else ''),
    })


@web_login_required
@web_requer_admin
def fila_excluir(request, pk):
    """Exclui uma fila (admin)."""
    fila = get_object_or_404(_filas_scope(request), pk=pk)
    if request.method == 'POST':
        fila.delete()
        return redirect('discador:filas')
    return render(request, 'discador/fila_form.html', {
        'confirmar_exclusao': True,
        'fila': fila,
        'titulo_form': 'Excluir fila',
        'erros': [],
        'carteiras': [],
        'scripts': [],
        'ordens': Fila.ORDENS,
        'nome': fila.nome,
        'descricao': fila.descricao,
        'ordem': fila.ordem,
        'ativa': fila.ativa,
        'carteira_selecionada': str(fila.carteira_id) if fila.carteira_id else '',
        'script_selecionado': str(fila.script_id) if fila.script_id else '',
    })


@web_login_required
@web_requer_admin
def scripts(request):
    """Lista os scripts de atendimento (gestão — admin da empresa)."""
    itens = [
        {
            'id': s.id,
            'nome': s.nome,
            'descricao': s.descricao,
            'ativa': s.ativa,
            'passos': len([p for p in s.conteudo.splitlines() if p.strip()]),
        }
        for s in _scripts_scope(request)
    ]
    return render(request, 'discador/scripts.html', {'itens': itens})


@web_login_required
@web_requer_admin
def script_form(request, pk=None):
    """Cria/edita um script de atendimento (admin)."""
    script = get_object_or_404(_scripts_scope(request), pk=pk) if pk else None
    erros = []
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        conteudo = (request.POST.get('conteudo') or '').strip()
        if not nome:
            erros.append('Informe o nome do script.')
        elif _scripts_scope(request).filter(nome__iexact=nome).exclude(pk=script.pk if script else None).exists():
            erros.append(f'Já existe um script chamado "{nome}".')
        if not conteudo:
            erros.append('Escreva o roteiro (um passo por linha).')
        if not erros:
            if script is None:
                script = Script(tenant_id=tenant_id_da_sessao(request))
            script.nome = nome
            script.descricao = (request.POST.get('descricao') or '').strip()
            script.conteudo = conteudo
            script.ativa = request.POST.get('ativa') == 'on'
            script.save()
            return redirect('discador:scripts')
    return render(request, 'discador/script_form.html', {
        'script': script,
        'titulo_form': 'Editar script' if script else 'Novo script',
        'erros': erros,
        'nome': request.POST.get('nome', script.nome if script else ''),
        'descricao': request.POST.get('descricao', script.descricao if script else ''),
        'conteudo': request.POST.get('conteudo', script.conteudo if script else ''),
        'ativa': (script.ativa if script else True) or request.POST.get('ativa') == 'on',
    })


@web_login_required
@web_requer_admin
def script_excluir(request, pk):
    """Exclui um script (admin)."""
    script = get_object_or_404(_scripts_scope(request), pk=pk)
    if request.method == 'POST':
        script.delete()
        return redirect('discador:scripts')
    return render(request, 'discador/script_form.html', {
        'confirmar_exclusao': True,
        'script': script,
        'titulo_form': 'Excluir script',
        'erros': [],
        'nome': script.nome,
        'descricao': script.descricao,
        'conteudo': script.conteudo,
        'ativa': script.ativa,
    })
