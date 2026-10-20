"""Modelos do tema 'acesso' — Tenant, Usuario (RBAC + JWT) e Convite."""
import secrets

from django.db import models
from django.db.models.functions import Lower

ROLE_ADMIN_SAAS = 'admin_saas'
ROLE_ADMIN_COMPANY = 'admin_company'
ROLE_OPERACIONAL = 'operacional'
ROLE_VIEWER = 'viewer'

ROLE_ADM = 'ADM'
ROLE_TESOUREIRO = 'tesoureiro'
ROLE_SECRETARIO = 'secretario'
ROLE_DELEGADO = 'delegado'
ROLE_PRESIDENTE_CORPO = 'presidente_corpo'

ROLES = [
    (ROLE_ADMIN_SAAS, 'Admin SaaS'),
    (ROLE_VIEWER, 'Somente leitura'),
    (ROLE_ADM, 'Administrador'),
    (ROLE_TESOUREIRO, 'Tesoureiro'),
    (ROLE_SECRETARIO, 'Secretário'),
    (ROLE_DELEGADO, 'Delegado'),
    (ROLE_PRESIDENTE_CORPO, 'Presidente de Corpo'),
]

ROLES_DE_TENANT = (ROLE_VIEWER,)
# Base de edição (admin_saas inclui — o dono da plataforma). O oficialato entra
# abaixo, junto com os demais conjuntos de perfil.
_ROLES_EDITAM_BASE = (ROLE_ADMIN_SAAS,)

# Perfis de oficialato que podem criar/reenviar usuários (PRD-USUARIOS-SEM-SENHA).
ROLES_OFICIAIS = (
    ROLE_ADM, ROLE_TESOUREIRO,
    ROLE_SECRETARIO, ROLE_DELEGADO, ROLE_PRESIDENTE_CORPO,
)
# Tudo que não é viewer pode editar — inclusive o oficialato (coexistência).
ROLES_QUE_EDITAM = _ROLES_EDITAM_BASE + ROLES_OFICIAIS
# Quem gerencia usuários: oficialato + admin_saas.
# admin_saas permanece tenantless; o tenant administrado e selecionado no
# contexto da requisicao, nao vinculado ao registro da identidade.
ROLES_GESTORES_USUARIOS = ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,)
# Perfis que podem ser atribuídos ao criar um usuário: oficialato + viewer.
ROLES_ATRIB_CRIACAO = ROLES_OFICIAIS + ROLES_DE_TENANT
# Perfis com acesso administrativo amplo (config/gestão) — oficialato incluso.
ROLES_ADMINISTRATIVOS = ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,)

# Estados de conta de usuário.
USUARIO_ATIVO = 'ativo'
USUARIO_PENDENTE_SENHA = 'pendente_senha'
STATUS_USUARIO = [
    (USUARIO_ATIVO, 'Ativo'),
    (USUARIO_PENDENTE_SENHA, 'Aguardando ativação (sem senha)'),
]
# Senha não utilizável usada em contas pendentes (pref. '!' = hash inutilizável).
SENHA_PENDENTE = '!'


