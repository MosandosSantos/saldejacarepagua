"""Check-in do irmão via QRCode (auto-presença na sessão).

Fluxo: o secretário gera o QRCode do evento (`evento_qrcode`) e o expõe na
porta; o irmão escaneia e abre a página pública (`checkin`), que mostra os
dados da sessão e pede número do cadastro + senha. Autenticado (mesma credencial do
login), a presença dele é registrada automaticamente — sem criar sessão de
CRM no aparelho e sem expor a lista de irmãos.

Segurança:
- URL assinada (`TimestampSigner`, salt próprio) amarrada ao evento: forjar
  check-in de outro evento exigiria o `SECRET_KEY`;
- janela de check-in: abre 2h antes do início, fecha 24h após o fim;
- só registra quem é irmão DAQUELA loja (UUID: lista do GPRB; local:
  vínculo Membro↔Loja);
- a view aplica Turnstile + rate limit como o login.
"""
import base64
import io
from datetime import timedelta

import qrcode
from django.core.signing import BadSignature, TimestampSigner
from django.urls import reverse
import psycopg

ASSINANTE_SAL = 'tarefas-checkin-presenca'
JANELA_ABERTURA = timedelta(hours=2)
JANELA_FECHAMENTO = timedelta(hours=24)


def _assinante():
    """Signer dedicado ao check-in (não compartilha salt com outros usos)."""
    return TimestampSigner(salt=ASSINANTE_SAL)


def assinar_evento(evento_id):
    """Token opaco e íntegro identificando o evento do check-in."""
    return _assinante().sign(str(evento_id))


def conferir_token(evento_id, token):
    """True quando o token foi gerado para este evento (assinatura válida)."""
    if not token:
        return False
    try:
        valor = _assinante().unsign(token)
    except BadSignature:
        return False
    return str(valor) == str(evento_id)


def url_checkin(request, evento):
    """URL absoluta da página pública de check-in do evento."""
    caminho = reverse('tarefas:checkin', args=[evento.pk])
    return request.build_absolute_uri(f'{caminho}?t={assinar_evento(evento.pk)}')


def checkin_aberto(evento, agora=None):
    """True dentro da janela de check-in (2h antes → 24h após o fim)."""
    from django.utils import timezone

    agora = agora or timezone.now()
    inicio, fim = evento.data_inicio, evento.data_fim
    if inicio is None or fim is None:
        return False
    padrao = timezone.get_default_timezone()
    if timezone.is_naive(inicio):
        inicio = timezone.make_aware(inicio, padrao)
    if timezone.is_naive(fim):
        fim = timezone.make_aware(fim, padrao)
    if timezone.is_naive(agora):
        agora = timezone.make_aware(agora, padrao)
    return inicio - JANELA_ABERTURA <= agora <= fim + JANELA_FECHAMENTO


def qr_data_uri(url):
    """QRCode da URL como data-URI PNG (pronto para <img> ou impressão)."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def nome_da_loja(evento):
    """Nome de exibição da loja do evento (local ou GPRB)."""
    valor = str(evento.loja_id or '').strip()
    if valor.isdigit():
        from contatos.models import Loja

        loja = Loja.objects.filter(pk=int(valor)).first()
        return loja.nome if loja is not None else '—'
    try:
        from core.gprb.connection import connect
        from core.gprb.connection import resolve_tenant_code
    except ImportError:  # pragma: no cover - sem camada GPRB
        return '—'
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT COALESCE(l."nomeFantasia", l."lojaMX", \'Loja \' || l.numero::text) '
                'FROM loja l JOIN tenant t ON l."tenantId" = t.id '
                'WHERE t.code = %s AND l.id = %s',
                (resolve_tenant_code(None), valor),
            )
            linha = cur.fetchone()
        finally:
            conn.close()
    except psycopg.Error:
        return '—'
    return (linha[0] if linha and linha[0] else '—') or '—'
