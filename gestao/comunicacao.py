"""Servico de comunicacao (PRD_comunicacao) — envio por E-mail ou WhatsApp.

Monta destinatarios a partir de Prefeituras/Lojas do banco GPRB:
- **Prefeitura** (ou "Todas") -> contato do **Prefeito** (`prefeitura.email` / `telefone`).
- **Loja** de uma prefeitura -> contato do **Deputado Mestre** da loja
  (`loja."deputadoMestreId"` aponta para um `member` da propria loja).

Aplica placeholders ({{NOME}}, {{EMAIL}}, {{CELULAR}}) e dispara por E-mail
(reusando `emails.servico.enviar_mensagem` — SMTP real ou simulado) ou WhatsApp
(`gestao/whatsapp.py` — PyWhatKit sobre o WhatsApp Web do navegador padrao,
com degradacao graciosa). O envio roda em thread daemon e o snapshot em
`Campanha.destinatarios` garante auditoria do que foi enviado.
"""
import logging
import re
import threading

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone


from emails.servico import enviar_mensagem
from django.db import Error as DBError
from gestao.whatsapp import ErroEnvioWhatsApp, enviar_lote

logger = logging.getLogger(__name__)

# Placeholders suportados no corpo/assunto (PRD §4) — aceitos maiusculos ou minusculos
_PLACEHOLDER_RE = re.compile(r'\{\{(nome|email|celular)\}\}', re.IGNORECASE)

def _aplicar_placeholders(corpo, destinatario):
    """Substitui {{NOME}}, {{EMAIL}} e {{CELULAR}} pelos dados do destinatario."""
    valores = {
        'nome': destinatario.get('nome', ''),
        'email': destinatario.get('email', ''),
        'celular': destinatario.get('zap', '') or destinatario.get('celular', ''),
    }

    def _troca(m):
        chave = m.group(1).lower()
        return str(valores.get(chave, ''))

    return _PLACEHOLDER_RE.sub(_troca, corpo)


def _normalizar_celular(valor):
    """Mantem apenas digitos; garante DDI 55 (usado no WhatsApp)."""
    digitos = re.sub(r'\D', '', str(valor or ''))
    if not digitos:
        return ''
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


# ---------------------------------------------------------------------------
# Consultas ao banco GPRB.
#
# Colunas novas que o operador adiciona no GPRB (schema compartilhado):
#   ALTER TABLE prefeitura ADD COLUMN IF NOT EXISTS email VARCHAR(200);
#   ALTER TABLE loja ADD COLUMN IF NOT EXISTS "deputadoMestreId" UUID REFERENCES member(id);
# Se as colunas ainda nao existirem, as rotinas degradam com erro amigavel.
# ---------------------------------------------------------------------------




def listar_prefeituras():
    """Vales ATIVOS cadastrados (dados locais) para o select do form."""
    from contatos.models import Vale

    return [
        {'id': str(v.pk), 'nome': v.nome}
        for v in Vale.objects.filter(status='ATIVA').order_by('nome', 'pk')
    ]


def listar_lojas(prefeitura_id):
    """Lojas ATIVAS do Vale (dados locais) para o select."""
    if not (prefeitura_id or '').strip().isdigit():
        return []
    from contatos.models import Loja, Vale

    return [
        {'id': str(l.pk), 'nome': l.nome}
        for l in Loja.objects.filter(tenant_id__in=Vale.objects.filter(
            pk=int(prefeitura_id), status='ATIVA',
        ).values_list('tenant_id', flat=True)).order_by('nome', 'pk')
    ]


def _destinatarios_prefeitos(canal, prefeitura_id, erros):
    """Prefeitos dos Vales (dados locais): todas — ou apenas o Vale filtrado.

    Campos usados: `vale.prefeito` (nome), `vale.email` e `vale.telefone`
    (WhatsApp). A validação de contato por canal acontece em `montar_destinatarios`.
    """
    from contatos.models import Vale

    vales = Vale.objects.filter(status='ATIVA').order_by('nome', 'pk')
    if (prefeitura_id or '').strip().isdigit():
        vales = vales.filter(pk=int(prefeitura_id))
    destinatarios = []
    for vale in vales:
        dest = {'nome': vale.prefeito or vale.nome or ''}
        if canal == 'EMAIL':
            dest['email'] = vale.email or ''
        else:
            dest['zap'] = _normalizar_celular(vale.telefone)
        destinatarios.append(dest)
    return destinatarios


