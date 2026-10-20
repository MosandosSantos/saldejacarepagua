"""Sonda temporária 8: membros vinculados a lojas de Capítulo e elegibilidade
para a coluna Grau 15 (detentores do 14 com 6+ meses do 14)."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils import timezone
from dateutil.relativedelta import relativedelta

from contatos.models import GrauMembro, Loja, Membro

hoje = timezone.localdate()
limite = hoje - relativedelta(months=6)

for loja in Loja.objects.filter(corpo='capitulo').order_by('nome'):
    membros = list(loja.membros.all())
    print(f"{loja.tenant} | {loja.nome} | membros vinculados: {len(membros)}")
    for m in membros:
        graus = list(
            GrauMembro.objects.filter(membro=m)
            .order_by('-grau__numero')
            .values_list('grau__numero', 'data')
        )
        max_grau = graus[0][0] if graus else None
        data14 = dict(graus).get(14)
        elegivel = (
            max_grau == 14 and data14 is not None and data14 <= limite
        )
        if max_grau in (14, 15, 16, 17):
            print(
                f"   {m.nome} ({m.situacao}) max={max_grau} "
                f"dt14={data14} elegivel_15={elegivel}",
            )
