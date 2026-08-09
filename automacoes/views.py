"""Views web do app automacoes — regras no-code de negócio.

Listagem com cards (ativa/desativada, ações, contadores e execuções recentes),
formulário "sem código" (gatilho + lista de ações), além de ativar/desativar,
duplicar, excluir, testar e o botão "verificar estagnados agora".
Gestão é restrita ao admin (da clínica ou da plataforma); os demais papéis
apenas visualizam a lista.
"""

import json

from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from acesso.decorators import (
    e_admin_do_tenant,
    web_login_required,
    web_requer_admin,
)
from acesso.models import Usuario
from automacoes.engine import disparar, executar_estagnados
from automacoes.models import ACOES, TRIGGERS, Automacao, PassoAutomacao, RegistroExecucao
from contatos.models import Contato
from emails.models import ModeloEmail
from funil.models import etapa_map_do_tenant, etapas_do_tenant
from tarefas.models import PRIORIDADES

LIMITE_PASSOS = 20

CORES_TRIGGER = {
    'contato_criado': '#7fe3c4',
    'negocio_criado': '#60a5fa',
    'negocio_movido': '#fbbf24',
    'negocio_estagnado': '#f87171',
}

EMOJIS_ACAO = {
    'tarefa': '📋',
    'nota': '🗒️',
    'tag': '🏷️',
    'email': '✉️',
}


def _tenant_id(request):
    return request.session.get('usuario', {}).get('tenant_id')


def _descricao(a, mapa):
    """Frase humana que descreve o gatilho da automação (para os cards da lista)."""
    p = a.parametros or {}
    if a.trigger == 'negocio_movido':
        alvo = (p.get('para_etapa') or '').strip()
        if alvo:
            nome = mapa.get(alvo, {}).get('name', alvo)
            return f'Quando um negócio entrar em “{nome}”'
        return 'Quando um negócio mudar de etapa'
    if a.trigger == 'negocio_estagnado':
        dias = p.get('dias', 7)
        etapa = (p.get('etapa') or '').strip()
        extra = f' em “{mapa.get(etapa, {}).get("name", etapa)}”' if etapa else ''
        return f'Negócios abertos parados há {dias} dia(s){extra}'
    if a.trigger == 'contato_criado':
        return 'Quando um contato novo for cadastrado'
    return 'Quando um negócio novo for criado'


# ---------------------------------------------------------------------------
# Validação/parse do formulário
# ---------------------------------------------------------------------------


def _parametros_do_trigger(trigger, request, tid, erros):
    """Parâmetros do gatilho vindos do formulário (etapa de destino / dias de estagnação)."""
    p = {}
    mapa = etapa_map_do_tenant(tid)
    if trigger == 'negocio_movido':
        para = (request.POST.get('para_etapa') or '').strip()
        if para and para not in mapa:
            erros.append('Etapa de destino inválida.')
        else:
            p['para_etapa'] = para
    elif trigger == 'negocio_estagnado':
        raw = (request.POST.get('dias') or '').strip()
        try:
            dias = int(raw) if raw else 7
            dias = max(1, min(dias, 90))
        except ValueError:
            dias = 7
        p['dias'] = dias
        etapa = (request.POST.get('etapa_estagnada') or '').strip()
        if etapa and etapa not in mapa:
            erros.append('Etapa do estagnado inválida.')
        else:
            p['etapa'] = etapa
    return p


