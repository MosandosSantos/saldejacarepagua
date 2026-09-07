"""Notas e tags do contato — adicionar/remover via POST."""

from django.shortcuts import get_object_or_404, redirect

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    web_login_required,
    web_requer_edicao,
)
from contatos.forms import NotaForm
from contatos.models import Contato, Tag
from contatos.scoring import atualizar_score
from contatos.views.helpers import CORES_TAG, _tenant_id


def _criar_e_anexar_tag(request, contato, nome):
    """Cria (se preciso) a tag do tenant da sessao e vincula ao contato."""
    nome = (nome or '').strip()
    if not nome:
        return
    tag, _ = Tag.objects.get_or_create(
        nome=nome[:40], tenant_id=_tenant_id(request), defaults={'cor': CORES_TAG[0]}
    )
    contato.tags.add(tag)


def _aplicar_nova_tag(request, contato):
    """Cria a tag digitada no formulario (campo nova_tag) e vincula ao contato."""
    _criar_e_anexar_tag(request, contato, request.POST.get('nova_tag', ''))


@web_login_required
@web_requer_edicao
def adicionar_nota(request, pk):
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        form = NotaForm(request.POST)
        if form.is_valid():
            nota = form.save(commit=False)
            nota.contato = contato
            nota.autor_id = request.session.get('usuario_id')
            nota.save()
            atualizar_score(contato)
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
def excluir_nota(request, pk, nota_id):
    """Excluir nota — apenas admin."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        contato.notas.filter(pk=nota_id).delete()
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
@web_requer_edicao
def adicionar_tag(request, pk):
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    if request.method == 'POST':
        _criar_e_anexar_tag(request, contato, request.POST.get('nome', ''))
    return redirect('contatos:detalhe', pk=contato.id)


@web_login_required
def remover_tag(request, pk, tag_id):
    """Remover tag do contato — apenas admin."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:detalhe', pk=pk)
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    if request.method == 'POST':
        contato.tags.remove(tag_id)
    return redirect('contatos:detalhe', pk=contato.id)
