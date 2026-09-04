"""Views do e-mail marketing — modelos (ModeloEmail), campanha e rastreio de abertura."""
from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from urllib.parse import urlparse

from django.urls import reverse
from django.utils import timezone

from acesso.decorators import filtro_tenant, web_login_required, web_requer_edicao
from contatos.models import Contato
from core.dominio import SEGS
from emails.models import EmailEnviado, ModeloEmail
from emails.servico import (
    EMAIL_VAZIO,
    GIF_1PX,
    _expandir_url,
    disparar_campanha,
    registrar_e_enviar,
)


def _tem_tenant(request) -> bool:
    """Módulo de e-mail exige tenant (admin_saas da plataforma não tem)."""
    return request.session.get('usuario', {}).get('tenant_id') is not None


def _base_pixel(request):
    """URL base do pixel de abertura, sem barra final (ex.: http://host/emails/aberto)."""
    fake = '00000000-0000-0000-0000-000000000000'
    return request.build_absolute_uri(reverse('emails:aberto', args=[fake])).replace(fake, '').rstrip('/')


def _erros_do_form(request):
    erros = []
    if not request.POST.get('nome', '').strip():
        erros.append('Informe o nome do modelo.')
    if not request.POST.get('assunto', '').strip():
        erros.append('Informe o assunto do e-mail.')
    if not request.POST.get('corpo', '').strip():
        erros.append('Escreva o corpo do e-mail.')
    return erros


@web_login_required
def lista(request):
    """Lista os modelos de e-mail do tenant + status do SMTP + KPIs de rastreio."""
    modelos = filtro_tenant(request, ModeloEmail.objects.annotate(total_envios=Count('envios')))
    envios = filtro_tenant(request, EmailEnviado.objects.select_related('contato', 'modelo'))
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
    recentes = [
        {
            'id': e.id,
            'contato_id': e.contato_id,
            'destinatario': e.destinatario,
            'contato_nome': e.contato.nome,
            'modelo_nome': e.modelo.nome if e.modelo else e.assunto[:40],
            'assunto': e.assunto,
            'status': e.status,
            'aberto_em': e.aberto_em,
            'cliques': e.cliques,
            'convertido_em': e.convertido_em,
            'enviado_em': e.enviado_em or e.created_at,
        }
        for e in envios.order_by('-created_at')[:12]
    ]
    return render(request, 'emails/lista.html', {
        'modelos': modelos,
        'total_envios': total_envios,
        'kpis': kpis,
        'recentes': recentes,
        'email_configurado': settings.EMAIL_CONFIGURADO,
        'email_host': getattr(settings, 'EMAIL_HOST', ''),
    })


@web_login_required
@web_requer_edicao
def novo(request):
    if not _tem_tenant(request):
        return redirect('dashboard:index')
    erros = []
    if request.method == 'POST':
        erros = _erros_do_form(request)
        if not erros:
            modelo = ModeloEmail.objects.create(
                tenant_id=request.session.get('usuario', {}).get('tenant_id'),
                nome=request.POST['nome'].strip(),
                assunto=request.POST['assunto'].strip(),
                corpo=request.POST['corpo'].strip(),
            )
            return redirect('emails:lista')
    return render(request, 'emails/form_modelo.html', {
        'titulo_form': 'Novo modelo de e-mail',
        'modelo': None,
        'erros': erros,
        'nome': request.POST.get('nome', ''),
        'assunto': request.POST.get('assunto', ''),
        'corpo': request.POST.get('corpo', ''),
    })


@web_login_required
@web_requer_edicao
def editar(request, pk):
    modelo = get_object_or_404(filtro_tenant(request, ModeloEmail.objects.all()), pk=pk)
    erros = []
    if request.method == 'POST':
        erros = _erros_do_form(request)
        if not erros:
            modelo.nome = request.POST['nome'].strip()
            modelo.assunto = request.POST['assunto'].strip()
            modelo.corpo = request.POST['corpo'].strip()
            modelo.save(update_fields=['nome', 'assunto', 'corpo'])
            return redirect('emails:lista')
    return render(request, 'emails/form_modelo.html', {
        'titulo_form': 'Editar modelo de e-mail',
        'modelo': modelo,
        'erros': erros,
        'nome': request.POST.get('nome', modelo.nome),
        'assunto': request.POST.get('assunto', modelo.assunto),
        'corpo': request.POST.get('corpo', modelo.corpo),
    })


