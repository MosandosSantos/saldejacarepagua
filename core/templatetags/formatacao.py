"""Templatags de formatacao locale-aware (pt-BR).

Objetivo: substituir os formatos de data/moeda fixos no template
(`|date:"d/m/Y"`, `"R$ " + valor`) por filtros que seguem a locale ativa
do Django — assim trocar a locale do projeto troca o formato em todo o app.

Uso nos templates:
    {% load formatacao %}
    {{ pedido.data|datahora_br }}
    {{ pedido.valor|moeda_br }}
"""
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import formats
from django.utils.formats import date_format, number_format

register = template.Library()


@register.filter(name="databr")
def databr(valor, formato="SHORT_DATE_FORMAT"):
    """Data no formato curto da locale ativa (pt-BR -> dd/mm/aaaa)."""
    if not valor:
        return ""
    try:
        return date_format(valor, formato)
    except (AttributeError, ValueError, TypeError):
        return ""


@register.filter(name="datahorabr")
def datahorabr(valor):
    """Data + hora no formato curto da locale ativa (pt-BR -> dd/mm/aaaa HH:MM)."""
    if not valor:
        return ""
    try:
        return date_format(valor, "SHORT_DATETIME_FORMAT")
    except (AttributeError, ValueError, TypeError):
        return ""


@register.filter(name="horabr")
def horabr(valor):
    """Somente a hora, no formato da locale ativa (pt-BR -> HH:MM)."""
    if not valor:
        return ""
    try:
        return date_format(valor, formats.get_format("TIME_FORMAT"))
    except (AttributeError, ValueError, TypeError):
        return ""


@register.filter(name="mesanome")
def mesanome(valor):
    """Nome do mes/ano por extenso e localizado (ex.: 'julho de 2026')."""
    if not valor:
        return ""
    try:
        return date_format(valor, formats.get_format("YEAR_MONTH_FORMAT"))
    except (AttributeError, ValueError, TypeError):
        return ""


@register.filter(name="moedabr")
def moedabr(valor, prefixo="R$ "):
    """Valor monetario formatado na locale ativa (pt-BR -> R$ 1.234,56).

    Usa `number_format` do Django, que respeita `USE_THOUSAND_SEPARATOR` e
    `DECIMAL_SEPARATOR` da locale configurada em settings.
    """
    if valor is None or valor == "":
        return ""
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return valor
    try:
        texto = number_format(numero, decimal_pos=2, use_l10n=True, force_grouping=True)
    except (TypeError, ValueError):
        return valor
    return f"{prefixo}{texto}"


@register.filter(name="numerobr")
def numerobr(valor, casas=0):
    """Numero formatado na locale ativa, sem moeda (pt-BR -> 1.234)."""
    if valor is None or valor == "":
        return ""
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return valor
    try:
        return number_format(
            numero,
            decimal_pos=int(casas),
            use_l10n=True,
            force_grouping=True,
        )
    except (TypeError, ValueError):
        return valor
