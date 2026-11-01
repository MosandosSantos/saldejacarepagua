"""Eligibility calculations for member degree progression.

A member can belong to Lojas in more than one Potência. Presence is counted
over the member's Lojas within the requested tenant scope; for global
admins (``tenant_ids is None``) every linked Loja counts.
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from collections import Counter

from django.db.models import Count, Prefetch, Q
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from contatos.models import Filiacao, GrauMembro, Loja, Membro, Vale
from tarefas.models import PresencaEvento


def candidatos_grau_9(tenant_ids: list[int] | None, hoje: date | None = None):
    """Return active degree-8 members with old enough degree 4 and Vale presence.

    A member can belong to Lojas in more than one Potência. Presence is counted
    over the member's Lojas within the requested tenant scope; for global
    admins (``tenant_ids is None``) every linked Loja counts.
    """
    hoje = hoje or timezone.localdate()
    limite_grau_4 = hoje - relativedelta(months=6)
    if tenant_ids is not None and not tenant_ids:
        return []
    membros = Membro.objects.filter(situacao='ATIVO').prefetch_related(
        Prefetch(
            'graus',
            queryset=GrauMembro.objects.select_related('grau'),
        ),
        Prefetch('lojas', queryset=Loja.objects.all()),
    )

    historicos_validos = {}
    lojas_por_membro = {}
    for membro in membros.order_by('nome', 'pk'):
        graus = {
            historico.grau.numero: historico
            for historico in membro.graus.all()
        }
        if max(graus, default=None) != 8:
            continue
        grau_4 = graus.get(4)
        if grau_4 is None or grau_4.data >= limite_grau_4:
            continue
        lojas = list(membro.lojas.all())
        if not lojas:
            continue
        historicos_validos[membro.pk] = (membro, grau_4.data)
        lojas_por_membro[membro.pk] = [loja.pk for loja in lojas]

    if not historicos_validos:
        return []

    filtro_presencas = Q(pk__in=[])
    for membro_id, loja_ids in lojas_por_membro.items():
        if loja_ids:
            filtro_presencas |= Q(
                membro_id=membro_id,
                evento__loja_id__in=loja_ids,
            )

    if not filtro_presencas:
        return []

    chamadas_por_membro = {
        linha['membro_id']: linha
        for linha in PresencaEvento.objects.filter(filtro_presencas).values(
            'membro_id',
        ).annotate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True)),
        )
    }

    # O Vale do membro vem da Filiação (que ainda guarda o tenant).
    vales_por_tenant = dict(Vale.objects.values_list('tenant_id', 'nome'))

    candidatos = []
    for membro, data_grau_4 in historicos_validos.values():
        chamadas = chamadas_por_membro.get(membro.pk)
        if not chamadas:
            continue
        percentual = chamadas['presentes'] / chamadas['total'] * 100
        if percentual >= 50:
            tenant_vale = (
                Filiacao.objects.filter(membro=membro)
                .values_list('tenant_id', flat=True)
                .first()
            )
            candidatos.append(CandidatoGrau9(
                membro=membro,
                vale_nome=vales_por_tenant.get(tenant_vale, ''),
                data_grau_4=data_grau_4,
                presenca_percentual=percentual,
            ))
    return candidatos
