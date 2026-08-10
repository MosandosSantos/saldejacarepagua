"""Validadores de senha em portugues (sobrepoe os defaults do Django).

O Django 5.x nao envia mais traducoes embutidas — para manter as mensagens da
UI em pt-br (e o LANGUAGE_CODE do projeto), herdamos os validators nativos e
sobrescrevemos apenas os textos. O comportamento (regras) continua identico.
"""
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class TamanhoMinimoValidator(MinimumLengthValidator):
    """Senha deve ter ao menos `min_length` caracteres."""

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _('A senha deve ter pelo menos %(min_length)d caracteres.'),
                code='password_too_short',
                params={'min_length': self.min_length},
            )


class AtributoSimilarValidator(UserAttributeSimilarityValidator):
    """Senha nao pode ser muito parecida com nome/e-mail/username do usuario."""

    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(
                _('A senha e muito parecida com os seus dados pessoais.'),
                code='password_too_similar',
            )


class SenhaComumValidator(CommonPasswordValidator):
    """Rejeita as 20 mil senhas mais comuns (lista do Django)."""

    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(
                _('Esta senha e muito comum e facil de adivinhar.'),
                code='password_too_common',
            )


class SenhaNumericaValidator(NumericPasswordValidator):
    """Rejeita senhas formadas apenas por digitos."""

    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(
                _('A senha nao pode conter apenas numeros.'),
                code='password_entirely_numeric',
            )
