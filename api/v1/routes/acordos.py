"""Endpoints de acordos (/api/v1/acordos) — PRD Sprint 6.

Acordos escopados por tenant; simular aplica as regras de desconto da empresa;
registrar exige papel de edição (viewer recebe 403).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.v1.deps import get_scope, require_edicao
from acordos.models import Acordo, MODALIDADES, STATUS_ACORDO
from acordos.servico import _normalizar_valor, registrar_acordo, simular
from contatos.models import Contato

router = APIRouter()


class SimularIn(BaseModel):
    """Entrada da simulação financeira."""

    contato_id: int
    valor_original: str = Field(min_length=1)


class OpcaoOut(BaseModel):
    """Opção de pagamento da simulação."""

    modalidade: str
    parcelas: int
    percentual: Decimal
    desconto: Decimal
    valor_final: Decimal
    parcela: Decimal
    valor_final_label: str


class AcordoIn(BaseModel):
    """Entrada de registro de acordo."""

    contato_id: int
    valor_original: str = Field(min_length=1)
    modalidade: str
    parcelas: int = Field(ge=1)
    chamada_id: int | None = None
    observacao: str = ''


class AcordoOut(BaseModel):
    """Saída de um acordo."""

    id: int
    contato_id: int
    valor_original: Decimal
    modalidade: str
    parcelas: int
    percentual_desconto: Decimal
    desconto: Decimal
    valor_final: Decimal
    status: str
    tem_pix: bool


class ResultadoIn(BaseModel):
    """Entrada de mudança de estado do acordo (6.4.8)."""

    status: str = Field(min_length=1)


def _acordos_scope(scope):
    qs = Acordo.objects.all()
    if scope['tenant_id'] is not None:
        qs = qs.filter(tenant_id=scope['tenant_id'])
    return qs


@router.get('', response_model=list[AcordoOut])
def listar_acordos(scope: dict = Depends(get_scope)):
    return [
        {
            'id': a.id,
            'contato_id': a.contato_id,
            'valor_original': a.valor_original,
            'modalidade': a.modalidade,
            'parcelas': a.parcelas,
            'percentual_desconto': a.percentual_desconto,
            'desconto': a.desconto,
            'valor_final': a.valor_final,
            'status': a.status,
            'tem_pix': bool(a.pix_payload),
        }
        for a in _acordos_scope(scope)[:200]
    ]


@router.post('/simular', response_model=list[OpcaoOut])
def simular_acordo(payload: SimularIn, scope: dict = Depends(get_scope)):
    contato = _get_contato(scope, payload.contato_id)
    if contato is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='contato nao encontrado')
    try:
        valor = _normalizar_valor(payload.valor_original)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return simular(valor, scope['tenant_id'])


@router.post('', response_model=AcordoOut, status_code=status.HTTP_201_CREATED)
def criar_acordo(
    payload: AcordoIn,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    if payload.modalidade not in dict(MODALIDADES):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='modalidade invalida')
    contato = _get_contato(scope, payload.contato_id)
    if contato is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='contato nao encontrado')
    try:
        valor = _normalizar_valor(payload.valor_original)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    acordo = registrar_acordo(
        contato, valor, payload.modalidade, payload.parcelas, scope['tenant_id'],
        chamada_id=payload.chamada_id, observacao=payload.observacao,
    )
    return {
        'id': acordo.id,
        'contato_id': acordo.contato_id,
        'valor_original': acordo.valor_original,
        'modalidade': acordo.modalidade,
        'parcelas': acordo.parcelas,
        'percentual_desconto': acordo.percentual_desconto,
        'desconto': acordo.desconto,
        'valor_final': acordo.valor_final,
        'status': acordo.status,
        'tem_pix': False,
    }


@router.post('/{acordo_id}/resultado', response_model=AcordoOut)
def resultado_acordo(
    acordo_id: int,
    payload: ResultadoIn,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    acordo = _acordos_scope(scope).filter(pk=acordo_id).first()
    if acordo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='acordo nao encontrado')
    if payload.status not in dict(STATUS_ACORDO):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='status invalido')
    acordo.status = payload.status
    acordo.save(update_fields=['status', 'updated_at'])
    return {
        'id': acordo.id,
        'contato_id': acordo.contato_id,
        'valor_original': acordo.valor_original,
        'modalidade': acordo.modalidade,
        'parcelas': acordo.parcelas,
        'percentual_desconto': acordo.percentual_desconto,
        'desconto': acordo.desconto,
        'valor_final': acordo.valor_final,
        'status': acordo.status,
        'tem_pix': bool(acordo.pix_payload),
    }


def _get_contato(scope, contato_id):
    qs = Contato.objects.filter(pk=contato_id)
    if scope['tenant_id'] is not None:
        qs = qs.filter(tenant_id=scope['tenant_id'])
    return qs.first()
