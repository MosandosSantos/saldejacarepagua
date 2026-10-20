"""Shared numbered pagination links for local list pages."""


def urls_paginacao(request, page_obj, base_path=None):
    """Build elided links, retaining active GET filters and canonical paths."""
    paginator = page_obj.paginator
    base_path = base_path or request.path

    def url_para_pagina(numero):
        parametros = request.GET.copy()
        parametros['page'] = str(numero)
        return f'{base_path}?{parametros.urlencode()}'

    paginas = []
    for numero in paginator.get_elided_page_range(
        page_obj.number,
        on_each_side=2,
        on_ends=1,
    ):
        if numero == paginator.ELLIPSIS:
            paginas.append({'ellipsis': True})
            continue
        paginas.append({
            'number': numero,
            'url': url_para_pagina(numero),
            'current': numero == page_obj.number,
        })

    return {
        'previous': (
            url_para_pagina(page_obj.previous_page_number())
            if page_obj.has_previous() else None
        ),
        'next': (
            url_para_pagina(page_obj.next_page_number())
            if page_obj.has_next() else None
        ),
        'pages': paginas,
    }
