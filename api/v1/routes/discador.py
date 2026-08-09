"""Endpoints do discador (/api/v1/discador) — Nation Dialer (PRD Sprint 5).

Filas e scripts escopados por tenant; iniciar/registrar chamada exigem papel de
edição (viewer recebe 403); contatos e filas de outro tenant retornam 404.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.v1.deps import get_scope, require_edicao
from contatos.models import Contato
from discador.models import Chamada, Fila, Script
from discador.softphone import uri_chamada

router = APIRouter()


class FilaIn(BaseModel):
    """Entrada de criação de fila."""

    nome: str = Field(min_length=1, max_length=120)
    descricao: str = ''
    carteira_id: int | None = None
    script_id: int | None = None
    ordem: str = 'score'
    ativa: bool = True


class FilaOut(BaseModel):
    """Saída de uma fila."""

    id: int
    nome: str
    descricao: str = ''
    carteira_id: int | None = None
    script_id: int | None = None
    ordem: str
    ativa: bool
    total_contatos: int = 0


class ContatoFilaOut(BaseModel):
    """Contato da fila com os dados exibidos ao operador (5.1.4)."""

    id: int
    nome: str
    empresa: str
    cargo: str = ''
    tel: str
    lead_score: int
    uri: str = ''


class ChamarIn(BaseModel):
    """Entrada para iniciar uma chamada (5.2.2)."""

    contato_id: int


class ChamarOut(BaseModel):
    """Saída de início de chamada — a URI abre o softphone."""

    chamada_id: int
    uri: str


class ResultadoIn(BaseModel):
    """Entrada de registro do resultado da chamada (5.2.5)."""

    status: str = Field(min_length=1)
    observacao: str = ''
    retorno_em: str = ''


class ResultadoOut(BaseModel):
    """Saída do registro de resultado."""

    chamada_id: int
    status: str
    status_label: str


class ScriptOut(BaseModel):
    """Saída de um script de atendimento (5.3)."""

    id: int
    nome: str
    descricao: str = ''
    conteudo: str
    ativa: bool


def _filas_scope(scope):
    qs = Fila.objects.all()
    if scope['tenant_id'] is not None:
        qs = qs.filter(tenant_id=scope['tenant_id'])
    return qs


def _get_fila(scope, fila_id):
    fila = _filas_scope(scope).filter(pk=fila_id).first()
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='fila nao encontrada')
    return fila


@router.get('/filas', response_model=list[FilaOut])
def listar_filas(scope: dict = Depends(get_scope)):
    itens = []
    for f in _filas_scope(scope):
        itens.append({
            'id': f.id,
            'nome': f.nome,
            'descricao': f.descricao,
            'carteira_id': f.carteira_id,
            'script_id': f.script_id,
            'ordem': f.ordem,
            'ativa': f.ativa,
            'total_contatos': f.contatos().count(),
        })
    return itens


@router.post('/filas', response_model=FilaOut, status_code=status.HTTP_201_CREATED)
def criar_fila(
    payload: FilaIn,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    tid = scope['tenant_id']
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='nome da fila é obrigatório')
    if payload.ordem not in dict(Fila.ORDENS):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='ordem inválida')
    qs = _filas_scope(scope)
    if qs.filter(nome__iexact=nome).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='fila ja existe')
    fila = Fila(
        nome=nome,
        descricao=payload.descricao.strip(),
        ordem=payload.ordem,
        ativa=payload.ativa,
        carteira_id=payload.carteira_id,
        script_id=payload.script_id,
    )
    if tid is not None:
        fila.tenant_id = tid
    fila.save()
    return {
        'id': fila.id,
        'nome': fila.nome,
        'descricao': fila.descricao,
        'carteira_id': fila.carteira_id,
        'script_id': fila.script_id,
        'ordem': fila.ordem,
        'ativa': fila.ativa,
        'total_contatos': fila.contatos().count(),
    }


@router.get('/filas/{fila_id}/contatos', response_model=list[ContatoFilaOut])
def contatos_da_fila(fila_id: int, scope: dict = Depends(get_scope)):
    fila = _get_fila(scope, fila_id)
    itens = []
    for c in fila.contatos()[:200]:
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'empresa': c.empresa,
            'cargo': c.cargo,
            'tel': c.tel,
            'lead_score': c.lead_score,
            'uri': uri_chamada(c, c.tenant),
        })
    return itens


@router.post('/filas/{fila_id}/chamar', response_model=ChamarOut, status_code=status.HTTP_201_CREATED)
def iniciar_chamada(
    fila_id: int,
    payload: ChamarIn,
    scope: dict = Depends(get_scope),
    usuario=Depends(require_edicao),
):
    fila = _get_fila(scope, fila_id)
    contatos = Contato.objects.filter(pk=payload.contato_id)
    if scope['tenant_id'] is not None:
        contatos = contatos.filter(tenant_id=scope['tenant_id'])
    contato = contatos.first()
    if contato is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='contato nao encontrado')
    if not contato.tel_normalizado:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='contato sem telefone valido')
    chamada = Chamada.objects.create(
        fila=fila,
        contato=contato,
        operador_id=usuario.id,
        tenant_id=scope['tenant_id'],
    )
    return {'chamada_id': chamada.id, 'uri': uri_chamada(contato, contato.tenant)}


@router.post('/chamadas/{chamada_id}/resultado', response_model=ResultadoOut)
def registrar_resultado(
    chamada_id: int,
    payload: ResultadoIn,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    qs = Chamada.objects.all()
    if scope['tenant_id'] is not None:
        qs = qs.filter(tenant_id=scope['tenant_id'])
    chamada = qs.filter(pk=chamada_id).first()
    if chamada is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='chamada nao encontrada')
    if payload.status not in dict(Chamada.STATUS):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='status invalido')
    chamada.status = payload.status
    chamada.observacao = payload.observacao.strip()
    if payload.retorno_em:
        try:
            chamada.retorno_em = datetime.fromisoformat(payload.retorno_em.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='retorno_em invalido')
    chamada.save(update_fields=['status', 'observacao', 'retorno_em', 'updated_at'])
    return {
        'chamada_id': chamada.id,
        'status': chamada.status,
        'status_label': chamada.get_status_display(),
    }


@router.get('/scripts', response_model=list[ScriptOut])
def listar_scripts(scope: dict = Depends(get_scope)):
    qs = Script.objects.all()
    if scope['tenant_id'] is not None:
        qs = qs.filter(tenant_id=scope['tenant_id'])
    return [
        {'id': s.id, 'nome': s.nome, 'descricao': s.descricao, 'conteudo': s.conteudo, 'ativa': s.ativa}
        for s in qs
    ]
