"""Serviço de presença (lista de chamada) para eventos da Agenda de Sessões.

SRP: única responsabilidade é detalhar/atualizar a chamada de um evento e
calcular o percentual de presença de um membro. As permissões ficam na view
(quem pode chamar) — o serviço só enxerga dados. A fonte dos percentuais é a
mesma tabela `tarefas.PresencaEvento`, garantindo um único ponto da verdade.
"""
from django.db.models import Count, Q
from django.http import JsonResponse

from contatos.models import Membro
from core.gprb.members import irmaos_da_loja
from tarefas.models import PresencaEvento


class PresencaServico:
    """Fachada estática das operações da lista de chamada (dados puros)."""

    @staticmethod
    def _membros_da_loja(loja_id):
        """Membros ATIVOS vinculados à loja local identificada por loja_id."""
        valor = str(loja_id or '').strip()
        if not valor.isdigit():
            return Membro.objects.none()
        return (
            Membro.objects
            .filter(lojas__pk=int(valor), situacao='ATIVO')
            .distinct()
            .order_by('nome')
        )

    @staticmethod
    def _tenant_padrao():
        """Tenant canônico para espelhar irmãos do GPRB (sem vínculo local)."""
        from acesso.models import tenant_gprb

        tenant = tenant_gprb()
        return tenant.pk if tenant is not None else None

    @staticmethod
    def espelhar_irmao(tenant_id, irmao):
        """Localiza ou cria o espelho local de um irmão vindo do GPRB.

        Casamento por CPF e, na falta, por e-mail dentro do tenant — nunca
        duplica quem já existe. Devolve o `Membro` local (ou None sem tenant).
        """
        if tenant_id is None:
            tenant_id = PresencaServico._tenant_padrao()
        if tenant_id is None:
            return None
        cpf = (irmao.get('cpf') or '').strip()
        email = (irmao.get('email') or '').strip().lower()
        if cpf:
            espelho = Membro.objects.filter(tenant_id=tenant_id, cpf=cpf).first()
            if espelho is not None:
                return espelho
        if email:
            espelho = Membro.objects.filter(
                tenant_id=tenant_id, email__iexact=email,
            ).first()
            if espelho is not None:
                return espelho
        return Membro.objects.create(
            tenant_id=tenant_id,
            nome=irmao.get('nome') or 'Irmão',
            cpf=cpf,
            email=irmao.get('email') or '',
            celular=irmao.get('celular') or '',
            situacao='ATIVO',
        )

    @staticmethod
    def _presentes_dos_espelhos(evento, espelhos_por_gprb):
        """Estado da chamada indexado pelo id UUID do irmão no GPRB."""
        if not espelhos_por_gprb:
            return {}
        locais = {m.pk: gid for gid, m in espelhos_por_gprb.items()}
        estado = {
            p.membro_id: p.presente
            for p in PresencaEvento.objects.filter(
                evento=evento, membro_id__in=list(locais),
            )
        }
        return {gid: estado.get(pk) for gid, pk in locais.items()}

    @staticmethod
    def membros_da_loja(evento, tenant_id=None):
        """Detalha a lista de chamada: membros da loja + estado da presença.

        Loja local (id numérico) usa o vínculo Membro↔Loja; loja GPRB (UUID)
        lista os irmãos ativos do banco GPRB, espelhando no tenant para
        gravar a chamada. Devolve [{'id', 'nome', 'presente'}] — presente
        True/False quando já houver registro, None quando o membro ainda
        não foi chamado no evento.
        """
        valor = str(evento.loja_id or '').strip()
        if valor.isdigit():
            do_evento = {
                p.membro_id: p.presente
                for p in PresencaEvento.objects.filter(evento=evento)
            }
            return [
                {
                    'id': membro.pk,
                    'nome': membro.nome,
                    'presente': do_evento.get(membro.pk),
                }
                for membro in PresencaServico._membros_da_loja(valor)
            ]
        espelhos = {}
        linhas = []
        for irmao in irmaos_da_loja(valor):
            espelho = PresencaServico.espelhar_irmao(tenant_id, irmao)
            if espelho is not None:
                espelhos[irmao['id']] = espelho
            linhas.append({'id': irmao['id'], 'nome': irmao['nome'], 'presente': None})
        presentes = PresencaServico._presentes_dos_espelhos(evento, espelhos)
        for linha in linhas:
            if linha['id'] in presentes:
                linha['presente'] = presentes[linha['id']]
        return linhas

    @staticmethod
    def resposta_do_evento(evento, ok=False, tenant_id=None):
        """Payload JSON da chamada: dados do evento + membros com estado.

        `ok=True` marca uma gravação bem-sucedida (POST); leitura (GET) não
        precisa da flag.
        """
        return JsonResponse({
            'ok': ok,
            'evento': {
                'id': evento.pk,
                'titulo': evento.titulo,
                'loja_id': evento.loja_id,
                'data_inicio': evento.data_inicio.strftime('%Y-%m-%dT%H:%M'),
            },
            'membros': PresencaServico.membros_da_loja(evento, tenant_id=tenant_id),
        })

    @staticmethod
    def _pk_para_registro(evento, tenant_id, membro_ref, irmaos):
        """PK local de um item da chamada: id numérico direto ou UUID do GPRB.

        UUID espelha o irmão no tenant (cria o vínculo local na primeira
        chamada). Devolve None quando o item não resolve para ninguém.
        """
        texto = str(membro_ref or '').strip()
        if texto.isdigit():
            return int(texto)
        irmao = (irmaos or {}).get(texto)
        if irmao is None:
            for candidato in irmaos_da_loja(evento.loja_id):
                if candidato['id'] == texto:
                    irmao = candidato
                    break
        if irmao is None:
            return None
        espelho = PresencaServico.espelhar_irmao(tenant_id, irmao)
        return espelho.pk if espelho is not None else None

    @staticmethod
    def registrar_chamada(evento, presencas, usuario=None, tenant_id=None):
        """Grava a chamada em lote (idempotente, na mesma tabela auxiliar).

        `presencas` é [{'membro': pk|uuid, 'presente': bool}, ...];
        re-registrar atualiza o par (evento, membro) sem duplicar.
        """
        irmaos = {
            i['id']: i
            for i in irmaos_da_loja(evento.loja_id)
            if not str(evento.loja_id or '').strip().isdigit()
        }
        for item in presencas or []:
            # 'membro' e obrigatorio no item: sem ele nao ha o que registrar.
            membro_ref = item.get('membro')
            if not membro_ref:
                continue
            membro_pk = PresencaServico._pk_para_registro(
                evento, tenant_id, membro_ref, irmaos,
            )
            if membro_pk is None:
                continue
            presente = bool(item.get('presente', False))
            defaults = {'presente': presente}
            if usuario is not None:
                defaults['registrado_por'] = usuario
            PresencaEvento.objects.update_or_create(
                evento=evento, membro_id=membro_pk, defaults=defaults,
            )

    @staticmethod
    def percentuais(membros):
        """Percentual de presença por membro: presentes/total de chamadas.

        Devolve {pk: percentual} — None quando o membro não tem chamada
        registrada (exibição "—").
        """
        pks = [m.pk for m in membros]
        if not pks:
            return {}
        agrupado = PresencaEvento.objects.filter(membro_id__in=pks).values(
            'membro_id',
        ).annotate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True)),
        )
        bruto = {row['membro_id']: row for row in agrupado}
        return {
            m.pk: (
                round(bruto[m.pk]['presentes'] / bruto[m.pk]['total'] * 100)
                if m.pk in bruto else None
            )
            for m in membros
        }

    @staticmethod
    def percentuais_da_loja(membros, loja):
        """Percentual exato por membro, considerando apenas chamadas desta Loja."""
        membros = list(membros)
        pks = [m.pk for m in membros]
        if not pks:
            return {}
        agrupado = PresencaEvento.objects.filter(
            membro_id__in=pks,
            membro__tenant_id=loja.tenant_id,
            evento__loja_id=str(loja.pk),
        ).values(
            'membro_id',
        ).annotate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True)),
        )
        bruto = {row['membro_id']: row for row in agrupado}
        return {
            membro.pk: (
                bruto[membro.pk]['presentes'] / bruto[membro.pk]['total'] * 100
                if membro.pk in bruto else None
            )
            for membro in membros
        }
