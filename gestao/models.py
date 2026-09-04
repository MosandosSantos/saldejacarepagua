"""Modelos do app gestao — Inscricoes, Congressistas e Pagamentos (GEOD-CEOD)."""
from django.db import models


class Capitulo(models.Model):
    """Capitulo (loja/loja) que o congressista representa."""
    nome = models.CharField(max_length=200)
    numero = models.IntegerField(null=True, blank=True)
    cidade = models.CharField(max_length=200, blank=True, default='')
    uf = models.CharField(max_length=2, blank=True, default='')
    potencia = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestao_capitulo'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.numero or "?"})'


class TipoInscricao(models.Model):
    """Tipo de inscricao (ex: Inteira, Meia, Isenta, etc.)."""
    nome = models.CharField(max_length=100)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descricao = models.TextField(blank=True, default='')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestao_tipo_inscricao'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} — R$ {self.valor}'


class Inscricao(models.Model):
    """Inscricao de um quarto no congresso."""
    STATUS_CHOICES = [
        ('emitiu_boleto', 'Emitiu Boleto'),
        ('aguardando_aprovacao', 'Aguardando Aprovacao'),
        ('aguardando_documentos', 'Aguardando Documentos'),
        ('aprovado', 'Aprovado'),
        ('hospedado', 'Hospedado'),
        ('nao_compareceu', 'Nao Compareceu'),
        ('isenta', 'Isenta'),
        ('cancelada', 'Cancelada'),
    ]
    FLUXO_KANBAN = [
        'emitiu_boleto',
        'aguardando_aprovacao',
        'aguardando_documentos',
        'aprovado',
        'hospedado',
        'nao_compareceu',
    ]
    STATUS_ATIVOS = [
        'emitiu_boleto', 'aguardando_aprovacao', 'aguardando_documentos',
        'aprovado', 'hospedado', 'nao_compareceu', 'isenta',
    ]

    titulo = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='emitiu_boleto')
    tipo = models.ForeignKey(TipoInscricao, on_delete=models.SET_NULL, null=True, blank=True, related_name='inscricoes')
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quarto_numero = models.CharField(max_length=20, blank=True, default='')
    observacoes = models.TextField(blank=True, default='')
    dados_json = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestao_inscricao'
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo or f'Inscricao #{self.pk}'


class Congressista(models.Model):
    """Pessoa vinculada a uma inscricao (1 inscricao = N congressistas = 1 quarto)."""
    CATEGORIAS = [
        ('escudeiro', 'Escudeiro'),
        ('demolay', 'DeMolay'),
        ('macom', 'Macom'),
        ('mestre', 'Mestre'),
        ('outro', 'Outro'),
    ]
    TAMANHOS_CAMISA = [
        ('P', 'P'),
        ('M', 'M'),
        ('G', 'G'),
        ('GG', 'GG'),
        ('XG', 'XG'),
        ('XXG', 'XXG'),
        ('OUTRO', 'Outro'),
    ]

    inscricao = models.ForeignKey(Inscricao, on_delete=models.CASCADE, related_name='congressistas')
    nome_completo = models.CharField(max_length=200)
    cpf = models.CharField(max_length=14, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    celular = models.CharField(max_length=20, blank=True, default='')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='outro')
    capitulo = models.ForeignKey(Capitulo, on_delete=models.SET_NULL, null=True, blank=True, related_name='congressistas')
    tamanho_camisa = models.CharField(max_length=5, choices=TAMANHOS_CAMISA, blank=True, default='')
    mc_lanche = models.BooleanField(default=False, help_text='Participa do McDia Feliz')
    aceita_comunicacao = models.BooleanField(default=True, help_text='Aceita receber comunicacoes (e-mail/WhatsApp)')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestao_congressista'
        ordering = ['nome_completo']

    def __str__(self):
        return self.nome_completo


class Pagamento(models.Model):
    """Pagamento vinculado a uma inscricao."""
    FORMA_CHOICES = [
        ('PIX', 'PIX'),
        ('BOLETO', 'Boleto'),
        ('CREDIT_CARD', 'Cartao de Credito'),
        ('DEBIT_CARD', 'Cartao de Debito'),
        ('DINHEIRO', 'Dinheiro'),
        ('OUTRO', 'Outro'),
    ]
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('confirmado', 'Confirmado'),
        ('sistema', 'Sistema'),
        ('cancelado', 'Cancelado'),
        ('estornado', 'Estornado'),
    ]

    inscricao = models.ForeignKey(Inscricao, on_delete=models.CASCADE, related_name='pagamentos')
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    forma = models.CharField(max_length=20, choices=FORMA_CHOICES, default='PIX')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    data_pagamento = models.DateTimeField(null=True, blank=True)
    comprovante = models.CharField(max_length=200, blank=True, default='')
    observacoes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gestao_pagamento'
        ordering = ['-data_pagamento', '-created_at']

    def __str__(self):
        return f'R$ {self.valor} — {self.get_forma_display()}'


class Campanha(models.Model):
    """Comunicacao em massa/individual (e-mail ou WhatsApp) com snapshot auditavel.

    `destinatarios` guarda a lista no momento do envio (auditoria) e `filtros`
    os filtros aplicados (categoria/pagamento) quando a origem foi `cadastrados`.
    """
    CANAIS = [
        ('EMAIL', 'E-mail'),
        ('ZAP', 'WhatsApp'),
    ]
    ORIGENS = [
        ('prefeituras', 'Coletivo (Prefeituras / Lojas)'),
        ('individual', 'Individual (uma pessoa)'),
    ]
    STATUS = [
        ('rascunho', 'Rascunho'),
        ('enviando', 'Enviando'),
        ('enviada', 'Enviada'),
        ('falha', 'Falha parcial'),
    ]

    canal = models.CharField(max_length=10, choices=CANAIS)
    assunto = models.CharField(max_length=200, blank=True, default='')
    corpo = models.TextField()
    origem = models.CharField(max_length=20, choices=ORIGENS)
    filtros = models.JSONField(default=dict, blank=True)
    destinatarios = models.JSONField(default=list, blank=True)
    total_enviados = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS, default='rascunho')
    criado_por = models.ForeignKey(
        'acesso.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'gestao_campanha'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.get_canal_display()} · {self.corpo[:40]}'
