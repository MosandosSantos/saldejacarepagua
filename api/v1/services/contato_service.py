"""Regras de negocio do tema 'contatos'."""
from automacoes.engine import disparar
from contatos.models import Carteira, Contato, criar_negocio, registrar_movimentacao
from contatos.scoring import atualizar_score
from api.v1.repositories.contato_repository import ContatoRepository
from api.v1.schemas.contato import ContatoPayload, StageUpdate
from core.dominio import NICHO_PADRAO
from funil.models import etapa_map_do_tenant

VAZIO = '—'


class ContatoNaoEncontrado(Exception):
    """Erro de dominio: contato inexistente (ou fora do tenant)."""


class StageInvalido(Exception):
    """Erro de dominio: etapa fora do pipeline do tenant."""


class CarteiraInvalida(Exception):
    """Erro de dominio: carteira fora do tenant (ou inexistente)."""


def _validar_stage(stage: str, tenant_id: int | None) -> None:
    """Levanta StageInvalido quando a etapa não existe no pipeline do tenant.

    Com etapas agora deletáveis, a API não pode mais aceitar qualquer string —
    um negócio criado numa etapa inexistente sumiria do funil.
    """
    if stage not in etapa_map_do_tenant(tenant_id, NICHO_PADRAO):
        raise StageInvalido(stage)


def normalizar(dados: dict) -> dict:
    """Aplica os defaults do negocio (campos vazios viram '—')."""
    for campo in ('empresa', 'tel', 'email', 'procedimento', 'ultima_consulta', 'origem', 'pagamento'):
        dados[campo] = (dados.get(campo) or '').strip() or VAZIO
    dados['valor'] = float(dados.get('valor') or 0)
    dados['cargo'] = (dados.get('cargo') or '').strip()
    return dados


def _validar_carteira(carteira_id, tenant_id: int | None) -> int | None:
    """Confirma que a carteira pertence ao tenant; devolve o id (ou None).

    Levanta CarteiraInvalida quando o id informado não existe no escopo — um
    POST manipulado não pode associar um contato a uma carteira de outra empresa.
    """
    if carteira_id is None:
        return None
    qs = Carteira.objects.filter(pk=carteira_id)
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)
    if not qs.exists():
        raise CarteiraInvalida(carteira_id)
    return carteira_id


class ContatoService:
    """Orquestra as operacoes de contato, sem conhecer HTTP nem o ORM diretamente.

    `tenant_id` vem do token do usuario (escopo): operacional/admin_company so
    enxergam os dados do proprio tenant; admin_saas (None) enxerga tudo.
    """

    def __init__(self, repository: ContatoRepository):
        self._repository = repository

    def listar(self, tenant_id: int | None = None) -> list[Contato]:
        return self._repository.list_all(tenant_id=tenant_id)

    def obter(self, contato_id: int, tenant_id: int | None = None) -> Contato:
        contato = self._repository.get(contato_id, tenant_id=tenant_id)
        if contato is None:
            raise ContatoNaoEncontrado()
        return contato

    def _negocio_do(self, contato: Contato, tenant_id: int | None):
        """Negócio do contato; cria um padrão quando o contato ainda não tem."""
        negocio = getattr(contato, 'negocio', None)
        if negocio is None:
            negocio = criar_negocio(contato, tenant_id=tenant_id)
        return negocio

    def criar(self, payload: ContatoPayload, tenant_id: int | None = None) -> Contato:
        dados = normalizar(payload.model_dump())
        stage = dados.pop('stage', 'interessado')
        _validar_stage(stage, tenant_id)
        valor = dados.pop('valor', 0)
        dados['carteira_id'] = _validar_carteira(dados.get('carteira_id'), tenant_id)
        dados['tenant_id'] = tenant_id
        contato = self._repository.create(dados)
        negocio = criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant_id)
        atualizar_score(contato)
        disparar('contato_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        disparar('negocio_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        if stage == 'fechado':
            from emails.servico import marcar_conversoes

            marcar_conversoes(contato)
        return contato

    def atualizar(self, contato_id: int, payload: ContatoPayload, tenant_id: int | None = None) -> Contato:
        contato = self.obter(contato_id, tenant_id=tenant_id)
        dados = normalizar(payload.model_dump())
        stage = dados.pop('stage', 'interessado')
        _validar_stage(stage, tenant_id)
        valor = dados.pop('valor', 0)
        dados['carteira_id'] = _validar_carteira(dados.get('carteira_id'), tenant_id)
        atualizado = self._repository.update(contato, dados)
        negocio = self._negocio_do(atualizado, tenant_id)
        stage_antigo = negocio.stage
        if negocio.stage != stage:
            # Sem usuario na API, o autor fica vazio; o histórico continua completo.
            registrar_movimentacao(negocio, negocio.stage, stage, None)
        negocio.stage = stage
        negocio.valor = valor
        negocio.titulo = atualizado.nome
        negocio.save()
        atualizar_score(atualizado)
        if stage_antigo != stage:
            disparar(
                'negocio_movido',
                tenant_id=tenant_id,
                contato=atualizado,
                negocio=negocio,
                de_etapa=stage_antigo,
                para_etapa=stage,
            )
        if stage == 'fechado':
            from emails.servico import marcar_conversoes

            marcar_conversoes(atualizado)
        return atualizado

    def mover_etapa(self, contato_id: int, payload: StageUpdate, tenant_id: int | None = None) -> Contato:
        _validar_stage(payload.stage, tenant_id)
        contato = self.obter(contato_id, tenant_id=tenant_id)
        negocio = self._negocio_do(contato, tenant_id)
        if negocio.stage != payload.stage:
            de_etapa = negocio.stage
            registrar_movimentacao(negocio, negocio.stage, payload.stage, None)
            negocio.stage = payload.stage
            negocio.save(update_fields=['stage', 'updated_at'])
            atualizar_score(contato)
            disparar(
                'negocio_movido',
                tenant_id=tenant_id,
                contato=contato,
                negocio=negocio,
                de_etapa=de_etapa,
                para_etapa=payload.stage,
            )
            if payload.stage == 'fechado':
                from emails.servico import marcar_conversoes

                marcar_conversoes(contato)
        return contato

    def excluir(self, contato_id: int, tenant_id: int | None = None) -> None:
        if not self._repository.delete(contato_id, tenant_id=tenant_id):
            raise ContatoNaoEncontrado()
