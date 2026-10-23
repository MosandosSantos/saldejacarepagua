"""Server-side Cloudflare Turnstile verification."""

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from urllib.error import URLError


logger = logging.getLogger(__name__)
SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
SITEVERIFY_TIMEOUT_SECONDS = 5
MAX_TOKEN_LENGTH = 2048


def verify_turnstile_token(token):
    """Return True only when Cloudflare confirms a configured token."""
    token = (token or '').strip()
    secret = getattr(settings, 'CLOUDFLARE_TURNSTILE_SECRET_KEY', '').strip()

    if (
        not getattr(settings, 'CLOUDFLARE_TURNSTILE_CONFIGURED', False)
        or not secret
        or not token
        or len(token) > MAX_TOKEN_LENGTH
    ):
        return False

    request = Request(
        SITEVERIFY_URL,
        data=urlencode({'secret': secret, 'response': token}).encode('ascii'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )

    try:
        with urlopen(request, timeout=SITEVERIFY_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode('utf-8'))
    except (URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError) as exc:
        logger.warning('Cloudflare Turnstile verification failed: %s', type(exc).__name__)
        return False

    if not (isinstance(result, dict) and result.get('success') is True):
        # Sem isto o login falha com "voce e humano" e nenhum log diz por que.
        # error-codes esperados: timeout-or-duplicate (token expirado/reusado),
        # invalid-input-response, siteverify-key-mismatch, hostname mismatch.
        logger.warning(
            'Cloudflare Turnstile rejected token: codes=%s hostname=%s action=%s',
            result.get('error-codes') if isinstance(result, dict) else 'non-dict',
            result.get('hostname') if isinstance(result, dict) else '-',
            result.get('action') if isinstance(result, dict) else '-',
        )
        return False

    return True
