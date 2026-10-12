"""Views de configuracao: config (God Function decomposta) e convite/ativacao."""

import logging
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, models
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from acesso.ativacao import (
    LIMITE_REENVIOS,
    ativar_senha,
    criar_usuario_pendente,
    enviar_email_ativacao,
    reenviar_ativacao,
)
from acesso.context_processors import ROLE_LABELS
from acesso.decorators import web_login_required
from acesso.models import (
    ROLE_ADMIN_COMPANY,
    ROLES_ATRIB_CRIACAO,
    ROLES_DE_TENANT,
    ROLES_GESTORES_USUARIOS,
    Convite,
    MetaVendedor,
    Usuario,
    token_captura_do_tenant,
)
from acesso.session import iniciar_sessao
from contatos.models import Negocio
from core.dominio import NICHO_PADRAO
from core.utils import parse_brl
from recepcao.models import EtapaFunil, garantir_etapas

from .helpers import (
    chave_etapa,
    sessoes_do_usuario,
    validar_email,
)

logger = logging.getLogger(__name__)


def _processar_perfil(usuario, request, erros, msgs, sessao):
    """Acao 'perfil': atualiza nome e email."""
    nome = request.POST.get('nome', '').strip()
    email = validar_email(request.POST.get('email', ''), erros)
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


def _processar_senha(usuario, request, erros, msgs):
    """Acao 'senha': altera a senha do usuario."""
    atual = request.POST.get('senha_atual', '')
    nova = request.POST.get('nova_senha', '')
    confirma = request.POST.get('confirma_senha', '')
    if not check_password(atual, usuario.senha):
        erros.append('A senha atual está incorreta.')
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


def _processar_sessao(request, msgs):
    """Acao 'sessao': encerra uma sessao ativa."""
    chave = request.POST.get('sessao_key', '')
    if chave and chave != request.session.session_key:
        Session.objects.filter(session_key=chave).delete()
        msgs.append('Sessão encerrada.')


def _processar_meta(usuario, request, erros, msgs, role, tid):
    """Acao 'meta': atualiza meta mensal de faturamento."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    raw = (request.POST.get('meta_mensal', '') or '').strip()
    meta = parse_brl(raw)
    if meta < 0:
        erros.append('Informe um valor de meta válido (ex.: 50.000,00).')
    else:
        tenant = usuario.tenant
        tenant.meta_mensal = meta if meta > 0 else None
        tenant.save(update_fields=['meta_mensal'])
        msgs.append('Meta de faturamento atualizada.')


def _processar_metas_vendedores(usuario, request, erros, msgs, role, tid):
    """Acao 'metas_vendedores': salva metas individuais por vendedor."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
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


def _processar_equipe(usuario, request, erros, msgs, role, tid):
    """Acao 'equipe': cria convite para novo membro."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    email = validar_email(request.POST.get('email', ''), erros)
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


def _processar_criar_usuario(usuario, request, erros, msgs, role, tid):
    """Acao 'criar_usuario': cria usuario com link de ativacao."""
    if role not in ROLES_GESTORES_USUARIOS or not tid:
        return
    nome = (request.POST.get('nome', '') or '').strip()
    email = validar_email(request.POST.get('email', ''), erros)
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
                return link
    return None


def _processar_reenviar_ativacao(request, erros, msgs, role, tid):
    """Acao 'reenviar_ativacao': reenvia link de ativacao."""
    if role not in ROLES_GESTORES_USUARIOS or not tid:
        return None
    alvo_id = request.POST.get('usuario_id', '')
    if not alvo_id.isdigit():
        erros.append('Usuário inválido.')
        return None
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
            return link
    return None


def _processar_convite_cancelar(request, msgs, role, tid):
    """Acao 'convite_cancelar': cancela um convite pendente."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    convite_id = request.POST.get('convite_id', '')
    if convite_id.isdigit():
        convite = Convite.objects.filter(
            tenant_id=tid, pk=convite_id, cancelado_em__isnull=True
        ).first()
        if convite and convite.usado_em is None:
            convite.cancelado_em = timezone.now()
            convite.save(update_fields=['cancelado_em'])
            msgs.append('Convite cancelado.')


def _ler_dados_etapa(request, erros):
    """Lê e valida nome/cor/peso/ordem do formulário de etapa."""
    nome = (request.POST.get('nome', '') or '').strip()
    cor = (request.POST.get('cor', '') or '').strip()
    cor = cor if re.fullmatch(r'#[0-9a-fA-F]{3,8}', cor) else '#94a3b8'
    peso = None
    peso_raw = (request.POST.get('peso', '') or '').strip()
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
    return nome, cor, peso, ordem


def _etapa_criar(nome, cor, peso, ordem, msgs, tid):
    """Cria uma etapa nova no funil do tenant."""
    etapa = EtapaFunil.objects.create(
        tenant_id=tid, key=chave_etapa(tid, nome), nome=nome,
        cor=cor, ordem=ordem, peso=peso if peso is not None else Decimal('0.500'),
    )
    msgs.append(f'Etapa "{etapa.nome}" adicionada ao funil.')


