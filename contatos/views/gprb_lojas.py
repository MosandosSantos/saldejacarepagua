"""Views de lojas GPRB — CRUD completo via repository."""
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from acesso.decorators import web_login_required, web_requer_edicao
from repositories import gprb_repository as repo


@web_login_required
def lojas(request):
    """Lista de lojas do banco GPRB."""
    termo = request.GET.get('q', '').strip()
    lojas_list, total = repo.listar_lojas(termo)
    return render(request, 'contatos/lojas.html', {
        'lojas': lojas_list, 'q': termo, 'total': total,
    })


@web_login_required
def loja_detalhe(request, pk):
    """Detalhe de uma loja GPRB."""
    loja = repo.buscar_loja(pk)
    if loja is None:
        raise Http404('Loja nao encontrada')
    return render(request, 'contatos/loja_detalhe.html', {'loja': loja})


@web_login_required
def loja_membros_json(request, pk):
    """Retorna JSON com todos os membros de uma loja (para drill-down)."""
    membros = repo.listar_membros_loja(pk)
    return JsonResponse({'membros': membros})


@web_login_required
@web_requer_edicao
def loja_nova(request):
    """Inclui uma nova loja GPRB."""
    erro = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            erro = 'Informe o nome da loja.'
        else:
            repo.criar_loja({
                'nome': nome,
                'numero': request.POST.get('numero', '').strip(),
                'telefone': request.POST.get('telefone', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'prefeitura_id': request.POST.get('prefeitura', '').strip(),
                'cidade': request.POST.get('cidade', '').strip(),
                'uf': request.POST.get('uf', '').strip(),
            })
            return redirect('contatos:lojas')

    prefeituras = repo.listar_lojas_para_select()
    return render(request, 'contatos/loja_nova.html', {'erro': erro, 'prefeituras': prefeituras})


@web_login_required
@web_requer_edicao
def loja_editar(request, pk):
    """Edicao de uma loja GPRB."""
    resultado = repo.buscar_loja_para_edicao(pk)
    if resultado is None:
        raise Http404('Loja nao encontrada')
    loja, prefeituras, membros = resultado

    erro = None
    sucesso = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            erro = 'Informe o nome da loja.'
        else:
            repo.atualizar_loja(pk, {
                'nome': nome,
                'telefone': request.POST.get('telefone', '').strip(),
                'email': request.POST.get('email', '').strip(),
                'prefeitura_id': request.POST.get('prefeitura', '').strip(),
                'cidade': request.POST.get('cidade', '').strip(),
                'uf': request.POST.get('uf', '').strip(),
                'deputado_mestre': request.POST.get('deputado_mestre', '').strip(),
            })
            return redirect('contatos:lojas')

    return render(request, 'contatos/loja_editar.html', {
        'loja': loja, 'prefeituras': prefeituras, 'membros': membros,
        'erro': erro, 'sucesso': sucesso,
    })


@web_login_required
@web_requer_edicao
def loja_excluir(request, pk):
    """Exclui uma loja GPRB."""
    loja = repo.buscar_loja(pk)
    if loja is None:
        raise Http404('Loja nao encontrada')

    membros = repo.contar_membros_loja(pk)
    erro = None
    if request.method == 'POST':
        if membros > 0:
            erro = (f'Nao e possivel excluir a loja: ha {membros} '
                    f'membro(s) vinculado(s) a ela. Transfira os membros '
                    'para outra loja antes de excluir.')
        else:
            repo.excluir_loja(pk)
            return redirect('contatos:lojas')

    return render(request, 'contatos/loja_excluir.html', {
        'loja': loja, 'membros': membros, 'erro': erro,
    })
