"""Motor de automações — dispara regras no-code sobre eventos do sistema.

Uso (a partir das views/API/importador):

    from automacoes.engine import disparar

    disparar('contato_criado', tenant_id=tid, contato=contato, negocio=negocio)
    disparar('negocio_movido', tenant_id=tid, contato=contato, negocio=negocio,
             de_etapa='interessado', para_etapa='orcamento')

Regras:
- Só automações ATIVAS do mesmo tenant são consideradas.
- O gatilho `negocio_movido` pode filtrar por etapa de destino (parametro
  `para_etapa`); vazio = qualquer mudança.
- Cada execução roda as ações em ordem; um erro numa ação não derruba o fluxo
  (fica registrado no log com status 'erro').
- O trigger `negocio_estagnado` não é um evento: é varrido sob demanda por
  `executar_estagnados()` (botão na tela + comando de agendamento).
"""

from datetime import timedelta

from django.utils import timezone

from acesso.models import Usuario
from automacoes.models import Automacao, RegistroExecucao
from contatos.models import Negocio, Nota, Tag
from emails.models import EmailEnviado, ModeloEmail
from emails.servico import EMAIL_VAZIO, enviar_um
from recepcao.models import etapa_map_do_tenant
from tarefas.models import PRIORIDADES, Tarefa
import smtplib
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import Error as DBError

ETAPAS_ENCERRADAS = ('fechado', 'perdido')


def _render(texto, contato, negocio, auto):
    """Substitui {{placeholders}} pelos dados do contato (e do negocio principal).

    Mesmos placeholders do e-mail marketing ({{nome}}, {{empresa}}, {{procedimento}},
    {{valor}}, {{telefone}}, {{email}}) + {{etapa}} (rótulo do pipeline do tenant)
    e {{origem}}.
    """
    if contato is None or not texto:
        return texto
    principal = negocio or (contato.negocios.filter(principal=True).first() or contato.negocios.first())
    etapa = ''
    if principal is not None:
        etapa = etapa_map_do_tenant(auto.tenant_id).get(principal.stage, {}).get('name', principal.stage)
    valor = ''
    if principal is not None and principal.valor:
        valor = f'R$ {float(principal.valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    valores = {
        'nome': contato.nome or '',
        'empresa': contato.empresa or '',
        'procedimento': contato.procedimento or '',
        'valor': valor,
        'telefone': contato.tel or '',
        'email': contato.email or '',
        'etapa': etapa,
        'origem': contato.origem or '',
    }
    for chave, v in valores.items():
        texto = texto.replace('{{' + chave + '}}', str(v))
    return texto


def _casa_trigger(auto, de_etapa=None, para_etapa=None):
    """Filtros do gatilho (hoje só o `negocio_movido` filtra por etapa de destino)."""
    if auto.trigger != 'negocio_movido':
        return True
    alvo = ((auto.parametros or {}).get('para_etapa') or '').strip()
    if not alvo:
        return True
    return alvo == para_etapa


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------


def _acao_tarefa(passo, auto, contato, negocio):
    p = passo.parametros or {}
    titulo = _render((p.get('titulo') or '').strip(), contato, negocio, auto)
    if not titulo:
        titulo = f'Follow-up: {contato.nome if contato else "contato"}'
    vencimento = None
    dias = p.get('vencimento_dias')
    if dias:
        try:
            vencimento = timezone.localdate() + timedelta(days=int(dias))
        except (TypeError, ValueError):
            vencimento = None
    responsavel_id = p.get('responsavel_id')
    if responsavel_id and not Usuario.objects.filter(tenant_id=auto.tenant_id, pk=responsavel_id).exists():
        responsavel_id = None  # responsável de outra clínica via JSON manipulado → descartado
    Tarefa.objects.create(
        tenant_id=auto.tenant_id,
        titulo=titulo,
        contato=contato,
        responsavel_id=responsavel_id,
        prioridade=p.get('prioridade') if p.get('prioridade') in dict(PRIORIDADES) else 'media',
        vencimento=vencimento,
        criado_por_id=auto.criado_por_id,
    )


def _acao_nota(passo, auto, contato, negocio):
    if contato is None:
        return
    texto = _render((passo.parametros or {}).get('texto', ''), contato, negocio, auto)
    if not (texto or '').strip():
        return
    Nota.objects.create(contato=contato, autor_id=auto.criado_por_id, texto=texto)


def _acao_tag(passo, auto, contato, negocio):
    if contato is None:
        return
    nome = ((passo.parametros or {}).get('tag') or '').strip()
    if not nome:
        return
    tag, _ = Tag.objects.get_or_create(
        nome=nome[:40], tenant_id=auto.tenant_id, defaults={'cor': '#74b3c6'}
    )
    contato.tags.add(tag)


