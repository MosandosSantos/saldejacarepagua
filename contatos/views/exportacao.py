"""Exportacao CSV (Fase E) — contatos e negocios do tenant."""

import csv
from datetime import date

from django.http import HttpResponse

from acesso.decorators import filtro_tenant, nicho_da_sessao, web_login_required
from contatos.models import Contato, Negocio
from contatos.views.helpers import _tenant_id
from core.dominio import SEG_FALLBACK, SEGS
from funil.models import etapa_map_do_tenant


def _resposta_csv(nome_arquivo):
    """Resposta CSV com BOM (Excel abre acentos corretamente)."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    resposta.write('\ufeff')
    return resposta


def _csv_seguro(valor):
    """Previne injeção de fórmula no Excel (CSV injection): célula iniciando com
    `=`, `+`, `-` ou `@` vira texto com apóstrofo inicial."""
    texto = str(valor or '')
    if texto.startswith(('=', '+', '-', '@')):
        return "'" + texto
    return texto


@web_login_required
def exportar_csv(request):
    """Exporta os contatos do tenant (com o negócio principal) em CSV."""
    contatos = (
        filtro_tenant(request, Contato.objects.all())
        .prefetch_related('tags', 'negocios')
        .order_by('id')
    )
    resposta = _resposta_csv(f'contatos-{date.today().isoformat()}.csv')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Nome', 'Empresa', 'Telefone', 'E-mail', 'Segmento', 'Procedimento',
                'Última consulta', 'Origem', 'Pagamento', 'Cidade', 'Bairro', 'Observações',
                'Tags', 'Negócio principal', 'Etapa', 'Valor (R$)'])
    for c in contatos:
        principal = c.negocios.filter(principal=True).first() or c.negocios.first()
        w.writerow([
            _csv_seguro(c.nome), _csv_seguro(c.empresa), _csv_seguro(c.tel), _csv_seguro(c.email),
            _csv_seguro(SEGS.get(c.seg, SEG_FALLBACK)['label']),
            _csv_seguro(c.procedimento), _csv_seguro(c.ultima_consulta), _csv_seguro(c.origem),
            _csv_seguro(c.pagamento), _csv_seguro(c.cidade), _csv_seguro(c.bairro),
            _csv_seguro(c.observacoes),
            _csv_seguro(', '.join(t.nome for t in c.tags.all())),
            _csv_seguro(principal.titulo if principal else ''),
            _csv_seguro(principal.stage if principal else ''),
            _csv_seguro(str(principal.valor).replace('.', ',') if principal and principal.valor else ''),
        ])
    return resposta


@web_login_required
def exportar_negocios_csv(request):
    """Exporta os negócios (deals) do tenant em CSV."""
    negocios = filtro_tenant(request, Negocio.objects.select_related('contato')).order_by('id')
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    resposta = _resposta_csv(f'negocios-{date.today().isoformat()}.csv')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Contato', 'Negócio', 'Etapa', 'Valor (R$)', 'Principal', 'Criado em', 'Atualizado em'])
    for n in negocios:
        w.writerow([
            _csv_seguro(n.contato.nome),
            _csv_seguro(n.titulo),
            _csv_seguro(stage_map.get(n.stage, {'name': n.stage})['name']),
            _csv_seguro(str(n.valor).replace('.', ',')),
            'Sim' if n.principal else '',
            n.created_at.strftime('%d/%m/%Y'),
            n.updated_at.strftime('%d/%m/%Y'),
        ])
    return resposta
