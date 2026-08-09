"""Endpoints de agendamentos (/api/v1/agendamentos) — isolados por tenant (escopo do token)."""
from fastapi import APIRouter, Depends

from api.v1.deps import get_scope
from api.v1.repositories.agendamento_repository import AgendamentoRepository
from api.v1.schemas.agendamento import AgendamentoOut
from api.v1.services.agendamento_service import AgendamentoService

router = APIRouter()


def get_service() -> AgendamentoService:
    return AgendamentoService(AgendamentoRepository())


@router.get('', response_model=list[AgendamentoOut])
def listar_agendamentos(
    scope: dict = Depends(get_scope),
    service: AgendamentoService = Depends(get_service),
):
    return service.listar(tenant_id=scope['tenant_id'])
