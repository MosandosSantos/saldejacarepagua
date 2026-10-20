"""Views de prefeituras GPRB — CRUD completo via repository."""
from datetime import date

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render

from acesso.decorators import web_login_required, web_requer_edicao, web_requer_tenant_context
from acesso.models import ROLE_ADMIN_SAAS, ROLE_ADM
from contatos.importador import normalizar_valor
from repositories import gprb_repository as repo


def _pode_criar_vale(request):
    """Só admin_saas e ADM cadastram Vale — delegado, presidente/secretário
    de loja e demais cargos não criam (regra de criação de Vale e Loja)."""
    role = None
    usuario = getattr(request, 'usuario_logado', None)
    role = getattr(usuario, 'role', None)
    if not role:
        snapshot = request.session.get('usuario', {})
        role = snapshot.get('role') if isinstance(snapshot, dict) else None
    return role in (ROLE_ADMIN_SAAS, ROLE_ADM)


def _data_anuidade(raw):
    """'AAAA-MM-DD' (input date) → date; None se vazio/inválido."""
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _dados_do_post(request):
    """Monta o dict da prefeitura a partir do POST (form de Potência)."""
    valor = (request.POST.get('valor_anuidade', '') or '').strip()
    return {
        'nome': request.POST.get('nome', '').strip(),
        'sigla': request.POST.get('sigla', '').strip(),
        'prefeito': request.POST.get('prefeito', '').strip(),
        'telefone': request.POST.get('telefone', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'secretario_email': request.POST.get('secretario_email', '').strip(),
        'secretario_telefone': request.POST.get('secretario_telefone', '').strip(),
        'tesoureiro_email': request.POST.get('tesoureiro_email', '').strip(),
        'tesoureiro_telefone': request.POST.get('tesoureiro_telefone', '').strip(),
        'pix': request.POST.get('pix', '').strip(),
        'valor_anuidade': normalizar_valor(valor) if valor else None,
        'vencimento_anuidade': _data_anuidade(request.POST.get('vencimento_anuidade')),
    }


@web_login_required
def prefeituras(request):
    """Lista de prefeituras do banco GPRB."""
    prefeituras_list, total_pf, total_lojas, total_membros = repo.listar_prefeituras()
    return render(request, 'contatos/prefeituras.html', {
        'prefeituras': prefeituras_list,
        'total_pf': total_pf,
        'total_lojas': total_lojas,
        'total_membros': total_membros,
        'pode_criar_vale': _pode_criar_vale(request),
    })


@web_login_required
def prefeitura_lojas_json(request, pk):
    """Retorna JSON com lojas de uma prefeitura (para drill-down)."""
    lojas = repo.listar_lojas_por_prefeitura(pk)
    return JsonResponse({'lojas': lojas})


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_nova(request):
    """Inclui uma nova prefeitura GPRB (só admin_saas/ADM)."""
    if not _pode_criar_vale(request):
        return HttpResponseForbidden('Sem permissão para cadastrar um Vale.')

    erro = None
    if request.method == 'POST':
        dados = _dados_do_post(request)
        if not dados['nome']:
            erro = 'Informe o nome da prefeitura.'
        else:
            repo.criar_prefeitura(dados)
            return redirect('vales')

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_editar(request, pk):
    """Edição de uma prefeitura GPRB."""
    prefeitura = repo.buscar_prefeitura(pk)
    if prefeitura is None:
        raise Http404('Potência nao encontrada')

    erro = None
    sucesso = None
    if request.method == 'POST':
        dados = _dados_do_post(request)
        if not dados['nome']:
            erro = 'Informe o nome da potência.'
        else:
            repo.atualizar_prefeitura(pk, dados)
            return redirect('vales')

    return render(request, 'contatos/prefeitura_editar.html', {
        'prefeitura': prefeitura, 'erro': erro, 'sucesso': sucesso,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def prefeitura_excluir(request, pk):
    """Exclui uma prefeitura GPRB."""
    prefeitura = repo.buscar_prefeitura(pk)
    if prefeitura is None:
        raise Http404('Potência nao encontrada')

    lojas = repo.contar_lojas_prefeitura(pk)
    erro = None
    if request.method == 'POST':
        if lojas > 0:
            erro = (f'Nao e possivel excluir a prefeitura: ha {lojas} '
                    f'loja(s) vinculada(s) a ela. Transfira as lojas '
                    'para outra prefeitura antes de excluir.')
        else:
            repo.excluir_prefeitura(pk)
            return redirect('vales')

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': prefeitura, 'lojas': lojas, 'erro': erro,
    })
