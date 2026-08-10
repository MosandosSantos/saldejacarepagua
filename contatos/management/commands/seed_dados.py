"""Carga de dados de demonstração/testes.

Semeia um volume realista para o tenant de destino: contatos, negócios em todas
as etapas do funil (com movimentações e notas), tarefas, carteiras, campanhas
(com e-mails enviados), discador (filas, scripts e chamadas), metas de vendedores
e automações.

Uso:
    python manage.py seed_dados
    python manage.py seed_dados --reset
    python manage.py seed_dados --total 100 --tenant clinica-aurora --reset
"""
import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from acesso.models import (
    ROLE_ADMIN_COMPANY,
    ROLE_OPERACIONAL,
    MetaVendedor,
    Tenant,
    Usuario,
)
from automacoes.models import Automacao, PassoAutomacao
from campanhas.models import Campanha
from contatos.models import (
    Carteira,
    Contato,
    Movimentacao,
    Negocio,
    Nota,
    Tag,
    criar_negocio,
)
from contatos.scoring import atualizar_score
from core.dominio import ORIGENS, PAGAMENTOS, SEGS, STAGES
from discador.models import Chamada, Fila, Script
from emails.models import EmailEnviado, ModeloEmail
from funil.models import garantir_etapas
from tarefas.models import Tarefa

# Etapas do pipeline na ordem do fluxo (base das cadeias de movimentação).
_NORMAIS = ['interessado', 'avaliacao_agendada', 'avaliacao_feita', 'orcamento', 'fechado']

# Peso de cada etapa na distribuição dos negócios principais (soma 100).
_PESOS_ETAPAS = {
    'interessado': 20,
    'avaliacao_agendada': 18,
    'avaliacao_feita': 17,
    'orcamento': 15,
    'fechado': 15,
    'perdido': 15,
}

# Faixa de valor (R$) por etapa — fecha mais alto, perdido mais baixo.
_VALORES = {
    'interessado': (0, 800),
    'avaliacao_agendada': (0, 1500),
    'avaliacao_feita': (300, 2500),
    'orcamento': (800, 6000),
    'fechado': (1200, 9000),
    'perdido': (200, 3000),
}

_PRIMEIROS = [
    'Maria', 'Ana', 'Julia', 'Fernanda', 'Camila', 'Patricia', 'Beatriz', 'Larissa',
    'Carolina', 'Renata', 'Juliana', 'Mariana', 'Aline', 'Bruna', 'Carla', 'Debora',
    'Fabiana', 'Gabriela', 'Helena', 'Isabela', 'Jessica', 'Kelly', 'Leticia', 'Luciana',
    'Marcela', 'Nathalia', 'Priscila', 'Raquel', 'Sabrina', 'Tatiane', 'Vanessa', 'Yasmin',
    'Joao', 'Pedro', 'Lucas', 'Gabriel', 'Rafael', 'Matheus', 'Felipe', 'Gustavo',
]
_SOBRENOMES = [
    'Silva', 'Santos', 'Oliveira', 'Souza', 'Lima', 'Pereira', 'Almeida', 'Costa',
    'Rodrigues', 'Ferreira', 'Gomes', 'Martins', 'Rocha', 'Ribeiro', 'Carvalho', 'Alves',
    'Nascimento', 'Araujo', 'Barbosa', 'Cardoso', 'Dias', 'Freitas', 'Lopes', 'Mendes',
    'Moreira', 'Moura', 'Nunes', 'Pinto', 'Ramos', 'Teixeira', 'Vieira', 'Campos',
    'Duarte', 'Farias', 'Fontes', 'Guimaraes', 'Monteiro', 'Peixoto', 'Xavier', 'Castro',
]

_CIDADES = ['São Paulo', 'Campinas', 'Santos', 'Ribeirão Preto', 'São José dos Campos',
            'Guarulhos', 'Osasco', 'Santo André', 'Sorocaba', 'Jundiaí']
_BAIRROS = ['Centro', 'Vila Mariana', 'Moema', 'Pinheiros', 'Tatuapé', 'Santana',
            'Jardins', 'Itaim Bibi', 'Perdizes', 'Alphaville']