def _etapa_editar(request, nome, cor, peso, ordem, erros, msgs, tid):
    """Edita uma etapa existente do funil do tenant."""
    etapa = EtapaFunil.objects.filter(
        tenant_id=tid, pk=request.POST.get('etapa_id', '')
    ).first()
    if etapa is None:
        erros.append('Etapa não encontrada.')
        return
    etapa.nome, etapa.cor, etapa.ordem = nome, cor, ordem
    campos = ['nome', 'cor', 'ordem']
    if peso is not None:
        etapa.peso = peso
        campos.append('peso')
    etapa.save(update_fields=campos)
    msgs.append(f'Etapa "{etapa.nome}" atualizada.')


def _etapa_excluir(request, erros, msgs, tid):
    """Exclui uma etapa (regra: sistema ou com negócios não exclui)."""
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
        etapa.delete()
        msgs.append(f'Etapa "{etapa.nome}" excluída do funil.')


def _processar_etapa(request, erros, msgs, role, tid, acao):
    """Acoes 'etapa_nova', 'etapa_editar', 'etapa_excluir' (uma por helper)."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    if acao == 'etapa_excluir':
        _etapa_excluir(request, erros, msgs, tid)
        return
    nome, cor, peso, ordem = _ler_dados_etapa(request, erros)
    if erros:
        return
    if acao == 'etapa_nova':
        _etapa_criar(nome, cor, peso, ordem, msgs, tid)
    elif acao == 'etapa_editar':
        _etapa_editar(request, nome, cor, peso, ordem, erros, msgs, tid)


def _processar_captura(usuario, request, msgs, role, tid, acao):
    """Acoes 'captura_salvar', 'captura_gerar'."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    tenant = usuario.tenant
    if acao == 'captura_salvar':
        origem = (request.POST.get('origem_captura', '') or '').strip()
        if origem:
            tenant.origem_captura = origem[:40]
        tenant.captura_ativa = request.POST.get('captura_ativa') == 'on'
        tenant.save(update_fields=['origem_captura', 'captura_ativa'])
        msgs.append('Captura de lead atualizada.')
    elif acao == 'captura_gerar':
        tenant.token_captura = secrets.token_urlsafe(32)
        tenant.save(update_fields=['token_captura'])
        msgs.append('Novo link de captura gerado — o link antigo deixou de funcionar.')


