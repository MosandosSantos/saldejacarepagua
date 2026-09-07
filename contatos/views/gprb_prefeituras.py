"""Views de prefeituras GPRB — CRUD completo via repository."""
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from acesso.decorators import web_login_required, web_requer_edicao
from repositories import gprb_repository as repo


@web_login_required
def prefeituras(request):
    """Lista de prefeituras do banco GPRB."""
    prefeituras_list, total_pf, total_lojas, total_membros = repo.listar_prefeituras()
    return render(request, 'contatos/prefeituras.html', {
        'prefeituras': prefeituras_list,
        'total_pf': total_pf,
        'total_lojas': total_lojas,
        'total_membros': total_membros,
    })


@web_login_required
def prefeitura_lojas_json(request, pk):
    """Retorna JSON com lojas de uma prefeitura (para drill-down)."""
    lojas = repo.listar_lojas_por_prefeitura(pk)
    return JsonResponse({'lojas': lojas})


@web_login_required
@web_requer_edicao
def prefeitura_nova(request):
    """Inclui uma nova prefeitura GPRB."""
    erro = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        sigla = request.POST.get('sigla', '').strip()
        regiao = request.POST.get('regiao', '').strip()
        prefeito = request.POST.get('prefeito', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()

        if not nome:
            erro = 'Informe o nome da prefeitura.'
        elif not regiao:
            erro = 'Informe a regiao.'
        else:
            repo.criar_prefeitura({
                'nome': nome, 'sigla': sigla, 'regiao': regiao,
                'prefeito': prefeito, 'telefone': telefone, 'email': email,
            })
            return redirect('contatos:prefeituras')

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
@web_requer_edicao
def prefeitura_editar(request, pk):
    """Edição de uma prefeitura GPRB."""
    prefeitura = repo.buscar_prefeitura(pk)
    if prefeitura is None:
        raise Http404('Prefeitura nao encontrada')

    erro = None
    sucesso = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        sigla = request.POST.get('sigla', '').strip()
        prefeito = request.POST.get('prefeito', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()
        if not nome:
            erro = 'Informe o nome da prefeitura.'
        else:
            repo.atualizar_prefeitura(pk, {
                'nome': nome, 'sigla': sigla, 'prefeito': prefeito,
                'telefone': telefone, 'email': email,
            })
            sucesso = 'Prefeitura atualizada com sucesso!'
            prefeitura.update({
                'nome': nome, 'sigla': sigla, 'prefeito': prefeito,
                'telefone': telefone, 'email': email,
            })

    return render(request, 'contatos/prefeitura_editar.html', {
        'prefeitura': prefeitura, 'erro': erro, 'sucesso': sucesso,
    })


@web_login_required
@web_requer_edicao
def prefeitura_excluir(request, pk):
    """Exclui uma prefeitura GPRB."""
    prefeitura = repo.buscar_prefeitura(pk)
    if prefeitura is None:
        raise Http404('Prefeitura nao encontrada')

    lojas = repo.contar_lojas_prefeitura(pk)
    erro = None
    if request.method == 'POST':
        if lojas > 0:
            erro = (f'Nao e possivel excluir a prefeitura: ha {lojas} '
                    f'loja(s) vinculada(s) a ela. Transfira as lojas '
                    'para outra prefeitura antes de excluir.')
        else:
            repo.excluir_prefeitura(pk)
            return redirect('contatos:prefeituras')

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': prefeitura, 'lojas': lojas, 'erro': erro,
    })
