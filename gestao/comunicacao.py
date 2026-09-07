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

logger = logging.getLogger(__name__)

# Placeholders suportados no corpo/assunto (PRD §4) — aceitos maiusculos ou minusculos
_PLACEHOLDER_RE = re.compile(r'\{\{(nome|email|celular)\}\}', re.IGNORECASE)

# Tenant GPRB (o restante do projeto usa 'GPRB' fixo)
_TENANT_GPRB = 'GPRB'


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

def _erro_gprb(e):
    """Mensagem amigavel conforme o tipo de falha do GPRB."""
    try:
        import psycopg
        if isinstance(e, psycopg.errors.UndefinedColumn):
            return (
                'Banco GPRB sem as colunas novas: adicione `prefeitura.email` e '
                '`loja."deputadoMestreId"` (veja DOCS/PRD_comunicacao.md §3.4).'
            )
    except ImportError:
        pass
    return 'Banco GPRB indisponível no momento — tente novamente em instantes.'


def listar_prefeituras():
    """Prefeituras para o select do formulario; [] se o GPRB estiver fora."""
    from core.gprb import connect
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM tenant WHERE code = %s', (_TENANT_GPRB,))
            tid = cur.fetchone()[0]
            cur.execute(
                'SELECT id, nome FROM prefeitura WHERE "tenantId" = %s ORDER BY nome',
                (tid,),
            )
            return [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        logger.exception('GPRB indisponivel ao listar prefeituras')
        return []


def listar_lojas(prefeitura_id):
    """Lojas de uma prefeitura para o select; [] se o GPRB estiver fora."""
    from core.gprb import connect
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT l.id, COALESCE(l."nomeFantasia", l."lojaMX", \'Loja \' || l.numero::text) '
                'FROM loja l JOIN tenant t ON l."tenantId" = t.id '
                'WHERE t.code = %s AND l."prefeituraId" = %s ORDER BY 2',
                (_TENANT_GPRB, prefeitura_id),
            )
            return [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        logger.exception('GPRB indisponivel ao listar lojas da prefeitura %s', prefeitura_id)
        return []


def _destinatarios_prefeitos(canal, prefeitura_id, erros):
    """Prefeitos: todas as prefeituras (ou uma especifica) do banco GPRB.

    Colunas usadas: `prefeitura.prefeito` (nome), `prefeitura.email` e
    `prefeitura.telefone` (WhatsApp). A validacao de contato por canal acontece
    em `montar_destinatarios`.
    """
    from core.gprb import connect
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM tenant WHERE code = %s', (_TENANT_GPRB,))
            tid = cur.fetchone()[0]
            sql = (
                'SELECT p.id, p.nome, p.prefeito, p.email, p.telefone '
                'FROM prefeitura p WHERE p."tenantId" = %s'
            )
            params = [tid]
            if prefeitura_id:
                sql += ' AND p.id = %s'
                params.append(prefeitura_id)
            sql += ' ORDER BY p.nome'
            cur.execute(sql, params)
            destinatarios = []
            for r in cur.fetchall():
                dest = {'nome': r[2] or r[1] or ''}
                if canal == 'EMAIL':
                    dest['email'] = r[3] or ''
                else:
                    dest['zap'] = _normalizar_celular(r[4])
                destinatarios.append(dest)
            return destinatarios
        finally:
            conn.close()
    except Exception as e:
        logger.exception('GPRB falhou ao buscar prefeitos (prefeitura=%s)', prefeitura_id)
        erros.append(_erro_gprb(e))
        return []


def _destinatarios_deputados(loja_id, erros):
    """Deputado(s) Mestre(s) da loja: `loja."deputadoMestreId"` -> member.

    Retorna dest com nome/email/celular do membro; a validacao por canal
    acontece em `montar_destinatarios`.
    """
    from core.gprb import connect
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT m.id, m."nomeCompleto", m.email, m.celular '
                'FROM loja l '
                'JOIN member m ON m.id = l."deputadoMestreId" '
                'JOIN tenant t ON l."tenantId" = t.id '
                'WHERE l.id = %s AND t.code = %s',
                (loja_id, _TENANT_GPRB),
            )
            rows = cur.fetchall()
            destinatarios = []
            for r in rows:
                dest = {'nome': r[1] or ''}
                if r[2]:
                    dest['email'] = r[2]
                if r[3]:
                    dest['zap'] = _normalizar_celular(r[3])
                destinatarios.append(dest)
            return destinatarios
        finally:
            conn.close()
    except Exception as e:
        logger.exception('GPRB falhou ao buscar deputado mestre da loja %s', loja_id)
        erros.append(_erro_gprb(e))
        return []


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
    origem='prefeituras' -> coletivo:
      - sem `filtro_prefeitura`  -> Prefeitos de todas as prefeituras;
      - com `filtro_prefeitura`  -> Prefeito da prefeitura escolhida;
      - com `filtro_prefeitura` + `filtro_loja` -> Deputado Mestre da loja.
    """
    if origem == 'individual':
        destinatarios = _destinatario_individual(request, erros)
    elif origem == 'prefeituras':
        prefeitura_id = request.POST.get('filtro_prefeitura', '').strip()
        loja_id = request.POST.get('filtro_loja', '').strip()

        if loja_id and not prefeitura_id:
            erros.append('Escolha a prefeitura antes de selecionar a loja.')
            return []

        if loja_id:
            destinatarios = _destinatarios_deputados(loja_id, erros)
        else:
            destinatarios = _destinatarios_prefeitos(canal, prefeitura_id, erros)
    else:
        erros.append('Escolha um destino: individual (uma pessoa) ou coletivo (prefeituras/lojas).')
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
    from gestao.whatsapp import enviar_lote

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
        except Exception:
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
    except Exception:
        logger.exception('erro inesperado na campanha %s', campanha_id)
        campanha.status = 'falha'
        campanha.save(update_fields=['status'])


def disparar_async(campanha_id):
    """Dispara o envio em thread daemon (nao bloqueia o request)."""
    threading.Thread(
        target=_rodar_envio, args=(campanha_id,), daemon=True,
    ).start()
