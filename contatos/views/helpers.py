"""Helpers compartilhados pelas views de contatos (escopo de tenant, decoracao)."""

from contatos.models import Tag
from contatos.scoring import NIVEIS, completude_do_contato, nivel_do_score
from core.dominio import SEG_FALLBACK, SEGS
from core.utils import brl as _brl, iniciais as _iniciais, tenant_id as _tenant_id

CORES_TAG = ['#74b3c6', '#7fe3c4', '#fbbf24', '#c084fc', '#fb923c', '#60a5fa', '#4ade80', '#f472b6']

# Campos renderizados fora do loop do formulario (secao empresa e tags)
CAMPOS_FORA_DO_LOOP = ['tags', 'nova_tag', 'cnpj', 'razao_social', 'cnae', 'endereco', 'responsavel']


# _brl, _iniciais, _tenant_id → importados de core.utils (re-exportados para backward compat)


def _tags_do_tenant(request):
    """Tags do tenant da sessao; admin_saas (sem tenant) ve todas."""
    tid = _tenant_id(request)
    if tid is None:
        return Tag.objects.all()
    return Tag.objects.filter(tenant_id=tid)


def _membros_do_tenant(request):
    """Membros (vendedores) do tenant da sessão para o select de responsável."""
    tid = _tenant_id(request)
    if tid is None:
        return []
    from acesso.models import ROLES_DE_TENANT, Usuario

    return [
        {'id': u.id, 'nome': u.nome}
        for u in Usuario.objects.filter(tenant_id=tid, role__in=ROLES_DE_TENANT).order_by('nome')
    ]


def _responsavel_do_post(request):
    """Id do responsável (vendedor) do formulário, validado no tenant da sessão."""
    tid = _tenant_id(request)
    raw = request.POST.get('responsavel', '')
    if not raw.isdigit() or tid is None:
        return None
    from acesso.models import Usuario

    return Usuario.objects.filter(tenant_id=tid, pk=raw).values_list('id', flat=True).first()


def _erros_do_form(form):
    return [msg for campo_erros in form.errors.values() for msg in campo_erros]


def _tags_marcadas(form):
    """Ids das tags selecionadas (como strings) para renderizar os checkboxes do formulario."""
    if form.is_bound:
        return [str(i) for i in form.data.getlist('tags')]
    return [str(i) for i in (form.initial.get('tags') or [])]


def _decorar(c, stage_map):
    negocio = getattr(c, 'negocio', None)
    stage = negocio.stage if negocio else ''
    valor = negocio.valor if negocio else 0
    nivel = nivel_do_score(c.lead_score)
    return {
        'id': c.id,
        'nome': c.nome,
        'empresa': c.empresa,
        'tel': c.tel,
        'email': c.email,
        'valor': _brl(valor),
        'seg': SEGS.get(c.seg, SEG_FALLBACK),
        'stage': stage_map.get(stage, {'name': stage, 'color': '#888'}),
        'procedimento': c.procedimento,
        'ultima_consulta': c.ultima_consulta,
        'origem': c.origem,
        'pagamento': c.pagamento,
        'nascimento': c.nascimento,
        'cpf': c.cpf,
        'cidade': c.cidade,
        'bairro': c.bairro,
        'observacoes': c.observacoes,
        'cnpj': c.cnpj,
        'razao_social': c.razao_social,
        'cnae': c.cnae,
        'endereco': c.endereco,
        'responsavel': c.responsavel,
        'cargo': c.cargo,
        'carteira': {'id': c.carteira_id, 'nome': c.carteira.nome} if c.carteira_id else None,
        'score': c.lead_score,
        'score_nivel': nivel,
        'score_label': NIVEIS[nivel]['label'],
        'score_cor': NIVEIS[nivel]['cor'],
        'completude': completude_do_contato(c),
        'tags': [{'id': t.id, 'nome': t.nome, 'cor': t.cor} for t in c.tags.all()],
    }


def _decorar_nota(n):
    autor = n.autor
    return {
        'id': n.id,
        'texto': n.texto,
        'created_at': n.created_at,
        'autor': autor.nome if autor else '—',
        'autor_iniciais': _iniciais(autor.nome if autor else ''),
    }
