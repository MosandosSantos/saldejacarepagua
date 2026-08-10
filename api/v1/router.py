"""Agregador de rotas da API v1."""
from fastapi import APIRouter, Depends

from api.v1.rate_limit import limitar
from api.v1.routes.auth import router as auth_router
from api.v1.routes.campanhas import router as campanhas_router
from api.v1.routes.carteiras import router as carteiras_router
from api.v1.routes.discador import router as discador_router
from api.v1.routes.contatos import router as contatos_router
from api.v1.routes.tenants import router as tenants_router
from api.v1.routes.usuarios import router as usuarios_router

# Limite global por IP (300 req/min) — so ativo em producao (DEBUG=False).
api_router = APIRouter(
    prefix='/api/v1',
    dependencies=[Depends(limitar(300, 60))],
)

api_router.include_router(auth_router)
api_router.include_router(contatos_router, prefix='/contatos', tags=['contatos'])
api_router.include_router(carteiras_router, prefix='/carteiras', tags=['carteiras'])
api_router.include_router(campanhas_router, prefix='/campanhas', tags=['campanhas'])
api_router.include_router(discador_router, prefix='/discador', tags=['discador'])
api_router.include_router(usuarios_router)
api_router.include_router(tenants_router)