_EMPRESAS = ['Studio Bella', 'OdontoMais', 'Prime Consultoria', 'Vida Ativa', 'Bem Estar',
             'Sorriso Perfeito', 'Nova Era Estética', 'Vitalle Saúde', 'Clínica Aurora']
_CARGOS = ['Gerente', 'Proprietária', 'Coordenadora', 'Sócia', 'Diretora']
_PROCEDIMENTOS = ['Limpeza de pele', 'Harmonização facial', 'Botox', 'Preenchimento labial',
                  'Depilação a laser', 'Clareamento dental', 'Implante dentário',
                  'Avaliação postural', 'Fisioterapia', 'Acompanhamento nutricional',
                  'Terapia', 'Check-up geral']
_NOTAS = [
    'Preferiu aguardar o contato do financeiro.',
    'Pediu orçamento por WhatsApp.',
    'Interessada em pacote de 5 sessões.',
    'Encaminhada pelo Dr. Carlos.',
    'Retornar após o dia 15 (pagamento).',
    'Reclamou do tempo de espera na última visita.',
    'Confirmou presença na avaliação.',
    'Solicitou reenvio do orçamento por e-mail.',
]

_CARTEIRAS = [
    ('Cobrança', 'Base de cobrança — débitos e renegociação'),
    ('Prospecção', 'Leads novos capturados por canal'),
    ('Retenção', 'Clientes antigos sem retorno recente'),
    ('Indicações', 'Clientes que vieram por indicação'),
    ('Ativos', 'Clientes ativos com recorrência'),
]

_TAGS = [
    ('VIP', '#f59e0b'),
    ('Retorno', '#60a5fa'),
    ('Indicação', '#4ade80'),
    ('Pendência', '#ef4444'),
    ('Novo', '#38bdf8'),
    ('Inativo', '#94a3b8'),
]

_TITULOS_TAREFAS = [
    'Ligar para retornar orçamento',
    'Enviar proposta por e-mail',
    'Agendar avaliação',
    'Confirmar consulta',
    'Reagendar consulta perdida',
    'Enviar lembrete de pagamento',
    'Pedir indicações',
    'Cobrar pendência financeira',
    'Enviar material do procedimento',
    'Follow-up pós-avaliação',
    'Renovar plano de fidelidade',
    'Atualizar dados cadastrais',
]

_CAMPANHAS = [
    ('Boas-vindas', 'E-mail de boas-vindas para novos contatos', 'email', True),
    ('Promoção de Inverno', 'Divulgação da campanha promocional da estação', 'email', True),
    ('Recall de consultas', 'Lembrete de consultas e retornos', 'whatsapp', True),
    ('Novidades da clínica', 'Anúncio de novos procedimentos', 'whatsapp', True),
    ('Telecobrança', 'Contato telefônico de pendências', 'telefone', True),
    ('Fidelização', 'Campanha de retorno de clientes antigos', 'telefone', False),
]

_MODELOS_EMAIL = [
    ('Boas-vindas', 'Seja bem-vinda(o), {{nome}}!',
     'Olá {{nome}}, é um prazer ter você com a gente. Conte com nossa equipe para o que precisar.'),
    ('Lembrete de consulta', 'Lembrete: sua consulta se aproxima',
     'Olá {{nome}}, passando pra lembrar do seu horário na {{empresa}}. Qualquer dúvida, é só chamar.'),
    ('Orçamento', 'Seu orçamento, {{nome}}',
     'Olá {{nome}}, segue o orçamento do procedimento {{procedimento}} no valor de R$ {{valor}}. Ficamos à disposição.'),
]

_SCRIPTS = [
    ('Cobrança amigável',
     'Roteiro para contato de cobrança com abordagem consultiva.',
     '1. Cumprimentar pelo nome e confirmar identidade\n'
     '- Bom dia! Falo com {nome}? Aqui é da Clínica Aurora.\n'
     '2. Contextualizar a pendência\n'
     '- Estamos ligando sobre o valor de R$ {valor}, referente a {procedimento}.\n'
     '3. Ouvir e negociar\n'
     '- Qual seria uma data viável para o senhor(a) regularizar?\n'
     '- Posso oferecer condições especiais para pagamento à vista.\n'
     '4. Fechar e registrar\n'
     '- Combinado então: retorno em {retorno}. Obrigado pela atenção!'),
    ('Prospecção de novos leads',
     'Roteiro para qualificar leads novos e agendar avaliação.',
     '1. Abrir com a origem do contato\n'
     '- Vi que você nos procurou pelo {origem}. Como podemos ajudar?\n'
     '2. Descobrir o interesse\n'
     '- O que te motivou a nos procurar? Já fez algum procedimento parecido?\n'
     '3. Oferecer a avaliação\n'
     '- Posso agendar uma avaliação gratuita com nossa equipe.\n'
     '4. Registrar o próximo passo\n'
     '- Vou anotar tudo aqui e confirmar seu horário por WhatsApp.'),
]

