"""Tenant-scoped local CRUD for Lojas and their values PDFs."""

from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from acesso.decorators import (
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from acesso.models import ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO
from contatos.importador import normalizar_valor
from contatos.models import Loja, LojaPdf, Membro, Vale

TAMANHO_MAX_PDF = 10 * 1024 * 1024  # 10 MB

# Estados da união com o RJ em primeiro, como pedido.
UFS = [
    ('RJ', 'Rio de Janeiro'),
    ('AC', 'Acre'),
    ('AL', 'Alagoas'),
    ('AP', 'Amapá'),
    ('AM', 'Amazonas'),
    ('BA', 'Bahia'),
    ('CE', 'Ceará'),
    ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'),
    ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'),
    ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'),
    ('PA', 'Pará'),
    ('PB', 'Paraíba'),
    ('PR', 'Paraná'),
    ('PE', 'Pernambuco'),
    ('PI', 'Piauí'),
    ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'),
    ('RO', 'Rondônia'),
    ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'),
    ('SE', 'Sergipe'),
    ('TO', 'Tocantins'),
]


def _role(request):
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None)
    if role:
        return role
    return snapshot.get('role') if isinstance(snapshot, dict) else None


def _pode_criar_loja(request):
    """Apenas admin_saas e ADM podem criar Lojas (mesma regra do Vale)."""
    return _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)


def _pode_alterar_loja(request):
    """admin_saas, ADM, Delegado e Presidente de Corpo podem alterar Lojas."""
    return _role(request) in (
        ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO,
    )


def _pode_excluir_loja(request):
    """Apenas admin_saas e ADM podem excluir Lojas (mesma regra do Vale)."""
    return _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)

_MENSAGENS_ERRO = {
    'arquivo': 'Selecione o arquivo PDF com a tabela de valores.',
    'invalido': 'O arquivo enviado não é um PDF válido.',
    'tamanho': 'O PDF não pode passar de 10 MB.',
}
_MENSAGENS_OK = {
    'atualizado': 'PDF de valores atualizado.',
    'removido': 'PDF de valores removido.',
}


def _vale_do_request(request):
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').first()


def _eh_admin_global(request):
    """admin_saas e ADM operam em todos os Vales/Lojas."""
    return _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)


def _lojas_visiveis(request):
    """Queryset de Lojas operáveis; None quando sem contexto e sem perfil global."""
    base = (
        Loja.objects
        .select_related('tenant__vales', 'deputado_mestre')
        .annotate(total_membros=Count('membros', distinct=True))
    )
    if _eh_admin_global(request):
        return base
    vale = _vale_do_request(request)
    if vale is None:
        return None
    return base.filter(tenant_id=vale.tenant_id)


