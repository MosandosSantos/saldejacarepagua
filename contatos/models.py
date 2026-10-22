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

    Um único arquivo por loja local (substituir apaga o anterior).
    """

    loja = models.OneToOneField(
        'contatos.Loja',
        on_delete=models.CASCADE,
        db_column='loja_id',
        related_name='pdf',
    )
    arquivo = models.FileField(upload_to='lojas/valores/%Y/%m/')
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loja_pdf'
        ordering = ['loja_id']

    def __str__(self):
        return f'PDF de valores da loja {self.loja_id}'


class Vale(models.Model):
    """Tenant-scoped local Vale directory and its Secretaria/Tesouraria contacts."""

    tenant = models.OneToOneField(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='vales',
    )
    nome = models.CharField(max_length=160)
    sigla = models.CharField(max_length=10, unique=True)
    prefeito = models.CharField(max_length=160, blank=True, default='')
    telefone = models.CharField(max_length=40, blank=True, default='')
    email = models.CharField(max_length=254, blank=True, default='')
    secretario_nome = models.CharField(max_length=160, blank=True, default='')
    secretario_email = models.CharField(max_length=254, blank=True, default='')
    secretario_telefone = models.CharField(max_length=40, blank=True, default='')
    tesoureiro_nome = models.CharField(max_length=160, blank=True, default='')
    tesoureiro_email = models.CharField(max_length=254, blank=True, default='')
    tesoureiro_telefone = models.CharField(max_length=40, blank=True, default='')
    pix = models.CharField(max_length=255, blank=True, default='')
    valor_anuidade = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    vencimento_anuidade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, default='ATIVA')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vales'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Loja(models.Model):
    """Loja local pertencente ao tenant de um Vale."""

    CORPO_CHOICES = (
        ('perfeicao', 'Perfeição'),
        ('capitulo', 'Capítulo'),
        ('kadosh', 'Kadosh'),
        ('consistorio', 'Consistório'),
        ('sc33', 'SC33'),
    )

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='lojas',
    )
    nome = models.CharField(max_length=200)
    numero = models.CharField(max_length=20, blank=True, default='')
    corpo = models.CharField(
        max_length=20,
        choices=CORPO_CHOICES,
        default='perfeicao',
    )
    telefone = models.CharField(max_length=40, blank=True, default='')
    email = models.CharField(max_length=254, blank=True, default='')
    presidente_nome = models.CharField(max_length=200, blank=True, default='')
    deputado_mestre = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lojas_presididas',
    )
    secretario = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lojas_secretariadas',
    )
    tesoureiro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lojas_tesoureiradas',
    )
    cidade = models.CharField(max_length=120, blank=True, default='')
    uf = models.CharField(max_length=2, blank=True, default='')
    endereco = models.CharField(max_length=255, blank=True, default='')
    secretario_nome = models.CharField(max_length=160, blank=True, default='')
    secretario_email = models.CharField(max_length=254, blank=True, default='')
    secretario_telefone = models.CharField(max_length=40, blank=True, default='')
    tesoureiro_nome = models.CharField(max_length=160, blank=True, default='')
    tesoureiro_email = models.CharField(max_length=254, blank=True, default='')
    tesoureiro_telefone = models.CharField(max_length=40, blank=True, default='')
    mensalidade = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    situacao = models.CharField(
        max_length=10,
        choices=[('ATIVA', 'Ativa'), ('INATIVA', 'Inativa')],
        default='ATIVA',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lojas'
        ordering = ['nome', 'id']

    def __str__(self):
        return self.nome


class Grau(models.Model):
    """Catálogo de graus maçônicos (4 a 33) — chave estrangeira p/ histórico.

    Evita hardcode nos modelos e permite nome/sigla por grau — espelhando o
    MemberDegree do esquema legado, que usava int solto sem nomes.
    """
    numero = models.PositiveSmallIntegerField(unique=True)
    nome = models.CharField(max_length=120, blank=True, default='')
    sigla = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        db_table = 'graus'
        ordering = ['numero']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(numero__gte=4, numero__lte=33),
                name='grau_numero_4_33',
            ),
        ]

    def __str__(self):
        return self.nome or f'Grau {self.numero}'


class Rito(models.Model):
    """Rito maçônico praticado (YR, REE, RER, AASR...) — global.

    Catálogo compartilhado por toda a aplicação, como o de graus: não pertence
    a um tenant e é visível para todos.
    """

    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=20, blank=True, default='')
    descricao = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'ritos'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome'], name='rito_nome_unico'),
        ]

    def __str__(self):
        return self.sigla or self.nome


class Membro(models.Model):
    """Registro local de uma pessoa vinculada ao tenant de um Vale."""

    POTENCIA_CHOICES = (
        ('COMAB', 'COMAB'),
        ('CSMB', 'CSMB'),
        ('GOB', 'GOB'),
    )

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='membros',
    )
    nome = models.CharField(max_length=200)
    nome_historico = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text=(
            'Nome simbólico do membro: vulto histórico que o motiva '
            '(ex.: "Dom Pedro I", "Anne Frank"). Serve como avatar pessoal.'
        ),
    )
    cpf = models.CharField(max_length=14, blank=True, default='')
    numero_filiado = models.CharField(max_length=30, blank=True, default='')
    foto = models.ImageField(upload_to='membros/', null=True, blank=True)
    situacao = models.CharField(
        max_length=10,
        choices=[('ATIVO', 'Ativo'), ('INATIVO', 'Inativo')],
        default='ATIVO',
    )
    rito = models.CharField(max_length=100, blank=True, default='')
    cadastro_maconico = models.CharField(max_length=40, blank=True, default='')
    cadastro_numero = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text='Número de cadastro maçônico (1 a 9999999, único no sistema).',
    )
    tipo_admissao = models.CharField(max_length=100, blank=True, default='')
    data_admissao = models.DateField(null=True, blank=True)
    escolaridade = models.CharField(max_length=120, blank=True, default='')
    potencia = models.CharField(
        max_length=120,
        choices=POTENCIA_CHOICES,
        blank=True,
        default='',
    )
    cargo = models.CharField(max_length=120, blank=True, default='')
    condicao = models.CharField(max_length=80, blank=True, default='')
    data_nascimento = models.DateField(null=True, blank=True)
    nacionalidade = models.CharField(max_length=80, blank=True, default='')
    naturalidade = models.CharField(max_length=120, blank=True, default='')
    estado_civil = models.CharField(max_length=40, blank=True, default='')
    pai = models.CharField(max_length=200, blank=True, default='')
    mae = models.CharField(max_length=200, blank=True, default='')
    identidade = models.CharField(max_length=40, blank=True, default='')
    orgao_emissor = models.CharField(max_length=40, blank=True, default='')
    data_emissao = models.DateField(null=True, blank=True)
    email = models.CharField(max_length=254, blank=True, default='')
    celular = models.CharField(max_length=40, blank=True, default='')
    telefone_urgencia = models.CharField(max_length=40, blank=True, default='')
    endereco = models.CharField(max_length=200, blank=True, default='')
    numero = models.CharField(max_length=20, blank=True, default='')
    complemento = models.CharField(max_length=100, blank=True, default='')
    bairro = models.CharField(max_length=100, blank=True, default='')
    cidade = models.CharField(max_length=120, blank=True, default='')
    uf = models.CharField(max_length=2, blank=True, default='')
    cep = models.CharField(max_length=12, blank=True, default='')
    apresentacao_mx = models.DateField(null=True, blank=True)
    apresentacao_ec = models.DateField(null=True, blank=True)
    armadura_cbcs = models.DateField(null=True, blank=True)
    data_instalacao = models.DateField(null=True, blank=True)
    loja_iniciacao_nome = models.CharField(max_length=200, blank=True, default='')
    loja_iniciacao_numero = models.CharField(max_length=30, blank=True, default='')
    loja_passagem_nome = models.CharField(max_length=200, blank=True, default='')
    loja_passagem_numero = models.CharField(max_length=30, blank=True, default='')
    loja_elevacao_nome = models.CharField(max_length=200, blank=True, default='')
    loja_elevacao_numero = models.CharField(max_length=30, blank=True, default='')
    loja_instalacao_nome = models.CharField(max_length=200, blank=True, default='')
    loja_instalacao_numero = models.CharField(max_length=30, blank=True, default='')
    lojas = models.ManyToManyField('contatos.Loja', blank=True, related_name='membros')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'membros'
        ordering = ['nome', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'cpf'],
                condition=models.Q(cpf__gt=''),
                name='membro_tenant_cpf_unico',
            ),
        ]

    def __str__(self):
        return self.nome


class GrauMembro(models.Model):
    """Histórico do(s) grau(s) conquistado(s) por um membro (MemberDegree)."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='graus_membros',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.CASCADE,
        db_column='membro_id',
        related_name='graus',
    )
    grau = models.ForeignKey(
        'contatos.Grau',
        on_delete=models.PROTECT,
        db_column='grau_id',
        related_name='membros_graus',
    )
    data = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'graus_membros'
        ordering = ['membro', 'grau__numero']
        constraints = [
            models.UniqueConstraint(
                fields=['membro', 'grau'],
                name='grau_membro_unico',
            ),
        ]

    def __str__(self):
        return f'{self.membro.nome} — grau {self.grau.numero}'