def _parametros_do_passo(raw, tid, erros, idx):
    """Converte uma linha do builder em (acao, parametros); None quando inválida."""
    if not isinstance(raw, dict):
        erros.append(f'Passo {idx + 1} inválido.')
        return None
    acao = raw.get('acao', '')
    if acao not in dict(ACOES):
        erros.append(f'Passo {idx + 1}: escolha uma ação válida.')
        return None
    p = {}
    if acao == 'tarefa':
        p['titulo'] = (raw.get('titulo') or '').strip()
        prio = raw.get('prioridade', 'media')
        p['prioridade'] = prio if prio in dict(PRIORIDADES) else 'media'
        dias = (raw.get('vencimento_dias') or '').strip()
        if dias:
            try:
                dias_i = int(dias)
                if dias_i < 0:
                    raise ValueError
                p['vencimento_dias'] = dias_i
            except ValueError:
                erros.append(f'Passo {idx + 1}: vencimento em dias inválido.')
        resp = (raw.get('responsavel_id') or '').strip()
        if resp.isdigit() and Usuario.objects.filter(tenant_id=tid, pk=resp).exists():
            p['responsavel_id'] = int(resp)
    elif acao == 'nota':
        p['texto'] = (raw.get('texto') or '').strip()
        if not p['texto']:
            erros.append(f'Passo {idx + 1}: escreva o texto da nota.')
    elif acao == 'tag':
        p['tag'] = (raw.get('tag') or '').strip()
        if not p['tag']:
            erros.append(f'Passo {idx + 1}: informe o nome da tag.')
    elif acao == 'email':
        mid = (raw.get('modelo_id') or '').strip()
        if mid.isdigit() and ModeloEmail.objects.filter(tenant_id=tid, pk=mid).exists():
            p['modelo_id'] = int(mid)
        else:
            erros.append(f'Passo {idx + 1}: escolha um modelo de e-mail válido.')
    return (acao, p)


def _salvar(request, automacao, tid):
    """Valida e grava (ou atualiza) uma automação + passos; devolve (erros, automacao|None)."""
    erros = []
    nome = (request.POST.get('nome') or '').strip()
    trigger = request.POST.get('trigger', '')
    if not nome:
        erros.append('Informe o nome da automação.')
    if trigger not in dict(TRIGGERS):
        erros.append('Escolha um gatilho.')
    parametros = _parametros_do_trigger(trigger, request, tid, erros)

    passos_raw = request.POST.get('passos_json', '[]')
    try:
        passos_lista = json.loads(passos_raw)
    except json.JSONDecodeError:
        passos_lista = []
    if not isinstance(passos_lista, list) or not passos_lista:
        erros.append('Adicione pelo menos uma ação.')
    passos = []
    for i, raw in enumerate(passos_lista[:LIMITE_PASSOS]):
        result = _parametros_do_passo(raw, tid, erros, i)
        if result is not None:
            passos.append(result)

    if erros:
        return erros, None

    if automacao is None:
        automacao = Automacao.objects.create(
            tenant_id=tid,
            nome=nome,
            trigger=trigger,
            parametros=parametros,
            ativa=request.POST.get('ativa') == 'on',
            criado_por_id=request.session.get('usuario_id'),
        )
    else:
        automacao.nome = nome
        automacao.trigger = trigger
        automacao.parametros = parametros
        automacao.ativa = request.POST.get('ativa') == 'on'
        automacao.save(update_fields=['nome', 'trigger', 'parametros', 'ativa'])
        automacao.passos.all().delete()
    for i, (acao, p) in enumerate(passos):
        PassoAutomacao.objects.create(automacao=automacao, ordem=i, acao=acao, parametros=p)
    return erros, automacao


def _passos_para_form(automacao):
    """Passos prontos para o builder do formulário (edição)."""
    passos = []
    for i, p in enumerate(automacao.passos.all().order_by('ordem', 'id')):
        params = p.parametros or {}
        passos.append({
            'idx': i,
            'acao': p.acao,
            'titulo': params.get('titulo', ''),
            'prioridade': params.get('prioridade', 'media'),
            'vencimento_dias': params.get('vencimento_dias', ''),
            'responsavel_id': params.get('responsavel_id', ''),
            'texto': params.get('texto', ''),
            'tag': params.get('tag', ''),
            'modelo_id': params.get('modelo_id', ''),
        })
    return passos


