"""Views web de autenticacao (sessao), configuracao, convites e equipe. O JWT continua exclusivo da API FastAPI."""

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
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from acesso.context_processors import ROLE_LABELS
from acesso.decorators import web_login_required
from acesso.models import (
    ROLE_ADMIN_COMPANY,
    ROLE_OPERACIONAL,
    ROLE_VIEWER,
    ROLES_DE_TENANT,
    Convite,
    MetaVendedor,
    Tenant,
    Usuario,
    token_captura_do_tenant,
)
from acesso.rate_limit import (
    bloqueado as login_bloqueado,
    limpar as login_limpar,
    registrar_falha as login_registrar_falha,
    tentativas_restantes as login_tentativas_restantes,
)
from contatos.models import Negocio
from core.dominio import NICHO_PADRAO, NICHOS, stages_do_nicho
from funil.models import EtapaFunil, adotar_nicho, garantir_etapas


# A4/S8 — hash pre-computado para o caso de usuario inexistente: garante que
# `check_password` rode o PBKDF2 completo mesmo sem usuario, eliminando a
# diferenca de timing que permitia enumerar e-mails validos.
_HASH_DUMMY = make_password('usuario-inexistente-dummy')


def _client_ip(request) -> str:
    """IP do cliente para fins de rate limiting (sem confiar em X-Forwarded-For)."""
    return request.META.get('REMOTE_ADDR', '') or '0.0.0.0'


def login_web(request):
    """POST /login/ — valida email+senha contra Usuario e abre sessao (com tenant)."""
    if request.session.get('usuario_id'):
        return redirect('dashboard:index')

    erro = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        ip = _client_ip(request)

        # Rate limit — bloqueia antes de gastar CPU com PBKDF2.
        if login_bloqueado(ip, email):
            erro = 'Muitas tentativas. Aguarde alguns minutos e tente novamente.'
        elif not email or not senha:
            erro = 'Informe e-mail e senha.'
        else:
            # A4/S8 — roda check_password sempre (hash dummy quando usuario nao existe)
            # para o tempo de resposta nao revelar quais e-mails estao cadastrados.
            usuario = Usuario.objects.filter(email__iexact=email).first()
            senha_ok = check_password(senha, usuario.senha) if usuario else check_password(senha, _HASH_DUMMY)
            if usuario is None or not senha_ok:
                login_registrar_falha(ip, email)
                erro = 'E-mail ou senha inválidos.'
            else:
                login_limpar(ip, email)
                request.session.flush()
                request.session['usuario_id'] = usuario.id
                request.session['usuario'] = {
                    'nome': usuario.nome,
                    'email': usuario.email,
                    'role': usuario.role,
                    'tenant_id': usuario.tenant_id,
                }
                request.session['dispositivo'] = (request.META.get('HTTP_USER_AGENT', '') or '')[:140]
                tenant = usuario.tenant
                request.session['nicho'] = tenant.nicho if tenant else ''
                if usuario.role == ROLE_ADMIN_COMPANY and tenant is not None and not tenant.nicho:
                    return redirect('acesso:onboarding')
                return redirect('dashboard:index')

    return render(request, 'acesso/login.html', {'erro': erro})


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


