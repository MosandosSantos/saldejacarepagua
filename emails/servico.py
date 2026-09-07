"""Servico de e-mail marketing — renderizacao de placeholders, envio, campanhas,
reescrita de links (tracking de clique) e conversao de propostas.

Sem SMTP configurado (settings.EMAIL_CONFIGURADO = False), o envio roda em
MODO SIMULACAO: o registro e criado com status "simulado" e o pixel de abertura
continua funcionando — ideal para demonstrar o fluxo sem custo.
"""
import logging
import re
from base64 import b64decode, urlsafe_b64decode, urlsafe_b64encode

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from emails.models import EmailEnviado

logger = logging.getLogger(__name__)

# Pixel 1x1 transparente (GIF) usado no tracking de abertura
GIF_1PX = b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

# Link em href (http/https) — alvo da reescrita para tracking de clique.
# Só href: imagens (src) não contam como clique (o pixel já mede a abertura).
# Só https?:// (sem protocol-relative): o endpoint de clique redireciona apenas
# para http/https — um //host viraria link morto.
_RE_LINK = re.compile(r'href="((?:https?://)[^"]+)"', re.IGNORECASE)

# Placeholders suportados no corpo/assunto dos modelos
_PLACEHOLDERS = ('nome', 'empresa', 'procedimento', 'valor', 'telefone', 'email')

# Valores de e-mail considerados vazios (o modelo usa '—' como placeholder de campo)
EMAIL_VAZIO = ('', '—')


def _encurtar_url(url):
    """Codifica a URL de destino em base64url (seguro para path de URL)."""
    return urlsafe_b64encode(url.encode('utf-8')).decode('ascii').rstrip('=')


def _expandir_url(codigo):
    """Decodifica a URL de destino do tracking de clique."""
    pad = '=' * (-len(codigo) % 4)
    try:
        return urlsafe_b64decode((codigo + pad).encode('ascii')).decode('utf-8')
    except Exception:
        return None


def reescrever_links(corpo, base_url, token):
    """Troca os links do corpo para o endpoint de tracking de clique.

    Cada <a href="https://..."> vira <a href="BASE/emails/clique/<token>/<codigo>/">;
    o endpoint registra o clique e redireciona para a URL original. Links relativos
    (sem http) e o próprio link de abertura ficam intactos.
    """
    def _troca(m):
        url = m.group(1)
        destino = f'{base_url}/clique/{token}/{_encurtar_url(url)}/'
        return f'href="{destino}"'

    return _RE_LINK.sub(_troca, corpo)


def marcar_conversoes(contato):
    """Marca os e-mails do contato como convertidos quando um negocio fecha.

    Chame quando o negocio principal do contato passar para a etapa "fechado":
    todos os envios ainda sem conversao ganham `convertido_em` (a proposta enviada
    por e-mail converteu em venda). S4 do PRD HAZON — 4.3.6.
    """
    agora = timezone.now()
    return contato.emails_enviados.filter(convertido_em__isnull=True).update(convertido_em=agora)


def renderizar(texto, contato):
    """Substitui {{placeholder}} pelos dados do contato (e do negocio principal)."""
    principal = contato.negocios.filter(principal=True).first() or contato.negocios.first()
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
    }
    for chave in _PLACEHOLDERS:
        texto = texto.replace('{{' + chave + '}}', str(valores[chave]))
    return texto


def enviar_mensagem(assunto, corpo, destinatario, anexo=None, anexo_nome='anexo',
                    conteudo_tipo='application/octet-stream'):
    """Envia uma mensagem via SMTP real; sem SMTP configurado, retorna 'simulado'.

    Rotina única de "simulação vs SMTP" do projeto (PRD 4.1): campanhas, envio
    individual, automações e o comando de relatório passam todos por aqui.
    Retorna: 'enviado' | 'simulado' | 'erro'.
    """
    if not settings.EMAIL_CONFIGURADO:
        return 'simulado'
    try:
        msg = EmailMessage(assunto, corpo, settings.DEFAULT_FROM_EMAIL, [destinatario])
        if anexo is not None:
            msg.attach(anexo_nome, anexo, conteudo_tipo)
        msg.send(fail_silently=False)
        return 'enviado'
    except Exception:
        logger.exception('falha ao enviar e-mail para %s', destinatario)
        return 'erro'


def enviar_um(registro):
    """Envia um EmailEnviado via SMTP real; sem SMTP, marca como 'simulado'."""
    registro.status = enviar_mensagem(registro.assunto, registro.corpo, registro.destinatario)
    registro.enviado_em = timezone.now()
    registro.save(update_fields=['status', 'enviado_em'])
    return registro.status


def _anexar_pixel_e_links(registro, base_url):
    """Adiciona o pixel de abertura e reescreve os links para tracking de clique."""
    pixel = (
        f'<img src="{base_url}/{registro.token}/" width="1" height="1" '
        'style="display:none" alt="">'
    )
    registro.corpo = reescrever_links(registro.corpo, base_url, registro.token)
    registro.corpo = registro.corpo + pixel


def registrar_e_enviar(modelo, contato, base_url, campanha=None):
    """Cria um EmailEnviado para o contato (render + pixel/links) e dispara.

    Rotina única de "criar registro + anexar pixel + salvar + enviar" (PRD 4.1),
    usada pela campanha e pelo envio individual. Retorna o registro criado, ou
    None quando o contato não tem e-mail.
    """
    if contato.email in EMAIL_VAZIO:
        return None
    registro = EmailEnviado.objects.create(
        tenant_id=modelo.tenant_id,
        contato=contato,
        modelo=modelo,
        campanha=campanha,
        assunto=renderizar(modelo.assunto, contato),
        corpo=renderizar(modelo.corpo, contato),
        destinatario=contato.email,
        status='pendente',
    )
    _anexar_pixel_e_links(registro, base_url)
    registro.save(update_fields=['corpo'])
    enviar_um(registro)
    return registro


def disparar_campanha(modelo, contatos, base_url, campanha=None):
    """Cria e dispara um EmailEnviado por contato com e-mail (pixel + links rastreados).

    `campanha` (opcional, S4): quando informada, os envios ficam vinculados à
    campanha — o detalhe da campanha mostra os KPIs (enviados/abertos/cliques/convertidos).
    """
    criados = 0
    for contato in contatos:
        if registrar_e_enviar(modelo, contato, base_url, campanha) is not None:
            criados += 1
    return criados