class LojaCargo(models.Model):
    """Catálogo de cargos de uma Loja (VM, 1V, 2V, SC, ...)."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='lojas_cargos',
    )
    loja = models.ForeignKey(
        'contatos.Loja',
        on_delete=models.CASCADE,
        db_column='loja_id',
        related_name='cargos',
    )
    nome = models.CharField(max_length=120)
    abreviatura = models.CharField(max_length=20)
    grau_minimo = models.ForeignKey(
        'contatos.Grau',
        on_delete=models.PROTECT,
        db_column='grau_minimo_id',
        related_name='cargos_com_grau_minimo',
        null=True,
        blank=True,
    )
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'lojas_cargos'
        ordering = ['ordem', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['loja', 'abreviatura'],
                name='cargo_loja_abreviatura_unica',
            ),
        ]

    def __str__(self):
        return f'{self.abreviatura} — {self.loja.nome}'


class Filiacao(models.Model):
    """Vinculo entre membro e loja, com cargo atual (MemberLoja)."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='filiacoes',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.CASCADE,
        db_column='membro_id',
        related_name='filiacoes',
    )
    loja = models.ForeignKey(
        'contatos.Loja',
        on_delete=models.CASCADE,
        db_column='loja_id',
        related_name='filiacoes',
    )
    cargo_atual = models.ForeignKey(
        'contatos.LojaCargo',
        on_delete=models.SET_NULL,
        db_column='cargo_atual_id',
        related_name='ocupado_por',
        null=True,
        blank=True,
    )
    data_inicio = models.DateField(null=True, blank=True)
    diploma = models.BooleanField(default=False)
    cargo = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'filiacoes'
        ordering = ['loja', 'membro']
        constraints = [
            models.UniqueConstraint(
                fields=['membro', 'loja'],
                name='filiacao_membro_loja_unica',
            ),
        ]

    def __str__(self):
        return f'{self.membro.nome} @ {self.loja.nome}'


class HistoricoCargo(models.Model):
    """Histórico de cargos ocupados pelo membro na loja (MemberCargoHistory)."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='historicos_cargos',
    )
    filiacao = models.ForeignKey(
        'contatos.Filiacao',
        on_delete=models.CASCADE,
        db_column='filiacao_id',
        related_name='cargos_historicos',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.CASCADE,
        db_column='membro_id',
        related_name='cargos_historicos',
    )
    loja = models.ForeignKey(
        'contatos.Loja',
        on_delete=models.CASCADE,
        db_column='loja_id',
        related_name='cargos_historicos',
    )
    cargo = models.ForeignKey(
        'contatos.LojaCargo',
        on_delete=models.PROTECT,
        db_column='cargo_id',
        related_name='historicos',
    )
    data_assuncao = models.DateField()
    data_passagem = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'historicos_cargos'
        ordering = ['data_assuncao']

    def __str__(self):
        return f'{self.membro.nome} — {self.cargo.abreviatura} ({self.data_assuncao})'



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
