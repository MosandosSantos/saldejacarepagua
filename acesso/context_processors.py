"""Context processors da camada web: injetam a navegacao e o usuario da sessao em todos os templates."""

import os

from django.conf import settings
from django.urls import reverse

from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLE_ADM,
    ROLE_DELEGADO,
    ROLE_PRESIDENTE_CORPO,
    ROLE_SECRETARIO,
    ROLE_TESOUREIRO,
    ROLES_ADMINISTRATIVOS,
    ROLES_GESTORES_USUARIOS,
    ROLES_QUE_EDITAM,
    Tenant,
)
from acesso.tenant_context import resolve_tenant_id
from tarefas.models import resumo_tarefas

_ICONE_DASH = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
               'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/>'
               '<rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/>'
               '<rect x="3" y="16" width="7" height="5" rx="1"/></svg>')
_ICONE_FUNIL = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                'stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18l-7 8v6l-4 2v-8z"/></svg>')
_ICONE_CONTATOS = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
                   '<circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>')
_ICONE_CONFIG = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                 'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/>'
                 '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>')
_ICONE_TAREFAS = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                  'stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/>'
                  '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>')
_ICONE_EQUIPE = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                 'stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
                 '<circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>')
_ICONE_CARTEIRA = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>')
_ICONE_FINANCEIRO = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                     'stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/>'
                     '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>')
_ICONE_CAMPANHA = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg>')

# (label, app, rota, icone, match_urls, excluir_urls, [subitens])
# - match_urls  (None = destaque por app): urls que destacam este item
# - excluir_urls: urls do MESMO app que NÃO devem destacar (ex.: páginas de
#   carteiras ficam com 'Carteiras' ativo, não 'Contatos')
_ROTAS = [
    ('Dashboard', 'dashboard', 'dashboard:index', _ICONE_DASH, None, set()),
    ('Vale', 'contatos', 'contatos:prefeituras', _ICONE_CARTEIRA, {'prefeituras'}, set()),
    ('Lojas', 'contatos', 'contatos:lojas', _ICONE_CARTEIRA, {'lojas', 'loja_detalhe'}, set()),
    ('Membros', 'contatos', 'contatos:lista', _ICONE_CONTATOS, None, {'carteiras', 'carteira_detalhe'}),
    ('Financeiro', 'contatos', 'contatos:financeiro', _ICONE_FINANCEIRO, {'financeiro'}, set()),
    ('Agenda', 'tarefas', 'tarefas:ranking', _ICONE_TAREFAS, None, set()),
    ('Comunicações', 'gestao', 'comunicacoes', _ICONE_CAMPANHA, {'comunicacoes'}, set()),
    ('Iniciação', 'recepcao', 'recepcao:kanban', _ICONE_FUNIL, None, set()),
    # Equipe/Usuários: gestão — oficialato (ADM, Delegado, ...) + admin da plataforma.
    ('Usuários', 'acesso', 'equipe', _ICONE_EQUIPE, {'equipe', 'equipe_novo'}, set(), None, ROLES_GESTORES_USUARIOS),
]

ROLE_LABELS = {
    'admin_saas': 'Admin SaaS',
    'viewer': 'Somente leitura',
    ROLE_ADM: 'Administrador',
    ROLE_TESOUREIRO: 'Tesoureiro',
    ROLE_SECRETARIO: 'Secretário',
    ROLE_DELEGADO: 'Delegado',
    ROLE_PRESIDENTE_CORPO: 'Presidente de Corpo',
    None: '',
}


def _nav_itens(url_name='', app_atual='', tarefas_atrasadas=0, role=None):
    """Monta a navegação com o item ativo já calculado (evita depender só do app).

    `role` filtra itens restritos (ex.: Equipe só para admin da empresa).
    """
    itens = []
    for item_tupla in _ROTAS:
        label, app, rota, icone, match_urls, excluir_urls = item_tupla[:6]
        subs = item_tupla[6] if len(item_tupla) > 6 else None
        papeis = item_tupla[7] if len(item_tupla) > 7 else None
        if papeis is not None and role not in papeis:
            continue
        sub_itens = None
        ativa = False
        if subs:
            sub_itens = []
            for sub in subs:
                sub_ativa = app_atual == sub['app'] and url_name in sub['match']
                ativa = ativa or sub_ativa
                sub_itens.append({
                    'label': sub['label'],
                    'url': reverse(sub['rota']),
                    'icone': sub['icone'],
                    'ativa': sub_ativa,
                })
        elif match_urls:
            ativa = url_name in match_urls
        else:
            ativa = app_atual == app and url_name not in excluir_urls
        item = {'label': label, 'app': app, 'url': reverse(rota), 'icone': icone,
                'ativa': ativa, 'subitens': sub_itens}
        if app == 'tarefas' and tarefas_atrasadas:
            item['badge'] = tarefas_atrasadas
        itens.append(item)
    return itens


def _css_versao():
    """Versão do CSS compilado (mtime) — busta o cache do navegador quando o
    Tailwind regenera o arquivo durante o desenvolvimento."""
    caminho = os.path.join(settings.BASE_DIR, 'theme', 'static', 'css', 'dist', 'styles.css')
    try:
        return str(int(os.path.getmtime(caminho)))
    except OSError:
        return '1'


def web_sessao(request):
    """Disponibiliza NAV_ITENS, web_usuario, web_logado e o resumo de tarefas pendentes."""
    usuario = request.session.get('usuario', {})
    role = usuario.get('role') if isinstance(usuario, dict) else None
    nome = usuario.get('nome', '') if isinstance(usuario, dict) else ''
    partes = [p for p in nome.split() if p]
    iniciais = (partes[0][0] + (partes[-1][0] if len(partes) > 1 else '')) if partes else 'A'

    # Tarefas pendentes (badge no header) — sem query para páginas públicas/API
    tenant_id = resolve_tenant_id(request) if request.session.get('usuario_id') else None
    resumo = resumo_tarefas(tenant_id) if request.session.get('usuario_id') else {
        'atrasadas': 0, 'hoje': 0, 'abertas': 0,
    }
    resolver = getattr(request, 'resolver_match', None)
    url_name = resolver.url_name if resolver else ''
    app_atual = resolver.app_name if resolver else ''
    contexto = {
        'APP_BRAND_NAME': settings.APP_BRAND_NAME,
        'css_versao': _css_versao(),
        'NAV_ITENS': _nav_itens(
            url_name, app_atual, tarefas_atrasadas=resumo['atrasadas'], role=role
        ),
        'web_logado': bool(request.session.get('usuario_id')),
        'web_eh_admin': role in ROLES_ADMINISTRATIVOS,
        'web_pode_editar': role in ROLES_QUE_EDITAM,
        'web_tema': request.session.get('tema', 'escuro'),
        'web_tarefas': resumo,
        'web_usuario': {
            'nome': nome,
            'iniciais': iniciais.upper(),
            'role': usuario.get('role'),
            'role_label': ROLE_LABELS.get(usuario.get('role'), ''),
            'tenant_id': usuario.get('tenant_id'),
        },
    }
    if role == ROLE_ADMIN_SAAS:
        tenants = list(
            Tenant.objects.exclude(vales__status='INATIVA')
            .only('id', 'nome')
            .order_by('nome', 'id')
        )
        selecionado = next(
            (tenant for tenant in tenants if tenant.pk == tenant_id),
            None,
        )
        contexto.update({
            'web_tenant_options': tenants,
            'web_tenant_selected_id': tenant_id,
            'web_tenant_selected_name': selecionado.nome if selecionado else '',
        })
    return contexto
