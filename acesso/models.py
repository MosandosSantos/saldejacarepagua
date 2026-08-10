"""Modelos do tema 'acesso' — Tenant, Usuario (RBAC + JWT) e Convite."""
import secrets

from django.db import models
from django.db.models.functions import Lower

ROLE_ADMIN_SAAS = 'admin_saas'
ROLE_ADMIN_COMPANY = 'admin_company'
ROLE_OPERACIONAL = 'operacional'
ROLE_VIEWER = 'viewer'

ROLES = [
    (ROLE_ADMIN_SAAS, 'Admin SaaS'),
    (ROLE_ADMIN_COMPANY, 'Admin da empresa'),
    (ROLE_OPERACIONAL, 'Operacional'),
    (ROLE_VIEWER, 'Somente leitura'),
]

ROLES_DE_TENANT = (ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL, ROLE_VIEWER)
# Tudo que não é viewer pode editar (admin_saas inclui — o dono da plataforma).
ROLES_QUE_EDITAM = (ROLE_ADMIN_SAAS, ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL)


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
        tenant.token_captura = secrets.token_urlsafe(18)
        tenant.save(update_fields=['token_captura'])
    return tenant.token_captura


class Usuario(models.Model):
    """Usuario do sistema. Roles: admin_saas (plataforma) e, por tenant, admin_company/operacional/viewer."""

    nome = models.TextField()
    email = models.TextField(unique=True)
    senha = models.TextField()  # hash (django.contrib.auth.hashers)
    role = models.TextField(choices=ROLES)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        db_column='tenant_id',
        null=True,
        blank=True,
        related_name='usuarios',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios'
        ordering = ['id']
        indexes = [
            models.Index(Lower('email'), name='usuario_email_lower_idx'),
        ]

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
