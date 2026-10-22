"""Tenant-scoped local CRUD for Lojas and their values PDFs."""

from dataclasses import dataclass

from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from acesso.decorators import (
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
    web_requer_tenant_context,
)
from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO
from contatos.importador import normalizar_valor
from contatos.models import Loja, LojaPdf, Vale
from contatos.paginacao import urls_paginacao
from contatos.relatorio_lojas import gerar_pdf_lojas, gerar_xlsx_lojas
from tarefas.presencas import PresencaServico

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


def _vale_do_delegado(request):
    """Vale do cargo delegado — vem do `prefeitura_id` do usuário.

    O delegado só atua dentro do Vale dele; sem vínculo ativo, devolve None
    (e, com isso, ele perde também o direito de criar Loja).
    """
    if _role(request) != ROLE_DELEGADO:
        return None
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    pid = getattr(usuario, 'prefeitura_id', None) or (
        snapshot.get('prefeitura_id') if isinstance(snapshot, dict) else None
    )
    pid = str(pid or '').strip()
    if not pid.isdigit():
        return None
    return Vale.objects.filter(pk=int(pid), status='ATIVA').first()


def _pode_criar_loja(request):
    """Quem cadastra Loja: admin_saas/ADM (qualquer Vale) e o delegado
    vinculado ao Vale dele (prefeitura_id). Presidente de loja, secretário
    e demais cargos não criam (mesma regra do Vale)."""
    if _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM):
        return True
    return _vale_do_delegado(request) is not None


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
_MIMES_RELATORIO_LOJAS = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


@dataclass(frozen=True)
class ConsultaLojas:
    """Tenant-scoped Loja query and current filter selections."""

    queryset: QuerySet[Loja]
    termo: str
    corpos_requisitados: tuple[str, ...]
    corpos_filtro: tuple[dict, ...]
    vale: Vale | None
    vale_id: str = ''
    uf: str = ''
    cidade: str = ''
    opcoes_vales: tuple[dict, ...] = ()
    opcoes_ufs: tuple[str, ...] = ()
    opcoes_cidades: tuple[str, ...] = ()


def _vale_do_request(request):
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return None
    return Vale.objects.filter(tenant_id=tenant_id, status='ATIVA').first()


def _lojas_visiveis(request):
    """Queryset de Lojas operáveis; None quando sem contexto de tenant.

    Admin SaaS e ADM são globais: consultam Lojas de todos os tenants sem
    selecionar um Vale (mesma política de /vales/ e membros).
    """
    base = (
        Loja.objects
        .select_related(
            'tenant__vales', 'deputado_mestre', 'secretario', 'tesoureiro',
        )
        .annotate(total_membros=Count('membros', distinct=True))
    )
    if _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM):
        return base
    vale = _vale_do_request(request)
    if vale is None:
        return None
    return base.filter(tenant_id=vale.tenant_id)


