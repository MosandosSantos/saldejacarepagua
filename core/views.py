"""Views auxiliares do core (páginas estáticas, upgrade, etc.)."""
from django.shortcuts import render


def versao_educativa(request, recurso=''):
    """Exibe mensagem de que a funcionalidade é exclusiva da versão Professional."""
    context = {
        'recurso': recurso,
        'titulo': recurso.replace('_', ' ').title() if recurso else 'Funcionalidade',
    }
    return render(request, 'core/versao_educativa.html', context)
