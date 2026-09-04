"""Templatetags de seguranca: serializacao segura para contexto JS.

Uso nos templates:
    {% load seguranca %}
    <script> var dados = {{ lista|js }}; </script>
"""
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True)
def js(valor):
    """Serializa um valor Python como JSON seguro para embutir em <script>.

    - `json.dumps(..., ensure_ascii=True, default=str)` produz JSON valido (UUID/date
      viram string) sem caracteres nao-ascii crus;
    - `<`, `>` e `&` sao escapados para \u003c/\u003e/\u0026 — impede que um valor
      vindo do banco (nome de loja, membro, rito, categoria...) feche a tag <script>
      ou quebre o codigo JS (XSS);
    - U+2028/U+2029 (separadores de linha JS) sao escapados.

    NUNCA use com `|safe` depois — o filtro ja devolve uma SafeString.
    """
    texto = json.dumps(valor, ensure_ascii=True, default=str)
    texto = (
        texto.replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
        .replace('\u2028', '\\u2028')
        .replace('\u2029', '\\u2029')
    )
    return mark_safe(texto)
