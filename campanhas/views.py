"""Views do app 'campanhas' — lista, criar, editar, excluir e detalhe.

O canal de e-mail já é operacional: o detalhe escolhe o modelo do app `emails`,
filtra o público (segmento + carteira) e dispara com rastreio individual; os
envios ficam vinculados à campanha e alimentam os KPIs (4.1 do PRD HAZON).
WhatsApp/telefone dependem de integrações externas (decisão de provedor).
"""

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from acesso.decorators import filtro_tenant, web_login_required, web_requer_edicao
from campanhas.models import Campanha
from contatos.models import Contato
from core.dominio import SEGS
from emails.models import ModeloEmail
from emails.servico import disparar_campanha


def _tenant_id(request):
    return request.session.get('usuario', {}).get('tenant_id')


def _tem_tenant(request) -> bool:
    return _tenant_id(request) is not None


def _campanhas_scope(request):
    qs = Campanha.objects.all()
    tid = _tenant_id(request)
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _base_pixel(request):
    fake = '00000000-0000-0000-0000-000000000000'
    return request.build_absolute_uri(reverse('emails:aberto', args=[fake])).replace(fake, '').rstrip('/')


@web_login_required
def lista(request):
    """Lista as campanhas do tenant com contadores (envios e conversões por canal)."""
    itens = []
    for c in _campanhas_scope(request).prefetch_related('envios'):
        envios = c.envios.all()
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao,
            'canal': c.canal,
            'canal_label': c.get_canal_display(),
            'ativa': c.ativa,
            'total_envios': envios.count(),
            'total_convertidos': envios.filter(convertido_em__isnull=False).count(),
            'criada_em': c.created_at,
        })
    return render(request, 'campanhas/lista.html', {
        'itens': itens,
        'web_pode_editar': request.session.get('usuario', {}).get('role') in ('admin_company', 'operacional'),
    })


@web_login_required
@web_requer_edicao
def novo(request):
    if not _tem_tenant(request):
        return redirect('dashboard:index')
    erros = []
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        canal = request.POST.get('canal', 'email')
        ativa = request.POST.get('ativa') == 'on'
        if not nome:
            erros.append('Informe o nome da campanha.')
        elif _campanhas_scope(request).filter(nome__iexact=nome).exists():
            erros.append(f'Já existe uma campanha chamada "{nome}".')
        else:
            campanha = Campanha(nome=nome, canal=canal, ativa=ativa)
            campanha.descricao = (request.POST.get('descricao') or '').strip()
            campanha.tenant_id = _tenant_id(request)
            campanha.save()
            return redirect('campanhas:detalhe', pk=campanha.id)
    return render(request, 'campanhas/form.html', {
        'titulo_form': 'Nova campanha',
        'campanha': None,
        'erros': erros,
        'nome': request.POST.get('nome', ''),
        'descricao': request.POST.get('descricao', ''),
        'canal': request.POST.get('canal', 'email'),
        'ativa': request.POST.get('ativa') == 'on',
    })


@web_login_required
@web_requer_edicao
def editar(request, pk):
    campanha = get_object_or_404(_campanhas_scope(request), pk=pk)
    erros = []
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            erros.append('Informe o nome da campanha.')
        elif _campanhas_scope(request).filter(nome__iexact=nome).exclude(pk=campanha.pk).exists():
            erros.append(f'Já existe uma campanha chamada "{nome}".')
        else:
            campanha.nome = nome
            campanha.descricao = (request.POST.get('descricao') or '').strip()
            campanha.canal = request.POST.get('canal', 'email')
            campanha.ativa = request.POST.get('ativa') == 'on'
            campanha.save()
            return redirect('campanhas:detalhe', pk=campanha.id)
    return render(request, 'campanhas/form.html', {
        'titulo_form': 'Editar campanha',
        'campanha': campanha,
        'erros': erros,
        'nome': request.POST.get('nome', campanha.nome),
        'descricao': request.POST.get('descricao', campanha.descricao),
        'canal': request.POST.get('canal', campanha.canal),
        'ativa': campanha.ativa or request.POST.get('ativa') == 'on',
    })


