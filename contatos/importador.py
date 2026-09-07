"""Importacao de contatos a partir de CSV — parse, normalizacao, deduplicacao e gravacao.

Fluxo: o usuario envia um CSV -> `parse_csv` devolve cabecalhos e linhas -> a view mostra
o mapeamento de colunas -> `importar_linhas` grava respeitando o tenant da sessao e
pulando duplicados por telefone/e-mail.
"""

import csv
import io
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from contatos.models import Contato, Tag
from contatos.services import criar_negocio_para_contato
from core.dominio import SEGS, STAGE_MAP, stages_do_nicho

# Campos importaveis: (campo no modelo, rotulo exibido no mapeamento)
CAMPOS_IMPORTAVEIS = [
    ('nome', 'Nome *'),
    ('empresa', 'Empresa'),
    ('tel', 'Telefone'),
    ('email', 'E-mail'),
    ('seg', 'Segmento'),
    ('stage', 'Etapa do funil'),
    ('valor', 'Valor (R$)'),
    ('procedimento', 'Procedimento'),
    ('ultima_consulta', 'Última consulta'),
    ('origem', 'Origem'),
    ('pagamento', 'Pagamento'),
    ('nascimento', 'Nascimento'),
    ('cpf', 'CPF'),
    ('cidade', 'Cidade'),
    ('bairro', 'Bairro'),
    ('observacoes', 'Observações'),
    ('cnpj', 'CNPJ'),
    ('razao_social', 'Razão social'),
    ('cnae', 'CNAE'),
    ('endereco', 'Endereço'),
    ('responsavel', 'Responsável'),
    ('cargo', 'Cargo'),
    ('tags', 'Tags (separadas por vírgula)'),
]

MAX_LINHAS = 20000
LIMITE_TAMANHO = 5 * 1024 * 1024  # 5 MB

COR_TAG_PADRAO = '#74b3c6'

# Apelidos aceitos para sugerir o mapeamento automatico (comparados sem acento/caixa)
ALIASES = {
    'nome': ['nome', 'cliente', 'paciente', 'nome completo', 'nome do cliente', 'nome do paciente'],
    'empresa': ['empresa', 'clinica', 'negocio', 'empresa/clinica'],
    'tel': ['telefone', 'tel', 'celular', 'whatsapp', 'fone', 'telefone/whatsapp', 'contato'],
    'email': ['email', 'e-mail', 'e mail', 'correio eletronico'],
    'seg': ['segmento', 'seg', 'especialidade', 'tipo'],
    'stage': ['etapa', 'etapa do funil', 'stage', 'status', 'fase'],
    'valor': ['valor', 'valor (r$)', 'preco', 'investimento'],
    'procedimento': ['procedimento', 'tratamento', 'servico', 'interesse'],
    'ultima_consulta': ['ultima consulta', 'ultima visita', 'data consulta'],
    'origem': ['origem', 'origem do contato', 'como conheceu'],
    'pagamento': ['pagamento', 'forma de pagamento', 'pagto'],
    'nascimento': ['nascimento', 'data de nascimento', 'data nascimento', 'nasc'],
    'cpf': ['cpf'],
    'cidade': ['cidade'],
    'bairro': ['bairro'],
    'observacoes': ['observacoes', 'obs', 'notas', 'comentarios'],
    'cnpj': ['cnpj'],
    'razao_social': ['razao social', 'razao'],
    'cnae': ['cnae', 'atividade'],
    'endereco': ['endereco', 'endereco completo', 'logradouro'],
    'responsavel': ['responsavel', 'contato responsavel'],
    'cargo': ['cargo', 'cargo do contato', 'funcao', 'posicao'],
    'tags': ['tags', 'etiquetas', 'marcadores'],
}


def _so_digitos(s):
    return re.sub(r'\D', '', s or '')


def normalizar_telefone(s):
    """Telefone em digitos puros (para deduplicacao)."""
    return _so_digitos(s)


def _sem_acento(s):
    s = unicodedata.normalize('NFD', s or '')
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().strip()


def normalizar_valor(s):
    """Converte '1.234,56', '1234,56', 'R$ 1.500,00' ou '1234.56' em Decimal (>= 0)."""
    t = re.sub(r'[^\d.,-]', '', str(s or '')).strip()
    if not t or t in ('-', '.'):
        return None
    if ',' in t and '.' in t:
        t = t.replace('.', '').replace(',', '.')
    elif ',' in t:
        t = t.replace(',', '.')
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    return d if d >= 0 else None


