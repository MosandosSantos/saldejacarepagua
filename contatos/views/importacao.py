"""Importacao de contatos via CSV — upload, mapeamento de colunas e relatorio."""

import csv

from django.http import HttpResponse
from django.shortcuts import render

from acesso.decorators import (
    nicho_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from contatos.importador import (
    CAMPOS_IMPORTAVEIS,
    LIMITE_TAMANHO,
    importar_linhas,
    parse_csv,
    sugerir_mapeamento,
)
from contatos.models import Carteira
from contatos.views.helpers import _tenant_id
from recepcao.models import etapas_do_tenant


def _coluna_post(request, campo):
    """Indice de coluna escolhido no mapeamento (ou -1 quando vazio)."""
    raw = request.POST.get(f'col_{campo}', '')
    return int(raw) if raw.isdigit() else -1


@web_login_required
@web_requer_edicao
def importar(request):
    """Importacao de contatos via CSV — fluxo em 3 etapas: upload -> mapeamento -> relatorio."""
    nicho = nicho_da_sessao(request)
    tid = _tenant_id(request)
    cabecalhos = request.session.get('import_cabecalhos')
    linhas = request.session.get('import_linhas')
    carteiras = (
        Carteira.objects.all() if tid is None else Carteira.objects.filter(tenant_id=tid)
    ).order_by('nome')
    ctx = {
        'etapa': 'upload',
        'campos': CAMPOS_IMPORTAVEIS,
        'erro_upload': None,
        'avisos': [],
        'carteiras': [{'id': c.id, 'nome': c.nome} for c in carteiras],
    }

    if request.method == 'POST':
        etapa = request.POST.get('etapa', '')
        if etapa == 'upload':
            arquivo = request.FILES.get('arquivo')
            if not arquivo:
                ctx['erro_upload'] = 'Selecione um arquivo CSV para enviar.'
            elif arquivo.size > LIMITE_TAMANHO:
                ctx['erro_upload'] = 'Arquivo muito grande (máximo 5 MB).'
            else:
                tem_cab = request.POST.get('tem_cabecalho') == 'on'
                try:
                    cabecalhos, linhas = parse_csv(arquivo.read(), tem_cabecalho=tem_cab)
                except ValueError as exc:
                    ctx['erro_upload'] = str(exc)
                else:
                    request.session['import_cabecalhos'] = cabecalhos
                    request.session['import_linhas'] = linhas
                    request.session['import_nome_arquivo'] = arquivo.name
                    request.session['import_tem_cabecalho'] = tem_cab
                    ctx['etapa'] = 'mapear'
        elif etapa == 'importar':
            if not cabecalhos or not linhas:
                ctx['avisos'].append('Os dados do arquivo expiraram — envie o CSV novamente.')
            else:
                mapeamento = {campo: _coluna_post(request, campo) for campo, _ in CAMPOS_IMPORTAVEIS}
                if mapeamento.get('nome', -1) < 0:
                    ctx['etapa'] = 'mapear'
                    ctx['erro_mapeamento'] = 'O campo "Nome" é obrigatório — selecione a coluna que contém os nomes.'
                else:
                    tem_cab = request.session.get('import_tem_cabecalho', True)
                    raw_cart = request.POST.get('carteira_id', '')
                    carteira_id = int(raw_cart) if raw_cart.isdigit() else None
                    relatorio = importar_linhas(
                        cabecalhos, linhas, mapeamento, tid,
                        nicho=nicho,
                        etapas=etapas_do_tenant(tid, nicho),
                        pular_duplicadas=request.POST.get('pular_duplicadas') == 'sim',
                        inicio_linhas=2 if tem_cab else 1,
                        carteira_id=carteira_id,
                    )
                    for chave in ('import_cabecalhos', 'import_linhas', 'import_nome_arquivo', 'import_tem_cabecalho'):
                        request.session.pop(chave, None)
                    ctx['etapa'] = 'relatorio'
                    ctx['relatorio'] = relatorio
    elif cabecalhos and linhas:
        # GET com dados pendentes -> volta para o mapeamento
        ctx['etapa'] = 'mapear'

    if ctx['etapa'] == 'mapear':
        sugestoes = sugerir_mapeamento(cabecalhos)
        ctx.update({
            'cabecalhos': cabecalhos,
            'linhas_preview': linhas[:5],
            'nome_arquivo': request.session.get('import_nome_arquivo', 'arquivo.csv'),
            'total_linhas': len(linhas),
            'campos_mapeamento': [
                {'campo': c, 'rotulo': r, 'sugerido': sugestoes.get(c, -1)}
                for c, r in CAMPOS_IMPORTAVEIS
            ],
            'carteira_escolhida': request.POST.get('carteira_id', ''),
        })

    return render(request, 'contatos/importar.html', ctx)


@web_login_required
def baixar_modelo(request):
    """Baixa um CSV modelo (com BOM, para o Excel abrir com acentos)."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="modelo_contatos.csv"'
    resposta.write('\ufeff')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Nome', 'Telefone', 'E-mail', 'Empresa', 'Segmento', 'Etapa do funil',
                'Valor (R$)', 'Procedimento', 'Origem', 'Pagamento', 'Cidade', 'Bairro',
                'Nascimento', 'Observações', 'Tags'])
    w.writerow(['Maria da Silva', '(11) 98888-7777', 'maria@exemplo.com', 'Empresa Aurora',
                'Estética', 'Interessado', '1500,00', 'Laser CO2', 'Instagram', 'Particular',
                'São Paulo', 'Pinheiros', '15/03/1990', 'Cliente indicada pela Ana.', 'VIP, Retorno'])
    return resposta