@web_login_required
@web_requer_edicao
def excluir(request, pk):
    modelo = get_object_or_404(filtro_tenant(request, ModeloEmail.objects.all()), pk=pk)
    if request.method == 'POST':
        modelo.delete()
        return redirect('emails:lista')
    return render(request, 'emails/form_modelo.html', {
        'titulo_form': 'Excluir modelo',
        'confirmar_exclusao': True,
        'modelo': modelo,
        'erros': [],
        'nome': modelo.nome,
        'assunto': modelo.assunto,
        'corpo': modelo.corpo,
    })


@web_login_required
@web_requer_edicao
def campanha(request):
    """Dispara um modelo de e-mail para um público (filtro por segmento), com rastreio."""
    if not _tem_tenant(request):
        return redirect('dashboard:index')
    modelos = filtro_tenant(request, ModeloEmail.objects.all())
    segs = [{'key': k, 'label': v['label']} for k, v in SEGS.items()]
    msg = request.GET.get('msg', '')
    previsao = None
    seg_selecionado = request.GET.get('seg', '')
    modelo_selecionado = request.GET.get('modelo_id', '')

    if request.method == 'POST':
        modelo = get_object_or_404(
            filtro_tenant(request, ModeloEmail.objects.all()),
            pk=request.POST.get('modelo_id', ''),
        )
        contatos = filtro_tenant(request, Contato.objects.all())
        seg = request.POST.get('seg', '')
        if seg:
            contatos = contatos.filter(seg=seg)
        total = disparar_campanha(modelo, contatos, _base_pixel(request))
        return redirect(f'{request.path}?msg=enviados-{total}')

    if modelo_selecionado.isdigit():
        base = filtro_tenant(request, Contato.objects.all())
        if seg_selecionado:
            base = base.filter(seg=seg_selecionado)
        previsao = base.exclude(email__in=EMAIL_VAZIO).count()

    return render(request, 'emails/campanha.html', {
        'modelos': modelos,
        'segs': segs,
        'previsao': previsao,
        'msg': msg,
        'seg_selecionado': seg_selecionado,
        'modelo_selecionado': modelo_selecionado,
        'email_configurado': settings.EMAIL_CONFIGURADO,
    })


@web_login_required
@web_requer_edicao
def enviar_contato(request, contato_id):
    """Envio individual: escolhe um modelo e dispara para um contato específico."""
    if not _tem_tenant(request):
        return redirect('dashboard:index')
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=contato_id)
    if request.method == 'POST':
        modelo = get_object_or_404(
            filtro_tenant(request, ModeloEmail.objects.all()),
            pk=request.POST.get('modelo_id', ''),
        )
        # registrar_e_enviar devolve None quando o contato não tem e-mail
        registro = registrar_e_enviar(modelo, contato, _base_pixel(request))
        if registro is None:
            return redirect('contatos:detalhe', pk=contato_id)
        return redirect(reverse('contatos:detalhe', args=[contato_id]) + '?email=ok')
    return redirect('contatos:detalhe', pk=contato_id)


def rastreio_abertura(request, token):
    """Pixel 1x1 público (sem login — o cliente de e-mail do destinatário o carrega)."""
    registro = EmailEnviado.objects.filter(token=token).first()
    if registro is None:
        return HttpResponseNotFound()
    if registro.aberto_em is None:
        registro.aberto_em = timezone.now()
        registro.save(update_fields=['aberto_em'])
    resposta = HttpResponse(GIF_1PX, content_type='image/gif')
    resposta['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resposta


def rastreio_clique(request, token, codigo):
    """Endpoint público de clique: registra o clique e redireciona para a URL original.

    O link do e-mail aponta para cá (sem login — o destinatário clica). O token
    identifica o envio; o código é a URL de destino codificada em base64url.
    """
    registro = EmailEnviado.objects.filter(token=token).first()
    url = _expandir_url(codigo) if codigo else None
    if registro is None or url is None:
        return HttpResponseNotFound()
    # Segurança: só redireciona para http/https (evita javascript:/data: no código)
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return HttpResponseNotFound()
    registro.ultimo_clique_em = timezone.now()  # sempre: é o ÚLTIMO clique
    registro.cliques += 1
    registro.save(update_fields=['cliques', 'ultimo_clique_em'])
    return redirect(url)
