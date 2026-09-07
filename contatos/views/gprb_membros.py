"""Views de membros GPRB — detalhe, edicao, exclusao via repository."""
import uuid
from datetime import datetime

from django.http import Http404
from django.shortcuts import redirect, render

from acesso.decorators import web_login_required, web_requer_edicao
from repositories import gprb_repository as repo

# Mapping: campo_form -> coluna_GPRB
_CAMPOS_DATA = {
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


def _iso(v):
    """Data -> YYYY-MM-DD para input type=date."""
    if not v:
        return ''
    if hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    return str(v)[:10]


def _parse_data(v):
    """String -> date ou None."""
    v = (v or '').strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_campos_data(request):
    """Parse de todos os campos de data do POST. Retorna (valores_dict, erro_or_None)."""
    valores = {}
    for chave_form, coluna in _CAMPOS_DATA.items():
        raw = request.POST.get(chave_form, '').strip()
        valores[coluna] = _parse_data(raw)
        if raw and valores[coluna] is None:
            return None, f'Data invalida no campo {chave_form.replace("_", " ").title()}.'
    return valores, None


def _validar_classe(valor_str):
    """Valida e converte UUID da classe. Retorna (uuid_or_None, erro_or_None)."""
    if not valor_str:
        return None, None
    try:
        return uuid.UUID(valor_str), None
    except (ValueError, AttributeError):
        return None, 'Classe selecionada invalida.'


def _valor(campo, request):
    """Extrai valor limpo do POST (string vazia -> None)."""
    return (request.POST.get(campo, '') or '').strip() or None


def _construir_dados_membro(nome, request, valores, classe_val):
    """Monta o dict de dados para atualizar o membro no GPRB."""
    v = lambda campo: _valor(campo, request)
    return {
        '"nomeCompleto"': nome,
        'email': v('email'), 'celular': v('celular'), 'cpf': v('cpf'),
        '"telefoneUrgencia"': v('telefone_urgencia'),
        'situacao': v('situacao') or 'ATIVO',
        'class_id': classe_val, '"lojaId"': v('loja'),
        'rito': v('rito'), '"numeroFiliado"': v('cadastro_maconico'),
        '"tipoAdmissao"': v('tipo_admissao'), 'escolaridade': v('escolaridade'),
        'nacionalidade': v('nacionalidade'), '"naturalCidade"': v('naturalidade'),
        '"estadoCivil"': v('estado_civil'), 'pai': v('pai'), 'mae': v('mae'),
        '"identidadeNumero"': v('identidade'), '"orgaoEmissor"': v('orgao_emissor'),
        '"enderecoLogradouro"': v('endereco'), '"enderecoNumero"': v('numero'),
        '"enderecoComplemento"': v('complemento'), '"enderecoBairro"': v('bairro'),
        '"enderecoCidade"': v('cidade'), '"enderecoUf"': v('uf'),
        '"enderecoCep"': v('cep'),
        '"potencia_simbolismo"': v('potencia'), 'cargo': v('cargo'),
        '"condicao_mensalidade"': v('condicao'),
        '"dataAdmissao"': valores['dataAdmissao'],
        '"dataNascimento"': valores['dataNascimento'],
        '"apresentacao_mx"': valores['apresentacao_mx'],
        '"apresentacao_ec"': valores['apresentacao_ec'],
        '"armadura_cbcs"': valores['armadura_cbcs'],
        '"dataEmissao"': valores['dataEmissao'],
        '"dataPassagem"': valores['dataPassagem'],
        '"dataElevacao"': valores['dataElevacao'],
        '"dataInstalacao"': valores['dataInstalacao'],
        '"dataIniciacao"': valores['dataIniciacao'],
    }


def _preparar_membro_para_form(membro):
    """Converte datas do membro para YYYY-MM-DD (inputs type=date)."""
    for chave in _CAMPOS_DATA.values():
        membro[chave.replace('"', '')] = _iso(membro.get(chave))


@web_login_required
def membro_detalhe(request, pk):
    """Detalhe de um membro GPRB."""
    membro = repo.buscar_membro(pk)
    if membro is None:
        raise Http404('Membro nao encontrado')
    return render(request, 'contatos/membro_detalhe.html', {'membro': membro})


@web_login_required
@web_requer_edicao
def membro_editar(request, pk):
    """Edicao completa de um membro GPRB."""
    membro = repo.buscar_membro(pk)
    if membro is None:
        raise Http404('Membro nao encontrado')

    classes = repo.listar_classes()
    lojas = repo.listar_lojas_select()
    sugestoes = repo.sugestoes_membro()

    erro = None
    sucesso = request.GET.get('sucesso')
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            erro = 'Informe o nome do membro.'
        else:
            valores, erro = _parse_campos_data(request)
            if not erro:
                classe_val, erro = _validar_classe(_valor('classe', request))
            if not erro:
                dados = _construir_dados_membro(nome, request, valores, classe_val)
                repo.atualizar_membro(pk, dados)
                return redirect(f'{request.path}?sucesso=1')

    if membro:
        _preparar_membro_para_form(membro)

    return render(request, 'contatos/membro_editar.html', {
        'membro': membro, 'erro': erro, 'sucesso': sucesso,
        'classes': classes, 'lojas': lojas, 'sugestoes': sugestoes,
    })


@web_login_required
@web_requer_edicao
def membro_excluir(request, pk):
    """Exclui ou inativa um membro GPRB."""
    membro = repo.buscar_membro(pk)
    if membro is None:
        raise Http404('Membro nao encontrado')

    if request.method == 'POST':
        acao = request.POST.get('acao', '')
        if acao == 'inativar':
            repo.inativar_membro(pk)
        else:
            repo.excluir_membro(pk)
        return redirect('contatos:lista')

    return render(request, 'contatos/membro_excluir.html', {'membro': membro})
