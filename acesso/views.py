"""Views web de autenticacao (sessao), configuracao, convites e equipe. O JWT continua exclusivo da API FastAPI."""

import logging
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, models
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from acesso.ativacao import (
    LIMITE_REENVIOS,
    ativar_senha,
    criar_usuario_pendente,
    enviar_email_ativacao,
    reenviar_ativacao,
)
from acesso.context_processors import ROLE_LABELS
from acesso.decorators import (
    pode_gerir_usuarios,
    web_login_required,
)
from acesso.models import (
    ROLE_ADMIN_COMPANY,
    ROLE_ADMIN_SAAS,
    ROLE_OPERACIONAL,
    ROLES_ATRIB_CRIACAO,
    ROLES_DE_TENANT,
    ROLES_GESTORES_USUARIOS,
    SENHA_PENDENTE,
    USUARIO_PENDENTE_SENHA,
    Convite,
    MetaVendedor,
    Tenant,
    Usuario,
    token_captura_do_tenant,
)
from acesso.rate_limit import (
    bloqueado as login_bloqueado,
)
from acesso.rate_limit import (
    limpar as login_limpar,
)
from acesso.rate_limit import (
    registrar_falha as login_registrar_falha,
)
from acesso.session import iniciar_sessao
from contatos.models import Negocio
from core.dominio import NICHO_PADRAO, NICHOS, stages_do_nicho
from core.gprb import (
    ROLE_LABELS_GPRB,
    atualizar_usuario_sistema,
    excluir_usuario_sistema,
    listar_usuarios_sistema,
    obter_usuario_sistema,
    opcoes_lojas_usuario,
    opcoes_perfis_usuario,
    opcoes_prefeituras_usuario,
)
from core.gprb import autenticar_usuario as gprb_autenticar
from core.gprb import existe_usuario as gprb_existe_usuario
from core.utils import parse_brl
from recepcao.models import EtapaFunil, adotar_nicho, garantir_etapas

# A4/S8 — hash pre-computado para o caso de usuario inexistente: garante que
# `check_password` rode o PBKDF2 completo mesmo sem usuario, eliminando a
# diferenca de timing que permitia enumerar e-mails validos.
_HASH_DUMMY = make_password('usuario-inexistente-dummy')

# Hostnames/portas que indicam acesso vindo do Saldorer (autenticacao GPRB)
_SALDORER_HOSTS = ('saldorer.cloud', 'www.saldorer.cloud')

# Mapeamento de role GPRB -> role CRM (espelho local). O oficialato do GPRB
# (GRANDE_PRIOR, PREFEITO, TI, ...) mapeia 1:1 para os perfis RER do CRM.
_GPRB_ROLE_MAP = {
    'SYS_ADMIN': ROLE_ADMIN_SAAS,
    'ADMIN_LOJA': ROLE_ADMIN_COMPANY,
    'OPERADOR': ROLE_OPERACIONAL,
    'GRANDE_PRIOR': 'grande_prior',
    'GRANDE_CHANCELER': 'grande_chanceler',
    'GRANDE_TESOUREIRO': 'grande_tesoureiro',
    'GRANDE_SECRETARIO': 'grande_secretario',
    'PREFEITO': 'prefeito',
    'DEPUTADO': 'deputado_mestre',
    'DEPUTADO_MESTRE': 'deputado_mestre',
    'MEMBER': 'operacional',
}


def _tenant_gprb_local():
    """Tenant local que representa a organizacao GPRB (criado sob demanda)."""
    tenant = Tenant.objects.filter(slug='gprb').first()
    if tenant is None:
        tenant = Tenant.objects.create(nome='GPRB', slug='gprb')
    return tenant


def _client_ip(request) -> str:
    """IP do cliente para fins de rate limiting (sem confiar em X-Forwarded-For)."""
    return request.META.get('REMOTE_ADDR', '') or '0.0.0.0'


def _is_saldorer(request) -> bool:
    """Detecta se a requisicao veio do Saldorer (host ou porta)."""
    host = request.get_host().split(':')[0].lower()
    if any(host == h or host.endswith('.' + h) for h in _SALDORER_HOSTS):
        return True
    # Fallback: porta 3000 = saldorer local
    port = request.get_host().split(':')[1] if ':' in request.get_host() else ''
    return port == '3000'


def _gprb_autenticar_seguro(login_id, senha):
    """Autentica no banco GPRB sem estourar excecao se o banco estiver fora.

    Retorna (ok: bool | None, eh_do_gprb: bool | None):
        (user_dict, True)   -> autenticado
        (None, True)        -> usuario e do GPRB mas senha/status invalidos
        (None, False)       -> identificador nao existe no GPRB
        (None, None)        -> banco GPRB indisponivel (nao da para saber)
    """
    try:
        user = gprb_autenticar(login_id, senha)
        if user is not None:
            return user, True
        return None, gprb_existe_usuario(login_id)
    except Exception as e:
        logger.error('Erro na autenticacao GPRB para %s: %s', login_id, e)
        return None, None


def _entrar_com_usuario_gprb(request, gprb_user, senha, origem='gprb'):
    """Abre sessao com um usuario autenticado no banco GPRB.

    Cria/atualiza o espelho local (nome/role sincronizados com o GPRB a cada
    login — o GPRB e a fonte da verdade).
    """
    local_user = Usuario.objects.filter(email__iexact=gprb_user['email']).first()
    crm_role = _GPRB_ROLE_MAP.get(gprb_user['role'], ROLE_OPERACIONAL)
    tenant_gprb = _tenant_gprb_local()
    if local_user is None:
        local_user = Usuario.objects.create(
            nome=gprb_user['name'] or gprb_user['email'] or '',
            email=gprb_user['email'],
            senha=make_password(senha),
            role=crm_role,
            tenant=tenant_gprb,
        )
    else:
        # Sincroniza espelho com o GPRB (nome/role podem ter mudado la).
        if local_user.nome != (gprb_user['name'] or local_user.nome):
            local_user.nome = gprb_user['name'] or local_user.nome
        if local_user.role != crm_role:
            local_user.role = crm_role
        if local_user.tenant_id is None:
            local_user.tenant = tenant_gprb
        if not local_user.senha or local_user.senha == SENHA_PENDENTE:
            local_user.senha = make_password(senha)
        local_user.save(update_fields=['nome', 'role', 'senha', 'tenant', 'updated_at'])
    request.session.flush()
    iniciar_sessao(
        request, local_user,
        nicho=local_user.tenant.nicho if local_user.tenant else '',
        dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
    )
    request.session['origem'] = origem
    return local_user