def _passos_post_para_form(passos_raw):
    """Passos do POST (erro de validação) de volta ao formato do builder."""
    if not isinstance(passos_raw, list):
        return []
    passos = []
    for i, raw in enumerate(passos_raw[:LIMITE_PASSOS]):
        if not isinstance(raw, dict):
            continue
        passos.append({
            'idx': i,
            'acao': raw.get('acao', 'tarefa'),
            'titulo': raw.get('titulo', ''),
            'prioridade': raw.get('prioridade', 'media'),
            'vencimento_dias': raw.get('vencimento_dias', ''),
            'responsavel_id': raw.get('responsavel_id', ''),
            'texto': raw.get('texto', ''),
            'tag': raw.get('tag', ''),
            'modelo_id': raw.get('modelo_id', ''),
        })
    return passos


def _ctx_form(request, automacao, erros):
    """Contexto compartilhado do formulário (novo/editar)."""
    tid = _tenant_id(request)
    membros = list(Usuario.objects.filter(tenant_id=tid).order_by('nome').values('id', 'nome'))
    modelos = list(ModeloEmail.objects.filter(tenant_id=tid).order_by('-created_at').values('id', 'nome'))
    if request.method == 'POST':
        # erro de validação: preserva o que o admin já digitou no builder
        try:
            passos = _passos_post_para_form(json.loads(request.POST.get('passos_json', '[]')))
        except json.JSONDecodeError:
            passos = []
    else:
        passos = _passos_para_form(automacao) if automacao else []
    parametros_auto = (automacao.parametros or {}) if automacao else {}
    return {
        'editando': automacao is not None,
        'automacao': automacao,
        'erros': erros,
        'nome': request.POST.get('nome', automacao.nome if automacao else ''),
        'trigger': request.POST.get('trigger', automacao.trigger if automacao else 'contato_criado'),
        'para_etapa': request.POST.get('para_etapa', parametros_auto.get('para_etapa', '')),
        'dias': request.POST.get('dias', parametros_auto.get('dias', 7)),
        'etapa_estagnada': request.POST.get('etapa_estagnada', parametros_auto.get('etapa', '')),
        'ativa': (automacao.ativa if automacao else True),
        'stages': etapas_do_tenant(tid),
        'membros': membros,
        'modelos': modelos,
        'prioridades': PRIORIDADES,
        'passos_edit': passos,
        # JSONs consumidos pelo builder JS (pares [valor, rótulo])
        'membros_json': json.dumps([[str(m['id']), m['nome']] for m in membros]),
        'modelos_json': json.dumps([[str(m['id']), m['nome']] for m in modelos]),
        'passos_json': json.dumps(passos).replace('<', '\\u003c'),
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


@web_login_required
def lista(request):
    tid = _tenant_id(request)
    msg = request.GET.get('msg', '')
    if tid is not None:
        automacoes = (
            Automacao.objects.filter(tenant_id=tid)
            .prefetch_related('passos')
            .annotate(qtd_exec=Count('execucoes'))
        )
        execucoes = (
            RegistroExecucao.objects.filter(automacao__tenant_id=tid)
            .select_related('automacao', 'contato')
            .order_by('-created_at')[:10]
        )
    else:
        automacoes = Automacao.objects.none()
        execucoes = []
    mapa = etapa_map_do_tenant(tid)
    itens = [
        {
            'id': a.id,
            'nome': a.nome,
            'trigger': a.trigger,
            'trigger_label': dict(TRIGGERS)[a.trigger],
            'trigger_cor': CORES_TRIGGER.get(a.trigger, '#94a3b8'),
            'descricao': _descricao(a, mapa),
            'ativa': a.ativa,
            'passos': [
                {'label': dict(ACOES)[p.acao], 'emoji': EMOJIS_ACAO.get(p.acao, '•')}
                for p in a.passos.all()
            ],
            'qtd_exec': a.qtd_exec,
            'ultima_execucao': a.ultima_execucao,
        }
        for a in automacoes
    ]
    return render(request, 'automacoes/lista.html', {
        'itens': itens,
        'execucoes': execucoes,
        'msg': msg,
        'pode_gerenciar': e_admin_do_tenant(request),
        'tem_tenant': tid is not None,
    })


@web_login_required
@web_requer_admin
def nova(request):
    tid = _tenant_id(request)
    if tid is None:
        return redirect('automacoes:lista')
    erros = []
    if request.method == 'POST':
        erros, auto = _salvar(request, None, tid)
        if auto:
            return redirect('automacoes:lista')
    return render(request, 'automacoes/formulario.html', _ctx_form(request, None, erros))


@web_login_required
@web_requer_admin
def editar(request, pk):
    tid = _tenant_id(request)
    automacao = get_object_or_404(Automacao.objects.filter(tenant_id=tid), pk=pk)
    erros = []
    if request.method == 'POST':
        erros, auto = _salvar(request, automacao, tid)
        if auto:
            return redirect('automacoes:lista')
    return render(request, 'automacoes/formulario.html', _ctx_form(request, automacao, erros))


@web_login_required
@web_requer_admin
def ativar(request, pk):
    automacao = get_object_or_404(Automacao.objects.filter(tenant_id=_tenant_id(request)), pk=pk)
    if request.method == 'POST':
        automacao.ativa = not automacao.ativa
        automacao.save(update_fields=['ativa'])
    return redirect('automacoes:lista')


@web_login_required
@web_requer_admin
def duplicar(request, pk):
    automacao = get_object_or_404(Automacao.objects.filter(tenant_id=_tenant_id(request)), pk=pk)
    if request.method == 'POST':
        copia = Automacao.objects.create(
            tenant_id=automacao.tenant_id,
            nome=automacao.nome + ' (cópia)',
            trigger=automacao.trigger,
            parametros=automacao.parametros,
            ativa=False,  # cópia nasce desativada, para o admin conferir antes de ligar
            criado_por_id=request.session.get('usuario_id'),
        )
        for i, p in enumerate(automacao.passos.all().order_by('ordem', 'id')):
            PassoAutomacao.objects.create(
                automacao=copia, ordem=i, acao=p.acao, parametros=p.parametros
            )
    return redirect('automacoes:lista')


@web_login_required
@web_requer_admin
def excluir(request, pk):
    automacao = get_object_or_404(Automacao.objects.filter(tenant_id=_tenant_id(request)), pk=pk)
    if request.method == 'POST':
        automacao.delete()
    return redirect('automacoes:lista')


@web_login_required
@web_requer_admin
def testar(request, pk):
    """Executa a automação uma vez contra o contato mais recente do tenant (sanity check)."""
    automacao = get_object_or_404(Automacao.objects.filter(tenant_id=_tenant_id(request)), pk=pk)
    if request.method == 'POST' and automacao.trigger != 'negocio_estagnado':
        contato = Contato.objects.filter(tenant_id=automacao.tenant_id).order_by('-id').first()
        if contato is None:
            url = reverse('automacoes:lista') + '?msg=sem-contato'
        else:
            disparar(
                automacao.trigger,
                tenant_id=automacao.tenant_id,
                contato=contato,
                negocio=contato.negocio,
                para_etapa=(automacao.parametros or {}).get('para_etapa', ''),
            )
            url = reverse('automacoes:lista') + '?msg=testado'
        return redirect(url)
    return redirect('automacoes:lista')


@web_login_required
@web_requer_admin
def estagnadas(request):
    """Verifica agora os negócios parados e dispara as automações de estagnação."""
    if request.method == 'POST':
        tid = _tenant_id(request)
        if tid is None:
            return redirect('automacoes:lista')  # admin_saas não tem clínica para varrer
        n = executar_estagnados(tid)
        return redirect(reverse('automacoes:lista') + f'?msg=estagnados-{n}')
    return redirect('automacoes:lista')
