"""Servico compartilhado de criacao/edicao de contato + negocio.

Centraliza a logica que antes estava duplicada em 3 lugares:
- api/v1/services/contato_service.py (API)
- contatos/views/crud.py (formulario web)
- contatos/importador.py (CSV import)
"""
from automacoes.engine import disparar
from contatos.models import criar_negocio, registrar_movimentacao
from contatos.scoring import atualizar_score
from emails.servico import marcar_conversoes


def criar_negocio_para_contato(contato, stage='interessado', valor=0,
                               tenant_id=None, usuario_id=None):
    """Cria negocio, dispara automacoes, atualiza score e registra movimentacao.

    Funcao compartilhada entre API, web e importador para eliminar duplicacao.
    Retorna o negocio criado.
    """
    negocio = criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant_id)
    atualizar_score(contato)
    disparar('contato_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
    disparar('negocio_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
    registrar_movimentacao(negocio, '', stage, usuario_id)
    if tenant_id is not None:
        negocio.responsavel_id = usuario_id
        negocio.save(update_fields=['responsavel'])
    if stage == 'fechado':
        marcar_conversoes(contato)
    return negocio


def mover_negocio_de_etapa(negocio, contato, nova_etapa, usuario_id=None, tenant_id=None):
    """Move negocio para nova etapa, registra movimentacao e dispara automacoes."""
    if negocio.stage == nova_etapa:
        return negocio
    etapa_antiga = negocio.stage
    registrar_movimentacao(negocio, etapa_antiga, nova_etapa, usuario_id)
    negocio.stage = nova_etapa
    negocio.save(update_fields=['stage', 'updated_at'])
    atualizar_score(contato)
    disparar(
        'negocio_movido',
        tenant_id=tenant_id,
        contato=contato,
        negocio=negocio,
        de_etapa=etapa_antiga,
        para_etapa=nova_etapa,
    )
    if nova_etapa == 'fechado':
        marcar_conversoes(contato)
    return negocio


def atualizar_negocio_do_contato(contato, negocio, stage, valor, tenant_id=None,
                                 usuario_id=None, stage_antigo=None):
    """Atualiza negocio existente, dispara automacoes e registra movimentacao.

    Retorna o negocio atualizado.
    """
    eh_novo = stage_antigo is None
    negocio.stage = stage
    negocio.valor = valor
    negocio.titulo = contato.nome
    negocio.save()
    atualizar_score(contato)

    if eh_novo:
        disparar('negocio_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
    elif stage_antigo != stage:
        registrar_movimentacao(negocio, stage_antigo, stage, usuario_id)
        disparar(
            'negocio_movido', tenant_id=tenant_id,
            contato=contato, negocio=negocio,
            de_etapa=stage_antigo, para_etapa=stage,
        )

    if stage == 'fechado':
        marcar_conversoes(contato)
    return negocio
