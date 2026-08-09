"""Adiciona os dados do PIX (Acordos) ao Tenant — PRD Sprint 6."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0010_tenant_softphone'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='pix_chave',
            field=models.CharField(blank=True, default='', help_text='Chave PIX da empresa (CPF/CNPJ/e-mail/telefone ou aleatória)', max_length=120),
        ),
        migrations.AddField(
            model_name='tenant',
            name='pix_recebedor',
            field=models.CharField(blank=True, default='', help_text='Nome do recebedor exibido no PIX', max_length=80),
        ),
        migrations.AddField(
            model_name='tenant',
            name='pix_cidade',
            field=models.CharField(blank=True, default='', help_text='Cidade do recebedor exibida no PIX', max_length=40),
        ),
    ]
