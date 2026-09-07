"""Modelo para candidatos a admissão (Súplica)."""

import hashlib
import secrets

from django.db import models


class Candidato(models.Model):
    """Modelo para candidatos a admissão (Súplica)."""

    class Status(models.TextChoices):
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        FICHA_ENVIADA = 'FICHA_ENVIADA', 'Convite'
        EM_PREENCHIMENTO = 'EM_PREENCHIMENTO', 'Em preenchimento'
        EM_REVISAO = 'EM_REVISAO', 'Aguardando aprovação'
        APROVADO = 'APROVADO', 'Aprovado'
        INICIADO = 'INICIADO', 'Iniciado'
        REPROVADO = 'REPROVADO', 'Reprovado'
        DESISTIU = 'DESISTIU', 'Desistiu'
        DEVOLVIDO_CANDIDATO = 'DEVOLVIDO_CANDIDATO', 'Devolvido ao candidato'

    # Status que aparecem como card na coluna Suplica do kanban
    STATUS_KANBAN = (
        Status.EM_ANALISE,
        Status.FICHA_ENVIADA,
        Status.EM_PREENCHIMENTO,
        Status.EM_REVISAO,
        Status.DEVOLVIDO_CANDIDATO,
        Status.APROVADO,
    )
    COR_STATUS_KANBAN = {
        Status.EM_ANALISE: '#94a3b8',
        Status.FICHA_ENVIADA: '#fbbf24',
        Status.EM_PREENCHIMENTO: '#5b8def',
        Status.EM_REVISAO: '#4ade80',
        Status.DEVOLVIDO_CANDIDATO: '#f87171',
    }

    class Grau(models.TextChoices):
        MX = 'MX', 'Mestre de Mesa'
        EC = 'EC', 'Escudeiro Noviço'
        CBCS = 'CBCS', 'Cavaleiro da Rosa Cruz'

    class RevisaoAtual(models.TextChoices):
        DM = 'DM', 'Delegado Mestre'
        PREFEITO = 'PREFEITO', 'Prefeito'
        TESOUREIRO = 'TESOUREIRO', 'Tesoureiro'
        CHANCELER = 'CHANCELER', 'Chanceler'
        PRIOR = 'PRIOR', 'Grão Prior'
        CHANCELER_2 = 'CHANCELER_2', 'Chanceler II'
        DM_FINAL = 'DM_FINAL', 'Delegado Mestre Final'

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        related_name='candidatos',
    )

    # Dados pessoais
    nome_completo = models.CharField(max_length=200)
    cpf = models.CharField(max_length=14, blank=True, default='')
    data_nascimento = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True, default='')
    celular = models.CharField(max_length=15, blank=True, default='')
    telefone_urgencia = models.CharField(max_length=15, blank=True, default='')

    # Estrutura GPRB (obrigatórios)
    prefeitura = models.CharField(max_length=200, blank=True, default='')
    loja = models.CharField(max_length=200, blank=True, default='')

    # Endereço
    endereco_logradouro = models.CharField(max_length=200, blank=True, default='')
    endereco_numero = models.CharField(max_length=20, blank=True, default='')
    endereco_complemento = models.CharField(max_length=100, blank=True, default='')
    endereco_bairro = models.CharField(max_length=100, blank=True, default='')
    endereco_cidade = models.CharField(max_length=100, blank=True, default='')
    endereco_uf = models.CharField(max_length=2, blank=True, default='')
    endereco_cep = models.CharField(max_length=9, blank=True, default='')

    # Dados familiares
    pai = models.CharField(max_length=200, blank=True, default='')
    mae = models.CharField(max_length=200, blank=True, default='')
    natural_cidade = models.CharField(max_length=100, blank=True, default='')
    nacionalidade = models.CharField(max_length=50, blank=True, default='Brasileira')
    estado_civil = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('SOLTEIRO', 'Solteiro(a)'),
            ('CASADO', 'Casado(a)'),
            ('DIVORCIADO', 'Divorciado(a)'),
            ('VIUVO', 'Viúvo(a)'),
            ('UNIAO_ESTAVEL', 'União Estável'),
        ],
    )

    # Documentos
    identidade_numero = models.CharField(max_length=30, blank=True, default='')
    orgao_emissor = models.CharField(max_length=30, blank=True, default='')
    data_emissao = models.DateField(null=True, blank=True)

    # Ritualístico
    grau = models.CharField(
        max_length=4,
        choices=Grau.choices,
        default=Grau.MX,
    )

    # Loja simbólica
    loja_simbolo = models.CharField(max_length=200, blank=True, default='')
    numero_loja_simbolo = models.CharField(max_length=20, blank=True, default='')
    data_exaltacao = models.DateField(null=True, blank=True)
    potencia_simbolo = models.CharField(max_length=100, blank=True, default='')
    rito_loja_simbolo = models.CharField(max_length=100, blank=True, default='')

    # Documentos (uploads)
    foto = models.ImageField(upload_to='candidatos/fotos/%Y/%m/', null=True, blank=True)
    quitacao_url = models.FileField(upload_to='candidatos/quitacoes/%Y/%m/', null=True, blank=True)
    pagamento_url = models.FileField(upload_to='candidatos/pagamentos/%Y/%m/', null=True, blank=True)

    # Acesso ao portal
    access_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_used_at = models.DateTimeField(null=True, blank=True)
    password_hash = models.CharField(max_length=128, blank=True, default='')
    confirmation_code_hash = models.CharField(max_length=128, blank=True, default='')
    code_attempts = models.PositiveIntegerField(default=0)
    code_validated_at = models.DateTimeField(null=True, blank=True)

    # Workflow
    data_inscricao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.EM_ANALISE,
    )
    revisao_atual = models.CharField(
        max_length=20,
        choices=RevisaoAtual.choices,
        null=True,
        blank=True,
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_reprovacao = models.DateTimeField(null=True, blank=True)
    data_desistencia = models.DateTimeField(null=True, blank=True)
    data_inicio = models.DateTimeField(null=True, blank=True)

    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidatos_criados',
    )

    class Meta:
        db_table = 'candidato'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'cpf'],
                name='candidato_tenant_cpf_uniq',
                condition=models.Q(cpf__gt=''),
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f'{self.nome_completo} ({self.get_status_display()})'

    @property
    def get_cor_status(self):
        from .models import Candidato as _C
        return _C.COR_STATUS_KANBAN.get(self.status, '#94a3b8')

    @property
    def get_revisaocurrent_display(self):
        from .models import Candidato as _C
        if not self.revisao_atual:
            return '—'
        return dict(_C.RevisaoAtual.choices).get(self.revisao_atual, self.revisao_atual)

    def generate_access_token(self):
        """Gera token de acesso de 32 bytes."""
        self.access_token = secrets.token_hex(32)
        return self.access_token

    def get_token_hash(self):
        """Retorna hash SHA-256 do token."""
        if not self.access_token:
            return None
        return hashlib.sha256(self.access_token.encode()).hexdigest()


class CandidatoObservacao(models.Model):
    """Observação registrada durante o workflow de aprovação."""

    candidato = models.ForeignKey(
        Candidato,
        on_delete=models.CASCADE,
        related_name='observacoes',
    )
    autor_id = models.CharField(max_length=100)
    autor_nome = models.CharField(max_length=200)
    autor_papel = models.CharField(max_length=50)
    texto = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'candidato_observacao'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.autor_nome}: {self.texto[:50]}'
