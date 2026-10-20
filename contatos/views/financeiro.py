"""View do menu Financeiro (placeholder inicial da área financeira)."""
from django.shortcuts import render

from acesso.decorators import web_login_required


@web_login_required
def financeiro(request):
    """Página inicial do módulo Financeiro."""
    return render(request, 'contatos/financeiro.html')