def _para_contexto_loja(loja):
    # Tenant pode não ter Vale cadastrado (ex.: tenant demo) — o reverso
    # OneToOne levanta Vale.DoesNotExist; tolera como sem Vale.
    vale = Vale.objects.filter(tenant_id=loja.tenant_id).order_by('-status').first()
    mensalidade = (
        f'{loja.mensalidade:.2f}'.replace('.', ',')
        if loja.mensalidade is not None else ''
    )
    total_membros = getattr(loja, 'total_membros', None)
    if total_membros is None:
        total_membros = loja.membros.count()
    presidente = (
        loja.deputado_mestre.nome
        if loja.deputado_mestre
        else (loja.presidente_nome or '')
    )
    secretario = (
        loja.secretario.nome
        if loja.secretario
        else (loja.secretario_nome or '')
    )
    secretario_email = (
        (loja.secretario_email or loja.secretario.email or '')
        if loja.secretario
        else (loja.secretario_email or '')
    )
    secretario_telefone = (
        (loja.secretario_telefone or loja.secretario.celular or '')
        if loja.secretario
        else (loja.secretario_telefone or '')
    )
    tesoureiro = (
        loja.tesoureiro.nome
        if loja.tesoureiro
        else (loja.tesoureiro_nome or '')
    )
    tesoureiro_email = (
        (loja.tesoureiro_email or loja.tesoureiro.email or '')
        if loja.tesoureiro
        else (loja.tesoureiro_email or '')
    )
    tesoureiro_telefone = (
        (loja.tesoureiro_telefone or loja.tesoureiro.celular or '')
        if loja.tesoureiro
        else (loja.tesoureiro_telefone or '')
    )
    return {
        'id': loja.pk,
        'nome': loja.nome,
        'numero': loja.numero,
        'telefone': loja.telefone,
        'email': loja.email,
        'prefeitura': (vale.nome if vale else ''),
        'prefeitura_id': (vale.pk if vale else None),
        'presidente_nome': loja.presidente_nome,
        'deputado_mestre': presidente,
        'deputado_mestre_id': loja.deputado_mestre_id,
        'presidente_celular': (
            loja.deputado_mestre.celular if loja.deputado_mestre else ''
        ),
        'secretario': secretario,
        'secretario_nome': loja.secretario_nome,
        'secretario_id': loja.secretario_id,
        'secretario_email': secretario_email,
        'secretario_telefone': secretario_telefone,
        'tesoureiro': tesoureiro,
        'tesoureiro_nome': loja.tesoureiro_nome,
        'tesoureiro_id': loja.tesoureiro_id,
        'tesoureiro_email': tesoureiro_email,
        'tesoureiro_telefone': tesoureiro_telefone,
        'mensalidade': mensalidade,
        'situacao': loja.situacao,
        'cidade': loja.cidade,
        'uf': loja.uf,
        'endereco': loja.endereco,
        # These legacy detail slots are not collected by the local forms.
        'numero_end': '',
        'bairro': '',
        'cep': '',
        'fundacao': None,
        'total_membros': total_membros,
    }


