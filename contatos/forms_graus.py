from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from contatos.models import GrauMembro, Membro


class GrauMembroForm(forms.ModelForm):
    class Meta:
        model = GrauMembro
        fields = ('grau', 'data')
        widgets = {
            'grau': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-white/15 bg-[#0a1e3d] px-3 py-2.5 text-[13px] text-white outline-none focus:border-[#5b8def]/60',
            }),
            'data': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-[13px] text-white outline-none focus:border-[#5b8def]/60 [color-scheme:dark]',
                },
                format='%Y-%m-%d',
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        grau = cleaned_data.get('grau')
        data = cleaned_data.get('data')

        if grau and not 4 <= grau.numero <= 33:
            self.add_error('grau', 'Selecione um grau entre 4 e 33.')
        if data and data > timezone.localdate():
            self.add_error('data', 'A data do grau não pode estar no futuro.')
        return cleaned_data


class BaseGrauMembroFormSet(BaseInlineFormSet):
    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.instance.tenant_id)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        pk_name = self.model._meta.pk.name
        if pk_name in form.fields:
            form.fields[pk_name].queryset = self.get_queryset()

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        graus = set()
        for form in self.forms:
            cleaned_data = getattr(form, 'cleaned_data', {})
            if not cleaned_data or cleaned_data.get('DELETE'):
                continue
            grau = cleaned_data.get('grau')
            if grau is None:
                continue
            if grau.pk in graus:
                raise ValidationError('O mesmo grau não pode ser cadastrado duas vezes.')
            graus.add(grau.pk)

    def save_new(self, form, commit=True):
        form.instance.tenant_id = self.instance.tenant_id
        return super().save_new(form, commit=commit)


GrauMembroFormSet = inlineformset_factory(
    Membro,
    GrauMembro,
    form=GrauMembroForm,
    formset=BaseGrauMembroFormSet,
    fields=('grau', 'data'),
    extra=1,
    can_delete=True,
    max_num=30,
    validate_max=True,
)
