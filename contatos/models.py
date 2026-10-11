"""Modelos do tema 'contatos' — Contato, Carteira, Negocio, Tag, Nota e Movimentacao."""
import re
from decimal import Decimal

from django.db import models


def so_digitos(s):
    """Somente os dígitos de uma string — base da normalização de telefone."""
    return re.sub(r'\D', '', s or '')


class Carteira(models.Model):
    """Carteira de clientes — agrupamento de contatos da operação (escopada por tenant).

    No PRD HAZON (Sprint 3 — Gestão de bases), a carteira organiza clientes/leads
    por operação (ex.: cobrança, prospecção) e os registros importados por CSV
    podem ser associados a uma carteira de destino.
    """

    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default='')
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='carteiras',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carteiras'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='carteira_nome_tenant_unico'),
        ]

    def __str__(self):
        return self.nome


class Tag(models.Model):
    """Etiqueta colorida para classificar contatos (escopada por tenant)."""

    nome = models.CharField(max_length=40)
    cor = models.CharField(max_length=7, default='#74b3c6')
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='tags',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tags'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='tag_nome_tenant_unico'),
        ]

    def __str__(self):
        return self.nome


class Contato(models.Model):
    nome = models.TextField()
    empresa = models.TextField(default='—')
    tel = models.TextField(default='—')
    tel_normalizado = models.CharField(max_length=20, blank=True, default='', db_index=True)
    email = models.TextField(default='—')
    seg = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    procedimento = models.TextField(default='—')
    ultima_consulta = models.TextField(default='—')
    origem = models.TextField(default='—')
    pagamento = models.TextField(default='—')
    # Campos extras da ficha enriquecida
    nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, blank=True, default='')
    cidade = models.CharField(max_length=80, blank=True, default='')
    bairro = models.CharField(max_length=80, blank=True, default='')
    observacoes = models.TextField(blank=True, default='')
    # Campos da empresa (preenchidos via consulta de CNPJ, sempre editaveis)
    cnpj = models.CharField(max_length=18, blank=True, default='')
    razao_social = models.CharField(max_length=160, blank=True, default='')
    cnae = models.CharField(max_length=160, blank=True, default='')
    endereco = models.CharField(max_length=200, blank=True, default='')
    responsavel = models.CharField(max_length=80, blank=True, default='')
    cargo = models.CharField(max_length=80, blank=True, default='')
    carteira = models.ForeignKey(
        Carteira,
        on_delete=models.SET_NULL,
        db_column='carteira_id',
        null=True,
        blank=True,
        related_name='contatos',
        help_text='Carteira da operação a que o contato pertence',
    )
    lead_score = models.IntegerField(
        default=0,
        help_text='Pontuação automática (lead scoring) — quanto maior, mais quente o lead',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='contatos')
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='contatos',
    )

    class Meta:
        db_table = 'contatos'
        ordering = ['id']
        indexes = [
            models.Index(fields=['tenant_id', 'seg'], name='cto_tenant_seg_idx'),
            models.Index(fields=['tenant_id', 'lead_score'], name='cto_tenant_score_idx'),
            models.Index(fields=['tenant_id', 'tel_normalizado'], name='cto_tenant_tel_idx'),
        ]

    @property
    def negocio(self):
        """Negócio principal do contato (compatibilidade — o dado vive em Negocio)."""
        return negocio_principal(self)

    @property
    def stage(self):
        """Etapa do negócio principal (leitura de compatibilidade)."""
        negocio = self.negocio
        return negocio.stage if negocio else ''

    @property
    def valor(self):
        """Valor do negócio principal (leitura de compatibilidade)."""
        negocio = self.negocio
        return negocio.valor if negocio else Decimal('0')

    def save(self, *args, **kwargs):
        """Mantém `tel_normalizado` sincronizado com `tel` (dígitos apenas)."""
        self.tel_normalizado = so_digitos(self.tel)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Negocio(models.Model):
    """Negócio (deal) — a venda em negociação, ligada a um contato (1:N).

    É aqui que vivem `stage` (etapa do funil) e `valor`; o contato guarda a ficha.
    O primeiro negócio criado para um contato é o **principal** (alvo das edições
    rápidas do formulário do contato e da API).
    """

    contato = models.ForeignKey(
        Contato,
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='negocios',
    )
    titulo = models.CharField(max_length=160, blank=True, default='')
    stage = models.TextField()
    valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    principal = models.BooleanField(default=False)
    responsavel = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='negocios_responsaveis',
        help_text='Vendedor responsável pelo negócio (alimenta as metas por vendedor)',
    )
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='negocios',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'negocios'
        ordering = ['id']
        indexes = [
            models.Index(fields=['tenant_id', 'stage'], name='neg_tenant_stage_idx'),
            models.Index(fields=['tenant_id', 'updated_at'], name='neg_tenant_upd_idx'),
            models.Index(fields=['tenant_id', 'responsavel_id'], name='neg_tenant_resp_idx'),
            models.Index(fields=['tenant_id', 'created_at'], name='neg_tenant_created_idx'),
            models.Index(fields=['responsavel_id', 'stage'], name='neg_resp_stage_idx'),
        ]

    def __str__(self):
        return f'{self.titulo or self.contato_id} ({self.stage})'


