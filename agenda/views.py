"""Views web da agenda (CRUD de eventos + registro de presença)."""
import datetime

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from acesso.decorators import (
    filtro_tenant,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from contatos.models import Filiacao, Loja

from .models import EventoAgenda, PresencaEvento, TipoEvento
from .permissions import agenda_requer_escrita, pode_escrever_agenda


def _lojas_do_tenant(request):
    tid = tenant_id_da_sessao(request)
    lojas = Loja.objects.all()
    if tid is not None:
        lojas = lojas.filter(tenant_id=tid)
    return lojas.order_by('nome', 'id')


def _evento_valido(request, tenant_id):
    """Extrai e valida o POST do form; retorna (instance, erro)."""
    dados = _dados_do_evento(request)
    if not dados['titulo']:
        return None, 'Informe o título.'
    if not dados['data_hora']:
        return None, 'Informe a data e hora.'
    if not dados['loja_id'].isdigit() or not dados['tipo_id'].isdigit():
        return None, 'Escolha a loja e o tipo do evento.'
    loja = Loja.objects.filter(
        id=int(dados['loja_id']), tenant_id=tenant_id,
    ).first()
    tipo = TipoEvento.objects.filter(id=int(dados['tipo_id'])).first()
    if loja is None or tipo is None:
        return None, 'Loja ou tipo inválido para este tenant.'
    try:
        data_hora = datetime.datetime.fromisoformat(dados['data_hora'])
    except ValueError:
        return None, 'Data inválida.'
    if timezone.is_naive(data_hora):
        data_hora = timezone.make_aware(data_hora)
    evento = EventoAgenda(
        loja=loja, tipo=tipo,
        titulo=dados['titulo'],
        data_hora=data_hora,
        local=dados['local'],
        descricao=dados['descricao'],
    )
    return evento, None


def _dados_do_evento(request):
    return {
        'loja_id': request.POST.get('loja', '').strip(),
        'tipo_id': request.POST.get('tipo', '').strip(),
        'titulo': request.POST.get('titulo', '').strip(),
        'data_hora': request.POST.get('data_hora', '').strip(),
        'local': request.POST.get('local', '').strip(),
        'descricao': request.POST.get('descricao', '').strip(),
    }


@web_login_required
def lista(request):
    """Lista de eventos do tenant (visível a todos os perfis logados)."""
    eventos = filtro_tenant(
        request, EventoAgenda.objects.select_related('loja', 'tipo'),
    ).order_by('-data_hora')

    loja = (request.GET.get('loja') or '').strip()
    tipo = (request.GET.get('tipo') or '').strip()
    if loja.isdigit():
        eventos = eventos.filter(loja_id=int(loja))
    if tipo.isdigit():
        eventos = eventos.filter(tipo_id=int(tipo))

    return render(request, 'agenda/lista.html', {
        'itens': eventos[:100],
        'tipos': TipoEvento.objects.order_by('nome'),
        'lojas': _lojas_do_tenant(request),
        'filtro_loja': loja, 'filtro_tipo': tipo,
        'pode_escrever': pode_escrever_agenda(request),
    })


def _avisos(request):
    return []


@web_login_required
@web_requer_tenant_context
@agenda_requer_escrita
def novo(request):
    tenant_id = tenant_id_da_sessao(request)
    if request.method == 'POST':
        evento, erro = _evento_valido(request, tenant_id)
        if evento is None:
            return redirect(f'/agenda/novo/?erro={erro}')
        evento.tenant_id = tenant_id
        evento.criado_por = _usuario_da_sessao(request)
        evento.save()
        return redirect('agenda:lista')
    return render(request, 'agenda/form.html', {
        'evento': None, 'tipos': TipoEvento.objects.order_by('nome'),
        'lojas': _lojas_do_tenant(request),
        'erro': request.GET.get('erro', ''), 'dados': {},
        'pode_escrever': True,
    })


def _usuario_da_sessao(request):
    from acesso.models import Usuario

    uid = request.session.get('usuario_id')
    if not uid:
        return None
    return Usuario.objects.filter(pk=uid).first()


@web_login_required
@web_requer_tenant_context
@agenda_requer_escrita
def editar(request, id):
    """Editar evento do tenant (GET mostra form, POST salva)."""
    eventos = filtro_tenant(request, EventoAgenda.objects.all())
    evento = get_object_or_404(eventos, pk=id)
    if request.method == 'POST':
        candidato, erro = _evento_valido(request, evento.tenant_id)
        if candidato is None:
            return redirect(f'/agenda/{id}/editar/?erro={erro}')
        evento.loja = candidato.loja
        evento.tipo = candidato.tipo
        evento.titulo = candidato.titulo
        evento.data_hora = candidato.data_hora
        evento.local = candidato.local
        evento.descricao = candidato.descricao
        evento.save()
        return redirect('agenda:lista')
    return render(request, 'agenda/form.html', {
        'evento': evento, 'tipos': TipoEvento.objects.order_by('nome'),
        'lojas': _lojas_do_tenant(request),
        'erro': request.GET.get('erro', ''), 'dados': {},
        'pode_escrever': True,
    })


@web_login_required
@web_requer_tenant_context
@agenda_requer_escrita
def excluir(request, id):
    """Excluir o evento do tenant (e best-effort no Google)."""
    eventos = filtro_tenant(request, EventoAgenda.objects.all())
    evento = get_object_or_404(eventos, pk=id)
    from .google_sync import remover_google

    remover_google(evento)
    evento.delete()
    return redirect('agenda:lista')


@web_login_required
@agenda_requer_escrita
def google_sync_view(request, id):
    """Envia o evento ao Google Calendar do tenant (POST)."""
    if request.method != 'POST':
        return redirect('agenda:lista')
    eventos = filtro_tenant(
        request, EventoAgenda.objects.select_related('loja', 'tipo', 'tenant'),
    )
    evento = get_object_or_404(eventos, pk=id)
    from .google_sync import sincronizar_google

    sincronizar_google(evento)
    return redirect('agenda:lista')


ESTADOS_VALIDOS = {'PRESENTE', 'AUSENTE', 'JUSTIFICADO'}


def _membros_do_evento(evento):
    """Membros ATIVOS filiados à loja do evento (fonte: Filiacao)."""
    from contatos.models import Membro

    return Membro.objects.filter(
        filiacoes__loja_id=evento.loja_id,
        situacao='ATIVO',
    ).order_by('nome', 'id')


@web_login_required
@agenda_requer_escrita
def presenca(request, id):
    """Form de presença: lista membros ativos da loja com rádio por estado."""
    eventos = filtro_tenant(request, EventoAgenda.objects.select_related('loja'))
    evento = get_object_or_404(eventos, pk=id)
    membros = _membros_do_evento(evento)
    estados = {
        p.membro_id: p for p in PresencaEvento.objects.filter(evento=evento)
    }
    linhas = [
        {'membro': m, 'presenca': estados.get(m.id)}
        for m in membros
    ]
    return render(request, 'agenda/presenca.html', {
        'evento': evento, 'linhas': linhas,
        'estados_do_form': PresencaEvento.ESTADOS,
        'erro': request.GET.get('erro', ''),
    })


@web_login_required
@agenda_requer_escrita
@transaction.atomic
def presenca_salvar(request, id):
    """Grava todos os rádios do POST em transação única (update_or_create)."""
    eventos = filtro_tenant(request, EventoAgenda.objects.all())
    evento = get_object_or_404(eventos, pk=id)
    usuario = _usuario_da_sessao(request)
    membros_validos = set(_membros_do_evento(evento).values_list('id', flat=True))

    for chave, valor in request.POST.items():
        if not chave.startswith('presenca_'):
            continue
        try:
            membro_id = int(chave.rsplit('_', 1)[1])
        except (ValueError, IndexError):
            continue
        if membro_id not in membros_validos or valor not in ESTADOS_VALIDOS:
            continue
        justificativa = (request.POST.get(f'justificativa_{membro_id}') or '').strip()
        if valor == 'JUSTIFICADO' and not justificativa:
            return redirect(
                f'/agenda/{id}/presenca/?erro=Informe a justificativa')
        PresencaEvento.objects.update_or_create(
            evento=evento, membro_id=membro_id,
            defaults={
                'estado': valor,
                'justificativa': justificativa if valor == 'JUSTIFICADO' else '',
                'registrado_por': usuario,
            },
        )
    return redirect('agenda:presenca', id)