def _acao_email(passo, auto, contato, negocio):
    if contato is None:
        return
    if contato.email in EMAIL_VAZIO:
        return  # sem e-mail real → ação não se aplica (não é erro)
    modelo_id = (passo.parametros or {}).get('modelo_id')
    modelo = ModeloEmail.objects.filter(tenant_id=auto.tenant_id, pk=modelo_id).first() if modelo_id else None
    if modelo is None:
        raise ValueError('modelo de e-mail não encontrado no tenant')
    registro = EmailEnviado.objects.create(
        tenant_id=auto.tenant_id,
        contato=contato,
        modelo=modelo,
        assunto=_render(modelo.assunto, contato, negocio, auto),
        corpo=_render(modelo.corpo, contato, negocio, auto),
        destinatario=contato.email,
        status='pendente',
    )
    enviar_um(registro)  # sem SMTP configurado, marca como 'simulado'


_ACOES = {
    'tarefa': _acao_tarefa,
    'nota': _acao_nota,
    'tag': _acao_tag,
    'email': _acao_email,
}


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


def _executar(auto, contato=None, negocio=None, passos=None):
    """Roda as ações de uma automação, registra o log e atualiza os contadores.

    `passos` (lista já carregada) evita re-consultas em loops (ex.: estagnados).
    """
    if passos is None:
        passos = list(auto.passos.all().order_by('ordem', 'id'))
    erros = []
    executadas = 0
    for passo in passos:
        runner = _ACOES.get(passo.acao)
        if runner is None:
            erros.append(f'ação desconhecida: {passo.acao}')
            continue
        try:
            runner(passo, auto, contato, negocio)
            executadas += 1
        except (DBError, DjangoValidationError, smtplib.SMTPException,
                OSError, ValueError, TypeError) as exc:
            erros.append(f'{passo.get_acao_display()}: {exc}')
    auto.total_execucoes += 1
    auto.ultima_execucao = timezone.now()
    auto.save(update_fields=['total_execucoes', 'ultima_execucao'])
    RegistroExecucao.objects.create(
        automacao=auto,
        contato=contato,
        negocio=negocio,
        status='erro' if erros else 'ok',
        mensagem='; '.join(erros) if erros else f'{executadas} ação(ões) executada(s)',
    )


def disparar(evento, *, tenant_id, contato=None, negocio=None, de_etapa=None, para_etapa=None):
    """Dispara as automações ativas do tenant que casam com o evento.

    Chamada nos pontos de evento (formulário web, captura pública, importador,
    kanban e API). Admin_saas (tenant_id None) não tem automações.
    """
    if tenant_id is None:
        return 0
    automacoes = Automacao.objects.filter(tenant_id=tenant_id, ativa=True, trigger=evento)
    disparadas = 0
    for auto in automacoes:
        if not _casa_trigger(auto, de_etapa=de_etapa, para_etapa=para_etapa):
            continue
        _executar(auto, contato=contato, negocio=negocio)
        disparadas += 1
    return disparadas


def executar_estagnados(tenant_id=None):
    """Varre negócios abertos parados e dispara as automações de estagnação.

    Usado pelo botão "Verificar agora" na tela e pelo comando de agendamento
    (`python manage.py verificar_estagnados`). `tenant_id` opcional restringe a
    varredura a uma clínica; sem ele, varre todas.
    """
    automacoes = Automacao.objects.filter(ativa=True, trigger='negocio_estagnado')
    if tenant_id is not None:
        automacoes = automacoes.filter(tenant_id=tenant_id)
    automacoes = automacoes.prefetch_related('passos')
    disparadas = 0
    agora = timezone.now()
    for auto in automacoes:
        p = auto.parametros or {}
        dias = p.get('dias') or 7
        try:
            dias = max(1, min(int(dias), 90))
        except (TypeError, ValueError):
            dias = 7
        limite = agora - timedelta(days=dias)
        negocios = (
            Negocio.objects.filter(tenant_id=auto.tenant_id, updated_at__lt=limite)
            .exclude(stage__in=ETAPAS_ENCERRADAS)
            .select_related('contato')
        )
        etapa = (p.get('etapa') or '').strip()
        if etapa:
            negocios = negocios.filter(stage=etapa)
        passos = list(auto.passos.all())  # prefetch_related já carregou
        for negocio in negocios[:100]:
            _executar(auto, contato=negocio.contato, negocio=negocio, passos=passos)
            disparadas += 1
    return disparadas