def _para_contexto_loja(loja):
    # Tenant pode não ter Vale cadastrado (ex.: tenant demo) — o reverso
    # OneToOne levanta Vale.DoesNotExist; tolera como sem Vale.
    try:
        vale = loja.tenant.vales
    except Vale.DoesNotExist:
        vale = None
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
        'corpo': loja.get_corpo_display(),
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
        'situacao_display': loja.get_situacao_display(),
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
    dados = {
        'nome': request.POST.get('nome', '').strip(),
        'numero': request.POST.get('numero', '').strip(),
        'corpo': request.POST.get('corpo', '').strip(),
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
    for campo in ('presidente_nome', 'secretario_nome', 'tesoureiro_nome'):
        if campo in request.POST:
            dados[campo] = request.POST.get(campo, '').strip()
    return dados


def _desvincular_cargos_renomeados(loja, dados):
    """Mantém o vínculo com o Membro apenas quando o nome digitado não mudou.

    A edição coleta os três cargos em texto (igual à criação). Se o nome
    digitado difere do membro atualmente vinculado, o vínculo é removido para
    que a tela não continue exibindo o nome antigo.
    """
    for campo_nome, campo_fk in (
        ('presidente_nome', 'deputado_mestre'),
        ('secretario_nome', 'secretario'),
        ('tesoureiro_nome', 'tesoureiro'),
    ):
        if campo_nome not in dados:
            continue
        membro = getattr(loja, campo_fk)
        if membro is None:
            continue
        digitado = (dados[campo_nome] or '').strip().casefold()
        if digitado != (membro.nome or '').strip().casefold():
            setattr(loja, campo_fk, None)


@web_login_required
def lojas(request):
    consulta = _consulta_lojas_filtradas(request)
    if consulta is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar as lojas.')

    page_obj = Paginator(consulta.queryset, 20).get_page(request.GET.get('page', 1))
    itens = [_para_contexto_loja(loja) for loja in page_obj.object_list]
    return render(request, 'contatos/lojas.html', {
        'lojas': itens,
        'q': consulta.termo,
        'corpos_filtro': consulta.corpos_filtro,
        'total': page_obj.paginator.count,
        'vale': consulta.vale,
        'vale_filtro': consulta.vale_id,
        'uf_filtro': consulta.uf,
        'cidade_filtro': consulta.cidade,
        'opcoes_vales': consulta.opcoes_vales,
        'opcoes_ufs': consulta.opcoes_ufs,
        'opcoes_cidades': consulta.opcoes_cidades,
        'pode_criar_loja': _pode_criar_loja(request),
        'page_obj': page_obj,
        'pagination_urls': urls_paginacao(
            request, page_obj, base_path=reverse('lojas'),
        ),
    })


@web_login_required
@require_GET
def lojas_exportar(request, formato):
    """Download all Loja rows matching the current tenant and filters."""
    consulta = _consulta_lojas_filtradas(request)
    if consulta is None:
        return HttpResponseForbidden(
            'Selecione um tenant ativo com Vale para exportar as lojas.',
        )
    if formato not in _MIMES_RELATORIO_LOJAS:
        return HttpResponseBadRequest('Formato de relatório inválido.')

    lojas_filtradas = list(consulta.queryset)
    linhas = [_para_contexto_loja(loja) for loja in lojas_filtradas]
    gerado_em = timezone.localdate()
    if formato == 'pdf':
        conteudo = gerar_pdf_lojas(linhas, gerado_em)
        extensao = 'pdf'
    else:
        conteudo = gerar_xlsx_lojas(linhas, gerado_em)
        extensao = 'xlsx'

    resposta = HttpResponse(conteudo, content_type=_MIMES_RELATORIO_LOJAS[formato])
    resposta['Content-Disposition'] = (
        f'attachment; filename="lojas-{gerado_em.isoformat()}.{extensao}"'
    )
    return resposta


def _consulta_lojas_filtradas(request):
    """Resolve the shared tenant-scoped Loja queryset and GET filters."""
    qs = _lojas_visiveis(request)
    if qs is None:
        return None

    termo = request.GET.get('q', '').strip()
    if termo:
        qs = qs.filter(
            Q(nome__icontains=termo)
            | Q(numero__icontains=termo)
            | Q(cidade__icontains=termo)
            | Q(uf__icontains=termo)
        )

    # Escopo para as opções do card (mesma política de visibilidade da listagem).
    escopo_global = _role(request) in (ROLE_ADMIN_SAAS, ROLE_ADM)
    vale_sessao = None if escopo_global else _vale_do_request(request)
    vales_qs = Vale.objects.filter(status='ATIVA').order_by('nome', 'id')
    lojas_base = Loja.objects
    if not escopo_global:
        if vale_sessao is None:
            vales_qs = vales_qs.none()
            lojas_base = lojas_base.none()
        else:
            vales_qs = vales_qs.filter(tenant_id=vale_sessao.tenant_id)
            lojas_base = lojas_base.filter(tenant_id=vale_sessao.tenant_id)
    opcoes_vales = tuple(
        {'id': str(v.pk), 'nome': v.nome} for v in vales_qs
    )

    vale_id = (request.GET.get('vale') or '').strip()
    if vale_id:
        try:
            vale_filtro = vales_qs.get(pk=int(vale_id))
        except (Vale.DoesNotExist, TypeError, ValueError):
            vale_filtro = None
        qs = qs.filter(tenant_id=vale_filtro.tenant_id) if vale_filtro else qs.none()

    uf = (request.GET.get('uf') or '').strip().upper()
    if uf:
        qs = qs.filter(uf=uf)
    cidade = (request.GET.get('cidade') or '').strip()
    if cidade:
        qs = qs.filter(cidade=cidade)

    corpos_requisitados = request.GET.getlist('corpo')
    corpos_validos = dict(Loja.CORPO_CHOICES)
    if any(corpo not in corpos_validos for corpo in corpos_requisitados):
        qs = qs.none()
    elif corpos_requisitados:
        qs = qs.filter(corpo__in=corpos_requisitados)
    # Faixas de grau nos chips — mesmo padrão visual de /membros/ e
    # /membros/acompanhamento/ (Performance→SC33) sobre o 'corpo' da Loja.
    CORPO_FAIXA = {
        'perfeicao': '4º-14º',
        'capitulo': '15º-18º',
        'kadosh': '19º-30º',
        'consistorio': '31º-32º',
        'sc33': '33º',
    }
    corpos_filtro = tuple(
        {
            'valor': valor,
            'rotulo': rotulo,
            'faixa': CORPO_FAIXA[valor],
            'selecionado': valor in corpos_requisitados,
        }
        for valor, rotulo in Loja.CORPO_CHOICES
    )
    opcoes_ufs = list(
        lojas_base.exclude(uf='').order_by('uf').values_list('uf', flat=True).distinct()
    )
    opcoes_cidades = list(
        lojas_base.exclude(cidade='').order_by('cidade').values_list('cidade', flat=True).distinct()
    )
    return ConsultaLojas(
        queryset=qs.order_by('nome', 'pk'),
        termo=termo,
        corpos_requisitados=tuple(corpos_requisitados),
        corpos_filtro=corpos_filtro,
        vale=_vale_do_request(request),
        vale_id=vale_id,
        uf=uf,
        cidade=cidade,
        opcoes_vales=opcoes_vales,
        opcoes_ufs=tuple(opcoes_ufs),
        opcoes_cidades=tuple(opcoes_cidades),
    )


@web_login_required
def loja_detalhe(request, pk):
    qs = _lojas_visiveis(request)
    if qs is None:
        return HttpResponseForbidden('Selecione um tenant ativo com Vale para consultar as lojas.')
    loja = get_object_or_404(qs, pk=pk)
    membros = list(
        loja.membros.filter(tenant_id=loja.tenant_id).order_by('nome', 'pk')
    )
    percentuais = PresencaServico.percentuais_da_loja(membros, loja)
    membros_presenca = [
        {
            'id': membro.pk,
            'nome': membro.nome,
            'situacao': membro.get_situacao_display(),
            'presenca': (
                round(percentuais[membro.pk])
                if percentuais[membro.pk] is not None else None
            ),
            'presenca_abaixo_50': (
                percentuais[membro.pk] is not None and percentuais[membro.pk] < 50
            ),
        }
        for membro in membros
    ]
    loja_contexto = _para_contexto_loja(loja)
    loja_contexto['total_membros'] = len(membros)
    pdf = LojaPdf.objects.filter(loja=loja).first()
    return render(request, 'contatos/loja_detalhe.html', {
        'loja': loja_contexto,
        'membros_presenca': membros_presenca,
        'pdf': pdf,
        'erro_pdf': _MENSAGENS_ERRO.get(request.GET.get('erro', '')),
        'ok_pdf': _MENSAGENS_OK.get(request.GET.get('ok', '')),
    })


@web_login_required
def loja_membros_json(request, pk):
    qs = _lojas_visiveis(request)
    if qs is None:
        # ADM/admin_saas em "Todos os tenants": o drill-down de /vales/ lista
        # lojas de todos os vales, então a leitura fica escopada à própria
        # loja (tenant dela), nunca além do registro já visível na página.
        if _role(request) not in (ROLE_ADMIN_SAAS, ROLE_ADM):
            return HttpResponseForbidden(
                'Selecione um tenant ativo com Vale para consultar membros.',
            )
        qs = Loja.objects.select_related('tenant')
    loja = get_object_or_404(qs, pk=pk)
    membros = list(
        loja.membros.filter(tenant_id=loja.tenant_id)
        .prefetch_related('graus__grau')
        .order_by('nome', 'pk')
    )
    percentuais = PresencaServico.percentuais_da_loja(membros, loja)
    linhas = []
    for membro in membros:
        grau_mais_alto = max(
            (historico.grau.numero for historico in membro.graus.all()),
            default=None,
        )
        percentual = percentuais[membro.pk]
        linhas.append({
            'id': membro.pk,
            'nome': membro.nome,
            'situacao': membro.situacao,
            'cadastro': (
                str(membro.cadastro_numero)
                if membro.cadastro_numero is not None
                else (membro.cadastro_maconico or '')
            ),
            'grau': grau_mais_alto,
            'presenca': round(percentual) if percentual is not None else None,
            'presenca_abaixo_50': percentual is not None and percentual < 50,
        })
    return JsonResponse({'membros': linhas})


@web_login_required
@web_requer_edicao
def loja_nova(request):
    role = _role(request)
    vale_do_delegado = _vale_do_delegado(request)
    if role in (ROLE_ADMIN_SAAS, ROLE_ADM):
        vale_sessao = _vale_do_request(request)
        if vale_sessao is None and role != ROLE_ADMIN_SAAS:
            return HttpResponseForbidden('Selecione um tenant ativo com Vale para criar uma loja.')
        # SaaS admins may choose the target tenant through an active Vale below.
        vales = list(Vale.objects.filter(status='ATIVA').order_by('nome', 'id'))
    elif role == ROLE_DELEGADO and vale_do_delegado is not None:
        # Delegado: Vale travado no dele (`prefeitura_id`) — vale para
        # qualquer loja que ele crie dentro do seu Vale.
        vale_sessao = vale_do_delegado
        vales = [vale_do_delegado]
    else:
        # Presidente de loja, secretário e demais cargos não criam nada.
        return HttpResponseForbidden('Sem permissão para cadastrar uma Loja.')

    erro = None
    corpo_atual = ''
    if request.method == 'POST':
        dados = _dados_da_loja(request)
        corpo_atual = (
            dados['corpo']
            if dados['corpo'] in dict(Loja.CORPO_CHOICES)
            else ''
        )
        vale_id = (request.POST.get('vale_id') or '').strip()
        # Para o delegado, o Vale do POST é ignorado: vale sempre o dele.
        vale_escolhido = (
            vale_do_delegado if vale_do_delegado is not None
            else next((v for v in vales if str(v.pk) == vale_id), None)
        )
        if vale_id == '':
            # Sem Vale no POST: o tenant ativo determina o Vale (spec de
            # isolamento). Delegados já receberam o Vale deles acima; admin
            # sem tenancy selection continua sem Vale e cai no erro abaixo.
            vale_escolhido = vale_sessao
        if not dados['nome']:
            erro = 'Informe o nome da loja.'
        elif dados['corpo'] not in dict(Loja.CORPO_CHOICES):
            erro = 'Selecione um Corpo válido.'
        elif vale_escolhido is None:
            erro = 'Selecione o Vale da loja.'
        else:
            Loja.objects.create(
                tenant_id=vale_escolhido.tenant_id,
                **dados,
            )
            return redirect('lojas')

    return render(request, 'contatos/loja_nova.html', {
        'erro': erro,
        'vale': vale_sessao,
        'vales': vales,
        'vale_travado': vale_do_delegado is not None,
        'corpos': Loja.CORPO_CHOICES,
        'corpo_atual': corpo_atual,
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
    corpo_atual = loja.corpo

    if request.method == 'POST':
        dados = _dados_da_loja(request)
        if dados['corpo'] in dict(Loja.CORPO_CHOICES):
            corpo_atual = dados['corpo']
        if not dados['nome']:
            erro = 'Informe o nome da loja.'
        elif dados['corpo'] not in dict(Loja.CORPO_CHOICES):
            erro = 'Selecione um Corpo válido.'
        else:
            for campo, valor in dados.items():
                setattr(loja, campo, valor)
            _desvincular_cargos_renomeados(loja, dados)
            loja.save()
            return redirect('lojas')

    return render(request, 'contatos/loja_editar.html', {
        'loja': _para_contexto_loja(loja),
        'vale': loja.tenant.vales,
        'prefeituras': [loja.tenant.vales],
        'ufs': UFS,
        'uf_atual': loja.uf or 'RJ',
        'corpos': Loja.CORPO_CHOICES,
        'corpo_atual': corpo_atual,
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
            return redirect('lojas')

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
