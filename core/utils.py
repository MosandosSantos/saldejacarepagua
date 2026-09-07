"""Utilitários compartilhados por todos os módulos do projeto.

Centraliza funções auxiliares que estavam duplicadas em dashboard, contatos,
tarefas, gestao, funil, relatorios, campanhas, automacoes e orcamento.
"""
from contextlib import contextmanager

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
    from decimal import Decimal, InvalidOperation
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
    """Retorna o tenant_id armazenado na sessão do request."""
    return request.session.get('usuario', {}).get('tenant_id')


# ---------------------------------------------------------------------------
# Context manager para conexões GPRB
# ---------------------------------------------------------------------------

@contextmanager
def gprb_connection():
    """Context manager que abre e fecha a conexão com o banco GPRB."""
    from core.gprb import connect
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