_AUTOMACOES = [
    ('Novo lead ganha follow-up', 'contato_criado', {},
     [('tarefa', {'titulo': 'Ligar para o novo lead', 'prioridade': 'media', 'vencimento_dias': 1})]),
    ('Orçamento enviado dispara e-mail', 'negocio_movido', {'para_etapa': 'orcamento'},
     [('email', {'modelo_id': 0})]),  # modelo_id preenchido após criar os modelos
    ('Negócio parado ganha nota', 'negocio_estagnado', {'dias': 7, 'etapa': ''},
     [('nota', {'texto': 'Negócio parado há 7 dias — retomar contato'})]),
]

_STATUS_CHAMADAS = (
    ['realizada'] * 30 + ['nao_atendeu'] * 20 + ['ocupado'] * 10 +
    ['retornar'] * 12 + ['sem_interesse'] * 10 + ['discada'] * 8 +
    ['acordo'] * 5 + ['erro'] * 5
)


def _sem_acento(s):
    """Remove acentos de uma string (para gerar e-mails sem caracteres especiais)."""
    mapa = {'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'é': 'e', 'ê': 'e', 'í': 'i',
            'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}
    return ''.join(mapa.get(c, c) for c in s.lower())


def _telefone():
    ddd = random.choice(['11', '19', '21', '31', '41', '51', '61'])
    num = f'{random.randint(10000000, 99999999)}'
    return f'({ddd}) {num[:5]}-{num[5:]}'


def _cpf():
    n = f'{random.randint(0, 99999999999):011d}'
    return f'{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}'


def _backdate(obj, quando):
    """Reescreve o created_at (auto_now_add) de um objeto já criado."""
    obj.__class__.objects.filter(pk=obj.pk).update(created_at=quando)


def _etapas_para(total):
    """Lista de etapas (chaves) distribuídas conforme os pesos, para `total` negócios."""
    etapas = []
    for chave, peso in _PESOS_ETAPAS.items():
        etapas.extend([chave] * round(total * peso / 100))
    chaves = [s['key'] for s in STAGES]
    while len(etapas) < total:
        etapas.append(random.choice(chaves))
    return etapas[:total]


def _valor_para(stage):
    lo, hi = _VALORES[stage]
    return Decimal(random.randint(lo, hi))


def _cadeia_movimentacoes(stage):
    """Passos (de_stage, para_stage) da trilha até a etapa final do negócio."""
    if stage == 'interessado':
        return []
    if stage in _NORMAIS:
        idx = _NORMAIS.index(stage)
        passos = [(_NORMAIS[i], _NORMAIS[i + 1]) for i in range(idx - 1)]
        return passos + [(_NORMAIS[idx - 1], stage)]
    # perdido — sai do orçamento
    passos = [(_NORMAIS[i], _NORMAIS[i + 1]) for i in range(len(_NORMAIS) - 2)]
    return passos + [(_NORMAIS[-2], stage)]


class Command(BaseCommand):
    help = ('Carga de dados de demonstração/testes: contatos, negócios em todas as etapas '
            'do funil, tarefas, carteiras, campanhas e dados de apoio.')

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='clinica-aurora',
                            help='Slug do tenant de destino (padrão: clinica-aurora).')
        parser.add_argument('--total', type=int, default=100,
                            help='Quantidade de contatos a semear (padrão: 100).')
        parser.add_argument('--reset', action='store_true',
                            help='Apaga os dados do tenant antes de semear.')

    def handle(self, *args, **options):
        random.seed(2026)  # carga determinística (mesmos dados a cada execução)
        slug = options['tenant']
        total = max(1, options['total'])

        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            tenant = Tenant.objects.create(
                nome='Empresa Aurora (demonstração)', slug=slug, nicho='saude')
            self.stdout.write(self.style.SUCCESS(f'Tenant "{slug}" criado.'))
        garantir_etapas(tenant.id, tenant.nicho)
        self._garantir_usuarios(tenant)

        if options['reset']:
            self._limpar(tenant)
            self.stdout.write(self.style.WARNING(f'Dados anteriores de "{slug}" removidos.'))

        agora = timezone.now()
        usuarios = list(tenant.usuarios.all())
        vendedores = [u for u in usuarios if u.role in (ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL)]
        admin = next((u for u in usuarios if u.role == ROLE_ADMIN_COMPANY), None)

        # Evita duplicar contatos/negócios em execuções sem --reset
        if not options['reset'] and Contato.objects.filter(tenant=tenant).exists():
            self.stderr.write(self.style.ERROR(
                f'O tenant "{slug}" já tem contatos. Reexecute com --reset para refazer a carga.'))
            return

        carteiras = self._seed_carteiras(tenant)
        tags = self._seed_tags(tenant)
        self.stdout.write(self.style.SUCCESS(f'Carteiras: {len(carteiras)} | Tags: {len(tags)}'))

        contatos = self._seed_contatos(tenant, total, carteiras, tags, vendedores, agora)
        self._seed_tarefas(tenant, contatos, usuarios, agora)
        self._seed_metas(tenant, vendedores)
        campanhas = self._seed_campanhas(tenant, agora)
        modelos = self._seed_modelos_email(tenant)
        self._seed_envios(tenant, campanhas, modelos, contatos, agora)
        self._seed_discador(tenant, carteiras, contatos, vendedores, agora)
        self._seed_automacoes(tenant, admin, modelos)

        self._resumo(tenant)

    # ------------------------------------------------------------------ apoio
    def _garantir_usuarios(self, tenant):
        padrao = [
            ('Admin SaaS', 'admin@esferacrm.com', 'admin_saas', None),
            ('Dona Aurora', 'dona@aurora.com', 'admin_company', tenant),
            ('Ana Souza', 'ana@aurora.com', 'operacional', tenant),
            ('Laura Leitura', 'laura@aurora.com', 'viewer', tenant),
        ]
        for nome, email, role, ten in padrao:
            Usuario.objects.get_or_create(
                email=email,
                defaults={'nome': nome, 'role': role, 'tenant': ten,
                          'senha': make_password('senha123')},
            )

    def _limpar(self, tenant):
        tenant.contatos.all().delete()  # cascata: negocios, notas, movimentacoes, envios, chamadas
        tenant.tarefas.all().delete()
        tenant.campanhas.all().delete()
        tenant.modelos_email.all().delete()
        tenant.scripts.all().delete()
        tenant.filas.all().delete()
        tenant.automacoes.all().delete()
        tenant.tags.all().delete()
        tenant.carteiras.all().delete()
        MetaVendedor.objects.filter(usuario__tenant=tenant).delete()

    # ------------------------------------------------------------ segmentos
    def _seed_carteiras(self, tenant):
        return [
            Carteira.objects.get_or_create(tenant=tenant, nome=nome, defaults={'descricao': desc})[0]
            for nome, desc in _CARTEIRAS
        ]

    def _seed_tags(self, tenant):
        return [
            Tag.objects.get_or_create(tenant=tenant, nome=nome, defaults={'cor': cor})[0]
            for nome, cor in _TAGS
        ]

    # -------------------------------------------------------------- contatos
    def _seed_contatos(self, tenant, total, carteiras, tags, vendedores, agora):
        etapas = _etapas_para(total)
        random.shuffle(etapas)
        criados = []

        for i, stage in enumerate(etapas):
            nome = f'{random.choice(_PRIMEIROS)} {random.choice(_SOBRENOMES)}'
            email = f'{_sem_acento(nome).replace(" ", ".")}@exemplo.com' if i % 10 != 0 else '—'
            tel = _telefone() if i % 12 != 0 else '—'
            rico = i % 3 != 0  # ~2/3 dos contatos com ficha enriquecida

            contato = Contato.objects.create(
                nome=nome,
                empresa=random.choice(_EMPRESAS) if rico else '—',
                tel=tel,
                email=email,
                seg=random.choice(list(SEGS)),
                procedimento=random.choice(_PROCEDIMENTOS) if i % 5 != 0 else '—',
                ultima_consulta=(agora - timedelta(days=random.randint(5, 180))).strftime('%d/%m/%Y')
                if i % 4 == 0 else '—',
                origem=random.choice(ORIGENS),
                pagamento=random.choice(PAGAMENTOS),
                nascimento=date(random.randint(1965, 2002), random.randint(1, 12), random.randint(1, 28))
                if rico else None,
                cpf=_cpf() if i % 3 != 0 else '',
                cidade=random.choice(_CIDADES) if rico else '',
                bairro=random.choice(_BAIRROS) if rico else '',
                observacoes=random.choice(_NOTAS) if i % 4 == 0 else '',
                cargo=random.choice(_CARGOS) if i % 4 == 0 else '',
                responsavel=random.choice([u.nome for u in vendedores]) if vendedores and i % 4 == 0 else '',
                carteira=random.choice(carteiras) if i % 6 != 0 else None,
                tenant=tenant,
            )
            criados.append(contato)

            contato_em = agora - timedelta(days=random.randint(1, 120))
            negocio_em = min(agora, contato_em + timedelta(days=random.randint(1, 45)))
            _backdate(contato, contato_em)

            negocio = criar_negocio(
                contato, stage=stage, valor=_valor_para(stage), tenant_id=tenant.id)
            _backdate(negocio, negocio_em)
            if vendedores and i % 4 != 0:
                negocio.responsavel_id = random.choice(vendedores).id
                negocio.save(update_fields=['responsavel'])

            self._registrar_movimentacoes(negocio, stage, vendedores, negocio_em, agora)

            if i % 2 == 0:
                for _ in range(random.randint(1, 2)):
                    nota = Nota.objects.create(
                        contato=contato,
                        autor_id=random.choice(vendedores).id if vendedores else None,
                        texto=random.choice(_NOTAS),
                    )
                    _backdate(nota, negocio_em - timedelta(days=random.randint(0, 20)))

            if i % 3 != 0:
                contato.tags.add(*random.sample(tags, k=random.randint(1, min(2, len(tags)))))

            # negócio secundário em ~1 em cada 7 contatos (vendas paralelas)
            if i % 7 == 0:
                s2 = random.choice([s['key'] for s in STAGES if s['key'] != stage])
                n2_em = min(agora, negocio_em + timedelta(days=random.randint(1, 30)))
                n2 = criar_negocio(
                    contato, stage=s2, valor=_valor_para(s2), tenant_id=tenant.id,
                    principal=False, titulo=f'{contato.nome} — recompra')
                _backdate(n2, n2_em)
                self._registrar_movimentacoes(n2, s2, vendedores, n2_em, agora)

            atualizar_score(contato)

        self.stdout.write(self.style.SUCCESS(
            f'Contatos: {len(criados)} | Negócios: {Negocio.objects.filter(tenant=tenant).count()}'))
        return criados

    def _registrar_movimentacoes(self, negocio, stage, vendedores, base, agora):
        # movimentações acontecem entre a criação do negócio e agora
        limite = max(1, (agora - base).days)
        for de, para in _cadeia_movimentacoes(stage):
            mov = Movimentacao.objects.create(
                negocio=negocio, de_stage=de, para_stage=para,
                autor_id=random.choice(vendedores).id if vendedores else None)
            _backdate(mov, min(agora, base + timedelta(days=random.randint(0, limite))))

    # --------------------------------------------------------------- tarefas
    def _seed_tarefas(self, tenant, contatos, usuarios, agora):
        hoje = timezone.localdate()
        vendedores = [u for u in usuarios if u.role in (ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL)]
        contatos_com_tel = [c for c in contatos if c.tel_normalizado]
        qtd = min(35, max(10, len(contatos) // 3))
        criadas = 0

        for i in range(qtd):
            titulo = random.choice(_TITULOS_TAREFAS)
            # garante variedade de vencimentos: atrasada, hoje e futura no início
            if i == 0:
                vencimento, concluida = hoje - timedelta(days=2), False
            elif i == 1:
                vencimento, concluida = hoje, False
            elif i == 2:
                vencimento, concluida = hoje + timedelta(days=1), False
            else:
                vencimento = hoje + timedelta(days=random.randint(-10, 15))
                concluida = random.random() < 0.3

            tarefa = Tarefa.objects.create(
                tenant=tenant,
                titulo=titulo,
                descricao='' if random.random() < 0.6 else random.choice(_NOTAS),
                contato=random.choice(contatos_com_tel) if contatos_com_tel else None,
                responsavel=random.choice(vendedores) if vendedores else None,
                prioridade=random.choice(['baixa', 'media', 'alta']),
                vencimento=vencimento,
                hora=time(random.randint(8, 18), random.choice([0, 15, 30, 45])) if i % 4 == 0 else None,
                concluida=concluida,
                concluida_em=timezone.now() if concluida else None,
                criado_por=random.choice(usuarios) if usuarios else None,
            )
            _backdate(tarefa, agora - timedelta(days=random.randint(0, 15)))
            criadas += 1

        self.stdout.write(self.style.SUCCESS(f'Tarefas: {criadas}'))

    # ------------------------------------------------------ metas vendedores
    def _seed_metas(self, tenant, vendedores):
        mes = timezone.localdate().replace(day=1)
        for v in vendedores:
            MetaVendedor.objects.get_or_create(
                usuario=v, mes=mes,
                defaults={'valor': Decimal(random.randint(25000, 60000))})

    # -------------------------------------------------------------- campanhas
    def _seed_campanhas(self, tenant, agora):
        criadas = []
        for i, (nome, desc, canal, ativa) in enumerate(_CAMPANHAS):
            campanha, _ = Campanha.objects.get_or_create(
                tenant=tenant, nome=nome,
                defaults={'descricao': desc, 'canal': canal, 'ativa': ativa})
            _backdate(campanha, agora - timedelta(days=random.randint(1, 30)))
            criadas.append(campanha)
        self.stdout.write(self.style.SUCCESS(f'Campanhas: {len(criadas)}'))
        return criadas

    def _seed_modelos_email(self, tenant):
        criados = []
        for nome, assunto, corpo in _MODELOS_EMAIL:
            modelo, _ = ModeloEmail.objects.get_or_create(
                tenant=tenant, nome=nome, defaults={'assunto': assunto, 'corpo': corpo})
            criados.append(modelo)
        return criados

    def _seed_envios(self, tenant, campanhas, modelos, contatos, agora):
        contatos_validos = [c for c in contatos if c.email and c.email != '—']
        if not contatos_validos or not modelos:
            self.stdout.write(self.style.SUCCESS('E-mails enviados: 0 (sem contatos com e-mail)'))
            return
        enviados = 0
        for campanha in campanhas:
            if campanha.canal != 'email':
                continue
            for contato in random.sample(contatos_validos, k=min(12, len(contatos_validos))):
                modelo = random.choice(modelos)
                enviado_em = agora - timedelta(days=random.randint(1, 15), hours=random.randint(0, 23))
                aberto = random.random() < 0.55
                cliques = random.randint(0, 4) if aberto else 0
                aberto_em = min(agora, enviado_em + timedelta(hours=random.randint(1, 48))) if aberto else None
                envio = EmailEnviado.objects.create(
                    tenant=tenant,
                    contato=contato,
                    modelo=modelo,
                    campanha=campanha,
                    assunto=modelo.assunto,
                    corpo=modelo.corpo,
                    destinatario=contato.email,
                    status=random.choice(['enviado'] * 6 + ['simulado'] * 2 + ['pendente'] * 1),
                    enviado_em=enviado_em,
                    aberto_em=aberto_em,
                    cliques=cliques,
                    ultimo_clique_em=min(agora, aberto_em + timedelta(days=random.randint(0, 4)))
                    if cliques and aberto_em else None,
                )
                _backdate(envio, enviado_em)
                enviados += 1
        self.stdout.write(self.style.SUCCESS(f'E-mails enviados: {enviados}'))

    # ---------------------------------------------------------------- discador
    def _seed_discador(self, tenant, carteiras, contatos, vendedores, agora):
        scripts = [
            Script.objects.get_or_create(tenant=tenant, nome=nome,
                                         defaults={'descricao': desc, 'conteudo': conteudo})[0]
            for nome, desc, conteudo in _SCRIPTS
        ]
        fila_cobranca = Fila.objects.get_or_create(
            tenant=tenant, nome='Cobrança',
            defaults={'descricao': 'Fila de cobrança da operação', 'carteira': carteiras[0],
                      'script': scripts[0], 'ordem': 'score'})[0]
        Fila.objects.get_or_create(
            tenant=tenant, nome='Prospecção',
            defaults={'descricao': 'Leads novos para qualificação', 'carteira': carteiras[1],
                      'script': scripts[1], 'ordem': 'score'})
        Fila.objects.get_or_create(
            tenant=tenant, nome='Ativos',
            defaults={'descricao': 'Clientes ativos para recall', 'carteira': carteiras[4],
                      'script': scripts[0], 'ordem': 'criacao_desc'})

        contatos_com_tel = [c for c in contatos if c.tel_normalizado]
        if not contatos_com_tel:
            self.stdout.write(self.style.SUCCESS('Chamadas: 0'))
            return
        chamadas = 0
        for _ in range(min(45, len(contatos_com_tel) * 2)):
            status = random.choice(_STATUS_CHAMADAS)
            retorno_em = (agora + timedelta(days=random.randint(1, 7))) if status == 'retornar' else None
            chamada = Chamada.objects.create(
                fila=fila_cobranca,
                contato=random.choice(contatos_com_tel),
                operador=random.choice(vendedores) if vendedores else None,
                status=status,
                observacao=random.choice(_NOTAS) if status in ('realizada', 'retornar') else '',
                retorno_em=retorno_em,
                tenant=tenant,
            )
            _backdate(chamada, agora - timedelta(days=random.randint(0, 20)))
            chamadas += 1
        self.stdout.write(self.style.SUCCESS(f'Scripts: {len(scripts)} | Filas: 3 | Chamadas: {chamadas}'))

    # -------------------------------------------------------------- automacoes
    def _seed_automacoes(self, tenant, admin, modelos):
        modelo_orcamento = next((m for m in modelos if m.nome == 'Orçamento'), None)
        for nome, trigger, parametros, passos in _AUTOMACOES:
            automacao, _ = Automacao.objects.get_or_create(
                tenant=tenant, nome=nome, trigger=trigger,
                defaults={'parametros': parametros, 'ativa': True, 'criado_por': admin})
            if not automacao.passos.exists():
                for ordem, (acao, params) in enumerate(passos):
                    if acao == 'email':
                        if modelo_orcamento is None:
                            continue  # sem modelo de orçamento, o passo de e-mail não faz sentido
                        params = dict(params, modelo_id=modelo_orcamento.id)
                    PassoAutomacao.objects.create(
                        automacao=automacao, ordem=ordem, acao=acao, parametros=params)
        self.stdout.write(self.style.SUCCESS(f'Automações: {Automacao.objects.filter(tenant=tenant).count()}'))

    # ----------------------------------------------------------------- resumo
    def _resumo(self, tenant):
        def contagem(model):
            return model.objects.filter(tenant=tenant).count()

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'Resumo da carga — "{tenant.slug}"'))
        self.stdout.write(f'  Contatos: {contagem(Contato)}')
        self.stdout.write(f'  Negócios: {contagem(Negocio)}')
        self.stdout.write(f'  Tarefas: {contagem(Tarefa)}')
        self.stdout.write(f'  Carteiras: {contagem(Carteira)}')
        self.stdout.write(f'  Campanhas: {contagem(Campanha)}')
        self.stdout.write(f'  E-mails enviados: {contagem(EmailEnviado)}')
        self.stdout.write(f'  Chamadas: {contagem(Chamada)}')
        self.stdout.write('')
        por_etapa = ', '.join(
            f'{e}: {Negocio.objects.filter(tenant=tenant, stage=e).count()}'
            for e in [s['key'] for s in STAGES])
        self.stdout.write(f'  Negócios por etapa — {por_etapa}')
        self.stdout.write(self.style.SUCCESS('Carga concluída. Senha padrão dos usuários: senha123'))