def normalizar_data(s):
    """Aceita dd/mm/aaaa e aaaa-mm-dd; devolve string ISO valida ou None."""
    t = (s or '').strip()
    if not t:
        return None
    m = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', t)
    if m:
        iso = f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    else:
        m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})', t)
        if not m:
            return None
        iso = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    try:
        date.fromisoformat(iso)
    except ValueError:
        return None  # data inexistente no calendario (ex.: 31/02/2020)
    return iso


def _mapa_stage(nicho, etapas=None):
    """Lookup sem acento (chave ou nome da etapa) -> chave, das etapas do tenant + padrao.

    `etapas` (opcional) são as etapas do pipeline do tenant (dicts key/name); quando
    ausente, usa as etapas padrão do nicho.
    """
    base = etapas if etapas is not None else stages_do_nicho(nicho)
    mapa = {}
    for s in base:
        mapa[_sem_acento(s['key'])] = s['key']
        mapa[_sem_acento(s['name'])] = s['key']
    for s in STAGE_MAP.values():
        mapa.setdefault(_sem_acento(s['key']), s['key'])
        mapa.setdefault(_sem_acento(s['name']), s['key'])
    return mapa


def normalizar_stage(valor, nicho='saude', etapas=None):
    """Nome ou chave de etapa -> chave canonica; desconhecido/vazio -> 'suplica'."""
    v = _sem_acento(valor)
    if not v:
        return 'suplica'
    return _mapa_stage(nicho, etapas).get(v, 'suplica')


def normalizar_seg(valor):
    """Rotulo ou chave de segmento -> chave canonica; desconhecido -> ''."""
    v = _sem_acento(valor)
    if not v:
        return ''
    for key, info in SEGS.items():
        if v == _sem_acento(key) or v == _sem_acento(info['label']):
            return key
    return ''


def parse_csv(dados, tem_cabecalho=True):
    """Le bytes de um CSV e devolve (cabecalhos, linhas).

    - Encoding: tenta UTF-8 (com BOM) e cai para Latin-1.
    - Delimitador: detectado automaticamente entre ';', ',' e tab.
    - Linhas vazias sao ignoradas; celulas ausentes sao completadas com ''.
    """
    texto = None
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            texto = dados.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if texto is None:
        raise ValueError('Encoding não reconhecido — use UTF-8 ou Latin-1.')

    amostra = texto[:4096]
    try:
        delim = csv.Sniffer().sniff(amostra, delimiters=';,\t').delimiter
    except csv.Error:
        delim = ';' if amostra.count(';') >= amostra.count(',') else ','

    linhas = [linha for linha in csv.reader(io.StringIO(texto), delimiter=delim)
              if any(cel.strip() for cel in linha)]
    if not linhas:
        raise ValueError('O arquivo está vazio.')

    if tem_cabecalho:
        cabecalhos = [h.strip() or f'Coluna {i + 1}' for i, h in enumerate(linhas[0])]
        linhas = linhas[1:]
        if not linhas:
            raise ValueError('O arquivo tem só o cabeçalho — nenhuma linha de dados.')
    else:
        cabecalhos = [f'Coluna {i + 1}' for i in range(len(linhas[0]))]

    if len(linhas) > MAX_LINHAS:
        raise ValueError(f'O arquivo tem {len(linhas)} linhas; o limite é {MAX_LINHAS}.')

    n = len(cabecalhos)
    linhas = [linha[:n] + [''] * (n - len(linha)) for linha in linhas]
    return cabecalhos, linhas


def _chaves_existentes(tenant_id):
    """Telefones (digitos) e e-mails ja cadastrados no tenant da sessao."""
    qs = Contato.objects.all()
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)
    chaves = set()
    for tel, email in qs.values_list('tel', 'email'):
        t = _so_digitos(tel)
        e = (email or '').strip().lower()
        if t:
            chaves.add(t)
        if e:
            chaves.add(e)
    return chaves


