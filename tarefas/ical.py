"""Utilitários iCalendar (RFC 5545) para exportação e importação de tarefas.

Formato compatível com Google Calendar, Apple Calendar e Outlook.
Exporta tarefas como VEVENT dentro de um VCALENDAR.
Importa VEVENTs de arquivos .ics e cria Tarefas no banco.
"""

import re
from datetime import datetime, timedelta
from email.utils import formatdate

from django.utils import timezone

# ── Geração de .ics ──────────────────────────────────────────────────────────

def _ical_escape(text):
    """Escapa caracteres especiais para o formato iCalendar."""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def _fold_line(line):
    """Dobra linhas longas (>75 octets) conforme RFC 5545 §3.1."""
    encoded = line.encode('utf-8')
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        cut = 75 if not parts else 74
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode('utf-8'))
        encoded = encoded[cut:]
    if encoded:
        parts.append(encoded.decode('utf-8'))
    return '\r\n '.join(parts)


def _unfold(text):
    """Recolhe linhas dobradas (continuation lines com espaço no início)."""
    return re.sub(r'\r?\n[ \t]', '', text)


def _prioridade_ics(prioridade):
    """Converte prioridade do CRM para iCalendar (1=alta, 5=média, 9=baixa)."""
    mapa = {'alta': 1, 'media': 5, 'baixa': 9}
    return mapa.get(prioridade, 5)


