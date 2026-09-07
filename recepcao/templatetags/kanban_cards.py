from django import template
from django.utils.html import format_html

register = template.Library()


_STATUS_PODE_VER = frozenset({
    'EM_ANALISE',
    'FICHA_ENVIADA',
    'EM_PREENCHIMENTO',
})


@register.simple_tag
def visualizar_candidato_card(card):
    """Botão de visualização do card do candidato (Súplica).

    Só aparece quando o candidato já enviou a ficha (token_used_at ou status
    avançado).
    """
    if card.get('token_used_at') or card.get('status') in _STATUS_PODE_VER:
        return format_html(
            '<a class="text-[10.5px] font-medium text-[#5b8def] hover:underline" '
            'href="/candidatos/detalhe/{}/">Visualizar</a>',
            card['pk']
        )
    return ''