def login_web(request):
    """POST /login/ — valida credenciais e abre sessao.

    O banco GPRB (compartilhado com o Saldorer/RER) e a fonte da verdade do
    login: tenta autenticar nele primeiro em QUALQUER origem. O cadastro local
    do CRM e usado apenas como fallback para identificadores que nao existem
    no GPRB (ou quando o banco GPRB esta indisponivel).
    """
    if request.session.get('usuario_id'):
        return redirect('dashboard:index')

    erro = None
    eh_saldorer = _is_saldorer(request)

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        ip = _client_ip(request)

        # Normaliza: Saldorer usa campo unico 'identifier' (telefone ou email)
        login_id = identifier or email

        # Rate limit — bloqueia antes de gastar CPU.
        if login_bloqueado(ip, login_id):
            erro = 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
        elif not login_id or not senha:
            erro = 'Informe seu celular e senha.'
        else:
            # --- 1) Autenticacao GPRB (banco compartilhado, primaria) ---
            gprb_user, eh_do_gprb = _gprb_autenticar_seguro(login_id, senha)
            if gprb_user is not None:
                login_limpar(ip, login_id)
                _entrar_com_usuario_gprb(
                    request, gprb_user, senha,
                    origem='saldorer' if eh_saldorer else 'gprb',
                )
                return redirect('dashboard:index')

            # Identificador pertence ao GPRB (senha/status invalidos la):
            # a palavra final e do GPRB — nao cai no login local.
            if eh_do_gprb:
                login_registrar_falha(ip, login_id)
                erro = 'Login ou senha inválidos.'
            else:
                # --- 2) Fallback: cadastro local do CRM ---
                usuario = Usuario.objects.filter(email__iexact=login_id).first()
                senha_ok = check_password(senha, usuario.senha) if usuario else check_password(senha, _HASH_DUMMY)
                if usuario is not None and senha_ok:
                    login_limpar(ip, login_id)
                    request.session.flush()
                    tenant = usuario.tenant
                    iniciar_sessao(
                        request, usuario,
                        nicho=tenant.nicho if tenant else '',
                        dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
                    )
                    request.session['origem'] = 'crm'
                    if usuario.role == ROLE_ADMIN_COMPANY and tenant is not None and not tenant.nicho:
                        return redirect('acesso:onboarding')
                    return redirect('dashboard:index')
                # S2 (PRD-USUARIOS): pendente ainda não definiu senha — não autentica.
                if usuario is not None and usuario.pendente_ativacao:
                    erro = ('Sua conta ainda não foi ativada. Abra o link de ativação '
                            'enviado por e-mail (válido por 72 horas) e defina sua senha.')
                else:
                    login_registrar_falha(ip, login_id)
                    erro = 'Login ou senha inválidos.'

    return render(request, 'acesso/login.html', {
        'erro': erro,
        'eh_saldorer': eh_saldorer,
    })


def onboarding(request):
    """Primeiro login do admin_company: pergunta o nicho do negócio e guarda no tenant."""
    usuario = Usuario.objects.filter(id=request.session.get('usuario_id')).first()
    if usuario is None or usuario.role != ROLE_ADMIN_COMPANY:
        return redirect('dashboard:index')
    tenant = usuario.tenant
    if tenant is None or tenant.nicho:
        return redirect('dashboard:index')

    opcoes = [
        {'key': k, 'label': v['label'], 'stages': [s['name'] for s in stages_do_nicho(k)]}
        for k, v in NICHOS.items()
    ]

    erro = None
    if request.method == 'POST':
        nicho = request.POST.get('nicho', '').strip()
        if nicho not in NICHOS:
            erro = 'Escolha uma das opções de negócio.'
        else:
            tenant.nicho = nicho
            tenant.save(update_fields=['nicho'])
            adotar_nicho(tenant.id, nicho)  # pipeline padrão do nicho escolhido
            request.session['nicho'] = nicho
            return redirect('dashboard:index')

    return render(request, 'acesso/onboarding.html', {
        'opcoes': opcoes,
        'erro': erro,
        'tenant': tenant,
    })


@require_POST
def logout_web(request):
    """S8/A5 — POST-only: evita logout CSRF via <img src="/logout/"> em site malicioso."""
    request.session.flush()
    return redirect('acesso:login')


def _guard_equipe(request):
    """Redireciona se o usuario nao pode gerir equipe.

    Gestor sem tenant (admin_saas) enxerga o escopo GLOBAL — todos os tenants,
    mesma regra do `filtro_tenant` e da premissa do PRD-USUARIOS-SEM-SENHA
    ("para um gestor sem tenant o escopo seria global").
    """
    if not pode_gerir_usuarios(request):
        return redirect('dashboard:index')
    if Usuario.objects.filter(id=request.session.get('usuario_id')).first() is None:
        return redirect('acesso:login')
    return None


def _qs_escopo(tid, qs):
    """Escopa o queryset ao tenant do gestor; gestor sem tenant (admin_saas) ve tudo."""
    if tid is not None:
        return qs.filter(tenant_id=tid)
    return qs


def _usuarios_locais_ativos(tid, emails_vistos, *, q='', perfil='', loja='', status=''):
    """Usuarios locais ativos do tenant (espelho CRM) ainda nao listados."""
    if status and status.upper() not in ('', 'ACTIVE'):
        return []
    if loja:
        return []
    qs = _qs_escopo(tid, Usuario.objects.exclude(status=USUARIO_PENDENTE_SENHA))
    if q:
        qs = qs.filter(
            models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
        )
    if perfil:
        qs = qs.filter(role=perfil)
    resultado = []
    for u in qs.order_by('nome', 'email'):
        email_key = u.email.lower()
        if email_key in emails_vistos:
            continue
        emails_vistos.add(email_key)
        resultado.append({
            'id': u.id,
            'gprb': False,
            'nome': u.nome,
            'email': u.email,
            'loja_nome': '',
            'loja_numero': '',
            'loja_display': '—',
            'papel': u.role,
            'papel_label': ROLE_LABELS.get(u.role, u.role),
            'ultimo_acesso': u.updated_at,
            'status_code': 'ACTIVE',
            'status_label': 'Ativo',
            'pendente': False,
            'pode_reenviar': False,
            'celular': u.celular,
        })
    return resultado


