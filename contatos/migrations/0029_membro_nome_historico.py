# 0029 — Nome simbólico/histórico do membro (avatar de um vulto da história).
# Campos novos ganham um nome aleatório da lista; já preenchidos são mantidos.

import random

from django.db import migrations, models

VULTOS_HISTORICOS = [
    'Dom Pedro I', 'Dom Pedro II', 'Dom João VI', 'José Bonifácio',
    'Tiradentes', 'Marechal Deodoro', 'Floriano Peixoto', 'Princesa Isabel',
    'Anita Garibaldi', 'Giuseppe Garibaldi', 'Simón Bolívar',
    'George Washington', 'Benjamin Franklin', 'Abraham Lincoln',
    'Thomas Jefferson', 'Napoleão Bonaparte', 'Alexandre, o Grande',
    'Júlio César', 'Marco Aurélio', 'Cícero', 'Espartaco', 'Leonidas',
    'Sócrates', 'Platão', 'Aristóteles', 'Pitágoras', 'Euclides',
    'Arquimedes', 'Galileu Galilei', 'Isaac Newton', 'René Descartes',
    'Voltaire', 'Rousseau', 'Montesquieu', 'Immanuel Kant', 'Goethe',
    'Viktor Frankl', 'Sigmund Freud', 'Carl Jung', 'Nikola Tesla',
    'Thomas Edison', 'Albert Einstein', 'Leonardo da Vinci',
    'Michelangelo', 'Rafael Sanzio', 'Mozart', 'Ludwig van Beethoven',
    'Johann Sebastian Bach', 'Victor Hugo', 'Machado de Assis',
    'Joaquim Nabuco', 'Rui Barbosa', 'Castelo Branco', 'Duque de Caxias',
    'Osório', 'Tamandaré', 'Barão do Rio Branco', 'Getúlio Vargas',
    'Zumbi dos Palmares', 'Lourenço da Silva', 'Anne Frank',
    'Madre Teresa', 'Mahatma Gandhi', 'Nelson Mandela', 'Martin L. King',
    'Franklin D. Roosevelt', 'Winston Churchill', 'Charles Lindbergh',
    'Santos Dumont', 'Graf Zeppelin', 'Christopher Columbus',
    'Amerigo Vespucci', 'Fernão de Magalhães', 'Vasco da Gama',
    'Pedro Álvares Cabral', 'Fernando Torres', 'Marcus Cicero',
    'Seneca', 'Epicteto', 'Pitágoras de Samos', 'Hipócrates',
    'Paracelso', 'Thomas More', 'João Gutenberg', 'Abraão Lincoln',
    'Emanuel Swedenborg', 'Cristóvão Colombo', 'D. Afonso Henriques',
    'D. AfonsoVI', 'Saladino', 'Ricardo Coração de Leão',
    'Roberto Carlos', 'Hercule Poirot', 'Luís de Camões',
    'Miguel de Cervantes', 'William Shakespeare', 'Dante Alighieri',
    'Maquiavel', 'Baltasar Gracián', 'Confúcio', 'Lao Tsé', 'Buda',
    'Moisés', 'Salomão', 'José do Egito', 'Hirão Abife',
    'Adoniram', 'Nabucodonosor', 'Ciro, o Grande', 'Dario I',
    'Artaxerxes', 'Xerxes', 'Temístocles', 'Péricles',
    'Alexandre Severo', 'Constantino', 'Teodósio',
]


def _preencher_vultos(apps, schema_editor):
    """Dá a cada membro sem nome histórico um vulto aleatório sem repetição."""
    Membro = apps.get_model('contatos', 'Membro')
    alvos = list(Membro.objects.filter(nome_historico='').order_by('id'))
    if not alvos:
        return
    vultos = list(VULTOS_HISTORICOS)
    random.shuffle(vultos)
    # Com mais membros que vultos, cycling: reembaralha e continua.
    gerador = (
        v for _ in range(max(1, (len(alvos) // len(vultos)) + 1))
        for v in (random.sample(vultos, len(vultos)))
    )
    for membro in alvos:
        membro.nome_historico = next(gerador)[:120]
        membro.save(update_fields=['nome_historico'])


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0028_membro_cadastro_numero'),
    ]

    operations = [
        migrations.AddField(
            model_name='membro',
            name='nome_historico',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Nome simbólico do membro: vulto histórico que o motiva '
                    '(ex.: "Dom Pedro I", "Anne Frank"). Serve como avatar pessoal.'
                ),
                max_length=120,
            ),
        ),
        migrations.RunPython(_preencher_vultos, migrations.RunPython.noop),
    ]
