"""Views públicas do portal do candidato (acesso via token)."""

import logging
from datetime import date

from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from candidatos.models import Candidato

logger = logging.getLogger(__name__)


def _parse_data(valor):
    """Converte 'YYYY-MM-DD' em date; vazio/inválido devolve None."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except (ValueError, TypeError):
        return None


def candidato_dashboard(request, token):
    """Portal do candidato: status da sua candidatura (Súplica).

    Acesso público — autenticação via token de acesso (uso único).
    Mostra card com status, descrição, datas e atalho para terminar a súplica.
    """
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )
    if candidato.token_used_at:
        return render(request, 'candidatos/portal_dashboard.html', {
            'candidato': candidato,
            'token': token,
        })
    return render(request, 'candidatos/portal_dashboard.html', {
        'candidato': candidato,
        'token': token,
        'pode_editar': False,
    })


def candidato_suplica(request, token):
    """Portal do candidato: terminar a súplica (formulario completo + uploads).

    Bloqueia campos após envio. Exibe observações recebidas quando disponíveis.
    """
    get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )
    return candidato_formulario(request, token)


def candidato_formulario(request, token):
    """View pública: candidato preenche a ficha completa (Súplica) e define senha."""
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )

    if candidato.token_used_at:
        return render(request, 'candidatos/sucesso.html', {'candidato': candidato})

    if candidato.status == Candidato.Status.FICHA_ENVIADA:
        Candidato.objects.filter(pk=candidato.pk).update(
            status=Candidato.Status.EM_PREENCHIMENTO,
        )
        candidato.status = Candidato.Status.EM_PREENCHIMENTO

    if request.method == 'POST':
        erros = []

        nome_completo = request.POST.get('nome_completo', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        senha = request.POST.get('senha', '')
        confirmar_senha = request.POST.get('confirmar_senha', '')
        foto = request.FILES.get('foto')

        if not nome_completo:
            erros.append('Nome completo é obrigatório')
        if not cpf:
            erros.append('CPF é obrigatório')
        elif Candidato.objects.filter(
            tenant_id=candidato.tenant_id, cpf=cpf,
        ).exclude(pk=candidato.pk).exists():
            erros.append('Já existe um candidato com este CPF')
        if not foto:
            erros.append('A fotografia é obrigatória')
        if len(senha) < 8:
            erros.append('A senha deve ter pelo menos 8 caracteres')
        if senha != confirmar_senha:
            erros.append('As senhas não conferem')

        if erros:
            return render(request, 'candidatos/formulario.html', {
                'candidato': candidato,
                'token': token,
                'primeiro_nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
                'erros': erros,
            })

        candidato.nome_completo = nome_completo
        candidato.cpf = cpf
        candidato.data_nascimento = _parse_data(request.POST.get('data_nascimento'))
        candidato.estado_civil = request.POST.get('estado_civil', '')
        candidato.nacionalidade = request.POST.get('nacionalidade', '') or 'Brasileira'
        candidato.natural_cidade = request.POST.get('natural_cidade', '')
        candidato.pai = request.POST.get('pai', '')
        candidato.mae = request.POST.get('mae', '')
        candidato.email = request.POST.get('email', '')
        candidato.celular = request.POST.get('celular', '')
        candidato.telefone_urgencia = request.POST.get('telefone_urgencia', '')
        candidato.identidade_numero = request.POST.get('identidade_numero', '')
        candidato.orgao_emissor = request.POST.get('orgao_emissor', '')
        candidato.data_emissao = _parse_data(request.POST.get('data_emissao'))
        candidato.endereco_logradouro = request.POST.get('endereco_logradouro', '')
        candidato.endereco_numero = request.POST.get('endereco_numero', '')
        candidato.endereco_complemento = request.POST.get('endereco_complemento', '')
        candidato.endereco_bairro = request.POST.get('endereco_bairro', '')
        candidato.endereco_cep = request.POST.get('endereco_cep', '')
        candidato.endereco_cidade = request.POST.get('endereco_cidade', '')
        candidato.endereco_uf = request.POST.get('endereco_uf', '').upper()
        candidato.loja_simbolo = request.POST.get('loja_simbolo', '')
        candidato.numero_loja_simbolo = request.POST.get('numero_loja_simbolo', '')
        candidato.data_exaltacao = _parse_data(request.POST.get('data_exaltacao'))
        candidato.potencia_simbolo = request.POST.get('potencia_simbolo', '')
        candidato.rito_loja_simbolo = request.POST.get('rito_loja_simbolo', '')

        if foto:
            candidato.foto = foto
        if request.FILES.get('quitacao'):
            candidato.quitacao_url = request.FILES.get('quitacao')
        if request.FILES.get('pagamento'):
            candidato.pagamento_url = request.FILES.get('pagamento')

        candidato.password_hash = make_password(senha)
        candidato.token_used_at = timezone.now()
        candidato.status = Candidato.Status.EM_REVISAO
        if not candidato.revisao_atual:
            from candidatos.oficialato import nivel_inicial_do_criador
            criador = candidato.created_by
            candidato.revisao_atual = nivel_inicial_do_criador(
                criador.role if criador else None,
            )
        candidato.save()

        return render(request, 'candidatos/sucesso.html', {'candidato': candidato})

    return render(request, 'candidatos/formulario.html', {
        'candidato': candidato,
        'token': token,
        'primeiro_nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
    })


@require_POST
def candidato_definir_senha(request, token):
    """View pública: candidato define sua senha e preenche dados complementares."""
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
        token_used_at__isnull=True,
    )

    senha = request.POST.get('senha', '')
    confirmar_senha = request.POST.get('confirmar_senha', '')

    if not senha or len(senha) < 8:
        return JsonResponse({'erros': ['Senha deve ter pelo menos 8 caracteres']}, status=400)

    if senha != confirmar_senha:
        return JsonResponse({'erros': ['Senhas não conferem']}, status=400)

    candidato.password_hash = make_password(senha)
    candidato.token_used_at = timezone.now()
    candidato.status = Candidato.Status.EM_REVISAO
    if not candidato.revisao_atual:
        from candidatos.oficialato import nivel_inicial_do_criador
        criador = candidato.created_by
        candidato.revisao_atual = nivel_inicial_do_criador(
            criador.role if criador else None,
        )
    candidato.save(update_fields=[
        'password_hash',
        'token_used_at',
        'status',
        'revisao_atual',
        'updated_at',
    ])

    return JsonResponse({
        'ok': True,
        'mensagem': 'Senha definida com sucesso! Sua ficha será analisada.',
    })