def tarefa_para_vevent(tarefa):
    """Converte uma Tarefa em VEVENT (string iCalendar)."""
    now = timezone.now()
    uid = f'tarefa-{tarefa.id}@gprbr.local'
    dtstamp = formatdate(now.timestamp(), usegmt=True)

    # DTSTART / DTEND
    if tarefa.vencimento and tarefa.hora:
        dtstart = datetime.combine(tarefa.vencimento, tarefa.hora)
        dtstart_ics = dtstart.strftime('%Y%m%dT%H%M%S')
        dtend_ics = (dtstart + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')
    elif tarefa.vencimento:
        dtstart_ics = tarefa.vencimento.strftime('%Y%m%d')
        dtend_ics = (tarefa.vencimento + timedelta(days=1)).strftime('%Y%m%d')
    else:
        dtstart_ics = now.strftime('%Y%m%dT%H%M%S')
        dtend_ics = (now + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')

    # Status iCalendar
    status = 'COMPLETED' if tarefa.concluida else 'NEEDS-ACTION'

    # Descrição (com info extra do CRM)
    desc_parts = []
    if tarefa.descricao:
        desc_parts.append(tarefa.descricao)
    if tarefa.contato:
        desc_parts.append(f'Contato: {tarefa.contato.nome}')
    if tarefa.responsavel:
        desc_parts.append(f'Responsável: {tarefa.responsavel.nome}')
    desc_parts.append(f'Prioridade: {tarefa.prioridade}')
    description = _ical_escape('\\n'.join(desc_parts))

    lines = [
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART:{dtstart_ics}',
        f'DTEND:{dtend_ics}',
        _fold_line(f'SUMMARY:{_ical_escape(tarefa.titulo)}'),
    ]
    if description:
        lines.append(_fold_line(f'DESCRIPTION:{description}'))
    lines.append(f'PRIORITY:{_prioridade_ics(tarefa.prioridade)}')
    lines.append(f'STATUS:{status}')
    lines.append('CATEGORIES:GPRBRCRM,Tarefa')

    # Concluída -> COMPLETED com data
    if tarefa.concluida and tarefa.concluida_em:
        completed = formatdate(tarefa.concluida_em.timestamp(), usegmt=True)
        lines.append(f'COMPLETED:{completed}')

    # Alarme (1 dia antes)
    if not tarefa.concluida:
        lines.extend([
            'BEGIN:VALARM',
            'TRIGGER:-P1D',
            'ACTION:DISPLAY',
            _fold_line(f'DESCRIPTION:Lembrete: {_ical_escape(tarefa.titulo)}'),
            'END:VALARM',
        ])

    lines.append('END:VEVENT')
    return '\r\n'.join(lines)


def evento_para_vevent(evento):
    """Converte um Evento da agenda em VEVENT (string iCalendar)."""
    now = timezone.now()
    uid = f'evento-{evento.id}@gprbr.local'
    dtstamp = formatdate(now.timestamp(), usegmt=True)
    dtstart = timezone.localtime(evento.data_inicio)
    dtend = timezone.localtime(evento.data_fim)

    lines = [
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART:{dtstart.strftime("%Y%m%dT%H%M%S")}',
        f'DTEND:{dtend.strftime("%Y%m%dT%H%M%S")}',
        _fold_line(f'SUMMARY:{_ical_escape(evento.titulo)}'),
    ]
    if evento.descricao:
        lines.append(_fold_line(f'DESCRIPTION:{_ical_escape(evento.descricao)}'))
    lines.append(f'CATEGORIES:{_ical_escape(evento.get_tipo_display())}')
    if getattr(evento, 'loja', None) and evento.loja.nome:
        lines.append(_fold_line(f'LOCATION:{_ical_escape(evento.loja.nome)}'))
    lines.append('END:VEVENT')
    return '\r\n'.join(lines)


def gerar_ics_eventos(eventos, nome_calendar='GPRBRCRM - Agenda'):
    """Gera arquivo .ics completo a partir de um queryset de Eventos."""
    vevents = [evento_para_vevent(e) for e in eventos]
    cal = '\r\n'.join([
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//GPRBRCRM//Agenda v1.0//PT',
        f'X-WR-CALNAME:{nome_calendar}',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        '\r\n'.join(vevents),
        'END:VCALENDAR',
        '',
    ])
    return cal.encode('utf-8')


def gerar_ics(tarefas, nome_calendar='GPRBRCRM - Tarefas'):
    """Gera arquivo .ics completo a partir de um queryset de Tarefas."""
    vevents = [tarefa_para_vevent(t) for t in tarefas]
    formatdate(timezone.now().timestamp(), usegmt=True)

    cal = '\r\n'.join([
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//GPRBRCRM//Tarefas v1.0//PT',
        f'X-WR-CALNAME:{nome_calendar}',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        '\r\n'.join(vevents),
        'END:VCALENDAR',
        '',
    ])
    return cal.encode('utf-8')


# ── Importação de .ics ───────────────────────────────────────────────────────

def _parse_dt(val):
    """Parse de data/hora iCalendar: 20260821 ou 20260821T093000Z."""
    if not val:
        return None, None
    val = val.strip()
    # ALLDAY: YYYYMMDD
    if len(val) == 8:
        try:
            d = datetime.strptime(val, '%Y%m%d').date()
            return d, None
        except ValueError:
            return None, None
    # Com hora: YYYYMMDDTHHMMSS ou com Z
    val = val.replace('Z', '')
    try:
        dt = datetime.strptime(val[:15], '%Y%m%dT%H%M%S')
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt.date(), dt.time()
    except ValueError:
        return None, None


def _parse_ical_text(val):
    """Remove escapes do iCalendar: \\n -> newline, \\; -> ; etc."""
    if not val:
        return ''
    return val.replace('\\n', '\n').replace('\\N', '\n').replace('\\;', ';').replace('\\,', ',').replace('\\\\', '\\')


def parse_ics(content):
    """Parse de conteúdo .ics e retorna lista de dicts com dados das tarefas.

    Aceita strings ou bytes. Cada dict tem:
    - titulo, descricao, vencimento (date), hora (time|None), concluida (bool)
    - prioridade ('baixa'|'media'|'alta')
    """
    if isinstance(content, bytes):
        content = content.decode('utf-8', errors='replace')

    content = _unfold(content)
    eventos = []

    # Separar blocos VEVENT
    blocks = re.split(r'BEGIN:VEVENT', content, flags=re.IGNORECASE)
    for block in blocks[1:]:  # pular antes do primeiro BEGIN
        end = block.find('END:VEVENT')
        if end == -1:
            continue
        block = block[:end]

        # Extrair campos-chave
        def get(name, default=''):
            pattern = rf'(?m)^{re.escape(name)}[^:]*:(.*)$'
            m = re.search(pattern, block, re.IGNORECASE)
            return m.group(1).strip() if m else default

        summary = _parse_ical_text(get('SUMMARY', 'Sem título'))
        description = _parse_ical_text(get('DESCRIPTION', ''))
        dtstart = get('DTSTART')
        status = get('STATUS', 'NEEDS-ACTION').upper()
        priority = get('PRIORITY', '5')
        completed = get('COMPLETED', '')

        # Vencimento
        vencimento, hora = _parse_dt(dtstart)

        # Prioridade
        prio_map = {'1': 'alta', '2': 'alta', '3': 'alta', '4': 'media',
                     '5': 'media', '6': 'media', '7': 'baixa', '8': 'baixa', '9': 'baixa'}
        prioridade = prio_map.get(priority, 'media')

        # Concluída
        concluida = status in ('COMPLETED', 'CANCELLED') or bool(completed)

        eventos.append({
            'titulo': summary,
            'descricao': description,
            'vencimento': vencimento,
            'hora': hora,
            'concluida': concluida,
            'prioridade': prioridade,
        })

    return eventos