class Tenant(models.Model):
    """Empresa/clinica que usa o sistema — base do isolamento multi-tenant."""

    nome = models.TextField()
    slug = models.TextField(unique=True)
    nicho = models.TextField(null=True, blank=True)  # ramo do negócio (core.dominio.NICHOS)
    meta_mensal = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Meta de faturamento mensal (R$) exibida no dashboard',
    )
    dono = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenants_que_administra',
        help_text='Dono(a) do tenant — quem pode transferir a propriedade (backfill: 1o admin_company)',
    )
    token_captura = models.CharField(
        max_length=64, unique=True, null=True, blank=True,
        help_text='Token público do formulário de captura de lead (gerado sob demanda)',
    )
    origem_captura = models.TextField(
        default='Site',
        help_text='Origem gravada nos contatos vindos do formulário (ex.: Site, Instagram, WhatsApp)',
    )
    captura_ativa = models.BooleanField(default=True)
    # Discador (PRD Sprint 5) — integração com o softphone da operação
    softphone_schema = models.CharField(
        max_length=10,
        choices=[('sip', 'SIP (MicroSIP e afins)'), ('tel', 'tel: (discador padrão)')],
        default='sip',
        help_text='Esquema de URI usado para iniciar a chamada no softphone',
    )
    softphone_dominio = models.CharField(
        max_length=160, blank=True, default='',
        help_text='Domínio SIP (ex.: sip.empresa.com.br) usado quando o esquema é SIP',
    )
    google_calendar_id = models.CharField(
        max_length=120, blank=True, default='',
        help_text='ID do calendário Google do tenant (exportação da agenda)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants'
        ordering = ['id']

    def __str__(self):
        return f'{self.nome} ({self.slug})'


def token_captura_do_tenant(tenant):
    """Token público único do formulário de captura do tenant (gerado sob demanda)."""
    if not tenant.token_captura:
        tenant.token_captura = secrets.token_urlsafe(32)  # 256 bits de entropia (S2.4)
        tenant.save(update_fields=['token_captura'])
    return tenant.token_captura


def tenant_gprb():
    """Tenant GPRB canônico (o login espelha usuários GPRB nele).

    Usado como fallback quando a sessão não tem tenant (admin_saas): criação de
    candidatos, kanban e contadores precisam resolver para o MESMO tenant, senão
    o candidato é gravado num tenant e exibido noutro ("some" do funil).
    Preferência: slug 'gprb' → 'gprbr' → primeiro tenant existente.
    """
    return (
        Tenant.objects.filter(slug='gprb').first()
        or Tenant.objects.filter(slug='gprbr').first()
        or Tenant.objects.first()
    )


class Usuario(models.Model):
    """Usuario do sistema. Roles: admin_saas (plataforma), por tenant admin_company/
    operacional/viewer e oficialato (Grão Prior, Grande Chanceler, ...)."""

    nome = models.TextField()
    email = models.TextField(unique=True)
    celular = models.TextField(blank=True, default='')
    senha = models.TextField()  # hash (django.contrib.auth.hashers); '!' = pendente
    role = models.TextField(choices=ROLES)
    status = models.TextField(
        choices=STATUS_USUARIO, default=USUARIO_ATIVO,
        help_text='pendente_senha = conta criada aguardando o usuário definir a senha (72h)',
    )
    token_ativacao = models.TextField(
        null=True, blank=True,
        help_text='Token de uso único do link de ativação de senha (PRD-USUARIOS-SEM-SENHA)',
    )
    ativacao_expira_em = models.DateTimeField(
        null=True, blank=True, help_text='Validade do link de ativação (72h)',
    )
    ativado_em = models.DateTimeField(null=True, blank=True)
    reenvios_ativacao = models.PositiveSmallIntegerField(
        default=0,
        help_text='Quantas vezes o link de ativação foi reenviado (limite de 3 por usuário pendente)',
    )
    criado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_criados',
        help_text='Quem criou a conta (auditoria)',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        null=True,
        blank=True,
        related_name='usuarios',
    )
    prefeitura_id = models.CharField(
        max_length=36, blank=True, default='',
        help_text='UUID da prefeitura GPRB vinculada ao usuário (opcional)',
    )
    loja_id = models.CharField(
        max_length=36, blank=True, default='',
        help_text='UUID da loja GPRB vinculada ao usuário (opcional)',
    )
    membro = models.OneToOneField(
        'contatos.Membro',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuario',
        help_text=('Membro cujo número de cadastro serve de login ao usuário '
                   '(None = contas administrativas entram por e-mail)'),
    )
    cadastro_numero = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text=('Número de cadastro próprio da conta, usado no login '
                   '(para contas administrativas sem membro vinculado)'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios'
        ordering = ['id']
        indexes = [
            models.Index(Lower('email'), name='usuario_email_lower_idx'),
        ]

    @property
    def pendente_ativacao(self):
        return self.status == USUARIO_PENDENTE_SENHA

    def pode_transferir_dono(self) -> bool:
        """So o admin da clinica que e o dono (ou, enquanto nao houver dono definido,
        qualquer admin_company) pode transferir a propriedade do tenant."""
        if self.role != ROLE_ADMIN_COMPANY or self.tenant is None:
            return False
        return self.tenant.dono_id is None or self.tenant.dono_id == self.id

    def __str__(self):
        return f'{self.email} ({self.role})'


class MetaVendedor(models.Model):
    """Meta de vendas de um membro para um mês — base do dashboard de atingimento.

    `mes` guarda o primeiro dia do mês de referência (ex.: 2026-08-01 para agosto/2026).
    """

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='metas',
    )
    mes = models.DateField(help_text='Primeiro dia do mês de referência')
    valor = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Meta de faturamento (R$) do vendedor no mês',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'metas_vendedores'
        ordering = ['mes', 'usuario_id']
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'mes'], name='meta_usuario_mes_unico'),
        ]

    def __str__(self):
        return f'Meta de {self.usuario_id} em {self.mes}: R$ {self.valor}'


class Convite(models.Model):
    """Convite por link para entrar na equipe de um tenant.

    O admin gera o link com o e-mail do convidado; a pessoa preenche nome e senha
    na página pública de aceite e vira membro do tenant com o papel escolhido.
    """

    token = models.CharField(max_length=64, unique=True)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='convites',
    )
    email = models.TextField()
    papel = models.TextField(choices=[(r, r) for r in ROLES_DE_TENANT])
    criado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='convites_criados',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)
    usado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='convites_usados',
    )
    cancelado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'convites'
        ordering = ['-created_at']

    @property
    def pendente(self):
        return self.usado_em is None and self.cancelado_em is None

    def __str__(self):
        return f'Convite {self.email} → {self.tenant_id}'