def _usuarios_locais_pendentes(tid, emails_gprb, *, q='', perfil='', status=''):
    """Usuarios locais pendentes de ativacao que ainda nao existem no GPRB."""
    qs = _qs_escopo(tid, Usuario.objects.filter(status=USUARIO_PENDENTE_SENHA))
    if q:
        qs = qs.filter(
            models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
        )
    if perfil:
        qs = qs.filter(role=perfil)
    if status and status.upper() != 'PENDENTE':
        return []
    resultado = []
    for u in qs.order_by('nome', 'email'):
        if u.email.lower() in emails_gprb:
            continue
        resultado.append({
            'id': u.id,
            'gprb': False,
            'nome': u.nome,
            'email': u.email,
            'loja_nome': '',
            'loja_numero': '',
            'loja_display': '—',
            'papel': u.role,
            'papel_label': ROLE_LABELS.get(u.role, u.role),
            'ultimo_acesso': None,
            'status_code': 'PENDENTE',
            'status_label': 'Aguardando ativação',
            'pendente': True,
            'pode_reenviar': u.reenvios_ativacao < LIMITE_REENVIOS,
            'celular': u.celular,
        })
    return resultado


def _opcoes_equipe_gprb():
    """Carrega opcoes de filtro do GPRB; retorna dicts vazios se indisponivel."""
    try:
        return {
            'lojas': opcoes_lojas_usuario(),
            'perfis': opcoes_perfis_usuario(),
            'gprb_ok': True,
        }
    except Exception as e:
        logger.warning('GPRB indisponivel para opcoes de equipe: %s', e)
        perfis = [{'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO]
        return {'lojas': [], 'perfis': perfis, 'gprb_ok': False}


@web_login_required
def equipe(request):
    """Lista de usuarios do sistema com busca e filtros."""
    if redir := _guard_equipe(request):
        return redir
    tid = request.session.get('usuario', {}).get('tenant_id')

    erros = []
    sucesso = None
    link_simulado = None

    if request.method == 'POST':
        alvo_id = request.POST.get('reenviar_id', '')
        if alvo_id.isdigit():
            alvo = _qs_escopo(tid, Usuario.objects.all()).filter(pk=alvo_id).first()
            if alvo is None:
                erros.append('Usuário não encontrado.')
            elif not alvo.pendente_ativacao:
                erros.append('Este usuário já ativou a conta — não há link para reenviar.')
            elif alvo.reenvios_ativacao >= LIMITE_REENVIOS:
                erros.append(f'Limite de {LIMITE_REENVIOS} reenvios atingido para {alvo.email}.')
            else:
                reenviar_ativacao(alvo)
                status, link = enviar_email_ativacao(request, alvo)
                sucesso = f'Novo link de ativação enviado para {alvo.email}.'
                if status == 'simulado':
                    link_simulado = link

    q = request.GET.get('q', '').strip()
    loja = request.GET.get('loja', '').strip()
    perfil = request.GET.get('perfil', '').strip()
    status = request.GET.get('status', '').strip()
    filtros_ativos = bool(q or loja or perfil or status)

    opcoes = _opcoes_equipe_gprb()
    usuarios = []
    try:
        gprb_status = status if status and status.upper() != 'PENDENTE' else ''
        if not status or status.upper() != 'PENDENTE':
            usuarios = listar_usuarios_sistema(
                q=q, loja_id=loja, perfil=perfil, status=gprb_status,
            )
        emails_gprb = {u['email'].lower() for u in usuarios if u.get('email')}
        if status.upper() == 'PENDENTE':
            usuarios = _usuarios_locais_pendentes(
                tid, set(), q=q, perfil=perfil, status=status,
            )
        else:
            usuarios.extend(_usuarios_locais_pendentes(
                tid, emails_gprb, q=q, perfil=perfil, status=status,
            ))
            emails_vistos = {u['email'].lower() for u in usuarios if u.get('email')}
            usuarios.extend(_usuarios_locais_ativos(
                tid, emails_vistos, q=q, perfil=perfil, loja=loja, status=status,
            ))
    except Exception as e:
        logger.error('Erro ao carregar usuarios do GPRB: %s', e)
        opcoes['gprb_ok'] = False
        emails_gprb = set()
        usuarios = _usuarios_locais_pendentes(tid, emails_gprb, q=q, perfil=perfil, status=status)
        if not status or status.upper() == 'ACTIVE':
            qs = _qs_escopo(tid, Usuario.objects.exclude(status=USUARIO_PENDENTE_SENHA))
            if q:
                qs = qs.filter(
                    models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
                )
            if perfil:
                qs = qs.filter(role=perfil)
            for u in qs.order_by('nome', 'email'):
                usuarios.append({
                    'id': u.id,
                    'gprb': False,
                    'nome': u.nome,
                    'email': u.email,
                    'loja_nome': '',
                    'loja_numero': '',
                    'loja_display': '—',
                    'papel': u.role,
                    'papel_label': ROLE_LABELS.get(u.role, u.role),
                    'ultimo_acesso': u.updated_at,
                    'status_code': 'ACTIVE',
                    'status_label': 'Ativo',
                    'pendente': False,
                    'pode_reenviar': False,
                    'celular': u.celular,
                })

    if not opcoes['perfis']:
        opcoes['perfis'] = [
            {'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO
        ]

    return render(request, 'acesso/equipe.html', {
        'usuarios': usuarios,
        'erros': erros,
        'sucesso': sucesso,
        'link_simulado': link_simulado,
        'q': q,
        'loja': loja,
        'perfil': perfil,
        'status': status,
        'filtros_ativos': filtros_ativos,
        'opcoes_lojas': opcoes['lojas'],
        'opcoes_perfis': opcoes['perfis'],
        'limite_reenvios': LIMITE_REENVIOS,
    })


@web_login_required
def equipe_novo(request):
    """Formulario para criar usuario do sistema (sem senha — link de ativacao 72h)."""
    if redir := _guard_equipe(request):
        return redir
    tid = request.session.get('usuario', {}).get('tenant_id')
    criador = Usuario.objects.filter(id=request.session.get('usuario_id')).first()

    erros = []
    sucesso = None
    link_simulado = None
    prefeituras = []
    try:
        prefeituras = opcoes_prefeituras_usuario()
    except Exception as e:
        logger.warning('Erro ao carregar prefeituras: %s', e)

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        celular = request.POST.get('celular', '').strip()
        papel = request.POST.get('papel', '')
        prefeitura_id = request.POST.get('prefeitura', '').strip()
        if not nome:
            erros.append('Informe o nome do usuário.')
        if not email:
            erros.append('Informe o e-mail do usuário.')
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                erros.append('Informe um e-mail válido.')
            if Usuario.objects.filter(email__iexact=email).exists():
                erros.append(f'Já existe um usuário com o e-mail {email}.')
        if not celular:
            erros.append('Informe o celular — ele será usado como login.')
        if papel not in ROLES_ATRIB_CRIACAO:
            erros.append('Escolha um perfil válido.')
        if not erros:
            try:
                novo = criar_usuario_pendente(
                    nome=nome, email=email, celular=celular, papel=papel,
                    criado_por=criador, tenant_id=tid, prefeitura_id=prefeitura_id,
                )
            except IntegrityError:
                erros.append(f'Já existe um usuário com o e-mail {email}.')
            else:
                status_envio, link = enviar_email_ativacao(request, novo)
                sucesso = (
                    f'{nome} foi cadastrado(a). Enviamos um link de ativação para '
                    f'{email} — válido por 72 horas.'
                )
                if status_envio == 'simulado':
                    link_simulado = link

    return render(request, 'acesso/equipe_novo.html', {
        'erros': erros,
        'sucesso': sucesso,
        'link_simulado': link_simulado,
        'prefeituras': prefeituras,
        'perfis': [
            {'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO
        ],
        'limite_reenvios': LIMITE_REENVIOS,
    })


def _usuario_para_edicao(user_id, tid):
    """Localiza o usuario alvo (GPRB por UUID ou local por id) para edicao/exclusao.

    Retorna (usuario_dict, usuario_local|None). GPRB dicionarios ganham 'gprb': True.
    """
    if user_id.isdigit():
        u = _qs_escopo(tid, Usuario.objects.all()).filter(pk=user_id).first()
        if u is None:
            return None, None
        return {
            'id': u.id,
            'gprb': False,
            'nome': u.nome,
            'email': u.email,
            'celular': u.celular or '',
            'papel': u.role,
            'status_code': 'PENDENTE' if u.pendente_ativacao else 'ACTIVE',
            'status_label': 'Aguardando ativação' if u.pendente_ativacao else 'Ativo',
            'prefeitura_id': u.prefeitura_id or '',
        }, u
    gprb_user = obter_usuario_sistema(user_id)
    if gprb_user is not None:
        gprb_user['gprb'] = True
        espelho = Usuario.objects.filter(email__iexact=gprb_user['email']).first()
        return gprb_user, espelho
    return None, None


def _prefeituras_para_form():
    try:
        return opcoes_prefeituras_usuario()
    except Exception as e:
        logger.warning('Erro ao carregar prefeituras para formulario: %s', e)
        return []


@web_login_required
def equipe_editar(request, user_id):
    """Edicao de um usuario do sistema (GPRB ou local)."""
    if redir := _guard_equipe(request):
        return redir
    tid = request.session.get('usuario', {}).get('tenant_id')

    usuario, espelho_local = _usuario_para_edicao(user_id, tid)
    if usuario is None:
        raise Http404('Usuário não encontrado')

    perfis = (
        [{'key': r, 'label': ROLE_LABELS_GPRB.get(r, r)} for r in ROLE_LABELS_GPRB]
        if usuario['gprb'] else
        [{'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO]
    )
    prefeituras = _prefeituras_para_form()
    erros = []

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        celular = request.POST.get('celular', '').strip()
        papel = request.POST.get('papel', '')
        prefeitura_id = request.POST.get('prefeitura', '').strip()

        if not nome:
            erros.append('Informe o nome do usuário.')
        if not email:
            erros.append('Informe o e-mail do usuário.')
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                erros.append('Informe um e-mail válido.')
        chaves_validas = {p['key'] for p in perfis}
        if papel not in chaves_validas:
            erros.append('Escolha um perfil válido.')

        if not erros:
            if usuario['gprb']:
                atualizar_usuario_sistema(
                    user_id, nome=nome, email=email, celular=celular,
                    role=papel, prefeitura_id=prefeitura_id,
                )
                if espelho_local is not None and espelho_local.email.lower() == email:
                    espelho_local.nome = nome
                    espelho_local.save(update_fields=['nome', 'updated_at'])
            else:
                duplicado = Usuario.objects.filter(email__iexact=email).exclude(pk=usuario['id']).exists()
                if duplicado:
                    erros.append(f'Já existe um usuário com o e-mail {email}.')
                else:
                    espelho_local.nome = nome
                    espelho_local.email = email
                    espelho_local.celular = celular
                    espelho_local.role = papel
                    espelho_local.prefeitura_id = prefeitura_id
                    espelho_local.save()
        if not erros:
            return redirect('equipe')
        usuario.update({'nome': nome, 'email': email, 'celular': celular,
                        'papel': papel, 'prefeitura_id': prefeitura_id})

    return render(request, 'acesso/equipe_editar.html', {
        'u': usuario,
        'perfis': perfis,
        'prefeituras': prefeituras,
        'erros': erros,
    })


@web_login_required
def equipe_excluir(request, user_id):
    """Exclusao de um usuario do sistema (soft-delete no GPRB, fisica no local)."""
    if redir := _guard_equipe(request):
        return redir
    tid = request.session.get('usuario', {}).get('tenant_id')

    usuario, espelho_local = _usuario_para_edicao(user_id, tid)
    if usuario is None:
        raise Http404('Usuário não encontrado')

    proprio = str(request.session.get('usuario_id')) == str(usuario['id']) and not usuario['gprb']
    erro = None
    if request.method == 'POST':
        if proprio:
            erro = 'Você não pode excluir o seu próprio usuário.'
        else:
            if usuario['gprb']:
                excluir_usuario_sistema(user_id)
                if espelho_local is not None and espelho_local.email.lower() == usuario['email'].lower():
                    espelho_local.delete()
            else:
                espelho_local.delete()
            return redirect('equipe')

    return render(request, 'acesso/equipe_excluir.html', {
        'u': usuario,
        'erro': erro,
        'proprio': proprio,
    })


def _sessoes_do_usuario(usuario_id, atual_key):
    """Sessoes ativas do usuario na tabela de sessoes do Django (sessao atual primeiro).

    S8 — filtra sessoes ja expiradas no banco antes de decodificar, reduzindo o
    volume de iteracoes e evitando processar dados obsoletos.
    """
    itens = []
    agora = timezone.now()
    for s in Session.objects.filter(expire_date__gt=agora):
        try:
            dados = s.get_decoded()
        except Exception as e:
            logger.warning('Erro ao decodificar sessao %s: %s', s.session_key, e)
            continue
        if dados.get('usuario_id') != usuario_id:
            continue
        itens.append({
            'key': s.session_key,
            'atual': s.session_key == atual_key,
            'dispositivo': dados.get('dispositivo') or 'Sessão antiga',
            'expira': s.expire_date,
        })
    itens.sort(key=lambda x: x['atual'], reverse=True)
    return itens


def _chave_etapa(tid, nome):
    """Chave interna única por tenant a partir do nome (evita colisões e etapas de sistema)."""
    base = slugify(nome) or 'etapa'
    existentes = set(EtapaFunil.objects.filter(tenant_id=tid).values_list('key', flat=True))
    chave, n = base, 2
    while chave in existentes or chave in ('fechado', 'perdido'):
        chave = f'{base}_{n}'
        n += 1
    return chave


def _validar_email(email, erros):
    """Valida formato de e-mail; devolve o e-mail normalizado (ou None com erro anexado)."""
    email = (email or '').strip().lower()
    if not email:
        erros.append('Informe o e-mail.')
        return None
    try:
        validate_email(email)
    except DjangoValidationError:
        erros.append('Informe um e-mail válido.')
    return email


@web_login_required
def config(request):
    """Configurações: perfil, senha, aparência, sessões ativas, equipe e convites.

    Cada formulário da página envia um campo oculto `acao`; o operacional só
    enxerga perfil/aparência/sessões — equipe e convites são do admin da clínica.
    """
    usuario = Usuario.objects.filter(id=request.session.get('usuario_id')).first()
    if usuario is None:
        return redirect('acesso:login')
    sessao = request.session.get('usuario', {})
    role = sessao.get('role')
    tid = sessao.get('tenant_id')

    erros, msgs = [], []
    contexto_link = None  # link de ativacao em modo simulacao (dev, sem SMTP)
    acao = request.POST.get('acao', '') if request.method == 'POST' else ''

    if acao == 'perfil':
        nome = request.POST.get('nome', '').strip()
        email = _validar_email(request.POST.get('email', ''), erros)
        if not nome:
            erros.append('Informe o nome.')
        if email and Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
            erros.append(f'Já existe um usuário com o e-mail {email}.')
        if not erros:
            usuario.nome, usuario.email = nome, email
            usuario.save(update_fields=['nome', 'email'])
            sessao.update({'nome': nome, 'email': email})
            request.session['usuario'] = sessao
            request.session.modified = True
            msgs.append('Perfil atualizado com sucesso.')

    elif acao == 'senha':
        atual = request.POST.get('senha_atual', '')
        nova = request.POST.get('nova_senha', '')
        confirma = request.POST.get('confirma_senha', '')
        if not check_password(atual, usuario.senha):
            erros.append('A senha atual está incorreta.')
        # A2/S8 — politica de senha via AUTH_PASSWORD_VALIDATORS.
        try:
            validate_password(nova, user=usuario)
        except DjangoValidationError as e:
            erros.extend(e.messages)
        if nova != confirma:
            erros.append('A confirmação da nova senha não confere.')
        if not erros:
            usuario.senha = make_password(nova)
            usuario.save(update_fields=['senha'])
            msgs.append('Senha alterada com sucesso.')

    elif acao == 'sessao':
        chave = request.POST.get('sessao_key', '')
        if chave and chave != request.session.session_key:
            Session.objects.filter(session_key=chave).delete()
            msgs.append('Sessão encerrada.')

    elif acao == 'meta' and role == ROLE_ADMIN_COMPANY and tid:
        raw = (request.POST.get('meta_mensal', '') or '').strip()
        meta = parse_brl(raw)
        if meta < 0:
            erros.append('Informe um valor de meta válido (ex.: 50.000,00).')
        else:
            if meta < 0:
                erros.append('A meta não pode ser negativa.')
            else:
                tenant = usuario.tenant
                tenant.meta_mensal = meta if meta > 0 else None
                tenant.save(update_fields=['meta_mensal'])
                msgs.append('Meta de faturamento atualizada.')

    elif acao == 'metas_vendedores' and role == ROLE_ADMIN_COMPANY and tid:
        try:
            mes = date.fromisoformat(request.POST.get('mes', ''))
        except ValueError:
            mes = timezone.localdate()
        mes = mes.replace(day=1)
        erros_meta = False
        for chave, bruto in request.POST.items():
            if not chave.startswith('meta_'):
                continue
            uid = chave.split('_', 1)[1]
            if not uid.isdigit():
                continue
            bruto = (bruto or '').strip()
            if not bruto:
                MetaVendedor.objects.filter(usuario_id=uid, mes=mes).delete()
                continue
            valor = parse_brl(bruto)
            if valor < 0:
                erros.append('As metas não podem ser negativas.')
                erros_meta = True
                continue
            if valor < 0:
                erros.append('As metas não podem ser negativas.')
                erros_meta = True
                continue
            if not Usuario.objects.filter(tenant_id=tid, pk=uid).exists():
                continue
            if valor > 0:
                MetaVendedor.objects.update_or_create(
                    usuario_id=uid, mes=mes, defaults={'valor': valor},
                )
            else:
                MetaVendedor.objects.filter(usuario_id=uid, mes=mes).delete()
        if not erros_meta:
            msgs.append(f'Metas de {mes.strftime("%m/%Y")} atualizadas.')

    elif acao == 'equipe' and role == ROLE_ADMIN_COMPANY and tid:
        email = _validar_email(request.POST.get('email', ''), erros)
        papel = request.POST.get('papel', '')
        if email and Usuario.objects.filter(email__iexact=email).exists():
            erros.append(f'Já existe um usuário com o e-mail {email}.')
        if email and Convite.objects.filter(
                tenant_id=tid, email__iexact=email, usado_em__isnull=True, cancelado_em__isnull=True).exists():
            erros.append(f'Já existe um convite pendente para {email}.')
        if papel not in ROLES_DE_TENANT:
            erros.append('Escolha um papel válido.')
        if not erros:
            convite = Convite.objects.create(
                token=secrets.token_urlsafe(32),
                tenant_id=tid,
                email=email,
                papel=papel,
                criado_por_id=usuario.id,
                expira_em=timezone.now() + timedelta(days=7),
            )
            return redirect(f'{request.path}?convite={convite.id}')

    elif acao == 'criar_usuario' and role in ROLES_GESTORES_USUARIOS and tid:
        # Fluxo novo (PRD-USUARIOS-SEM-SENHA): conta criada SEM senha; o proprio
        # usuario a define pelo link de ativacao enviado por e-mail (72h).
        nome = (request.POST.get('nome', '') or '').strip()
        email = _validar_email(request.POST.get('email', ''), erros)
        celular = (request.POST.get('celular', '') or '').strip()
        papel = request.POST.get('papel', '')
        if not nome:
            erros.append('Informe o nome do usuário.')
        if email and Usuario.objects.filter(email__iexact=email).exists():
            erros.append(f'Já existe um usuário com o e-mail {email}.')
        if papel not in ROLES_ATRIB_CRIACAO:
            erros.append('Escolha um perfil válido.')
        if not erros:
            try:
                novo = criar_usuario_pendente(
                    nome=nome, email=email, celular=celular, papel=papel,
                    criado_por=usuario, tenant_id=tid,
                )
            except IntegrityError:
                erros.append(f'Já existe um usuário com o e-mail {email}.')
            else:
                status, link = enviar_email_ativacao(request, novo)
                msgs.append(
                    f'Usuário "{nome}" criado — enviamos um link de ativação para '
                    f'{email} (válido por 72 horas).'
                )
                if status == 'simulado':
                    contexto_link = link

    elif acao == 'reenviar_ativacao' and role in ROLES_GESTORES_USUARIOS and tid:
        alvo_id = request.POST.get('usuario_id', '')
        if not alvo_id.isdigit():
            erros.append('Usuário inválido.')
        else:
            alvo = Usuario.objects.filter(tenant_id=tid, pk=alvo_id).first()
            if alvo is None:
                erros.append('Usuário não encontrado.')
            elif not alvo.pendente_ativacao:
                erros.append('Este usuário já ativou a conta.')
            elif alvo.reenvios_ativacao >= LIMITE_REENVIOS:
                erros.append(f'Limite de {LIMITE_REENVIOS} reenvios atingido para {alvo.email}.')
            else:
                reenviar_ativacao(alvo)
                status, link = enviar_email_ativacao(request, alvo)
                msgs.append(f'Novo link de ativação enviado para {alvo.email}.')
                if status == 'simulado':
                    contexto_link = link

    elif acao == 'convite_cancelar' and role == ROLE_ADMIN_COMPANY and tid:
        convite_id = request.POST.get('convite_id', '')
        if convite_id.isdigit():
            convite = Convite.objects.filter(
                tenant_id=tid, pk=convite_id, cancelado_em__isnull=True
            ).first()
            if convite and convite.usado_em is None:
                convite.cancelado_em = timezone.now()
                convite.save(update_fields=['cancelado_em'])
                msgs.append('Convite cancelado.')

    elif acao in ('etapa_nova', 'etapa_editar') and role == ROLE_ADMIN_COMPANY and tid:
        nome = (request.POST.get('nome', '') or '').strip()
        cor = (request.POST.get('cor', '') or '').strip()
        cor = cor if re.fullmatch(r'#[0-9a-fA-F]{3,8}', cor) else '#94a3b8'
        peso_raw = (request.POST.get('peso', '') or '').strip()
        peso = None
        if peso_raw:
            try:
                peso = Decimal(peso_raw.replace(',', '.'))
            except (InvalidOperation, ValueError):
                erros.append('Informe uma probabilidade válida (0 a 1).')
            else:
                if peso < 0 or peso > 1:
                    erros.append('A probabilidade deve estar entre 0 e 1.')
        ordem_raw = request.POST.get('ordem', '')
        ordem = int(ordem_raw) if ordem_raw.isdigit() else 999
        if not nome:
            erros.append('Informe o nome da etapa.')
        if not erros and acao == 'etapa_nova':
            etapa = EtapaFunil.objects.create(
                tenant_id=tid, key=_chave_etapa(tid, nome), nome=nome,
                cor=cor, ordem=ordem, peso=peso if peso is not None else Decimal('0.500'),
            )
            msgs.append(f'Etapa "{etapa.nome}" adicionada ao funil.')
        elif not erros:
            etapa = EtapaFunil.objects.filter(
                tenant_id=tid, pk=request.POST.get('etapa_id', '')
            ).first()
            if etapa is None:
                erros.append('Etapa não encontrada.')
            else:
                etapa.nome, etapa.cor, etapa.ordem = nome, cor, ordem
                campos = ['nome', 'cor', 'ordem']
                if peso is not None:
                    etapa.peso = peso
                    campos.append('peso')
                etapa.save(update_fields=campos)
                msgs.append(f'Etapa "{etapa.nome}" atualizada.')

    elif acao == 'etapa_excluir' and role == ROLE_ADMIN_COMPANY and tid:
        etapa = EtapaFunil.objects.filter(
            tenant_id=tid, pk=request.POST.get('etapa_id', '')
        ).first()
        if etapa is None:
            erros.append('Etapa não encontrada.')
        elif etapa.sistema:
            erros.append('Etapas de sistema (Fechado/Perdido) não podem ser excluídas — apenas renomeadas.')
        elif Negocio.objects.filter(tenant_id=tid, stage=etapa.key).exists():
            erros.append(f'A etapa "{etapa.nome}" ainda tem negócios — mova-os antes de excluir.')
        else:
            nome = etapa.nome
            etapa.delete()
            msgs.append(f'Etapa "{nome}" excluída do funil.')

    elif acao == 'captura_salvar' and role == ROLE_ADMIN_COMPANY and tid:
        tenant = usuario.tenant
        origem = (request.POST.get('origem_captura', '') or '').strip()
        if origem:
            tenant.origem_captura = origem[:40]
        tenant.captura_ativa = request.POST.get('captura_ativa') == 'on'
        tenant.save(update_fields=['origem_captura', 'captura_ativa'])
        msgs.append('Captura de lead atualizada.')

    elif acao == 'softphone' and role == ROLE_ADMIN_COMPANY and tid:
        tenant = usuario.tenant
        schema = request.POST.get('softphone_schema', 'sip')
        if schema not in ('sip', 'tel'):
            erros.append('Esquema de softphone inválido.')
        else:
            tenant.softphone_schema = schema
            tenant.softphone_dominio = (request.POST.get('softphone_dominio', '') or '').strip()[:160]
            tenant.save(update_fields=['softphone_schema', 'softphone_dominio'])
            msgs.append('Discador atualizado — a chamada agora usa a configuração do softphone da empresa.')

    elif acao == 'captura_gerar' and role == ROLE_ADMIN_COMPANY and tid:
        usuario.tenant.token_captura = secrets.token_urlsafe(32)  # S2.4 — 256 bits
        usuario.tenant.save(update_fields=['token_captura'])
        msgs.append('Novo link de captura gerado — o link antigo deixou de funcionar.')

    elif acao == 'transferir_dono' and role == ROLE_ADMIN_COMPANY and tid:
        alvo_id = request.POST.get('usuario_id', '')
        if not usuario.pode_transferir_dono():
            erros.append('Somente o(a) dono(a) da empresa pode transferir a propriedade.')
        elif not alvo_id.isdigit():
            erros.append('Membro inválido.')
        else:
            alvo = Usuario.objects.filter(tenant_id=tid, pk=alvo_id).first()
            if alvo is None:
                erros.append('Membro não encontrado nesta empresa.')
            elif alvo.pk == usuario.pk:
                erros.append('Você já é o(a) dono(a) — escolha outro membro para transferir.')
            else:
                usuario.tenant.dono = alvo
                usuario.tenant.save(update_fields=['dono'])
                msgs.append(f'{alvo.nome} agora é o(a) novo(a) dono(a) da empresa.')

    # ---- Contexto comum ----
    contexto = {'erros': erros, 'msgs': msgs, 'usuario': usuario, 'contexto_link': contexto_link}

    # Convite recém-criado (link para copiar, exibido em destaque)
    convite_id = request.GET.get('convite', '')
    novo_convite = None
    if convite_id.isdigit() and role == ROLE_ADMIN_COMPANY and tid:
        c = Convite.objects.filter(tenant_id=tid, pk=convite_id, cancelado_em__isnull=True).first()
        if c and c.usado_em is None:
            novo_convite = {
                'email': c.email,
                'papel_label': ROLE_LABELS.get(c.papel, c.papel),
                'link': request.build_absolute_uri(reverse('convidar', args=[c.token])),
            }
    contexto['novo_convite'] = novo_convite

    # Sessões ativas
    contexto['sessoes'] = _sessoes_do_usuario(usuario.id, request.session.session_key)

    # Meta de faturamento (admin da clínica)
    contexto['mostrar_meta'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if contexto['mostrar_meta'] and usuario.tenant is not None:
        meta = usuario.tenant.meta_mensal
        contexto['meta_atual'] = (
            str(meta).replace('.', ',') if meta is not None else ''
        )

    # Metas por vendedor (admin da clínica — dashboard individual de atingimento)
    contexto['mostrar_metas_vendedores'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if contexto['mostrar_metas_vendedores']:
        # após um POST, mantém o mês que estava sendo editado (mesmo com erro de validação)
        mes_raw = request.POST.get('mes', '') if request.method == 'POST' else request.GET.get('mes', '')
        try:
            mes_metas = date.fromisoformat(mes_raw).replace(day=1) if mes_raw else timezone.localdate().replace(day=1)
        except ValueError:
            mes_metas = timezone.localdate().replace(day=1)
        metas_existentes = dict(
            MetaVendedor.objects.filter(mes=mes_metas, usuario__tenant_id=tid)
            .values_list('usuario_id', 'valor')
        )
        contexto['mes_metas'] = mes_metas
        contexto['mes_metas_anterior'] = mes_metas.replace(month=mes_metas.month - 1) if mes_metas.month > 1 else mes_metas.replace(year=mes_metas.year - 1, month=12)
        contexto['mes_metas_proximo'] = mes_metas.replace(month=mes_metas.month + 1) if mes_metas.month < 12 else mes_metas.replace(year=mes_metas.year + 1, month=1)
        contexto['vendedores_metas'] = [
            {
                'id': u.id,
                'nome': u.nome,
                'meta': str(metas_existentes.get(u.id, '')).replace('.', ',') if metas_existentes.get(u.id) else '',
            }
            for u in Usuario.objects.filter(tenant_id=tid).order_by('nome')
        ]

    # Captura de lead (apenas admin da clínica — link público de captação)
    contexto['mostrar_captura'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if contexto['mostrar_captura'] and usuario.tenant is not None:
        token = token_captura_do_tenant(usuario.tenant)
        contexto['link_captura'] = request.build_absolute_uri(reverse('captura_lead', args=[token]))
        contexto['origem_captura'] = usuario.tenant.origem_captura
        contexto['captura_ativa'] = usuario.tenant.captura_ativa

    # Discador (apenas admin da clínica — integração com o softphone da operação)
    contexto['mostrar_discador'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if contexto['mostrar_discador'] and usuario.tenant is not None:
        contexto['softphone_schema'] = usuario.tenant.softphone_schema
        contexto['softphone_dominio'] = usuario.tenant.softphone_dominio

    # Etapas do funil (apenas admin da clínica — pipeline próprio do tenant)
    contexto['mostrar_etapas'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if contexto['mostrar_etapas'] and usuario.tenant is not None:
        nicho = usuario.tenant.nicho or NICHO_PADRAO
        garantir_etapas(tid, nicho)
        # Uma query só: contagem de negócios por etapa (sem N+1)
        contagem_por_etapa = dict(
            Negocio.objects.filter(tenant_id=tid)
            .values('stage').annotate(n=models.Count('id')).values_list('stage', 'n')
        )
        contexto['etapas'] = [
            {
                'id': e.id, 'key': e.key, 'nome': e.nome, 'cor': e.cor,
                'ordem': e.ordem, 'sistema': e.sistema,
                'peso': format(e.peso, 'f').rstrip('0').rstrip('.'),
                'qtd_negocios': contagem_por_etapa.get(e.key, 0),
            }
            for e in EtapaFunil.objects.filter(tenant_id=tid)
        ]

    # Equipe + convites (gestores de usuários — oficialato + admin da empresa)
    contexto['mostrar_equipe'] = role in ROLES_GESTORES_USUARIOS and tid is not None
    if role in ROLES_GESTORES_USUARIOS and tid:
        tenant = usuario.tenant
        dono_id = tenant.dono_id if tenant is not None else None
        eh_admin_company = role == ROLE_ADMIN_COMPANY
        contexto['eh_admin_company'] = eh_admin_company
        # Quem pode transferir o dono: o próprio dono (ou admin da clínica enquanto
        # o tenant ainda não tiver dono definido — ex.: tenantes criados antes da migração).
        contexto['eh_dono'] = eh_admin_company and usuario.pode_transferir_dono()
        contexto['membros'] = [
            {
                'id': u.id, 'nome': u.nome, 'email': u.email,
                'celular': u.celular,
                'papel_label': ROLE_LABELS.get(u.role, u.role),
                'pendente': u.pendente_ativacao,
                'pode_reenviar': u.pendente_ativacao and u.reenvios_ativacao < LIMITE_REENVIOS,
                'eh_admin': u.role == ROLE_ADMIN_COMPANY,
                'eh_dono': u.id == dono_id,
                'created_at': u.created_at,
            }
            for u in Usuario.objects.filter(tenant_id=tid).order_by('id')
        ]
        contexto['perfis'] = [
            {'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO
        ]
        contexto['limite_reenvios'] = LIMITE_REENVIOS
        if eh_admin_company and usuario.tenant is not None:
            agora = timezone.now()
            contexto['convites'] = [
                {
                    'id': c.id, 'email': c.email,
                    'papel_label': ROLE_LABELS.get(c.papel, c.papel),
                    'created_at': c.created_at, 'expira_em': c.expira_em,
                    'pendente': c.usado_em is None and c.cancelado_em is None and c.expira_em > agora,
                    'expirado': c.usado_em is None and c.cancelado_em is None and c.expira_em <= agora,
                    'link': request.build_absolute_uri(reverse('convidar', args=[c.token])),
                }
                for c in Convite.objects.filter(tenant_id=tid)
            ]

    return render(request, 'acesso/config.html', contexto)


def convidar(request, token):
    """Página pública de aceite do convite (o link chega por WhatsApp/e-mail)."""
    convite = Convite.objects.filter(token=token).first()
    invalido = {'valido': False, 'motivo': 'Convite não encontrado.'}
    if convite is None:
        return render(request, 'acesso/convidar.html', invalido)
    if convite.cancelado_em is not None:
        return render(request, 'acesso/convidar.html', {'valido': False, 'motivo': 'Este convite foi cancelado pelo admin.'})
    if convite.usado_em is not None:
        return render(request, 'acesso/convidar.html', {'valido': False, 'motivo': 'Este convite já foi utilizado — entre com a sua conta.'})
    if convite.expira_em <= timezone.now():
        return render(request, 'acesso/convidar.html', {'valido': False, 'motivo': 'Este convite expirou — peça um novo ao admin da empresa.'})
    if Usuario.objects.filter(email__iexact=convite.email).exists():
        return render(request, 'acesso/convidar.html', {'valido': False, 'motivo': 'Já existe uma conta com este e-mail — faça login normalmente.'})

    erros = []
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        senha = request.POST.get('senha', '')
        confirma = request.POST.get('confirma', '')
        if not nome:
            erros.append('Informe seu nome.')
        # A2/S8 — politica de senha via AUTH_PASSWORD_VALIDATORS.
        try:
            validate_password(senha, user=Usuario(nome=nome, email=convite.email))
        except DjangoValidationError as e:
            erros.extend(e.messages)
        if senha != confirma:
            erros.append('A confirmação de senha não confere.')
        if not erros:
            try:
                usuario = Usuario.objects.create(
                    nome=nome, email=convite.email, senha=make_password(senha),
                    role=convite.papel, tenant=convite.tenant,
                )
            except IntegrityError:
                erros.append('Já existe uma conta com este e-mail — entre com a sua conta.')
                return render(request, 'acesso/convidar.html', {
                    'valido': True, 'convite': convite, 'erros': erros,
                })
            convite.usado_em = timezone.now()
            convite.usado_por = usuario
            convite.save(update_fields=['usado_em', 'usado_por'])
            request.session.flush()
            iniciar_sessao(
                request, usuario,
                nicho=convite.tenant.nicho or '',
                dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
            )
            return redirect('dashboard:index')

    return render(request, 'acesso/convidar.html', {
        'valido': True, 'convite': convite, 'erros': erros,
    })


def ativar_conta(request, token):
    """Página pública de ativação: o usuário define a senha e ativa a conta.

    Link único (token de 256 bits) válido por 72h — PRD-USUARIOS-SEM-SENHA.
    Estados tratados: token inválido, expirado, já utilizado e sucesso.
    """
    usuario = Usuario.objects.filter(token_ativacao=token).first()
    invalido = None
    if usuario is None:
        invalido = 'Link de ativação inválido. Peça um novo link a um gestor de usuários.'
    elif not usuario.pendente_ativacao:
        invalido = 'Sua conta já foi ativada — faça login normalmente.'
    elif usuario.ativacao_expira_em is not None and usuario.ativacao_expira_em <= timezone.now():
        invalido = 'Este link expirou (válido por 72 horas). Peça um novo link a um gestor de usuários.'

    if invalido:
        return render(request, 'acesso/ativar.html', {'valido': False, 'motivo': invalido})

    erros = []
    if request.method == 'POST':
        senha = request.POST.get('senha', '')
        confirma = request.POST.get('confirma', '')
        # A2/S8 — politica de senha via AUTH_PASSWORD_VALIDATORS.
        try:
            validate_password(senha, user=usuario)
        except DjangoValidationError as e:
            erros.extend(e.messages)
        if senha != confirma:
            erros.append('A confirmação de senha não confere.')
        if not erros:
            ativar_senha(usuario, senha)
            # Login automático (mesmo padrão do convite).
            request.session.flush()
            iniciar_sessao(
                request, usuario,
                nicho=usuario.tenant.nicho if usuario.tenant else '',
                dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
            )
            request.session['origem'] = 'ativacao'
            return redirect('dashboard:index')

    return render(request, 'acesso/ativar.html', {
        'valido': True,
        'erros': erros,
        'nome': usuario.nome,
        'email': usuario.email,
    })


@web_login_required
def alternar_tema(request):
    """Troca o tema (claro/escuro) da sessão e volta para a página de origem."""
    if request.method == 'POST':
        tema = request.POST.get('tema', '')
        if tema in ('escuro', 'claro'):
            request.session['tema'] = tema
    voltar = request.POST.get('voltar') or request.META.get('HTTP_REFERER') or '/dashboard/'
    if url_has_allowed_host_and_scheme(voltar, allowed_hosts={request.get_host()}, require_https=False):
        return redirect(voltar)
    return redirect('dashboard:index')