@web_login_required
@web_requer_edicao
def excluir(request, pk):
    campanha = get_object_or_404(_campanhas_scope(request), pk=pk)
    if request.method == 'POST':
        campanha.delete()
        return redirect('campanhas:lista')
    return render(request, 'campanhas/form.html', {
        'titulo_form': 'Excluir campanha',
        'confirmar_exclusao': True,
        'campanha': campanha,
        'erros': [],
        'nome': campanha.nome,
        'descricao': campanha.descricao,
        'canal': campanha.canal,
        'ativa': campanha.ativa,
    })


@web_login_required
def detalhe(request, pk):
    """Detalhe da campanha — KPIs dos envios e, para e-mail, disparo integrado."""
    campanha = get_object_or_404(_campanhas_scope(request), pk=pk)
    erros = []
    sucesso = None
    envios = campanha.envios.all()

    if request.method == 'POST':
        if not request.session.get('usuario', {}).get('role') in ('admin_company', 'operacional'):
            return redirect('campanhas:detalhe', pk=pk)
        if not campanha.ativa:
            erros.append('Campanha inativa — reative para disparar.')
        elif campanha.canal != 'email':
            erros.append('O canal selecionado ainda não tem integração de envio (requer decisão de provedor).')
        else:
            modelo = get_object_or_404(
                filtro_tenant(request, ModeloEmail.objects.all()),
                pk=request.POST.get('modelo_id', ''),
            )
            contatos = filtro_tenant(request, Contato.objects.all())
            seg = request.POST.get('seg', '')
            if seg:
                contatos = contatos.filter(seg=seg)
            carteira_id = request.POST.get('carteira_id', '')
            if carteira_id.isdigit():
                contatos = contatos.filter(carteira_id=int(carteira_id))
            total = disparar_campanha(modelo, contatos, _base_pixel(request), campanha=campanha)
            sucesso = f'{total} envio(s) registrado(s) para a campanha.'
            envios = campanha.envios.all()

    # KPIs
    total_envios = envios.count()
    total_abertos = envios.filter(aberto_em__isnull=False).count()
    total_cliques = envios.filter(cliques__gt=0).count()
    total_convertidos = envios.filter(convertido_em__isnull=False).count()

    def _pct(parcial):
        return round(parcial * 100 / total_envios) if total_envios else 0

    kpis = [
        {'rotulo': 'Enviados', 'valor': total_envios, 'cor': '#74b3c6'},
        {'rotulo': 'Abertos', 'valor': total_abertos, 'pct': _pct(total_abertos), 'cor': '#7fe3c4'},
        {'rotulo': 'Cliques', 'valor': total_cliques, 'pct': _pct(total_cliques), 'cor': '#fbbf24'},
        {'rotulo': 'Convertidos', 'valor': total_convertidos, 'pct': _pct(total_convertidos), 'cor': '#c084fc'},
    ]

    modelos = filtro_tenant(request, ModeloEmail.objects.all())
    from contatos.models import Carteira

    carteiras = [
        {'id': c.id, 'nome': c.nome}
        for c in (Carteira.objects.all() if _tenant_id(request) is None
                  else Carteira.objects.filter(tenant_id=_tenant_id(request))).order_by('nome')
    ]

    recentes = [
        {
            'id': e.id,
            'contato_id': e.contato_id,
            'contato_nome': e.contato.nome,
            'destinatario': e.destinatario,
            'aberto_em': e.aberto_em,
            'cliques': e.cliques,
            'convertido_em': e.convertido_em,
        }
        for e in envios.select_related('contato').order_by('-created_at')[:12]
    ]

    return render(request, 'campanhas/detalhe.html', {
        'campanha': {
            'id': campanha.id,
            'nome': campanha.nome,
            'descricao': campanha.descricao,
            'canal': campanha.canal,
            'canal_label': campanha.get_canal_display(),
            'ativa': campanha.ativa,
            'criada_em': campanha.created_at,
        },
        'kpis': kpis,
        'modelos': modelos,
        'segs': [{'key': k, 'label': v['label']} for k, v in SEGS.items()],
        'carteiras': carteiras,
        'recentes': recentes,
        'erros': erros,
        'sucesso': sucesso,
        'email_configurado': settings.EMAIL_CONFIGURADO,
        'seg_selecionado': request.POST.get('seg', '') if request.method == 'POST' else '',
        'carteira_selecionada': request.POST.get('carteira_id', '') if request.method == 'POST' else '',
        'modelo_selecionado': request.POST.get('modelo_id', '') if request.method == 'POST' else '',
    })