def _destinatarios_deputados(canal, loja_id, erros):
    """Deputado Estadual da loja LOCAL: `loja.deputado_mestre` -> Membro.

    Retorna dest com nome/email/celular do membro; a validação por canal
    acontece em `montar_destinatarios`.
    """
    from contatos.models import Loja

    if not (loja_id or '').strip().isdigit():
        return []
    loja = Loja.objects.filter(pk=int(loja_id)).select_related('tenant', 'tenant__vales').first()
    if loja is None:
        erros.append('Loja não encontrada.')
        return []
    deu = loja.deputado_mestre
    if deu is None:
        erros.append('Esta loja não tem Deputado Estadual cadastrado.')
        return []
    dest = {'nome': deu.nome or ''}
    if canal == 'EMAIL':
        dest['email'] = deu.email or ''
    else:
        dest['zap'] = _normalizar_celular(deu.celular)
    return [dest]


def _destinatario_individual(request, erros):
    """Destino individual: nome opcional + contato (e-mail ou celular)."""
    nome = request.POST.get('ind_nome', '').strip()
    contato = request.POST.get('ind_contato', '').strip()
    if not contato:
        erros.append('Informe o contato individual (e-mail ou celular).')
        return []
    dest = {'nome': nome}
    if '@' in contato:
        dest['email'] = contato
    else:
        dest['zap'] = _normalizar_celular(contato)
    return [dest] if (dest.get('email') or dest.get('zap')) else []


def _validar_contatos(destinatarios, canal, erros):
    """Valida o contato exigido pelo canal e remove linhas sem ele."""
    validos = []
    for dest in destinatarios:
        if canal == 'EMAIL':
            email = dest.get('email', '')
            try:
                validate_email(email)
            except ValidationError:
                erros.append(
                    f'E-mail inválido ignorado: {email!r}' if email
                    else f'{dest.get("nome", "Contato")}: sem e-mail cadastrado — ignorado.'
                )
                continue
            validos.append({'nome': dest.get('nome', ''), 'email': email})
        else:
            zap = dest.get('zap', '')
            if not zap:
                erros.append(
                    f'{dest.get("nome", "Contato")}: sem telefone cadastrado — ignorado.'
                )
                continue
            validos.append({'nome': dest.get('nome', ''), 'zap': zap})
    return validos


def montar_destinatarios(origem, canal, request, erros):
    """Monta a lista de destinatarios conforme a origem; anexa erros de validacao.

    origem='individual'  -> uma pessoa (ind_nome + ind_contato, e-mail ou celular);
    origem='prefeituras' -> coletivo (dados locais):
      - sem `filtro_prefeitura`          -> Prefeitos de todos os Vales;
      - com `filtro_prefeitura` sem loja -> Prefeito do Vale escolhido;
      - com `filtro_loja`                -> Deputado Estadual da loja
        ("Todas" = deputado de cada loja do Vale; "uma" = só dela).
    """
    if origem == 'individual':
        destinatarios = _destinatario_individual(request, erros)
    elif origem == 'prefeituras':
        prefeitura_id = request.POST.get('filtro_prefeitura', '').strip()
        loja_id = request.POST.get('filtro_loja', '').strip()

        if loja_id and not prefeitura_id:
            erros.append('Escolha o Vale antes de selecionar a loja.')
            return []

        if loja_id and loja_id.isdigit():
            # Uma loja em especial: Deputado Estadual dela.
            destinatarios = _destinatarios_deputados(canal, loja_id, erros)
        elif prefeitura_id:
            # Vale escolhido, "Todas" as lojas: deputado de cada loja do Vale.
            from contatos.models import Loja as _Loja, Vale as _Vale

            lojas_do_vale = _Loja.objects.filter(
                tenant_id__in=_Vale.objects.filter(
                    pk=int(prefeitura_id), status='ATIVA',
                ).values_list('tenant_id', flat=True),
            ).select_related('deputado_mestre').order_by('nome', 'pk')
            destinatarios = []
            for lj in lojas_do_vale:
                if lj.deputado_mestre is None:
                    continue
                dest = {'nome': lj.deputado_mestre.nome or ''}
                if canal == 'EMAIL':
                    dest['email'] = lj.deputado_mestre.email or ''
                else:
                    dest['zap'] = _normalizar_celular(lj.deputado_mestre.celular)
                destinatarios.append(dest)
            if not destinatarios:
                # Sem deputados cadastrados: cai para o Prefeito do Vale.
                destinatarios = _destinatarios_prefeitos(canal, prefeitura_id, erros)
        else:
            destinatarios = _destinatarios_prefeitos(canal, prefeitura_id, erros)
    else:
        erros.append('Escolha um destino: individual (uma pessoa) ou coletivo (Vales/Lojas).')
        return []

    return _validar_contatos(destinatarios, canal, erros)


