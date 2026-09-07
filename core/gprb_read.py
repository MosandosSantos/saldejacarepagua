"""Capturas de valor mais recentes do GPRB (leitura) usadas pelo dashboard
e por relatórios que precisam dos dados oficiais do banco compartilhado.

O modelo local de candidato (`candidatos.models.Candidato`) é o sistema de
preliminares; os dados do banco GPRB são somente leitura para exibição.
"""

from core.gprb import (
    agendamento_lojas,
    anualidade_resumo,
    membros_por_classe,
    membros_por_idade_faixa,
    membros_por_potencia,
    membros_por_rito,
    membros_por_tempo_maconaria,
    novos_membros_ano,
    proximas_sessoes,
    ranking_dados,
    ranking_lojas,
    total_lojas_ativas,
    total_lojas_cadastradas,
    total_membros,
)


def dashboard_capa(tenant_code='GPRB', ano=None):
    """Dados do bloco superior do dashboard: KPIs de membros, lojas,
    sessões e anuidade. Caminhos legíveis, unificados, com lazy seguro.
    """
    return {
        'total_lojas_ativas': total_lojas_ativas(tenant_code),
        'total_lojas_cadastradas': total_lojas_cadastradas(tenant_code),
        'total_membros': total_membros(tenant_code),
        'membros_ano': novos_membros_ano(tenant_code, ano),
        'anuidade': anualidade_resumo(tenant_code),
        'proximas_sessoes': proximas_sessoes(tenant_code),
        'agendamento_lojas': agendamento_lojas(tenant_code),
    }


def ranking_context(tenant_code='GPRB', classe='MX',
                    loja_id=None, prefeitura_id=None,
                    data_inicio=None, data_fim=None):
    """Contexto do ranking de presença: sessões, membros, estatísticas.
    Chama o serviço GPRB com kwargs padrão para o ranking do oficialato.
    """
    return ranking_dados(
        tenant_code=tenant_code,
        classe=classe,
        loja_id=loja_id,
        prefeitura_id=prefeitura_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


def distribuicao_membros(tenant_code='GPRB'):
    """Composição do dashboard: classe, rito, potência, faixa etária.
    Retorna dict de listas de dicts ({label/nome, total}).
    """
    return {
        'classe': membros_por_classe(tenant_code),
        'rito': membros_por_rito(tenant_code),
        'potencia': membros_por_potencia(tenant_code),
        'idade': membros_por_idade_faixa(tenant_code),
        'tempo': membros_por_tempo_maconaria(tenant_code),
    }


def ranking_lojas_context(tenant_code='GPRB', limite=10):
    """Ranking de lojas (exibição, não edição)."""
    return ranking_lojas(tenant_code, limite)
