"""Adiciona a configuração do softphone (Discador) ao Tenant — PRD Sprint 5."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0009_alter_usuario_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='softphone_schema',
            field=models.CharField(choices=[('sip', 'SIP (MicroSIP e afins)'), ('tel', 'tel: (discador padrão)')], default='sip', help_text='Esquema de URI usado para iniciar a chamada no softphone', max_length=10),
        ),
        migrations.AddField(
            model_name='tenant',
            name='softphone_dominio',
            field=models.CharField(blank=True, default='', help_text='Domínio SIP (ex.: sip.empresa.com.br) usado quando o esquema é SIP', max_length=160),
        ),
    ]
