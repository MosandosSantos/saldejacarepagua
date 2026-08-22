"""Context processors da camada web: injetam a navegacao e o usuario da sessao em todos os templates."""

from django.urls import reverse

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
_ICONE_EMAIL = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                'stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/>'
                '<path d="m22 7-10 6L2 7"/></svg>')
_ICONE_TAREFAS = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                  'stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/>'
                  '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>')
_ICONE_CARTEIRA = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>')
_ICONE_CAMPANHA = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg>')
_ICONE_DISCADOR = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                   'stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>')
_ICONE_ADS = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
              'stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
              '<polyline points="17 6 23 6 23 12"/></svg>')
_ICONE_INSTAGRAM = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                     'stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/>'
                     '<path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>')
_ICONE_CRIATIVOS = ('<svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" '
                     'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/>'
                     '<circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>')

# (label, app, rota, icone, match_urls, excluir_urls, [subitens])
# - subitens (opcional): lista de dicts com 'label', 'app', 'rota', 'match' e 'icone' —
#   transforma o item em um menu dropdown/accordion (ex.: Campanhas > Ads/E-mails/...).
_CAMPANHA_SUBS = [
    {'label': 'Campanhas', 'app': 'campanhas', 'rota': 'campanhas:lista', 'match': {'lista', 'novo', 'detalhe', 'editar', 'excluir'}, 'icone': None},
    {'label': 'Ads', 'app': 'campanhas', 'rota': 'campanhas:ads', 'match': {'ads'}, 'icone': _ICONE_ADS},
    {'label': 'E-mails', 'app': 'emails', 'rota': 'emails:lista', 'match': {'lista', 'novo', 'editar', 'excluir', 'campanha', 'enviar_contato'}, 'icone': _ICONE_EMAIL},
    {'label': 'Instagram', 'app': 'campanhas', 'rota': 'campanhas:instagram', 'match': {'instagram'}, 'icone': _ICONE_INSTAGRAM},
    {'label': 'Criativos', 'app': 'campanhas', 'rota': 'campanhas:criativos', 'match': {'criativos'}, 'icone': _ICONE_CRIATIVOS},
]
# - match_urls  (None = destaque por app): urls que destacam este item
# - excluir_urls: urls do MESMO app que NÃO devem destacar (ex.: páginas de
#   carteiras ficam com 'Carteiras' ativo, não 'Contatos')
_ROTAS = [
    ('Dashboard', 'dashboard', 'dashboard:index', _ICONE_DASH, None, set()),
    ('Funil', 'funil', 'funil:kanban', _ICONE_FUNIL, None, set()),
    ('Contatos', 'contatos', 'contatos:lista', _ICONE_CONTATOS, None, {'carteiras', 'carteira_detalhe'}),
    ('Carteiras', None, 'premium_carteiras', _ICONE_CARTEIRA, None, set()),
    ('Tarefas', 'tarefas', 'tarefas:lista', _ICONE_TAREFAS, None, set()),
    ('Campanhas', None, 'premium_campanhas', _ICONE_CAMPANHA, None, set()),
    ('WhatsApp', None, 'premium_whatsapp', _ICONE_DISCADOR, None, set()),
]

ROLE_LABELS = {
    'admin_saas': 'Admin SaaS',
    'admin_company': 'Admin da empresa',
    'operacional': 'Operacional',
    'viewer': 'Somente leitura',
    None: '',
}


def _nav_itens(url_name='', app_atual='', tarefas_atrasadas=0):
    """Monta a navegação com o item ativo já calculado (evita depender só do app)."""
    itens = []
    for item_tupla in _ROTAS:
        label, app, rota, icone, match_urls, excluir_urls = item_tupla[:6]
        subs = item_tupla[6] if len(item_tupla) > 6 else None
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
    itens.append({'label': 'Configurações', 'app': None, 'url': reverse('config'),
                  'icone': _ICONE_CONFIG, 'ativa': url_name == 'config', 'subitens': None})
    return itens


def web_sessao(request):
    """Disponibiliza NAV_ITENS, web_usuario, web_logado e o resumo de tarefas pendentes."""
    usuario = request.session.get('usuario', {})
    role = usuario.get('role') if isinstance(usuario, dict) else None
    nome = usuario.get('nome', '') if isinstance(usuario, dict) else ''
    partes = [p for p in nome.split() if p]
    iniciais = (partes[0][0] + (partes[-1][0] if len(partes) > 1 else '')) if partes else 'A'

    # Tarefas pendentes (badge no header) — sem query para páginas públicas/API
    resumo = resumo_tarefas(usuario.get('tenant_id')) if request.session.get('usuario_id') else {
        'atrasadas': 0, 'hoje': 0, 'abertas': 0,
    }
    resolver = getattr(request, 'resolver_match', None)
    url_name = resolver.url_name if resolver else ''
    app_atual = resolver.app_name if resolver else ''
    return {
        'NAV_ITENS': _nav_itens(
            url_name, app_atual, tarefas_atrasadas=resumo['atrasadas']
        ),
        'web_logado': bool(request.session.get('usuario_id')),
        'web_eh_admin': role in ('admin_company', 'admin_saas'),
        'web_pode_editar': role in ('admin_company', 'operacional', 'admin_saas'),
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