@web_login_required
def equipe(request):
    """Gestao de equipe — apenas o admin da clinica convida membros do proprio tenant."""
    sessao = request.session.get('usuario', {})
    if sessao.get('role') != ROLE_ADMIN_COMPANY:
        return redirect('dashboard:index')
    tid = sessao.get('tenant_id')
    if tid is None:
        return redirect('dashboard:index')

    erros = []
    sucesso = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        senha = request.POST.get('senha', '')
        papel = request.POST.get('papel', '')
        if not nome:
            erros.append('Informe o nome do membro.')
        if not email:
            erros.append('Informe o e-mail do membro.')
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                erros.append('Informe um e-mail válido.')
            if Usuario.objects.filter(email__iexact=email).exists():
                erros.append(f'Já existe um usuário com o e-mail {email}.')
        if papel not in (ROLE_OPERACIONAL, ROLE_ADMIN_COMPANY, ROLE_VIEWER):
            erros.append('Escolha um papel válido (Operacional, Admin da empresa ou Somente leitura).')
        # A2/S8 — politica de senha (AUTH_PASSWORD_VALIDATORS do settings).
        try:
            validate_password(senha, user=Usuario(nome=nome, email=email))
        except DjangoValidationError as e:
            erros.extend(e.messages)
        if not erros:
            Usuario.objects.create(
                nome=nome, email=email, senha=make_password(senha), role=papel, tenant_id=tid,
            )
            sucesso = f'{nome} foi adicionado(a) à equipe com o papel {"Admin da empresa" if papel == ROLE_ADMIN_COMPANY else "Operacional"}.'

    membros = [
        {
            'id': u.id,
            'nome': u.nome,
            'email': u.email,
            'papel': u.role,
            'papel_label': ROLE_LABELS.get(u.role, u.role),
            'eh_admin': u.role == ROLE_ADMIN_COMPANY,
            'created_at': u.created_at,
        }
        for u in Usuario.objects.filter(tenant_id=tid).order_by('id')
    ]
    return render(request, 'acesso/equipe.html', {
        'membros': membros,
        'erros': erros,
        'sucesso': sucesso,
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
        except Exception:
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
        try:
            meta = Decimal(raw.replace('.', '').replace(',', '.')) if ',' in raw else Decimal(raw or '0')
        except (InvalidOperation, ValueError):
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
            try:
                valor = Decimal(bruto.replace('.', '').replace(',', '.')) if ',' in bruto else Decimal(bruto or '0')
            except (InvalidOperation, ValueError):
                erros.append(f'Meta inválida para o membro — use ex.: 30.000,00.')
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

    elif acao == 'criar_usuario' and role == ROLE_ADMIN_COMPANY and tid:
        nome = (request.POST.get('nome', '') or '').strip()
        email = _validar_email(request.POST.get('email', ''), erros)
        senha = request.POST.get('senha', '')
        papel = request.POST.get('papel', '')
        if not nome:
            erros.append('Informe o nome do usuário.')
        if not senha:
            erros.append('Informe a senha do usuário.')
        else:
            try:
                validate_password(senha)
            except DjangoValidationError as e:
                erros.extend(e.messages)
        if email and Usuario.objects.filter(email__iexact=email).exists():
            erros.append(f'Já existe um usuário com o e-mail {email}.')
        if papel not in ROLES_DE_TENANT:
            erros.append('Escolha um papel válido.')
        if not erros:
            Usuario.objects.create(
                nome=nome,
                email=email,
                senha=make_password(senha),
                role=papel,
                tenant_id=tid,
            )
            msgs.append(f'Usuário "{nome}" criado com sucesso!')

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
        usuario.tenant.token_captura = secrets.token_urlsafe(18)
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
    contexto = {'erros': erros, 'msgs': msgs, 'usuario': usuario}

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

    # Equipe + convites (apenas admin da clínica)
    contexto['mostrar_equipe'] = role == ROLE_ADMIN_COMPANY and tid is not None
    if role == ROLE_ADMIN_COMPANY and tid and usuario.tenant is not None:
        tenant = usuario.tenant
        dono_id = tenant.dono_id
        # Quem pode transferir o dono: o próprio dono (ou admin da clínica enquanto
        # o tenant ainda não tiver dono definido — ex.: tenantes criados antes da migração).
        contexto['eh_dono'] = usuario.pode_transferir_dono()
        contexto['membros'] = [
            {
                'id': u.id, 'nome': u.nome, 'email': u.email,
                'papel_label': ROLE_LABELS.get(u.role, u.role),
                'eh_admin': u.role == ROLE_ADMIN_COMPANY,
                'eh_dono': u.id == dono_id,
                'created_at': u.created_at,
            }
            for u in Usuario.objects.filter(tenant_id=tid).order_by('id')
        ]
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
            request.session['usuario_id'] = usuario.id
            request.session['usuario'] = {
                'nome': usuario.nome, 'email': usuario.email,
                'role': usuario.role, 'tenant_id': usuario.tenant_id,
            }
            request.session['nicho'] = convite.tenant.nicho or ''
            request.session['dispositivo'] = (request.META.get('HTTP_USER_AGENT', '') or '')[:140]
            return redirect('dashboard:index')

    return render(request, 'acesso/convidar.html', {
        'valido': True, 'convite': convite, 'erros': erros,
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