def _montar_envios(campanha):
    """Aplica placeholders por destinatario; devolve lista de envios por canal."""
    if campanha.canal == 'EMAIL':
        return [
            {
                'email': dest['email'],
                'assunto': _aplicar_placeholders(campanha.assunto, dest),
                'corpo': _aplicar_placeholders(campanha.corpo, dest),
            }
            for dest in campanha.destinatarios
        ]
    return [
        {
            'numero': dest['zap'],
            'texto': _aplicar_placeholders(campanha.corpo, dest),
        }
        for dest in campanha.destinatarios
    ]


def enviar_campanha(campanha):
    """Despacha a campanha para todos os destinatarios e atualiza os totais.

    E-mail: `enviar_mensagem` (SMTP real ou 'simulado' sem SMTP).
    WhatsApp: `gestao/whatsapp.enviar_lote` (intervalo 90s; gracioso se o
    pywhatkit/navegador nao estiverem disponiveis).
    """
    enviados = 0
    falhas = 0

    if campanha.canal == 'EMAIL':
        for envio in _montar_envios(campanha):
            status = enviar_mensagem(envio['assunto'], envio['corpo'], envio['email'])
            if status in ('enviado', 'simulado'):
                enviados += 1
            else:
                falhas += 1
    else:
        envios = _montar_envios(campanha)
        try:
            ok, erro = enviar_lote(envios, intervalo=90)
            enviados, falhas = ok, erro
        except (ErroEnvioWhatsApp, RuntimeError):
            logger.exception('falha ao enviar lote WhatsApp da campanha %s', campanha.id)
            falhas = len(envios)

    campanha.total_enviados = enviados
    campanha.total_falhas = falhas
    campanha.status = 'falha' if falhas else 'enviada'
    campanha.enviado_em = timezone.now()
    campanha.save(update_fields=[
        'total_enviados', 'total_falhas', 'status', 'enviado_em',
    ])
    logger.info(
        'campanha %s (%s) concluida: %d enviados, %d falhas',
        campanha.id, campanha.get_canal_display(), enviados, falhas,
    )
    return campanha.status


def _rodar_envio(campanha_id):
    """Executa o envio em thread; qualquer excecao marca a campanha como falha."""
    from gestao.models import Campanha

    campanha = Campanha.objects.filter(pk=campanha_id).first()
    if campanha is None:
        logger.error('campanha %s nao encontrada para envio', campanha_id)
        return
    if campanha.status != 'rascunho':
        return
    campanha.status = 'enviando'
    campanha.save(update_fields=['status'])
    try:
        enviar_campanha(campanha)
    except (ErroEnvioWhatsApp, RuntimeError, DBError):
        logger.exception('erro inesperado na campanha %s', campanha_id)
        campanha.status = 'falha'
        campanha.save(update_fields=['status'])


def disparar_async(campanha_id):
    """Dispara o envio em thread daemon (nao bloqueia o request)."""
    threading.Thread(
        target=_rodar_envio, args=(campanha_id,), daemon=True,
    ).start()
