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
    return 'R$ {:,.2f}'.format(float(n)).replace(',', 'X').replace('.', ',').replace('X', '.')


def brl_curto(n):
    """Formata valor em R$ compacto: 'R$ 1,5k'."""
    n = float(n or 0)
    if n >= 1000000:
        return 'R$ {:.1f}M'.format(n / 1000000).replace('.', ',')
    if n >= 1000:
        return 'R$ {:.1f}k'.format(n / 1000).replace('.0', '').replace('.', ',')
    return 'R$ {}'.format(int(n))


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
