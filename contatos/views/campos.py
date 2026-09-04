"""Campos personalizados — helpers de valor/validacao e views de administracao."""

import re

from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    filtro_tenant,
    nicho_da_sessao,
    web_login_required,
    web_requer_admin,
)
from contatos.forms import CampoForm
from contatos.importador import normalizar_data
from contatos.models import CampoPersonalizado, ValorCampoPersonalizado
from contatos.views.helpers import _erros_do_form, _tenant_id


def _campos_do_tenant(request):
    """Campos personalizados ativos do tenant da sessao (admin_saas ve todos)."""
    tid = _tenant_id(request)
    qs = CampoPersonalizado.objects.filter(ativo=True)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return list(qs)


def _campos_scope(tid):
    """Queryset de campos personalizados escopado ao tenant (admin_saas ve todos)."""
    qs = CampoPersonalizado.objects.all()
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _nome_ja_existe(tid, nome, excluir_pk=None):
    qs = _campos_scope(tid).filter(nome=nome)
    if excluir_pk is not None:
        qs = qs.exclude(pk=excluir_pk)
    return qs.exists()


def _campos_com_valores(request, campos, contato=None, erros=None):
    """Campos prontos para o template do formulario, com valor atual e erro (se houver)."""
    erros = erros or {}
    valores = {}
    if request.method != 'POST' and contato is not None:
        valores = {v.campo_id: v.valor for v in contato.valores_campos.all()}
    itens = []
    for c in campos:
        if request.method == 'POST':
            valor = request.POST.get(f'campo_{c.id}', '')
        else:
            valor = valores.get(c.id, '')
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'tipo': c.tipo,
            'obrigatorio': c.obrigatorio,
            'opcoes': [o.strip() for o in c.opcoes.split(',') if o.strip()],
            'valor': valor,
            'erro': erros.get(c.id, ''),
        })
    return itens


def _validar_valores_campos(request, campos):
    """Valida campos obrigatorios e tipos numerico/data; devolve {campo_id: mensagem}."""
    erros = {}
    for c in campos:
        valor = (request.POST.get(f'campo_{c.id}', '') or '').strip()
        if c.obrigatorio and not valor:
            erros[c.id] = 'Campo obrigatório.'
            continue
        if not valor:
            continue
        if c.tipo == 'numero':
            try:
                float(valor.replace(',', '.'))
            except ValueError:
                erros[c.id] = 'Informe um número válido.'
        elif c.tipo == 'data' and normalizar_data(valor) is None:
            erros[c.id] = 'Informe uma data válida (dd/mm/aaaa).'
    return erros


def _salvar_valores_campos(request, contato, campos):
    """Grava (ou remove) os valores dos campos personalizados do contato."""
    for c in campos:
        valor = (request.POST.get(f'campo_{c.id}', '') or '').strip()
        if c.tipo == 'data':
            m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', valor)
            if m:
                valor = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
        if valor:
            ValorCampoPersonalizado.objects.update_or_create(
                contato=contato, campo=c, defaults={'valor': valor},
            )
        else:
            contato.valores_campos.filter(campo=c).delete()


def _formata_valor_campo(tipo, valor):
    """Formatacao de exibicao na ficha (sim/nao e datas ISO)."""
    if tipo == 'sim_nao':
        return 'Sim' if valor == 'sim' else 'Não'
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', valor) if tipo == 'data' else None
    if m:
        return f'{m.group(3)}/{m.group(2)}/{m.group(1)}'
    return valor


def _valores_para_ficha(contato):
    """Valores preenchidos do contato, ordenados pela ordem do campo."""
    itens = []
    for v in contato.valores_campos.select_related('campo').order_by('campo__ordem', 'campo__id'):
        if v.valor:
            itens.append({'nome': v.campo.nome, 'valor': _formata_valor_campo(v.campo.tipo, v.valor)})
    return itens


@web_login_required
@web_requer_admin
def campos_personalizados(request):
    """Lista os campos do tenant e cria novos (nome unico por tenant) — apenas admin."""
    tid = _tenant_id(request)
    erros = []
    if request.method == 'POST':
        form = CampoForm(request.POST)
        nome_limpo = form.cleaned_data['nome'].strip() if form.is_valid() else ''
        if form.is_valid() and not _nome_ja_existe(tid, nome_limpo):
            campo = form.save(commit=False)
            campo.nome = nome_limpo
            if tid is not None:
                campo.tenant_id = tid
            campo.save()
            return redirect('contatos:campos')
        if not form.is_valid():
            erros = _erros_do_form(form)
        else:
            erros.append(f'Já existe um campo chamado "{nome_limpo}".')
    else:
        form = CampoForm()
    campos = [
        {
            'id': c.id,
            'nome': c.nome,
            'tipo': c.get_tipo_display(),
            'obrigatorio': c.obrigatorio,
            'ordem': c.ordem,
            'qtd_uso': c.valores.values('contato_id').distinct().count(),
        }
        for c in _campos_scope(tid)
    ]
    return render(request, 'contatos/campos.html', {
        'form': form, 'campos': campos, 'erros': erros,
    })


@web_login_required
@web_requer_admin
def editar_campo(request, pk):
    tid = _tenant_id(request)
    campo = get_object_or_404(_campos_scope(tid), pk=pk)
    erros = []
    if request.method == 'POST':
        form = CampoForm(request.POST, instance=campo)
        nome_limpo = form.cleaned_data['nome'].strip() if form.is_valid() else ''
        if form.is_valid() and not _nome_ja_existe(tid, nome_limpo, excluir_pk=campo.pk):
            campo.nome = nome_limpo
            form.save()
            return redirect('contatos:campos')
        if not form.is_valid():
            erros = _erros_do_form(form)
        else:
            erros.append(f'Já existe um campo chamado "{nome_limpo}".')
    else:
        form = CampoForm(instance=campo)
    return render(request, 'contatos/editar_campo.html', {
        'form': form, 'campo': campo, 'erros': erros,
    })


@web_login_required
@web_requer_admin
def excluir_campo(request, pk):
    tid = _tenant_id(request)
    campo = get_object_or_404(_campos_scope(tid), pk=pk)
    if request.method == 'POST':
        campo.delete()
        return redirect('contatos:campos')
    qtd = campo.valores.values('contato_id').distinct().count()
    return render(request, 'contatos/excluir_campo.html', {'campo': campo, 'qtd': qtd})
