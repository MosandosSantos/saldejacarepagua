"""Integracao WhatsApp Web (PRD_comunicacao §7) via PyWhatKit.

- O envio usa o WhatsApp Web do NAVEGADOR PADRAO da maquina: `pywhatkit.sendwhatmsg_instantly`
  abre `https://web.whatsapp.com/send?phone=...&text=...`, aguarda a pagina carregar e
  pressiona Enter (pyautogui). Por isso a conta precisa estar pareada nesse navegador
  (abrir web.whatsapp.com e escanear o QR code uma unica vez).
- `enviar_lote` respeita 90s entre mensagens (politica do WhatsApp) e roda serializado
  (um lote por vez — PRD §7).
- Sem pywhatkit/internet/navegador disponiveis, as rotinas degradam com
  `configurado=False`/erro amigavel — nunca quebram o request.
"""
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Intervalo minimo entre mensagens (politica WA — PRD §7)
INTERVALO_LOTE = 90

# Tempo (s) que o pywhatkit aguarda a pagina carregar antes de enviar (deve ser > 4)
_WAIT_PAGINA = 20

# Serializa envios: um unico lote por vez (PRD §7)
_LOCK = threading.Lock()

# Cache da disponibilidade do pywhatkit (import dele faz GET de checagem de internet)
_CACHE_DISPONIVEL = {'ts': 0.0, 'ok': False}


def _pywhatkit_disponivel(ttl=60):
    """True quando o pywhatkit importa; com cache curto (import faz GET de internet).

    O `import pywhatkit` roda `core.check_connection()` (GET em google.com) e pode
    falhar offline — tratamos como indisponivel, sem quebrar o request.
    """
    agora = time.monotonic()
    if agora - _CACHE_DISPONIVEL['ts'] < ttl:
        return _CACHE_DISPONIVEL['ok']
    try:
        import pywhatkit  # noqa: F401
        _CACHE_DISPONIVEL.update(ts=agora, ok=True)
        return True
    except Exception:
        logger.warning('pywhatkit indisponivel (pacote ausente ou sem internet)')
        _CACHE_DISPONIVEL.update(ts=agora, ok=False)
        return False


def _limpar_numero(numero):
    """Mantem apenas digitos e garante DDI 55 (aceito pelo WhatsApp)."""
    digitos = ''.join(c for c in str(numero or '') if c.isdigit())
    if not digitos:
        return ''
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


def _enviar_um(numero, texto):
    """Envia uma mensagem via PyWhatKit (navegador padrao, aba do WhatsApp Web).

    O pywhatkit exige o numero com '+' (CountryCodeException caso contrario) e
    preenche o texto via parametro `text` da URL. O log proprio dele (arquivo em
    disco, `pywhatkit_log.txt`) e desligado em favor do nosso `logger`.
    """
    import pywhatkit
    from pywhatkit.core import log as _log_pywhatkit

    _log_pywhatkit.log_message = lambda *_a, **_k: None

    pywhatkit.sendwhatmsg_instantly(
        '+' + numero,
        texto,
        wait_time=_WAIT_PAGINA,
        tab_close=False,  # evita o Ctrl+W+Enter do pywhatkit em aba alheia
    )


def verificar_conexao():
    """Status da conexao WhatsApp: {configurado, conectado, detalhe, erro}.

    O pywhatkit nao expoe o estado da sessao — o pareamento acontece no navegador
    padrao (web.whatsapp.com). `conectado` e informativo: retorna False ate que o
    envio seja validado na pratica, e o detalhe orienta o primeiro pareamento.
    """
    if not _pywhatkit_disponivel():
        return {
            'configurado': False, 'conectado': False,
            'detalhe': 'WhatsApp desativado (pacote pywhatkit ausente ou sem internet)',
            'erro': None,
        }
    return {
        'configurado': True, 'conectado': False,
        'detalhe': 'Abra https://web.whatsapp.com no navegador padrão e escaneie o '
                   'QR code (WhatsApp Web) para parear — o envio usa esse navegador.',
        'erro': None,
    }


def obter_qr_code():
    """Instrucoes de pareamento (o QR e gerado pelo proprio WhatsApp Web).

    Mantem o contrato JSON {logado, qr_base64, erro} — sem imagem, pois o
    pareamento acontece no navegador padrao do operador (nao em perfil headless).
    """
    if not _pywhatkit_disponivel():
        return {
            'logado': False, 'qr_base64': None,
            'erro': 'WhatsApp desativado (pacote pywhatkit ausente ou sem internet)',
        }
    return {
        'logado': False, 'qr_base64': None, 'erro': None,
        'detalhe': 'Abra https://web.whatsapp.com no navegador padrão, no celular vá '
                   'em Ajustes > Aparelhos conectados > Conectar aparelho e escaneie '
                   'o QR code exibido.',
    }


def enviar_lote(envios, intervalo=INTERVALO_LOTE):
    """Envia uma lista de {numero, texto} respeitando o intervalo entre mensagens.

    Retorna (ok, falhas). Levanta RuntimeError quando o pywhatkit nao esta
    disponivel (o chamador trata e marca tudo como falha).
    """
    if not envios:
        return 0, 0
    if not _pywhatkit_disponivel():
        raise RuntimeError(
            'Pacote pywhatkit indisponivel — instale via requirements.txt '
            '(ou use o canal E-mail enquanto isso).'
        )
    with _LOCK:
        ok = 0
        falhas = 0
        total = len(envios)
        for i, envio in enumerate(envios):
            numero = _limpar_numero(envio.get('numero', ''))
            if not numero:
                falhas += 1
                continue
            try:
                _enviar_um(numero, envio.get('texto', ''))
                ok += 1
            except Exception:
                logger.exception('falha no envio WhatsApp para %s', numero)
                falhas += 1
            if i < total - 1:
                time.sleep(intervalo)
        return ok, falhas