def importar_linhas(cabecalhos, linhas, mapeamento, tenant_id, nicho='saude',
                    etapas=None, pular_duplicadas=True, inicio_linhas=2, carteira_id=None):
    """Grava os contatos de um CSV conforme o mapeamento campo -> indice de coluna.

    `mapeamento`: dict {campo: indice_da_coluna}; indice ausente ou -1 = nao importar.
    `carteira_id` (opcional): carteira do tenant para associar os registros importados
    (Sprint 3 do PRD HAZON — 3.3.5). Ids de carteira de outro tenant sao descartados.
    Devolve: {'importados': n, 'duplicados': n, 'erros': n,
              'detalhes_erros': [(numero_da_linha, motivo), ...]}
    """
    def valor(linha, campo):
        idx = mapeamento.get(campo)
        if idx is None or idx < 0 or idx >= len(linha):
            return ''
        return (linha[idx] or '').strip()

    mapa_stage = _mapa_stage(nicho, etapas)
    seg_por_label = {}
    for key, info in SEGS.items():
        seg_por_label[_sem_acento(key)] = key
        seg_por_label[_sem_acento(info['label'])] = key

    existentes = _chaves_existentes(tenant_id)
    vistos = set()
    importados = duplicados = erros = 0
    detalhes_erros = []

    for i, linha in enumerate(linhas):
        numero_linha = i + inicio_linhas
        nome = valor(linha, 'nome')
        if not nome:
            erros += 1
            detalhes_erros.append((numero_linha, 'sem nome'))
            continue

        tel = normalizar_telefone(valor(linha, 'tel'))
        email = valor(linha, 'email').lower()
        colide = ((tel and tel in existentes) or (email and email in existentes)
                  or (tel and tel in vistos) or (email and email in vistos))
        if pular_duplicadas and colide:
            duplicados += 1
            if tel:
                vistos.add(tel)
            if email:
                vistos.add(email)
            continue

        v_valor = normalizar_valor(valor(linha, 'valor'))
        nasc_raw = valor(linha, 'nascimento')
        nascimento = normalizar_data(nasc_raw) if nasc_raw else None
        if nasc_raw and nascimento is None:
            erros += 1
            detalhes_erros.append((numero_linha, 'data de nascimento inválida'))
            continue
        stage_key = mapa_stage.get(_sem_acento(valor(linha, 'stage')), 'interessado')
        contato = Contato(
            nome=nome,
            empresa=valor(linha, 'empresa'),
            tel=valor(linha, 'tel'),
            email=valor(linha, 'email'),
            seg=seg_por_label.get(_sem_acento(valor(linha, 'seg')), ''),
            procedimento=valor(linha, 'procedimento'),
            ultima_consulta=valor(linha, 'ultima_consulta'),
            origem=valor(linha, 'origem'),
            pagamento=valor(linha, 'pagamento'),
            cpf=valor(linha, 'cpf'),
            cidade=valor(linha, 'cidade'),
            bairro=valor(linha, 'bairro'),
            observacoes=valor(linha, 'observacoes'),
            cnpj=valor(linha, 'cnpj'),
            razao_social=valor(linha, 'razao_social'),
            cnae=valor(linha, 'cnae'),
            endereco=valor(linha, 'endereco'),
            responsavel=valor(linha, 'responsavel'),
            cargo=valor(linha, 'cargo'),
        )
        if nascimento:
            contato.nascimento = nascimento
        if tenant_id is not None:
            contato.tenant_id = tenant_id
        if carteira_id is not None:
            # Associa à carteira escolhida (escopada ao tenant — id de outra empresa cai fora)
            from contatos.models import Carteira

            contato.carteira = Carteira.objects.filter(pk=carteira_id, tenant_id=tenant_id).first()
        contato.save()
        criar_negocio_para_contato(
            contato,
            stage=stage_key,
            valor=v_valor if v_valor is not None else Decimal(0),
            tenant_id=tenant_id,
        )

        for nome_tag in re.split(r'[,;]', valor(linha, 'tags')):
            nome_tag = nome_tag.strip()
            if nome_tag:
                tag, _ = Tag.objects.get_or_create(
                    nome=nome_tag[:40], tenant_id=tenant_id,
                    defaults={'cor': COR_TAG_PADRAO},
                )
                contato.tags.add(tag)

        importados += 1
        if tel:
            vistos.add(tel)
        if email:
            vistos.add(email)

    return {
        'importados': importados,
        'duplicados': duplicados,
        'erros': erros,
        'detalhes_erros': detalhes_erros,
    }


def sugerir_mapeamento(cabecalhos):
    """Tenta adivinhar a coluna de cada campo comparando os cabecalhos com ALIASES."""
    sugestoes = {}
    for campo, aliases in ALIASES.items():
        for i, h in enumerate(cabecalhos):
            if _sem_acento(h) in aliases and campo not in sugestoes:
                sugestoes[campo] = i
                break
    return sugestoes
