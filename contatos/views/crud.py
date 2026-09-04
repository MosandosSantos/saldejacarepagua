"""Views de CRUD de contatos — listar, detalhe, novo, editar, excluir e leads pobres."""

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    e_admin_do_tenant,
    filtro_tenant,
    nicho_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from automacoes.engine import disparar
from contatos.forms import ContatoForm, NotaForm
from contatos.models import Carteira, Contato, Movimentacao, criar_negocio, registrar_movimentacao
from contatos.scoring import completude_do_contato, atualizar_score
from contatos.views.campos import (
    _campos_com_valores,
    _campos_do_tenant,
    _validar_valores_campos,
    _salvar_valores_campos,
    _valores_para_ficha,
)
from contatos.views.helpers import (
    CAMPOS_FORA_DO_LOOP,
    _brl,
    _decorar,
    _decorar_nota,
    _iniciais,
    _tags_do_tenant,
    _tags_marcadas,
    _tenant_id,
)
from contatos.views.notas_tags import _aplicar_nova_tag
from funil.models import etapa_map_do_tenant


@web_login_required
def lista(request):
    """Lista de membros do banco GPRB — busca + filtros acumulativos
    (situacao/ativo, prefeitura, loja, estado, cidade, grau e anuidade).
    """
    from core.gprb import connect
    from django.core.paginator import Paginator
    from datetime import date

    def _limpar(texto):
        # Remove caracteres de encoding quebrado (U+FFFD) e espacos extras
        return (texto or '').replace('\ufffd', '').strip()

    hoje = date.today()
    ano_corrente = hoje.year
    em_q1 = hoje.month <= 3  # janeiro a marco = periodo de grace

    # ---- Filtros recebidos via GET (todos acumulam) ----
    termo = request.GET.get('q', '').strip()
    situacao = request.GET.get('situacao', '').strip().upper()
    if situacao not in ('ATIVO', 'INATIVO'):
        situacao = ''
    prefeitura_id = request.GET.get('prefeitura', '').strip()
    loja_id = request.GET.get('loja', '').strip()
    uf = request.GET.get('uf', '').strip().upper()
    cidade = _limpar(request.GET.get('cidade'))
    grau = request.GET.get('grau', '').strip().upper()
    anuidade = request.GET.get('anuidade', '').strip()
    if anuidade not in ('em_dia', 'atrasada', 'nunca'):
        anuidade = ''

    filtros_ativos = bool(termo or situacao or prefeitura_id or loja_id
                          or uf or cidade or grau or anuidade)

    # Query string atual (sem a pagina) para manter os filtros na paginacao
    qs_base = request.GET.copy()
    qs_base.pop('page', None)
    qs = qs_base.urlencode()

    def _categoria_anuidade(ultima):
        """Mesma regra dos chips da listagem -> categorias do filtro."""
        if ultima is None:
            return 'nunca'
        if ultima >= ano_corrente:
            return 'em_dia'
        return 'atrasada'  # inclui inadimplentes e o periodo de graca (Q1)

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        tid = cur.fetchone()[0]

        # --- Opcoes dos selects (filtros) ---
        cur.execute(
            'SELECT id, nome FROM prefeitura WHERE "tenantId" = %s ORDER BY nome',
            (tid,),
        )
        opcoes_prefeituras = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]

        cur.execute(
            'SELECT id, COALESCE("nomeFantasia", "lojaMX", \'Loja \' || numero::text) '
            'FROM loja WHERE "tenantId" = %s ORDER BY 2',
            (tid,),
        )
        opcoes_lojas = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT \"enderecoUf\" FROM member "
            "WHERE \"tenantId\" = %s AND \"enderecoUf\" IS NOT NULL "
            "AND \"enderecoUf\" <> '' ORDER BY 1",
            (tid,),
        )
        opcoes_ufs = [r[0] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT REPLACE(COALESCE(\"enderecoCidade\", ''), chr(65533), '') "
            "FROM member "
            "WHERE \"tenantId\" = %s "
            "AND REPLACE(COALESCE(\"enderecoCidade\", ''), chr(65533), '') <> '' "
            "ORDER BY 1",
            (tid,),
        )
        opcoes_cidades = [r[0] for r in cur.fetchall()]

        cur.execute(
            'SELECT DISTINCT c.abbreviation FROM member m '
            'JOIN class c ON m.class_id = c.id '
            'WHERE m."tenantId" = %s AND c.abbreviation IS NOT NULL '
            'AND c.abbreviation <> \'\' ORDER BY 1',
            (tid,),
        )
        opcoes_graus = [r[0] for r in cur.fetchall()]

        # --- Query principal (filtros acumulativos) ---
        where = 'WHERE t.code = %s'
        params = ['GPRB']
        if termo:
            where += ' AND (m."nomeCompleto" ILIKE %s OR m.email ILIKE %s OR m.celular ILIKE %s)'
            params.extend([f'%{termo}%', f'%{termo}%', f'%{termo}%'])
        if situacao == 'ATIVO':
            where += ' AND m.situacao = %s'
            params.append('ATIVO')
        elif situacao == 'INATIVO':
            where += " AND m.situacao IS DISTINCT FROM 'ATIVO'"
        if prefeitura_id:
            where += ' AND p.id = %s'
            params.append(prefeitura_id)
        if loja_id:
            where += ' AND m."lojaId" = %s'
            params.append(loja_id)
        if uf:
            where += ' AND m."enderecoUf" = %s'
            params.append(uf)
        if cidade:
            where += " AND REPLACE(COALESCE(m.\"enderecoCidade\", ''), chr(65533), '') = %s"
            params.append(cidade)
        if grau:
            where += ' AND c.abbreviation = %s'
            params.append(grau)

        # Dados paginados (com ultima anuidade paga)
        cur.execute(f'''
            SELECT m.id, m."nomeCompleto", m.email, m.celular, m.cpf,
                   m."enderecoCidade", m."enderecoUf", m.situacao,
                   c.name as classe, c.abbreviation as classe_abbr,
                   l."nomeFantasia", l.numero as loja_numero,
                   p.nome as prefeitura_nome, p.sigla as prefeitura_sigla,
                   m."createdAt",
                   (SELECT MAX(pp.year) FROM payment_status ps2
                    JOIN payment_period pp ON ps2."periodId" = pp.id
                    WHERE ps2."memberId" = m.id AND pp.type = 'ANNUAL'
                      AND ps2.status = 'PAID') as ultima_anuidade
            FROM member m
            JOIN tenant t ON m."tenantId" = t.id
            LEFT JOIN class c ON m.class_id = c.id
            LEFT JOIN loja l ON m."lojaId" = l.id
            LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
            {where}
            ORDER BY m."createdAt" DESC
        ''', params)
        todos = cur.fetchall()
    finally:
        conn.close()

    # Filtro de anuidade e aplicado sobre o resultado (regra identica aos chips)
    if anuidade:
        todos = [r for r in todos if _categoria_anuidade(r[15]) == anuidade]

    total = len(todos)
    page_num = request.GET.get('page', 1)
    paginator = Paginator(todos, 25)
    page_obj = paginator.get_page(page_num)

    membros = []
    for row in page_obj:
        ultima_anuidade = row[15]  # MAX(year) da ultima anuidade paga

        # Logica de cor da borda
        if ultima_anuidade is None:
            anuidade_cor = 'red'        # sem pagamento registrado
            anuidade_label = 'Não'
        elif ultima_anuidade >= ano_corrente:
            anuidade_cor = 'green'      # em dia ou adiantado
            anuidade_label = str(ultima_anuidade)
        elif ultima_anuidade == ano_corrente - 1 and em_q1:
            anuidade_cor = 'orange'     # atrasado mas em periodo de graca (Q1)
            anuidade_label = str(ultima_anuidade)
        else:
            anuidade_cor = 'red'        # inadimplente
            anuidade_label = str(ultima_anuidade)

        membros.append({
            'id': row[0],
            'nome': row[1] or '',
            'email': row[2] or '',
            'celular': row[3] or '',
            'cpf': row[4] or '',
            'cidade': row[5] or '',
            'uf': row[6] or '',
            'situacao': row[7] or '',
            'classe': row[8] or '',
            'classe_abbr': row[9] or '',
            'loja': row[10] or (f'Loja {row[11]}' if row[11] else '—'),
            'prefeitura': row[12] or row[13] or '—',
            'criado_em': row[14],
            'anuidade': anuidade_label,
            'anuidade_cor': anuidade_cor,
        })

    return render(request, 'contatos/lista.html', {
        'itens': membros,
        'q': termo,
        'page_obj': page_obj,
        'paginator': paginator,
        'mostrados': len(membros),
        'total': total,
        'eh_membros': True,
        # Estado dos filtros (para re-selecionar os selects)
        'situacao': situacao,
        'prefeitura': prefeitura_id,
        'loja': loja_id,
        'uf': uf,
        'cidade': cidade,
        'grau': grau,
        'anuidade': anuidade,
        'filtros_ativos': filtros_ativos,
        'opcoes_prefeituras': opcoes_prefeituras,
        'opcoes_lojas': opcoes_lojas,
        'opcoes_ufs': opcoes_ufs,
        'opcoes_cidades': opcoes_cidades,
        'opcoes_graus': opcoes_graus,
        'qs': qs,
    })


@web_login_required
def detalhe(request, pk):
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios__movimentacoes', 'negocios', 'tags'),
        pk=pk,
    )
    notas = [_decorar_nota(n) for n in contato.notas.select_related('autor').all()]
    negocios = [
        {
            'id': n.id,
            'titulo': n.titulo,
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
            'valor': _brl(n.valor),
            'principal': n.principal,
            'created_at': n.created_at,
            'qtd_movs': len(n.movimentacoes.all()),
        }
        for n in contato.negocios.all()
    ]
    movimentacoes = [
        {
            'de': stage_map.get(m.de_stage, {'name': m.de_stage, 'color': '#888'}) if m.de_stage else None,
            'para': stage_map.get(m.para_stage, {'name': m.para_stage, 'color': '#888'}),
            'negocio_titulo': m.negocio.titulo or contato.nome,
            'autor': m.autor.nome if m.autor else '—',
            'autor_iniciais': _iniciais(m.autor.nome if m.autor else ''),
            'created_at': m.created_at,
        }
        for m in (Movimentacao.objects.filter(negocio__contato=contato)
                  .select_related('negocio', 'autor')
                  .order_by('-created_at', '-id'))
    ]
    from emails.models import ModeloEmail
    from tarefas.models import PRIORIDADE_CORES

    tarefas = [
        {
            'id': t.id,
            'titulo': t.titulo,
            'prioridade': t.prioridade,
            'prioridade_cor': PRIORIDADE_CORES.get(t.prioridade, '#94a3b8'),
            'vencimento': t.vencimento,
            'atrasada': t.atrasada,
            'concluida': t.concluida,
            'concluida_em': t.concluida_em,
            'responsavel_nome': t.responsavel.nome if t.responsavel else '',
            'responsavel_iniciais': _iniciais(t.responsavel.nome if t.responsavel else ''),
        }
        for t in contato.tarefas.select_related('responsavel').order_by('concluida', 'vencimento', 'hora', 'id')
    ]

    return render(request, 'contatos/detalhe.html', {
        'contato': _decorar(contato, stage_map),
        'notas': notas,
        'negocios': negocios,
        'tarefas': tarefas,
        'movimentacoes': movimentacoes,
        'nota_form': NotaForm(),
        'campos_valores': _valores_para_ficha(contato),
        'modelos_email': [{'id': m.id, 'nome': m.nome} for m in filtro_tenant(request, ModeloEmail.objects.all())],
        'email_configurado': settings.EMAIL_CONFIGURADO,
    })


@web_login_required
@web_requer_edicao
def novo(request):
    nicho = nicho_da_sessao(request)
    campos = _campos_do_tenant(request)
    erros_campos = {}
    if request.method == 'POST':
        form = ContatoForm(request.POST, nicho=nicho, tenant_id=_tenant_id(request))
        erros_campos = _validar_valores_campos(request, campos)
        if form.is_valid() and not erros_campos:
            contato = form.save(commit=False)
            tid = _tenant_id(request)
            if tid is not None:
                contato.tenant_id = tid
            contato.save()
            form.save_m2m()
            _aplicar_nova_tag(request, contato)
            _salvar_valores_campos(request, contato, campos)
            negocio = criar_negocio(
                contato,
                stage=form.cleaned_data['stage'],
                valor=form.cleaned_data['valor'] or 0,
                tenant_id=tid,
            )
            registrar_movimentacao(negocio, '', negocio.stage, request.session.get('usuario_id'))
            # novo contato fica sob responsabilidade de quem cadastrou (metas por vendedor)
            if tid is not None:
                negocio.responsavel_id = request.session.get('usuario_id')
                negocio.save(update_fields=['responsavel'])
            disparar('contato_criado', tenant_id=tid, contato=contato, negocio=negocio)
            disparar('negocio_criado', tenant_id=tid, contato=contato, negocio=negocio)
            atualizar_score(contato)
            return redirect('contatos:detalhe', pk=contato.id)
    else:
        form = ContatoForm(nicho=nicho, tenant_id=_tenant_id(request))
    return render(request, 'contatos/formulario.html', {
        'form': form, 'titulo': 'Novo contato', 'editando': False,
        'tags_marcadas': _tags_marcadas(form),
        'campos_fora_do_loop': CAMPOS_FORA_DO_LOOP,
        'campos_personalizados': _campos_com_valores(request, campos, None, erros_campos),
    })


@web_login_required
@web_requer_edicao
def editar(request, pk):
    nicho = nicho_da_sessao(request)
    contato = get_object_or_404(
        filtro_tenant(request, Contato.objects.all()).prefetch_related('tags'), pk=pk
    )
    campos = _campos_do_tenant(request)
    erros_campos = {}
    if request.method == 'POST':
        form = ContatoForm(request.POST, instance=contato, nicho=nicho, tenant_id=_tenant_id(request))
        erros_campos = _validar_valores_campos(request, campos)
        if form.is_valid() and not erros_campos:
            negocio = getattr(contato, 'negocio', None)
            negocio_era_novo = negocio is None
            stage_antigo = negocio.stage if negocio else ''
            contato = form.save(commit=False)
            contato.save()
            form.save_m2m()
            _aplicar_nova_tag(request, contato)
            _salvar_valores_campos(request, contato, campos)
            tid = _tenant_id(request)
            if negocio is None:
                negocio = criar_negocio(contato, tenant_id=tid)
            negocio.stage = form.cleaned_data['stage']
            negocio.valor = form.cleaned_data['valor'] or 0
            negocio.titulo = contato.nome
            negocio.save()
            registrar_movimentacao(
                negocio, stage_antigo, negocio.stage, request.session.get('usuario_id')
            )
            if negocio_era_novo:
                disparar('negocio_criado', tenant_id=tid, contato=contato, negocio=negocio)
            elif stage_antigo != negocio.stage:
                disparar(
                    'negocio_movido',
                    tenant_id=tid,
                    contato=contato,
                    negocio=negocio,
                    de_etapa=stage_antigo,
                    para_etapa=negocio.stage,
                )
            if negocio.stage == 'fechado':
                from emails.servico import marcar_conversoes

                marcar_conversoes(contato)
            atualizar_score(contato)
            return redirect('contatos:detalhe', pk=contato.id)
    else:
        form = ContatoForm(instance=contato, nicho=nicho, tenant_id=_tenant_id(request))
    return render(request, 'contatos/formulario.html', {
        'form': form, 'titulo': 'Editar contato', 'editando': True, 'contato': contato,
        'tags_marcadas': _tags_marcadas(form),
        'campos_fora_do_loop': CAMPOS_FORA_DO_LOOP,
        'campos_personalizados': _campos_com_valores(request, campos, contato, erros_campos),
    })


@web_login_required
def excluir(request, pk):
    """Excluir contato — apenas admin (operacional nao pode remover)."""
    if not e_admin_do_tenant(request):
        return redirect('contatos:lista')
    stage_map = etapa_map_do_tenant(_tenant_id(request), nicho_da_sessao(request))
    contato = get_object_or_404(filtro_tenant(request, Contato.objects.all()), pk=pk)
    if request.method == 'POST':
        contato.delete()
        return redirect('contatos:lista')
    return render(request, 'contatos/excluir.html', {'contato': _decorar(contato, stage_map)})


@web_login_required
def leads_pobres(request):
    """Perfil dos leads (rico x pobre) — quem o time deve enriquecer.

    Agrupa os contatos por nível de completude (pobre / médio / rico) com a
    aba `?nivel=`. Cada card mostra o que falta no perfil e atalho para
    completar a ficha já com foco no primeiro campo ausente (`?focar=`).
    """
    tid = _tenant_id(request)
    nicho = nicho_da_sessao(request)
    stage_map = etapa_map_do_tenant(tid, nicho)
    contatos = (
        filtro_tenant(request, Contato.objects.all())
        .select_related('carteira')
        .prefetch_related('negocios', 'tags')
    )
    agrupados = {'pobre': [], 'medio': [], 'rico': []}
    for c in contatos:
        comp = completude_do_contato(c)
        negocio = getattr(c, 'negocio', None)
        agrupados[comp['nivel']].append({
            'id': c.id,
            'nome': c.nome,
            'tel': c.tel,
            'email': c.email,
            'empresa': c.empresa,
            'origem': c.origem,
            'created_at': c.created_at,
            'stage': stage_map.get(negocio.stage if negocio else '', {'name': '—', 'color': '#888'}),
            'valor': _brl(negocio.valor) if negocio else 'R$ 0,00',
            'completude': comp,
        })
    for lista in agrupados.values():
        lista.sort(key=lambda i: i['completude']['total'])
    nivel = request.GET.get('nivel', 'pobre')
    if nivel not in agrupados:
        nivel = 'pobre'
    tabs = {
        'pobre': {'rotulo': 'Pobre', 'cor': '#fb923c'},
        'medio': {'rotulo': 'Médio', 'cor': '#fbbf24'},
        'rico': {'rotulo': 'Completo', 'cor': '#7fe3c4'},
    }
    return render(request, 'contatos/leads_pobres.html', {
        'itens': agrupados[nivel],
        'total': len(agrupados[nivel]),
        'nivel': nivel,
        'nivel_opcoes': [
            {'chave': k, 'rotulo': tabs[k]['rotulo'], 'cor': tabs[k]['cor'],
             'qtd': len(agrupados[k])}
            for k in ('pobre', 'medio', 'rico')
        ],
        'cor_nivel': tabs[nivel]['cor'],
        'rotulo_nivel': tabs[nivel]['rotulo'],
    })


# ------------------------------------------------------------------
# Prefeituras GPRB
# ------------------------------------------------------------------

@web_login_required
def prefeituras(request):
    """Lista de prefeituras do banco GPRB."""
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        tid = cur.fetchone()[0]

        # KPIs
        cur.execute('SELECT COUNT(*) FROM prefeitura WHERE "tenantId" = %s', (tid,))
        total_pf = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM loja WHERE "tenantId" = %s', (tid,))
        total_lojas = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM member WHERE "tenantId" = %s', (tid,))
        total_membros = cur.fetchone()[0]

        # Listagem com contagem por classe (MX, EN, CBCS)
        cur.execute('''
            SELECT p.id, p.nome, p.regiao, p.prefeito, p.telefone,
                   COUNT(DISTINCT l.id) as total_lojas,
                   COUNT(DISTINCT m.id) as total_membros,
                   SUM(CASE WHEN c.abbreviation = 'MX' THEN 1 ELSE 0 END) as mx,
                   SUM(CASE WHEN c.abbreviation = 'EN' THEN 1 ELSE 0 END) as en,
                   SUM(CASE WHEN c.abbreviation = 'CBCS' THEN 1 ELSE 0 END) as cbcs
            FROM prefeitura p
            LEFT JOIN loja l ON l."prefeituraId" = p.id
            LEFT JOIN member m ON m."lojaId" = l.id AND m.situacao = 'ATIVO'
            LEFT JOIN class c ON m.class_id = c.id
            WHERE p."tenantId" = %s
            GROUP BY p.id, p.nome, p.regiao, p.prefeito, p.telefone
            ORDER BY p.nome
        ''', (tid,))
        prefeituras_list = [
            {
                'id': r[0], 'nome': r[1], 'regiao': r[2],
                'prefeito': r[3] or '—', 'telefone': r[4] or '—',
                'total_lojas': r[5], 'total_membros': r[6],
                'mx': r[7] or 0, 'en': r[8] or 0, 'cbcs': r[9] or 0,
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()

    return render(request, 'contatos/prefeituras.html', {
        'prefeituras': prefeituras_list,
        'total_pf': total_pf,
        'total_lojas': total_lojas,
        'total_membros': total_membros,
    })


@web_login_required
def prefeitura_lojas_json(request, pk):
    """Retorna JSON com lojas de uma prefeitura (para drill-down)."""
    from django.http import JsonResponse
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao,
                   COUNT(m.id) as membros,
                   SUM(CASE WHEN c.abbreviation = 'MX' THEN 1 ELSE 0 END) as mx,
                   SUM(CASE WHEN c.abbreviation = 'EN' THEN 1 ELSE 0 END) as en,
                   SUM(CASE WHEN c.abbreviation = 'CBCS' THEN 1 ELSE 0 END) as cbcs
            FROM loja l
            LEFT JOIN member m ON m."lojaId" = l.id AND m.situacao = 'ATIVO'
            LEFT JOIN class c ON m.class_id = c.id
            WHERE l."prefeituraId" = %s
            GROUP BY l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao
            ORDER BY l."nomeFantasia"
        ''', (pk,))
        lojas = [
            {
                'id': r[0], 'nome': r[1] or r[2] or f'Loja #{r[3]}',
                'loja_mx': r[2] or '', 'numero': r[3],
                'situacao': r[4], 'total_membros': r[5],
                'mx': r[6] or 0, 'en': r[7] or 0, 'cbcs': r[8] or 0,
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return JsonResponse({'lojas': lojas})


@web_login_required
def loja_membros_json(request, pk):
    """Retorna JSON com todos os membros de uma loja (para drill-down).

    Inclui ativos e inativos para calcular totais no footer da tabela.
    """
    from django.http import JsonResponse
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT m.id, m."nomeCompleto", c.abbreviation, c.name as classe_nome,
                   m.situacao, m."dataIniciacao"
            FROM member m
            LEFT JOIN class c ON m.class_id = c.id
            WHERE m."lojaId" = %s
            ORDER BY m.situacao, c.abbreviation, m."nomeCompleto"
        ''', (pk,))
        membros = [
            {
                'id': r[0], 'nome': r[1] or '',
                'classe': r[2] or '—', 'classe_nome': r[3] or '',
                'situacao': r[4] or '',
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return JsonResponse({'membros': membros})


@web_login_required
@web_requer_edicao
def prefeitura_nova(request):
    """Inclui uma nova prefeitura GPRB."""
    from core.gprb import coluna_existe, connect
    import uuid

    erro = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        sigla = request.POST.get('sigla', '').strip()
        regiao = request.POST.get('regiao', '').strip()
        prefeito = request.POST.get('prefeito', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()

        if not nome:
            erro = 'Informe o nome da prefeitura.'
        elif not regiao:
            erro = 'Informe a regiao.'
        else:
            conn = connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
                tid = cur.fetchone()[0]
                if coluna_existe(cur, 'prefeitura', 'email'):
                    cur.execute('''
                        INSERT INTO prefeitura (id, "tenantId", nome, sigla, regiao, prefeito, telefone, email, status, "createdAt", "updatedAt")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
                    ''', (str(uuid.uuid4()), tid, nome, sigla or None, regiao, prefeito or None, telefone or None, email or None))
                else:
                    cur.execute('''
                        INSERT INTO prefeitura (id, "tenantId", nome, sigla, regiao, prefeito, telefone, status, "createdAt", "updatedAt")
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
                    ''', (str(uuid.uuid4()), tid, nome, sigla or None, regiao, prefeito or None, telefone or None))
                conn.commit()
                return redirect('contatos:prefeituras')
            finally:
                conn.close()

    return render(request, 'contatos/prefeitura_nova.html', {'erro': erro})


@web_login_required
@web_requer_edicao
def prefeitura_editar(request, pk):
    """Edição de uma prefeitura GPRB."""
    from core.gprb import coluna_existe, connect
    conn = connect()
    try:
        cur = conn.cursor()
        tem_email = coluna_existe(cur, 'prefeitura', 'email')
        if tem_email:
            cur.execute('SELECT id, nome, sigla, regiao, prefeito, telefone, email FROM prefeitura WHERE id = %s', (pk,))
        else:
            cur.execute('SELECT id, nome, sigla, regiao, prefeito, telefone FROM prefeitura WHERE id = %s', (pk,))
        r = cur.fetchone()
        if r is None:
            from django.http import Http404
            raise Http404('Prefeitura nao encontrada')
        prefeitura = {'id': r[0], 'nome': r[1], 'sigla': r[2] or '', 'regiao': r[3], 'prefeito': r[4] or '', 'telefone': r[5] or '', 'email': r[6] or '' if tem_email else ''}

        erro = None
        sucesso = None
        if request.method == 'POST':
            nome = request.POST.get('nome', '').strip()
            sigla = request.POST.get('sigla', '').strip()
            prefeito = request.POST.get('prefeito', '').strip()
            telefone = request.POST.get('telefone', '').strip()
            email = request.POST.get('email', '').strip()
            if not nome:
                erro = 'Informe o nome da prefeitura.'
            else:
                if tem_email:
                    cur.execute('UPDATE prefeitura SET nome = %s, sigla = %s, prefeito = %s, telefone = %s, email = %s, "updatedAt" = NOW() WHERE id = %s',
                        (nome, sigla or None, prefeito or None, telefone or None, email or None, pk))
                else:
                    cur.execute('UPDATE prefeitura SET nome = %s, sigla = %s, prefeito = %s, telefone = %s, "updatedAt" = NOW() WHERE id = %s',
                        (nome, sigla or None, prefeito or None, telefone or None, pk))
                conn.commit()
                sucesso = 'Prefeitura atualizada com sucesso!'
                prefeitura.update({'nome': nome, 'sigla': sigla, 'prefeito': prefeito, 'telefone': telefone, 'email': email})
    finally:
        conn.close()

    return render(request, 'contatos/prefeitura_editar.html', {
        'prefeitura': prefeitura, 'erro': erro, 'sucesso': sucesso,
    })


@web_login_required
@web_requer_edicao
def prefeitura_excluir(request, pk):
    """Exclui uma prefeitura GPRB."""
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, nome FROM prefeitura WHERE id = %s', (pk,))
        r = cur.fetchone()
        if r is None:
            from django.http import Http404
            raise Http404('Prefeitura nao encontrada')
        prefeitura = {'id': r[0], 'nome': r[1]}

        cur.execute('SELECT COUNT(*) FROM loja WHERE "prefeituraId" = %s', (pk,))
        lojas = cur.fetchone()[0]

        erro = None
        if request.method == 'POST':
            if lojas > 0:
                erro = (f'Nao e possivel excluir a prefeitura: ha {lojas} '
                        f'loja(s) vinculada(s) a ela. Transfira as lojas '
                        'para outra prefeitura antes de excluir.')
            else:
                cur.execute('DELETE FROM prefeitura WHERE id = %s', (pk,))
                conn.commit()
                return redirect('contatos:prefeituras')
    finally:
        conn.close()

    return render(request, 'contatos/prefeitura_excluir.html', {
        'prefeitura': prefeitura, 'lojas': lojas, 'erro': erro,
    })


# ------------------------------------------------------------------
# Lojas GPRB
# ------------------------------------------------------------------

@web_login_required
def lojas(request):
    """Lista de lojas do banco GPRB."""
    from core.gprb import coluna_existe, connect
    termo = request.GET.get('q', '').strip()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        tid = cur.fetchone()[0]

        where = 'WHERE l."tenantId" = %s'
        params = [tid]
        if termo:
            where += ' AND (l."nomeFantasia" ILIKE %s OR l.numero::text ILIKE %s)'
            params.extend([f'%{termo}%', f'%{termo}%'])

        cur.execute(f'''SELECT COUNT(*) FROM loja l {where}''', params)
        total = cur.fetchone()[0]

        cur.execute(f'''
            SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                   l."enderecoCidade", l."enderecoUf", l.situacao,
                   p.nome as prefeitura_nome, p.regiao,
                   COUNT(DISTINCT m.id) as total_membros
            FROM loja l
            LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
            LEFT JOIN member m ON m."lojaId" = l.id
            {where}
            GROUP BY l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                     l."enderecoCidade", l."enderecoUf", l.situacao,
                     p.nome, p.regiao
            ORDER BY l."nomeFantasia"
        ''', params)
        lojas_list = [
            {
                'id': r[0], 'nome': r[1] or f'Loja {r[2]}', 'numero': r[2],
                'telefone': r[3] or '—', 'email': r[4] or '—',
                'cidade': r[5] or '', 'uf': r[6] or '',
                'situacao': r[7] or '',
                'prefeitura': r[8] or '—', 'regiao': r[9] or '',
                'total_membros': r[10],
            }
            for r in cur.fetchall()
        ]

        # Deputado Mestre por loja (coluna nova no GPRB — degrada sem ela)
        deputados = {}
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute(
                'SELECT l.id, dm."nomeCompleto" FROM loja l '
                'LEFT JOIN member dm ON dm.id = l."deputadoMestreId" ' + where,
                params,
            )
            deputados = {r[0]: r[1] for r in cur.fetchall()}
        for loja in lojas_list:
            loja['deputado_mestre'] = deputados.get(loja['id']) or '—'
    finally:
        conn.close()

    return render(request, 'contatos/lojas.html', {
        'lojas': lojas_list, 'q': termo, 'total': total,
    })


@web_login_required
def loja_detalhe(request, pk):
    """Detalhe de uma loja GPRB."""
    from core.gprb import coluna_existe, connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                   l."enderecoLogradouro", l."enderecoNumero", l."enderecoBairro",
                   l."enderecoCidade", l."enderecoUf", l."enderecoCep",
                   l.situacao, l."dataFundacao",
                   p.nome as prefeitura, p.regiao
            FROM loja l LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
            WHERE l.id = %s
        ''', (pk,))
        r = cur.fetchone()
        if r is None:
            from django.http import Http404
            raise Http404('Loja nao encontrada')
        loja = {
            'id': r[0], 'nome': r[1] or f'Loja {r[2]}', 'numero': r[2],
            'telefone': r[3] or '—', 'email': r[4] or '—',
            'endereco': r[5] or '', 'numero_end': r[6] or '', 'bairro': r[7] or '',
            'cidade': r[8] or '', 'uf': r[9] or '', 'cep': r[10] or '',
            'situacao': r[11] or '', 'fundacao': r[12],
            'prefeitura': r[13] or '—', 'regiao': r[14] or '',
        }
        cur.execute('''
            SELECT COUNT(DISTINCT m.id) FROM member m WHERE m."lojaId" = %s
        ''', (pk,))
        loja['total_membros'] = cur.fetchone()[0]

        # Deputado Mestre (coluna nova no GPRB — degrada sem ela)
        loja['deputado_mestre_id'] = ''
        loja['deputado_mestre'] = '—'
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('SELECT "deputadoMestreId" FROM loja WHERE id = %s', (pk,))
            dm_id = cur.fetchone()[0]
            if dm_id:
                loja['deputado_mestre_id'] = dm_id
                cur.execute('SELECT "nomeCompleto" FROM member WHERE id = %s', (dm_id,))
                dm = cur.fetchone()
                loja['deputado_mestre'] = dm[0] if dm else '—'
    finally:
        conn.close()
    return render(request, 'contatos/loja_detalhe.html', {'loja': loja})


@web_login_required
@web_requer_edicao
def loja_nova(request):
    """Inclui uma nova loja GPRB."""
    from core.gprb import connect
    import uuid

    erro = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        numero = request.POST.get('numero', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()
        prefeitura_id = request.POST.get('prefeitura', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        uf = request.POST.get('uf', '').strip()

        if not nome:
            erro = 'Informe o nome da loja.'
        else:
            conn = connect()
            try:
                cur = conn.cursor()
                cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
                tid = cur.fetchone()[0]
                cur.execute('''
                    INSERT INTO loja (id, "tenantId", "nomeFantasia", numero, telefone, email,
                        "prefeituraId", "enderecoCidade", "enderecoUf", situacao,
                        "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
                ''', (str(uuid.uuid4()), tid, nome, int(numero) if numero.isdigit() else None,
                      telefone or None, email or None, prefeitura_id or None,
                      cidade or None, uf or None))
                conn.commit()
                return redirect('contatos:lojas')
            finally:
                conn.close()

    # Carregar prefeituras para o select
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        tid = cur.fetchone()[0]
        cur.execute('SELECT id, nome, regiao FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        prefeituras = [{'id': r[0], 'nome': r[1], 'regiao': r[2]} for r in cur.fetchall()]
    finally:
        conn.close()

    return render(request, 'contatos/loja_nova.html', {'erro': erro, 'prefeituras': prefeituras})


@web_login_required
@web_requer_edicao
def loja_editar(request, pk):
    """Edicao de uma loja GPRB."""
    from core.gprb import coluna_existe, connect

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                   l."prefeituraId", l."enderecoCidade", l."enderecoUf", l.situacao
            FROM loja l WHERE l.id = %s
        ''', (pk,))
        r = cur.fetchone()
        if r is None:
            from django.http import Http404
            raise Http404('Loja nao encontrada')
        loja = {
            'id': r[0], 'nome': r[1] or '', 'numero': r[2] or '',
            'telefone': r[3] or '', 'email': r[4] or '',
            'prefeitura_id': r[5] or '', 'cidade': r[6] or '', 'uf': r[7] or '',
            'situacao': r[8] or '',
        }
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        tid = cur.fetchone()[0]
        cur.execute('SELECT id, nome, regiao FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        prefeituras = [{'id': pr[0], 'nome': pr[1], 'regiao': pr[2]} for pr in cur.fetchall()]
        cur.execute(
            'SELECT id, "nomeCompleto" FROM member '
            'WHERE "lojaId" = %s AND situacao = %s ORDER BY "nomeCompleto"',
            (pk, 'ATIVO'),
        )
        membros = [{'id': mr[0], 'nome': mr[1]} for mr in cur.fetchall()]

        # Deputado Mestre (coluna nova no GPRB — degrada sem ela)
        loja['deputado_mestre_id'] = ''
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('SELECT "deputadoMestreId" FROM loja WHERE id = %s', (pk,))
            dm_row = cur.fetchone()
            loja['deputado_mestre_id'] = (dm_row[0] or '') if dm_row else ''
    finally:
        conn.close()

    erro = None
    sucesso = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()
        prefeitura_id = request.POST.get('prefeitura', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        uf = request.POST.get('uf', '').strip()
        deputado_mestre = request.POST.get('deputado_mestre', '').strip()
        if not nome:
            erro = 'Informe o nome da loja.'
        else:
            conn = connect()
            try:
                cur = conn.cursor()
                if coluna_existe(cur, 'loja', 'deputadoMestreId'):
                    cur.execute('''
                        UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                            "prefeituraId" = %s, "enderecoCidade" = %s, "enderecoUf" = %s,
                            "deputadoMestreId" = %s, "updatedAt" = NOW()
                        WHERE id = %s
                    ''', (nome, telefone or None, email or None, prefeitura_id or None, cidade or None, uf or None,
                          deputado_mestre or None, pk))
                else:
                    cur.execute('''
                        UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                            "prefeituraId" = %s, "enderecoCidade" = %s, "enderecoUf" = %s,
                            "updatedAt" = NOW()
                        WHERE id = %s
                    ''', (nome, telefone or None, email or None, prefeitura_id or None, cidade or None, uf or None, pk))
                conn.commit()
                return redirect('contatos:lojas')
            finally:
                conn.close()

    return render(request, 'contatos/loja_editar.html', {
        'loja': loja, 'prefeituras': prefeituras, 'membros': membros,
        'erro': erro, 'sucesso': sucesso,
    })


@web_login_required
@web_requer_edicao
def loja_excluir(request, pk):
    """Exclui uma loja GPRB."""
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, "nomeFantasia", numero FROM loja WHERE id = %s', (pk,))
        r = cur.fetchone()
        if r is None:
            from django.http import Http404
            raise Http404('Loja nao encontrada')
        loja = {'id': r[0], 'nome': r[1] or f'Loja {r[2]}'}

        cur.execute('SELECT COUNT(*) FROM member WHERE "lojaId" = %s', (pk,))
        membros = cur.fetchone()[0]

        erro = None
        if request.method == 'POST':
            if membros > 0:
                erro = (f'Nao e possivel excluir a loja: ha {membros} '
                        f'membro(s) vinculado(s) a ela. Transfira os membros '
                        'para outra loja antes de excluir.')
            else:
                cur.execute('DELETE FROM loja WHERE id = %s', (pk,))
                conn.commit()
                return redirect('contatos:lojas')
    finally:
        conn.close()
    return render(request, 'contatos/loja_excluir.html', {
        'loja': loja, 'membros': membros, 'erro': erro,
    })


# ------------------------------------------------------------------
# CRUD de membros GPRB
# ------------------------------------------------------------------

def _buscar_membro_gprb(member_id):
    """Busca um membro pelo ID no banco GPRB — todos os campos da ficha."""
    from core.gprb import connect
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT m.id, m."nomeCompleto", m.email, m.celular, m.cpf,
                   m."enderecoLogradouro", m."enderecoNumero", m."enderecoComplemento",
                   m."enderecoBairro", m."enderecoCidade", m."enderecoUf", m."enderecoCep",
                   m.situacao, m."dataNascimento", m."dataAdmissao",
                   m."apresentacao_mx", m."apresentacao_ec", m."armadura_cbcs",
                   m.rito, m."numeroFiliado", m."tipoAdmissao", m.escolaridade,
                   m.nacionalidade, m."naturalCidade", m."estadoCivil", m.pai, m.mae,
                   m."identidadeNumero", m."orgaoEmissor", m."dataEmissao",
                   m."telefoneUrgencia", m."dataPassagem", m."dataElevacao", m."dataInstalacao",
                   m."dataIniciacao", m."potencia_simbolismo", m.cargo,
                   m."condicao_mensalidade", m."lojaId", m.class_id,
                   m."createdAt", m."updatedAt",
                   c.name as classe, c.abbreviation as classe_abbr,
                   l."nomeFantasia", l.numero as loja_numero,
                   p.nome as prefeitura_nome, p.sigla as prefeitura_sigla
            FROM member m
            LEFT JOIN class c ON m.class_id = c.id
            LEFT JOIN loja l ON m."lojaId" = l.id
            LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
            WHERE m.id = %s
        ''', (member_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            'id': row[0], 'nome': row[1] or '', 'email': row[2] or '',
            'celular': row[3] or '', 'cpf': row[4] or '',
            'endereco': row[5] or '', 'numero': row[6] or '',
            'complemento': row[7] or '', 'bairro': row[8] or '',
            'cidade': row[9] or '', 'uf': row[10] or '', 'cep': row[11] or '',
            'situacao': row[12] or '', 'data_nascimento': row[13],
            'data_admissao': row[14],
            'apresentacao_mx': row[15], 'apresentacao_ec': row[16],
            'armadura_cbcs': row[17],
            'rito': row[18] or '', 'cadastro_maconico': row[19] or '',
            'tipo_admissao': row[20] or '', 'escolaridade': row[21] or '',
            'nacionalidade': row[22] or '', 'naturalidade': row[23] or '',
            'estado_civil': row[24] or '', 'pai': row[25] or '', 'mae': row[26] or '',
            'identidade': row[27] or '', 'orgao_emissor': row[28] or '',
            'data_emissao': row[29],
            'telefone_urgencia': row[30] or '',
            'data_passagem': row[31], 'data_elevacao': row[32],
            'data_instalacao': row[33],
            'data_iniciacao': row[34],
            'potencia': row[35] or '', 'cargo': row[36] or '',
            'condicao': row[37] or '',
            'loja_id': row[38] or '', 'class_id': str(row[39]) if row[39] else '',
            'criado_em': row[40], 'atualizado_em': row[41],
            'classe': row[42] or '', 'classe_abbr': row[43] or '',
            'loja': row[44] or (f'Loja {row[45]}' if row[45] else '—'),
            'prefeitura': row[46] or row[47] or '—',
        }
    finally:
        conn.close()


@web_login_required
def membro_detalhe(request, pk):
    """Detalhe de um membro GPRB."""
    membro = _buscar_membro_gprb(pk)
    if membro is None:
        from django.http import Http404
        raise Http404('Membro não encontrado')
    return render(request, 'contatos/membro_detalhe.html', {'membro': membro})


@web_login_required
@web_requer_edicao
def membro_editar(request, pk):
    """Edição completa de um membro GPRB — ficha com todas as seções."""
    from datetime import datetime
    import uuid
    from core.gprb import connect

    def _iso(v):
        """Data -> YYYY-MM-DD para input type=date (colunas são timestamp)."""
        if not v:
            return ''
        if hasattr(v, 'strftime'):
            return v.strftime('%Y-%m-%d')
        return str(v)[:10]

    def _parse_data(v):
        v = (v or '').strip()
        if not v:
            return None
        try:
            return datetime.strptime(v, '%Y-%m-%d').date()
        except ValueError:
            return None

    membro = _buscar_membro_gprb(pk)
    if membro is None:
        from django.http import Http404
        raise Http404('Membro não encontrado')

    # Opções dos selects (lidas do GPRB)
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, name, abbreviation FROM class ORDER BY name')
        classes = [{'id': str(r[0]), 'name': r[1], 'abbr': r[2]} for r in cur.fetchall()]
        cur.execute(
            'SELECT id, COALESCE("nomeFantasia", "lojaMX", \'Loja \' || numero::text) '
            'FROM loja ORDER BY 2'
        )
        lojas = [{'id': str(r[0]), 'nome': r[1]} for r in cur.fetchall()]

        def _distintos(coluna):
            cur.execute(
                f'SELECT DISTINCT "{coluna}" FROM member '
                f'WHERE "{coluna}" IS NOT NULL AND "{coluna}" <> \'\' ORDER BY 1'
            )
            return [r[0] for r in cur.fetchall()]

        sugestoes = {
            'ritos': _distintos('rito'),
            'potencias': _distintos('potencia_simbolismo'),
            'cargos': _distintos('cargo'),
            'tipos_admissao': _distintos('tipoAdmissao'),
            'escolaridades': _distintos('escolaridade'),
            'estados_civis': _distintos('estadoCivil'),
        }
    finally:
        conn.close()

    erro = None
    sucesso = None
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            erro = 'Informe o nome do membro.'
        else:
            def _v(campo):
                return (request.POST.get(campo, '') or '').strip() or None

            campos_data = {
                'data_admissao': 'dataAdmissao',
                'data_nascimento': 'dataNascimento',
                'apresentacao_mx': 'apresentacao_mx',
                'apresentacao_ec': 'apresentacao_ec',
                'armadura_cbcs': 'armadura_cbcs',
                'data_emissao': 'dataEmissao',
                'data_passagem': 'dataPassagem',
                'data_elevacao': 'dataElevacao',
                'data_instalacao': 'dataInstalacao',
                'data_iniciacao': 'dataIniciacao',
            }
            valores = {}
            for chave_form, coluna in campos_data.items():
                raw = request.POST.get(chave_form, '').strip()
                valores[coluna] = _parse_data(raw)
                if raw and valores[coluna] is None:
                    erro = f'Data inválida no campo {chave_form.replace("_", " ").title()}.'
                    break

            if not erro:
                classe_val = _v('classe')
                try:
                    classe_val = uuid.UUID(classe_val) if classe_val else None
                except (ValueError, AttributeError):
                    erro = 'Classe selecionada inválida.'

            if not erro:
                conn = connect()
                try:
                    cur = conn.cursor()
                    cur.execute('''
                        UPDATE member SET
                            "nomeCompleto" = %s, email = %s, celular = %s, cpf = %s,
                            "telefoneUrgencia" = %s, situacao = %s, class_id = %s,
                            "lojaId" = %s, rito = %s, "numeroFiliado" = %s,
                            "tipoAdmissao" = %s, escolaridade = %s,
                            nacionalidade = %s, "naturalCidade" = %s, "estadoCivil" = %s,
                            pai = %s, mae = %s,
                            "identidadeNumero" = %s, "orgaoEmissor" = %s,
                            "enderecoLogradouro" = %s, "enderecoNumero" = %s,
                            "enderecoComplemento" = %s, "enderecoBairro" = %s,
                            "enderecoCidade" = %s, "enderecoUf" = %s, "enderecoCep" = %s,
                            "potencia_simbolismo" = %s, cargo = %s,
                            "condicao_mensalidade" = %s,
                            "dataAdmissao" = %s, "dataNascimento" = %s,
                            "apresentacao_mx" = %s, "apresentacao_ec" = %s,
                            "armadura_cbcs" = %s, "dataEmissao" = %s,
                            "dataPassagem" = %s, "dataElevacao" = %s,
                            "dataInstalacao" = %s, "dataIniciacao" = %s,
                            "updatedAt" = NOW()
                        WHERE id = %s
                    ''', (
                        nome, _v('email'), _v('celular'), _v('cpf'),
                        _v('telefone_urgencia'), _v('situacao') or 'ATIVO', classe_val,
                        _v('loja'), _v('rito'), _v('cadastro_maconico'),
                        _v('tipo_admissao'), _v('escolaridade'),
                        _v('nacionalidade'), _v('naturalidade'), _v('estado_civil'),
                        _v('pai'), _v('mae'),
                        _v('identidade'), _v('orgao_emissor'),
                        _v('endereco'), _v('numero'), _v('complemento'), _v('bairro'),
                        _v('cidade'), _v('uf'), _v('cep'),
                        _v('potencia'), _v('cargo'), _v('condicao'),
                        valores['dataAdmissao'], valores['dataNascimento'],
                        valores['apresentacao_mx'], valores['apresentacao_ec'],
                        valores['armadura_cbcs'], valores['dataEmissao'],
                        valores['dataPassagem'], valores['dataElevacao'],
                        valores['dataInstalacao'], valores['dataIniciacao'],
                        pk,
                    ))
                    conn.commit()
                    sucesso = 'Dados atualizados com sucesso!'
                    membro = _buscar_membro_gprb(pk)
                finally:
                    conn.close()

    # Prepara datas no formato YYYY-MM-DD para os inputs type=date
    for chave in ('data_admissao', 'data_nascimento', 'apresentacao_mx',
                  'apresentacao_ec', 'armadura_cbcs', 'data_emissao',
                  'data_passagem', 'data_elevacao', 'data_instalacao',
                  'data_iniciacao'):
        membro[chave] = _iso(membro.get(chave))

    return render(request, 'contatos/membro_editar.html', {
        'membro': membro, 'erro': erro, 'sucesso': sucesso,
        'classes': classes, 'lojas': lojas, 'sugestoes': sugestoes,
    })


@web_login_required
@web_requer_edicao
def membro_excluir(request, pk):
    """Exclui ou inativa um membro GPRB."""
    membro = _buscar_membro_gprb(pk)
    if membro is None:
        from django.http import Http404
        raise Http404('Membro não encontrado')

    if request.method == 'POST':
        acao = request.POST.get('acao', '')
        from core.gprb import connect
        conn = connect()
        try:
            cur = conn.cursor()
            if acao == 'inativar':
                cur.execute(
                    'UPDATE member SET situacao = %s, "updatedAt" = NOW() WHERE id = %s',
                    ('INATIVO', pk),
                )
            else:
                cur.execute('DELETE FROM member WHERE id = %s', (pk,))
            conn.commit()
        finally:
            conn.close()
        return redirect('contatos:lista')

    return render(request, 'contatos/membro_excluir.html', {'membro': membro})