class CampoPersonalizado(models.Model):
    """Campo extra definido pelo tenant, exibido no formulario e na ficha do contato."""

    TIPOS = [
        ('texto', 'Texto'),
        ('numero', 'Número'),
        ('data', 'Data'),
        ('telefone', 'Telefone'),
        ('email', 'E-mail'),
        ('sim_nao', 'Sim / Não'),
        ('lista', 'Lista'),
    ]

    nome = models.CharField(max_length=60)
    tipo = models.CharField(max_length=20, choices=TIPOS, default='texto')
    opcoes = models.TextField(blank=True, default='')  # usadas quando tipo == 'lista'
    obrigatorio = models.BooleanField(default=False)
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='campos_personalizados',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'campos_personalizados'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='campo_nome_tenant_unico'),
        ]

    def __str__(self):
        return self.nome


class ValorCampoPersonalizado(models.Model):
    """Valor de um campo personalizado para um contato (um valor por campo/contato)."""

    contato = models.ForeignKey(
        Contato,
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='valores_campos',
    )
    campo = models.ForeignKey(
        CampoPersonalizado,
        on_delete=models.CASCADE,
        db_column='campo_id',
        related_name='valores',
    )
    valor = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'valores_campos_personalizados'
        constraints = [
            models.UniqueConstraint(fields=['contato', 'campo'], name='valor_contato_campo_unico'),
        ]

    def __str__(self):
        return f'{self.campo.nome}: {self.valor}'


class Nota(models.Model):
    """Anotacao sobre um contato, com autor e data (linha do tempo)."""

    contato = models.ForeignKey(
        Contato,
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='notas',
    )
    autor = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas',
    )
    texto = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notas'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Nota {self.id} — contato {self.contato_id}'


class Movimentacao(models.Model):
    """Mudança de etapa de um negócio — alimenta o histórico da ficha e a atividade recente."""

    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        db_column='negocio_id',
        related_name='movimentacoes',
    )
    de_stage = models.CharField(max_length=40, blank=True, default='')
    para_stage = models.CharField(max_length=40)
    autor = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movimentacoes'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'negócio {self.negocio_id}: {self.de_stage or "novo"} → {self.para_stage}'


def registrar_movimentacao(negocio, de_stage, para_stage, autor_id=None):
    """Grava uma mudança de etapa no histórico (não grava quando não houve mudança)."""
    if not para_stage or de_stage == para_stage:
        return None
    return Movimentacao.objects.create(
        negocio=negocio,
        de_stage=de_stage or '',
        para_stage=para_stage,
        autor_id=autor_id,
    )


def criar_negocio(contato, stage='interessado', valor=0, tenant_id=None, principal=None, titulo=None):
    """Cria um negócio para o contato — o primeiro criado vira o principal.

    Factory única usada por formulário web, importador e API.
    """
    if principal is None:
        principal = not contato.negocios.exists()
    return Negocio.objects.create(
        contato=contato,
        titulo=titulo if titulo is not None else contato.nome,
        stage=stage,
        valor=valor,
        tenant_id=tenant_id,
        principal=principal,
    )


def tornar_principal(negocio):
    """Marca um negócio como principal do contato (desmarcando os demais)."""
    contato = negocio.contato
    contato.negocios.exclude(pk=negocio.pk).update(principal=False)
    if not negocio.principal:
        negocio.principal = True
        negocio.save(update_fields=['principal'])


class LojaPdf(models.Model):
    """PDF de valores (tabela de emolumentos) de uma loja — ex.: diploma, avental,
    anuidade e iniciação.

    Um único arquivo por loja (substituir apaga o anterior). `loja_id` referencia
    a loja do banco GPRB — não é FK do Django porque essa entidade vive fora.
    """

    loja_id = models.CharField(max_length=64, unique=True, db_index=True)
    arquivo = models.FileField(upload_to='lojas/valores/%Y/%m/')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loja_pdf'
        ordering = ['loja_id']

    def __str__(self):
        return f'PDF de valores da loja {self.loja_id}'


def negocio_principal(contato):
    """Negócio principal de um contato: o marcado como principal ou o mais antigo.

    Percorre `contato.negocios.all()` (e não `.filter(...)`) para aproveitar o
    cache do `prefetch_related('negocios')` — evita N+1 em listas e na API.
    """
    lista = list(contato.negocios.all())
    for n in lista:
        if n.principal:
            return n
    return lista[0] if lista else None
