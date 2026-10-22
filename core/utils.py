"""Utilitários compartilhados por todos os módulos do projeto.

Centraliza funções auxiliares que estavam duplicadas em dashboard, contatos,
tarefas, funil, relatorios, campanhas, automacoes e orcamento.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.urls import reverse

# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def brl(n):
    """Formata valor em R$ completo: 'R$ 1.500,00'."""
    if n is None:
        return 'R$ 0,00'
    return f'R$ {float(n):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def brl_curto(n):
    """Formata valor em R$ compacto: 'R$ 1,5k'."""
    n = float(n or 0)
    if n >= 1000000:
        return f'R$ {n / 1000000:.1f}M'.replace('.', ',')
    if n >= 1000:
        return f'R$ {n / 1000:.1f}k'.replace('.0', '').replace('.', ',')
    return f'R$ {int(n)}'


def parse_brl(raw):
    """Converte string BRL para Decimal: '1.500,00' → Decimal('1500.00')."""
    if not raw:
        return Decimal(0)
    try:
        raw = str(raw).strip()
        # Remove pontos de milhar e troca vírgula por ponto
        valor = raw.replace('.', '').replace(',', '.')
        return Decimal(valor)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def iniciais(nome):
    """Retorna as iniciais de um nome (ex.: 'João da Silva' → 'JS')."""
    partes = [p for p in (nome or '').split() if p]
    if not partes:
        return '?'
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else '')).upper()


# ---------------------------------------------------------------------------
# Tenant / Sessão
# ---------------------------------------------------------------------------

def tenant_id(request):
    """Retorna o tenant efetivo do request."""
    from acesso.tenant_context import resolve_tenant_id

    return resolve_tenant_id(request)


# ---------------------------------------------------------------------------
# Context manager para conexões GPRB
# ---------------------------------------------------------------------------

def base_pixel(request):
    """URL base do pixel de abertura, sem barra final (ex.: http://host/emails/aberto)."""
    fake = '00000000-0000-0000-0000-000000000000'
    return request.build_absolute_uri(reverse('emails:aberto', args=[fake])).replace(fake, '').rstrip('/')


def resposta_csv(nome_arquivo):
    """Resposta CSV com BOM (Excel abre acentos corretamente)."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    resposta.write('\ufeff')
    return resposta


def csv_seguro(valor):
    """Previne injeção de fórmula no Excel (CSV injection).

    Célula iniciando com `=`, `+`, `-` ou `@` vira texto com apóstrofo inicial.
    """
    texto = str(valor or '')
    if texto.startswith(('=', '+', '-', '@')):
        return "'" + texto
    return texto


@contextmanager
def gprb_connection():
    """Context manager que abre e fecha a conexão com o banco GPRB."""
    from core.gprb import connect
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
