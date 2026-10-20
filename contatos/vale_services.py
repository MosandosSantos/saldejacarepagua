"""Provisionamento atômico de Vale e seu tenant."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify

from acesso.models import Tenant
from contatos.models import Vale


def provisionar_vale(dados: dict[str, str]) -> Vale:
    """Cria um tenant nomeado pela sigla e o Vale associado, sem órfãos."""
    nome = (dados.get('nome') or '').strip()
    sigla = (dados.get('sigla') or '').strip()

    if not nome:
        raise ValidationError({'nome': 'Informe o nome do Vale.'})
    if not sigla:
        raise ValidationError({'sigla': 'Informe a sigla do Vale.'})
    if len(sigla) > 10:
        raise ValidationError({'sigla': 'A sigla deve ter no máximo 10 caracteres.'})

    slug = slugify(sigla)
    if not slug:
        raise ValidationError({'sigla': 'A sigla precisa conter letras ou números.'})
    if Tenant.objects.filter(slug=slug).exists() or Vale.objects.filter(
        sigla__iexact=sigla,
    ).exists():
        raise ValidationError({'sigla': 'Essa sigla já está em uso.'})

    valores = {**dados, 'nome': nome, 'sigla': sigla}
    try:
        with transaction.atomic():
            tenant = Tenant.objects.create(nome=sigla, slug=slug)
            return Vale.objects.create(tenant=tenant, **valores)
    except IntegrityError as exc:
        # A verificação prévia é UX; a constraint do banco resolve corridas.
        raise ValidationError({'sigla': 'Essa sigla já está em uso.'}) from exc
