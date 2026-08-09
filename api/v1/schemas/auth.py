"""Schemas Pydantic do tema 'acesso' — autenticacao, usuarios, tenants."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal['admin_saas', 'admin_company', 'operacional', 'viewer']


class LoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=2)
    email: EmailStr
    senha: str = Field(min_length=8)
    role: Role
    tenant_id: Optional[int] = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    role: str
    tenant_id: Optional[int] = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    usuario: UsuarioOut


class TenantIn(BaseModel):
    nome: str = Field(min_length=2)
    slug: str = Field(min_length=2, pattern=r'^[a-z0-9-]+$')


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    slug: str
    created_at: datetime