def _dados_da_loja(request):
    mensalidade = (request.POST.get('mensalidade', '') or '').strip()
    return {
        'nome': request.POST.get('nome', '').strip(),
        'numero': request.POST.get('numero', '').strip(),
        'telefone': request.POST.get('telefone', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'secretario_email': request.POST.get('secretario_email', '').strip(),
        'secretario_telefone': request.POST.get('secretario_telefone', '').strip(),
        'tesoureiro_email': request.POST.get('tesoureiro_email', '').strip(),
        'tesoureiro_telefone': request.POST.get('tesoureiro_telefone', '').strip(),
        'cidade': request.POST.get('cidade', '').strip(),
        'uf': request.POST.get('uf', '').strip().upper(),
        'endereco': request.POST.get('endereco', '').strip(),
        'mensalidade': normalizar_valor(mensalidade) if mensalidade else None,
    }


def _membro_do_tenant(tenant_id, membro_id):
    """Devolve o Membro do tenant ou None quando vazio/inexistente."""
    if not (membro_id or '').strip():
        return None
    try:
        pk = int(membro_id)
    except (TypeError, ValueError):
        return None
    return Membro.objects.filter(pk=pk, tenant_id=tenant_id).first()


def _cargos_do_post(request, tenant_id):
    """Lê os três cargos do formulário; cargos vagos viram None.

    Devolve (presidente, secretario, tesoureiro, erro). Erro quando um ID não
    pertence ao tenant ou quando a mesma pessoa ocupa dois cargos.
    """
    presidente = _membro_do_tenant(
        tenant_id, request.POST.get('deputado_mestre'),
    )
    secretario = _membro_do_tenant(
        tenant_id, request.POST.get('secretario'),
    )
    tesoureiro = _membro_do_tenant(
        tenant_id, request.POST.get('tesoureiro'),
    )
    if (
        (request.POST.get('deputado_mestre') or '').strip() and presidente is None
        or (request.POST.get('secretario') or '').strip() and secretario is None
        or (request.POST.get('tesoureiro') or '').strip() and tesoureiro is None
    ):
        return None, None, None, 'Selecione membros válidos para os cargos.'
    escolhidos = [m.pk for m in (presidente, secretario, tesoureiro) if m is not None]
    if len(escolhidos) != len(set(escolhidos)):
        return None, None, None, 'A mesma pessoa não pode ocupar dois cargos.'
    return presidente, secretario, tesoureiro, None


def _grupos_membros_por_vale(vales):
    """Membros agrupados por Vale para os selects de cargo."""
    tenant_ids = [v.tenant_id for v in vales]
    membros_por_tenant = {}
    for membro in Membro.objects.filter(tenant_id__in=tenant_ids).order_by('nome', 'id'):
        membros_por_tenant.setdefault(membro.tenant_id, []).append(membro)
    return [
        {'vale': vale, 'membros': membros_por_tenant.get(vale.tenant_id, [])}
        for vale in vales
    ]


@web_login_required
def lojas(request):
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar as lojas.')

    termo = request.GET.get('q', '').strip()
    if termo:
        qs = qs.filter(
            Q(nome__icontains=termo)
            | Q(numero__icontains=termo)
            | Q(cidade__icontains=termo)
            | Q(uf__icontains=termo)
        )
    itens = [_para_contexto_loja(loja) for loja in qs.order_by('nome', 'id')]
    return render(request, 'contatos/lojas.html', {
        'lojas': itens,
        'q': termo,
        'total': len(itens),
        'vale': _vale_do_request(request),
    })


@web_login_required
def loja_detalhe(request, pk):
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar as lojas.')
    loja = get_object_or_404(qs, pk=pk)
    pdf = LojaPdf.objects.filter(loja=loja).first()
    return render(request, 'contatos/loja_detalhe.html', {
        'loja': _para_contexto_loja(loja),
        'pdf': pdf,
        'erro_pdf': _MENSAGENS_ERRO.get(request.GET.get('erro', '')),
        'ok_pdf': _MENSAGENS_OK.get(request.GET.get('ok', '')),
    })


@web_login_required
def loja_membros_json(request, pk):
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar membros.')
    loja = get_object_or_404(qs, pk=pk)
    membros = list(
        loja.membros.filter(tenant_id=loja.tenant_id)
        .order_by('nome', 'id')
        .values('id', 'nome', 'situacao')
    )
    return JsonResponse({'membros': membros})


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def loja_nova(request):
    if not _pode_criar_loja(request):
        return HttpResponseForbidden('Sem permissão para cadastrar uma Loja.')

    vale_sessao = _vale_do_request(request)
    if vale_sessao is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para criar uma loja.')

    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None) or (
        snapshot.get('role') if isinstance(snapshot, dict) else None
    )
    if role == ROLE_ADMIN_SAAS:
        vales = list(Vale.objects.filter(status='ATIVA').order_by('nome', 'id'))
    else:
        vales = [vale_sessao]

    erro = None
    if request.method == 'POST':
        dados = _dados_da_loja(request)
        vale_id = (request.POST.get('vale_id') or '').strip()
        vale_escolhido = next((v for v in vales if str(v.pk) == vale_id), None)
        if not dados['nome']:
            erro = 'Informe o nome da loja.'
        elif vale_escolhido is None:
            erro = 'Selecione o Vale da loja.'
        else:
            presidente, secretario, tesoureiro, erro = _cargos_do_post(
                request, vale_escolhido.tenant_id,
            )
            if erro is None:
                loja = Loja.objects.create(
                    tenant_id=vale_escolhido.tenant_id,
                    deputado_mestre=presidente,
                    secretario=secretario,
                    tesoureiro=tesoureiro,
                    **dados,
                )
                for membro in (presidente, secretario, tesoureiro):
                    if membro is not None:
                        loja.membros.add(membro)
                return redirect('contatos:lojas')

    return render(request, 'contatos/loja_nova.html', {
        'erro': erro,
        'vale': vale_sessao,
        'vales': vales,
        'membros_por_vale': _grupos_membros_por_vale(vales),
        'ufs': UFS,
        'uf_atual': 'RJ',
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def loja_editar(request, pk):
    if not _pode_alterar_loja(request):
        return HttpResponseForbidden('Sem permissão para alterar uma Loja.')
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para alterar a loja.')
    loja = get_object_or_404(qs, pk=pk)
    erro = None

    if request.method == 'POST':
        dados = _dados_da_loja(request)
        if not dados['nome']:
            erro = 'Informe o nome da loja.'
        else:
            presidente, secretario, tesoureiro, erro = _cargos_do_post(
                request, loja.tenant_id,
            )
            if erro is None:
                for campo, valor in dados.items():
                    setattr(loja, campo, valor)
                loja.deputado_mestre = presidente
                loja.secretario = secretario
                loja.tesoureiro = tesoureiro
                loja.save()
                for membro in (presidente, secretario, tesoureiro):
                    if membro is not None:
                        loja.membros.add(membro)
                return redirect('contatos:lojas')

    membros = Membro.objects.filter(tenant_id=loja.tenant_id).order_by('nome', 'id')
    return render(request, 'contatos/loja_editar.html', {
        'loja': _para_contexto_loja(loja),
        'vale': loja.tenant.vales,
        'prefeituras': [loja.tenant.vales],
        'membros': membros,
        'ufs': UFS,
        'uf_atual': loja.uf or 'RJ',
        'erro': erro,
        'sucesso': None,
    })


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def loja_excluir(request, pk):
    if not _pode_excluir_loja(request):
        return HttpResponseForbidden('Sem permissão para excluir uma Loja.')
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para excluir a loja.')
    loja = get_object_or_404(qs, pk=pk)
    membros = loja.membros.filter(tenant_id=loja.tenant_id).count()
    erro = None

    if request.method == 'POST':
        if membros:
            erro = (
                f'Não é possível excluir a loja: há {membros} membro(s) vinculado(s). '
                'Transfira os membros para outra loja antes de excluir.'
            )
        else:
            pdf = LojaPdf.objects.filter(loja=loja).first()
            if pdf is not None:
                if pdf.arquivo:
                    pdf.arquivo.delete(save=False)
                pdf.delete()
            loja.delete()
            return redirect('contatos:lojas')

    return render(request, 'contatos/loja_excluir.html', {
        'loja': _para_contexto_loja(loja),
        'membros': membros,
        'erro': erro,
    })


def _validar_pdf(arquivo):
    """Confere o arquivo enviado — devolve a chave da mensagem de erro ou None."""
    if arquivo is None:
        return 'arquivo'
    if not (arquivo.name or '').lower().endswith('.pdf'):
        return 'invalido'
    if arquivo.size > TAMANHO_MAX_PDF:
        return 'tamanho'
    if arquivo.read(5) != b'%PDF-':
        return 'invalido'
    arquivo.seek(0)
    return None


def _redirecionar_com_feedback(pk, erro=None, ok=None):
    params = f'?erro={erro}' if erro else (f'?ok={ok}' if ok else '')
    return redirect(f"{reverse('contatos:loja_detalhe', args=[pk])}{params}")


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def loja_pdf_upload(request, pk):
    """Envia (ou substitui) o PDF de valores da Loja local — um arquivo por loja."""
    if request.method != 'POST':
        return redirect('contatos:loja_detalhe', pk=pk)
    if not _pode_alterar_loja(request):
        return HttpResponseForbidden('Sem permissão para alterar uma Loja.')
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para enviar um PDF.')
    loja = get_object_or_404(qs, pk=pk)

    erro = _validar_pdf(request.FILES.get('pdf'))
    if erro:
        return _redirecionar_com_feedback(pk, erro=erro)

    registro = LojaPdf.objects.filter(loja=loja).first() or LojaPdf(loja=loja)
    if registro.arquivo:
        registro.arquivo.delete(save=False)
    registro.arquivo = request.FILES['pdf']
    registro.save()
    return _redirecionar_com_feedback(pk, ok='atualizado')


@web_login_required
@web_requer_tenant_context
@web_requer_edicao
def loja_pdf_remover(request, pk):
    """Remove o PDF de valores da Loja local."""
    if request.method != 'POST':
        return redirect('contatos:loja_detalhe', pk=pk)
    if not _pode_alterar_loja(request):
        return HttpResponseForbidden('Sem permissão para alterar uma Loja.')
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para remover um PDF.')
    loja = get_object_or_404(qs, pk=pk)
    registro = LojaPdf.objects.filter(loja=loja).first()
    if registro is not None:
        if registro.arquivo:
            registro.arquivo.delete(save=False)
        registro.delete()
    return _redirecionar_com_feedback(pk, ok='removido')
