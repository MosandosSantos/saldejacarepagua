"""Sincronização de EventosAgenda com o Google Calendar (Service Account).

Estratégia: Service Account com delegação de domínio (Workspace) — o
evento é institucional da loja. Config:
- GOOGLE_SERVICE_ACCOUNT_JSON: caminho de arquivo ou JSON inline.
- GOOGLE_WORKSPACE_ADMIN: e-mail admin para .with_subject (opcional).
- Tenant.google_calendar_id: o calendário de destino por tenant.
"""
import json
import logging
import os
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

ESCOPO = 'https://www.googleapis.com/auth/calendar'

_cache = {'chave': None, 'credencial': None}


def _json_do_service_account():
    bruto = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip()
    if not bruto:
        return None
    if bruto.startswith('{'):
        return json.loads(bruto)
    with open(bruto, encoding='utf-8') as f:
        return json.load(f)


def _credencial():
    if not _json_do_service_account():
        return None
    chave = json.dumps(_json_do_service_account(), sort_keys=True)
    if _cache['chave'] != chave:
        from google.oauth2 import service_account

        cred = service_account.Credentials.from_service_account_info(
            _json_do_service_account(), scopes=[ESCOPO],
        )
        admin = os.getenv('GOOGLE_WORKSPACE_ADMIN', '').strip()
        if admin:
            cred = cred.with_subject(admin)
        _cache.update({'chave': chave, 'credencial': cred})
    return _cache['credencial']


def _cliente_do_calendar(calendar_id):
    """Constrói um client de eventos do Google Calendar (injetável em testes)."""
    from googleapiclient.discovery import build

    credencial = _credencial()
    if credencial is None:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON não configurado.')
    return build('calendar', 'v3', credentials=credencial).events()


def _corpo_do_evento(evento):
    return {
        'summary': evento.titulo,
        'location': evento.local or None,
        'description': evento.descricao or None,
        'start': {
            'dateTime': evento.data_hora.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': evento.data_hora.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
    }


def sincronizar_google(evento):
    """Cria/atualiza o evento no Google; retorna o id ou None se indisponível."""
    calendar_id = getattr(evento.tenant, 'google_calendar_id', '') or ''
    if not calendar_id:
        return None
    cliente = _cliente_do_calendar(calendar_id)
    corpo = _corpo_do_evento(evento)
    if evento.google_event_id:
        resposta = cliente.update(
            eventId=evento.google_event_id, calendarId=calendar_id, body=corpo,
        ).execute()
    else:
        resposta = cliente.insert(calendarId=calendar_id, body=corpo).execute()
    evento.google_event_id = resposta.get('id', '')
    evento.save(update_fields=['google_event_id'])
    return evento.google_event_id


def remover_google(evento):
    """Exclui o evento remoto; best-effort (nunca levanta)."""
    calendar_id = getattr(evento.tenant, 'google_calendar_id', '') or ''
    if not calendar_id or not evento.google_event_id:
        return False
    try:
        cliente = _cliente_do_calendar(calendar_id)
        cliente.delete(
            eventId=evento.google_event_id, calendarId=calendar_id,
        ).execute()
        return True
    except Exception:  # noqa: py-rules — contrato 'best-effort': nunca levanta; a falha vai para o log com exc_info
        logger.warning('Falha ao remover evento %s no Google Calendar', evento.id, exc_info=True)
        return False
