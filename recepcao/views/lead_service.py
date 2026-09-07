"""Service layer para criacao de leads no funil.

Separa a logica de negocio (validacao, criacao, side-effects) do I/O HTTP.
Otimizado: imports no topo do modulo.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from automacoes.engine import disparar
from contatos.models import Contato, criar_negocio, registrar_movimentacao, so_digitos
from contatos.scoring import atualizar_score
from core.dominio import ORIGENS
from core.utils import parse_brl
from recepcao.models import etapa_map_do_tenant


@dataclass
class LeadData:
    """Dados normalizados de um lead (input do dominio)."""
    nome: str
    tel: str = ''
    email: str = ''
    origem: str = ''
    stage: str = ''
    valor: Decimal = Decimal(0)


@dataclass
class LeadResult:
    """Resultado da criacao de um lead."""
    contato: Contato
    negocio: object  # Negocio


class LeadValidationError(Exception):
    """Erro de validacao nos dados do lead."""

    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__(erros)


class LeadService:
    """Orquestra a criacao de leads, sem conhecer HTTP.

    Responsabilidades (SRP):
      - Validar dados do lead
      - Criar contato + negocio
      - Disparar side-effects (automacoes, score)
    """

    def criar_lead(
        self,
        dados: LeadData,
        tenant_id: int,
        usuario_id: int | None = None,
    ) -> LeadResult:
        """Cria um lead completo: contato pobre + negocio no funil.

        Raises:
            LeadValidationError: se os dados forem invalidos.
        """
        self._validar(dados, tenant_id)

        contato = self._criar_contato(dados, tenant_id)
        negocio = self._criar_negocio(contato, dados, tenant_id, usuario_id)
        self._disparar_side_effects(contato, negocio, tenant_id)

        return LeadResult(contato=contato, negocio=negocio)

    def _validar(self, dados: LeadData, tenant_id: int) -> None:
        """Valida os dados do lead. Levanta LeadValidationError se invalido."""
        erros = []

        if not dados.nome:
            erros.append('Informe o nome do lead.')

        stage_map = etapa_map_do_tenant(tenant_id, None)
        if dados.stage not in stage_map:
            erros.append('Escolha uma etapa valida.')

        if dados.origem and dados.origem not in ORIGENS:
            erros.append('Origem invalida.')

        if dados.valor < 0:
            erros.append('O valor nao pode ser negativo.')

        if dados.tel:
            digitos = so_digitos(dados.tel)
            if Contato.objects.filter(tel_normalizado=digitos).exists():
                erros.append('Ja existe um contato com este telefone.')

        if erros:
            raise LeadValidationError(erros)

    def _criar_contato(self, dados: LeadData, tenant_id: int) -> Contato:
        """Cria o contato 'pobre' no banco."""
        return Contato.objects.create(
            nome=dados.nome,
            tel=dados.tel or '—',
            email=dados.email or '—',
            seg='',
            origem=dados.origem or '—',
            tenant_id=tenant_id,
        )

    def _criar_negocio(self, contato: Contato, dados: LeadData, tenant_id: int, usuario_id: int | None):
        """Cria o negocio associado ao contato."""
        negocio = criar_negocio(
            contato,
            stage=dados.stage,
            valor=dados.valor,
            tenant_id=tenant_id,
        )
        if usuario_id:
            negocio.responsavel_id = usuario_id
            negocio.save(update_fields=['responsavel'])

        registrar_movimentacao(negocio, '', dados.stage, usuario_id)
        return negocio

    def _disparar_side_effects(self, contato: Contato, negocio, tenant_id: int) -> None:
        """Dispara automacoes e atualiza score (side-effects)."""
        disparar('contato_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        disparar('negocio_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        atualizar_score(contato)


def parse_lead_data(post_data: dict) -> LeadData:
    """Converte dados brutos do POST em LeadData (normalizacao).

    Funcao pura: nao acessa banco, nao tem side-effects.
    """
    nome = (post_data.get('nome') or '').strip()
    tel = (post_data.get('tel') or '').strip()
    email = (post_data.get('email') or '').strip().lower()
    origem = (post_data.get('origem') or '').strip()
    stage = post_data.get('stage', '')
    raw_valor = (post_data.get('valor') or '').strip()

    valor = _parse_valor(raw_valor)

    return LeadData(
        nome=nome,
        tel=tel,
        email=email,
        origem=origem,
        stage=stage,
        valor=valor,
    )


def _parse_valor(raw: str) -> Decimal:
    """Converte string BRL para Decimal (funcao pura)."""
    if not raw:
        return Decimal(0)
    try:
        return parse_brl(raw)
    except (InvalidOperation, ValueError):
        return Decimal(0)
