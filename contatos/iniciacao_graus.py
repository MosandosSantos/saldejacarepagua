"""Eligibility calculations for member degree progression."""
from dataclasses import dataclass
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, Prefetch, Q
from django.utils import timezone

from contatos.models import GrauMembro, Loja, Membro, Vale
from tarefas.models import PresencaEvento


@dataclass(frozen=True)
class CandidatoGrau9:
    """A member who currently meets the requirements for degree 9."""

    membro: Membro
    vale_nome: str
    data_grau_4: date
    presenca_percentual: float


def candidatos_grau_9(tenant_ids: list[int] | None, hoje: date | None = None):
    """Return active degree-8 members with old enough degree 4 and Vale presence.

    Vale-wide presence includes recorded calls at every local Loja in the
    member's tenant. Call rows linked to a Loja from another tenant are ignored.
    """
    hoje = hoje or timezone.localdate()
    limite_grau_4 = hoje - relativedelta(months=6)
    membros = Membro.objects.filter(situacao='ATIVO').select_related(
        'tenant',
    ).prefetch_related(
        Prefetch(
            'graus',
            queryset=GrauMembro.objects.filter(
                tenant_id=F('membro__tenant_id'),
            ).select_related('grau'),
        ),
    )
    if tenant_ids is not None:
        if not tenant_ids:
            return []
        membros = membros.filter(tenant_id__in=tenant_ids)

    historicos_validos = {}
    membros_por_tenant = {}
    for membro in membros.order_by('nome', 'pk'):
        graus = {historico.grau.numero: historico for historico in membro.graus.all()}
        if max(graus, default=None) != 8:
            continue
        grau_4 = graus.get(4)
        if grau_4 is None or grau_4.data >= limite_grau_4:
            continue
        historicos_validos[membro.pk] = (membro, grau_4.data)
        membros_por_tenant.setdefault(membro.tenant_id, []).append(membro.pk)

    if not historicos_validos:
        return []

    vales_por_tenant = dict(Vale.objects.filter(
        tenant_id__in=membros_por_tenant,
    ).values_list('tenant_id', 'nome'))
    lojas_por_tenant = {}
    for tenant_id, loja_id in Loja.objects.filter(
        tenant_id__in=membros_por_tenant,
    ).values_list('tenant_id', 'pk'):
        lojas_por_tenant.setdefault(tenant_id, []).append(str(loja_id))

    filtro_presencas = Q(pk__in=[])
    for tenant_id, membro_ids in membros_por_tenant.items():
        loja_ids = lojas_por_tenant.get(tenant_id, [])
        if loja_ids:
            filtro_presencas |= Q(
                membro_id__in=membro_ids,
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

    candidatos = []
    for membro, data_grau_4 in historicos_validos.values():
        chamadas = chamadas_por_membro.get(membro.pk)
        if not chamadas:
            continue
        percentual = chamadas['presentes'] / chamadas['total'] * 100
        if percentual >= 50:
            candidatos.append(CandidatoGrau9(
                membro=membro,
                vale_nome=vales_por_tenant.get(
                    membro.tenant_id, membro.tenant.nome,
                ),
                data_grau_4=data_grau_4,
                presenca_percentual=percentual,
            ))
    return candidatos