def _processar_softphone(usuario, request, erros, msgs, role, tid):
    """Acao 'softphone': configura discador."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
    tenant = usuario.tenant
    schema = request.POST.get('softphone_schema', 'sip')
    if schema not in ('sip', 'tel'):
        erros.append('Esquema de softphone inválido.')
    else:
        tenant.softphone_schema = schema
        tenant.softphone_dominio = (request.POST.get('softphone_dominio', '') or '').strip()[:160]
        tenant.save(update_fields=['softphone_schema', 'softphone_dominio'])
        msgs.append('Discador atualizado — a chamada agora usa a configuração do softphone da empresa.')


def _processar_transferir_dono(usuario, request, erros, msgs, role, tid):
    """Acao 'transferir_dono': transfere propriedade do tenant."""
    if role != ROLE_ADMIN_COMPANY or not tid:
        return
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


def _eh_admin_com_tenant(role, tid):
    """Papel admin_company com tenant definido (gargalo comum das seções)."""
    return role == ROLE_ADMIN_COMPANY and tid is not None


def _ctx_novo_convite(contexto, request, role, tid):
    """Seção: destaque de convite recém-criado (via ?convite=ID)."""
    convite_id = request.GET.get('convite', '')
    novo_convite = None
    if convite_id.isdigit() and _eh_admin_com_tenant(role, tid):
        c = Convite.objects.filter(tenant_id=tid, pk=convite_id, cancelado_em__isnull=True).first()
        if c and c.usado_em is None:
            novo_convite = {
                'email': c.email,
                'papel_label': ROLE_LABELS.get(c.papel, c.papel),
                'link': request.build_absolute_uri(reverse('convidar', args=[c.token])),
            }
    contexto['novo_convite'] = novo_convite


def _ctx_meta(contexto, usuario, role, tid):
    """Seção: meta mensal do tenant."""
    contexto['mostrar_meta'] = _eh_admin_com_tenant(role, tid)
    if contexto['mostrar_meta'] and usuario.tenant is not None:
        meta = usuario.tenant.meta_mensal
        contexto['meta_atual'] = (
            str(meta).replace('.', ',') if meta is not None else ''
        )


def _ctx_metas_vendedores(contexto, request, role, tid):
    """Seção: metas por vendedor (navegação por mês + valores atuais)."""
    contexto['mostrar_metas_vendedores'] = _eh_admin_com_tenant(role, tid)
    if not contexto['mostrar_metas_vendedores']:
        return
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


def _ctx_captura(contexto, request, usuario, role, tid):
    """Seção: captura de leads (link público e configurações)."""
    contexto['mostrar_captura'] = _eh_admin_com_tenant(role, tid)
    if contexto['mostrar_captura'] and usuario.tenant is not None:
        token = token_captura_do_tenant(usuario.tenant)
        contexto['link_captura'] = request.build_absolute_uri(reverse('captura_lead', args=[token]))
        contexto['origem_captura'] = usuario.tenant.origem_captura
        contexto['captura_ativa'] = usuario.tenant.captura_ativa


def _ctx_discador(contexto, usuario, role, tid):
    """Seção: integração do softphone/discador."""
    contexto['mostrar_discador'] = _eh_admin_com_tenant(role, tid)
    if contexto['mostrar_discador'] and usuario.tenant is not None:
        contexto['softphone_schema'] = usuario.tenant.softphone_schema
        contexto['softphone_dominio'] = usuario.tenant.softphone_dominio


def _ctx_etapas(contexto, usuario, role, tid):
    """Seção: etapas do funil com contagem de negócios."""
    contexto['mostrar_etapas'] = _eh_admin_com_tenant(role, tid)
    if not (contexto['mostrar_etapas'] and usuario.tenant is not None):
        return
    nicho = usuario.tenant.nicho or NICHO_PADRAO
    garantir_etapas(tid, nicho)
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


def _ctx_equipe(contexto, request, usuario, role, tid):
    """Seção: equipe do tenant (membros, perfis, convites)."""
    contexto['mostrar_equipe'] = role in ROLES_GESTORES_USUARIOS and tid is not None
    if not (role in ROLES_GESTORES_USUARIOS and tid):
        return
    tenant = usuario.tenant
    dono_id = tenant.dono_id if tenant is not None else None
    eh_admin_company = role == ROLE_ADMIN_COMPANY
    contexto['eh_admin_company'] = eh_admin_company
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


def _montar_contexto(usuario, request, role, tid, erros, msgs, contexto_link):
    """Monta o contexto final da pagina de configuracao (uma secao por helper)."""
    contexto = {'erros': erros, 'msgs': msgs, 'usuario': usuario, 'contexto_link': contexto_link}
    contexto['sessoes'] = sessoes_do_usuario(usuario.id, request.session.session_key)
    _ctx_novo_convite(contexto, request, role, tid)
    _ctx_meta(contexto, usuario, role, tid)
    _ctx_metas_vendedores(contexto, request, role, tid)
    _ctx_captura(contexto, request, usuario, role, tid)
    _ctx_discador(contexto, usuario, role, tid)
    _ctx_etapas(contexto, usuario, role, tid)
    _ctx_equipe(contexto, request, usuario, role, tid)
    return contexto


@web_login_required
def config(request):
    """Configuracoes: perfil, senha, aparicao, sessoes ativas, equipe e convites."""
    usuario = Usuario.objects.filter(id=request.session.get('usuario_id')).first()
    if usuario is None:
        return redirect('acesso:login')
    sessao = request.session.get('usuario', {})
    role = sessao.get('role')
    tid = sessao.get('tenant_id')

    erros, msgs = [], []
    contexto_link = None
    acao = request.POST.get('acao', '') if request.method == 'POST' else ''

    if acao == 'perfil':
        _processar_perfil(usuario, request, erros, msgs, sessao)
    elif acao == 'senha':
        _processar_senha(usuario, request, erros, msgs)
    elif acao == 'sessao':
        _processar_sessao(request, msgs)
    elif acao == 'meta':
        _processar_meta(usuario, request, erros, msgs, role, tid)
    elif acao == 'metas_vendedores':
        _processar_metas_vendedores(usuario, request, erros, msgs, role, tid)
    elif acao == 'equipe':
        resultado = _processar_equipe(usuario, request, erros, msgs, role, tid)
        if resultado:
            return resultado
    elif acao == 'criar_usuario':
        contexto_link = _processar_criar_usuario(usuario, request, erros, msgs, role, tid)
    elif acao == 'reenviar_ativacao':
        contexto_link = _processar_reenviar_ativacao(request, erros, msgs, role, tid)
    elif acao == 'convite_cancelar':
        _processar_convite_cancelar(request, msgs, role, tid)
    elif acao in ('etapa_nova', 'etapa_editar', 'etapa_excluir'):
        _processar_etapa(request, erros, msgs, role, tid, acao)
    elif acao in ('captura_salvar', 'captura_gerar'):
        _processar_captura(usuario, request, msgs, role, tid, acao)
    elif acao == 'softphone':
        _processar_softphone(usuario, request, erros, msgs, role, tid)
    elif acao == 'transferir_dono':
        _processar_transferir_dono(usuario, request, erros, msgs, role, tid)

    contexto = _montar_contexto(usuario, request, role, tid, erros, msgs, contexto_link)
    return render(request, 'acesso/config.html', contexto)


def convidar(request, token):
    """Pagina publica de aceite do convite."""
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
    """Pagina publica de ativacao: o usuario define a senha e ativa a conta."""
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
        try:
            validate_password(senha, user=usuario)
        except DjangoValidationError as e:
            erros.extend(e.messages)
        if senha != confirma:
            erros.append('A confirmação de senha não confere.')
        if not erros:
            ativar_senha(usuario, senha)
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
