"""Vínculo Usuario ↔ Membro: o número de cadastro do membro vira login."""

from django.db import migrations, models
import django.db.models.deletion


def vincular_por_email(apps, schema_editor):
    """Cada usuário recebe o membro do mesmo tenant com o mesmo e-mail.

    Contas sem correspondência (admin_saas, equipe comercial) ficam sem membro
    vinculado e seguem entrando por e-mail.
    """
    Usuario = apps.get_model('acesso', 'Usuario')
    Membro = apps.get_model('contatos', 'Membro')

    membros_por_tenant = {}
    for membro in Membro.objects.exclude(email='').only(
        'id', 'tenant_id', 'email',
    ):
        membros_por_tenant.setdefault((membro.tenant_id, membro.email.strip().lower()), membro)

    for usuario in Usuario.objects.exclude(email='').only('id', 'tenant_id', 'email'):
        chave = (usuario.tenant_id, usuario.email.strip().lower())
        membro = membros_por_tenant.get(chave)
        if membro is not None:
            Usuario.objects.filter(pk=usuario.pk).update(membro_id=membro.pk)


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0022_tenant_google_calendar_id'),
        ('contatos', '0029_membro_nome_historico'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='membro',
            field=models.OneToOneField(
                blank=True,
                help_text=('Membro cujo número de cadastro serve de login ao usuário '
                           '(None = contas administrativas entram por e-mail)'),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='usuario',
                to='contatos.membro',
            ),
        ),
        migrations.RunPython(vincular_por_email, migrations.RunPython.noop),
    ]
