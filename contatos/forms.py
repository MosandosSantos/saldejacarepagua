"""Formularios web da app contatos — ContatoForm (ficha enriquecida) e NotaForm."""

import re

from django import forms

from contatos.models import CampoPersonalizado, Carteira, Contato, Nota, Tag
from core.dominio import NICHO_PADRAO, ORIGENS, PAGAMENTOS, SEGS, stages_do_nicho
from recepcao.models import etapas_do_tenant

CORES_TAG = ['#74b3c6', '#7fe3c4', '#fbbf24', '#c084fc', '#fb923c', '#60a5fa', '#4ade80', '#f472b6']


class ContatoForm(forms.ModelForm):
    seg = forms.ChoiceField(choices=[(k, v['label']) for k, v in SEGS.items()], label='Segmento')
    # Etapa e valor pertencem ao Negocio (o form apenas captura; a view grava no negocio)
    stage = forms.ChoiceField(choices=[(s['key'], s['name']) for s in stages_do_nicho(NICHO_PADRAO)], label='Etapa do funil')
    valor = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, label='Valor (R$)',
        widget=forms.NumberInput(attrs={'min': '0', 'step': '100', 'placeholder': '0'}),
    )
    origem = forms.ChoiceField(choices=[(o, o) for o in ORIGENS], label='Origem do contato', required=False)
    pagamento = forms.ChoiceField(choices=[(p, p) for p in PAGAMENTOS], label='Forma de pagamento', required=False)
    nova_tag = forms.CharField(
        max_length=40,
        required=False,
        label='Nova tag (opcional)',
        widget=forms.TextInput(attrs={'placeholder': 'ex.: VIP, Retorno, Indicação'}),
    )

    def __init__(self, *args, **kwargs):
        nicho = kwargs.pop('nicho', NICHO_PADRAO)
        tenant_id = kwargs.pop('tenant_id', None)
        super().__init__(*args, **kwargs)
        self.tenant_id = tenant_id
        # Etapas do tenant (pipeline próprio) com fallback para o nicho (admin_saas)
        etapas = etapas_do_tenant(tenant_id, nicho) if tenant_id is not None else stages_do_nicho(nicho)
        self.fields['stage'].choices = [(s['key'], s['name']) for s in etapas]
        # Tags sempre escopadas ao tenant da sessao
        qs = Tag.objects.filter(tenant_id=tenant_id) if tenant_id is not None else Tag.objects.all()
        self.fields['tags'].queryset = qs
        # Carteiras escopadas ao tenant da sessao (admin_saas ve todas)
        qs_cart = Carteira.objects.all() if tenant_id is None else Carteira.objects.filter(tenant_id=tenant_id)
        self.fields['carteira'].queryset = qs_cart

    def clean_tel(self):
        """Bloqueia telefone duplicado dentro do mesmo tenant (dedup por dígitos)."""
        tel = (self.cleaned_data.get('tel') or '').strip()
        digitos = re.sub(r'\D', '', tel)
        if not digitos:
            return tel
        qs = Contato.objects.filter(tel_normalizado=digitos)
        if self.tenant_id is not None:
            qs = qs.filter(tenant_id=self.tenant_id)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um contato com este telefone.')
        return tel

    def clean_cnpj(self):
        """Valida o formato do CNPJ quando preenchido (campo opcional)."""
        cnpj = (self.cleaned_data.get('cnpj') or '').strip()
        if not cnpj:
            return ''
        if not re.fullmatch(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}', cnpj):
            raise forms.ValidationError('CNPJ inválido — use o formato 00.000.000/0000-00.')
        return cnpj

    class Meta:
        model = Contato
        fields = [
            'nome', 'empresa', 'tel', 'email', 'seg',
            'procedimento', 'ultima_consulta', 'origem', 'pagamento',
            'nascimento', 'cpf', 'cidade', 'bairro', 'tags', 'observacoes',
            'cnpj', 'razao_social', 'cnae', 'endereco', 'responsavel',
            'cargo', 'carteira',
        ]
        labels = {
            'nome': 'Nome',
            'empresa': 'Empresa',
            'tel': 'Telefone',
            'email': 'E-mail',
            'procedimento': 'Procedimento',
            'ultima_consulta': 'Última consulta',
            'nascimento': 'Nascimento',
            'cpf': 'CPF',
            'cidade': 'Cidade',
            'bairro': 'Bairro',
            'tags': 'Tags',
            'observacoes': 'Observações',
            'cnpj': 'CNPJ',
            'razao_social': 'Razão social',
            'cnae': 'CNAE',
            'endereco': 'Endereço',
            'responsavel': 'Responsável',
            'cargo': 'Cargo',
            'carteira': 'Carteira',
        }
        widgets = {
            # TextField do modelo renderiza como <textarea>; forçamos <input> de uma linha
            'nome': forms.TextInput(attrs={'placeholder': 'Nome completo'}),
            'empresa': forms.TextInput(attrs={'placeholder': 'Nome da empresa'}),
            'tel': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'email': forms.TextInput(attrs={'placeholder': 'email@exemplo.com'}),
            'procedimento': forms.TextInput(attrs={'placeholder': 'Procedimento de interesse'}),
            'ultima_consulta': forms.DateInput(attrs={'type': 'date'}),
            'nascimento': forms.DateInput(attrs={'type': 'date'}),
            'cpf': forms.TextInput(attrs={'placeholder': '000.000.000-00', 'maxlength': '14'}),
            'observacoes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Preferências, histórico, pendências...'}),
            'tags': forms.CheckboxSelectMultiple(),
            'cnpj': forms.TextInput(attrs={'placeholder': '00.000.000/0000-00', 'maxlength': '18', 'autocomplete': 'off'}),
            'razao_social': forms.TextInput(attrs={'placeholder': 'Razão social da empresa'}),
            'cnae': forms.TextInput(attrs={'placeholder': 'Atividade principal (CNAE)'}),
            'endereco': forms.TextInput(attrs={'placeholder': 'Logradouro, número, complemento'}),
            'responsavel': forms.TextInput(attrs={'placeholder': 'Nome do responsável'}),
            'cargo': forms.TextInput(attrs={'placeholder': 'ex.: Gerente, Diretor, Comprador'}),
        }


class CampoForm(forms.ModelForm):
    """Formulario de gestao dos campos personalizados do tenant."""

    class Meta:
        model = CampoPersonalizado
        fields = ['nome', 'tipo', 'opcoes', 'obrigatorio', 'ordem']
        labels = {
            'nome': 'Nome do campo',
            'tipo': 'Tipo',
            'opcoes': 'Opções (tipo Lista)',
            'obrigatorio': 'Obrigatório',
            'ordem': 'Ordem',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'ex.: Plano de saúde, Nº do convênio'}),
            'opcoes': forms.TextInput(attrs={'placeholder': 'ex.: Bronze, Prata, Ouro'}),
            'ordem': forms.NumberInput(attrs={'min': '0', 'placeholder': '0'}),
        }

    def clean(self):
        dados = super().clean()
        if dados.get('tipo') == 'lista' and not (dados.get('opcoes') or '').strip():
            self.add_error('opcoes', 'Informe as opções separadas por vírgula para o tipo Lista.')
        return dados


class NotaForm(forms.ModelForm):
    class Meta:
        model = Nota
        fields = ['texto']
        labels = {'texto': 'Nova nota'}
        widgets = {
            'texto': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Escreva uma nota sobre este contato...'}),
        }
