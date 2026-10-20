"""Conexão ao banco de dados SAL GPRB (PostgreSQL compartilhado).

Fornece funções para consultar membros, lojas e outros dados do sistema
de gestão de lojas maônicas. A conexão é feita via psycopg3 com reuso
por thread (cada handshake TCP custa ~120ms — reutilizar corta ~1,5s do
dashboard, que faz ~15 consultas por render).

Re-exporta tudo dos submódulos para manter backward compatibility:
    from core.gprb import connect, total_membros, ...
"""

# Conexão
from core.gprb.connection import (  # noqa: F401
    _ConnProxy,
    _nova_conexao,
    _tenant_id_por_codigo,
    coluna_existe,
    connect,
)

# Membros / Lojas
from core.gprb.members import (  # noqa: F401
    agendamento_lojas,
    anuidade_ano_referencia,
    anualidade_resumo,
    emails_membros_da_loja,
    irmaos_da_loja,
    membros_por_situacao,
    membros_por_idade_faixa,
    membros_por_mes,
    membros_por_potencia,
    membros_por_rito,
    membros_por_tempo_maconaria,
    novos_membros_ano,
    proximas_sessoes,
    total_lojas_ativas,
    total_lojas_cadastradas,
    total_membros,
)

# Ranking
from core.gprb.ranking import (  # noqa: F401
    _months_between,
    _years_between,
    ranking_dados,
    ranking_lojas,
    ranking_lojas_mx,
)

# Usuários
from core.gprb.users import (  # noqa: F401
    ROLE_LABELS_GPRB,
    STATUS_LABELS_GPRB,
    atualizar_usuario_sistema,
    autenticar_usuario,
    existe_usuario,
    excluir_usuario_sistema,
    label_role_gprb,
    listar_usuarios_sistema,
    obter_usuario_sistema,
    opcoes_lojas_usuario,
    opcoes_perfis_usuario,
    opcoes_prefeituras_usuario,
)

# Dashboard
from core.gprb.dashboard import dashboard_kpis  # noqa: F401
