"""Service layer para importacao de leads via CSV.

Separa a logica de negocio (validacao, criacao em lote) do I/O HTTP.
Otimizado: imports no topo do modulo.
"""

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from automacoes.engine import disparar
from contatos.models import Contato, criar_negocio, registrar_movimentacao
from contatos.scoring import atualizar_score
from core.utils import parse_brl


@dataclass
class ImportResult:
    """Resultado da importacao."""
    criados: int = 0
    erros_linha: list[str] = field(default_factory=list)


class ImportValidationError(Exception):
    """Erro de validacao na importacao."""

    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__(erros)


class ImportService:
    """Orquestra a importacao de leads, sem conhecer HTTP.

    Responsabilidades (SRP):
      - Validar estrutura do CSV
      - Criar contatos + negocios em lote
      - Disparar side-effects
    """

    def importar_csv(
        self,
        conteudo: str,
        tenant_id: int,
        stage_map: dict,
        etapa_padrao: str,
        usuario_id: int | None = None,
    ) -> ImportResult:
        """Importa leads de um CSV e retorna o resultado.

        Raises:
            ImportValidationError: se o CSV for invalido.
        """
        reader = self._parse_csv(conteudo)
        return self._processar_linhas(reader, tenant_id, stage_map, etapa_padrao, usuario_id)

    def _parse_csv(self, conteudo: str) -> csv.DictReader:
        """Parse o conteudo CSV e valida estrutura."""
        reader = csv.DictReader(io.StringIO(conteudo))
        colunas = set(reader.fieldnames or [])

        if 'nome' not in colunas:
            raise ImportValidationError([
                f'O CSV precisa ter a coluna "nome". Colunas encontradas: {", ".join(colunas)}.'
            ])

        return reader

    def _processar_linhas(
        self,
        reader: csv.DictReader,
        tenant_id: int,
        stage_map: dict,
        etapa_padrao: str,
        usuario_id: int | None,
    ) -> ImportResult:
        """Processa todas as linhas do CSV em uma transacao."""
        resultado = ImportResult()

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                self._processar_linha(row, i, tenant_id, stage_map, etapa_padrao, usuario_id, resultado)

        return resultado

    def _processar_linha(
        self,
        row: dict,
        num_linha: int,
        tenant_id: int,
        stage_map: dict,
        etapa_padrao: str,
        usuario_id: int | None,
        resultado: ImportResult,
    ) -> None:
        """Processa uma unica linha do CSV."""
        dados = self._extrair_dados_linha(row)

        if not dados['nome']:
            resultado.erros_linha.append(f'Linha {num_linha}: nome vazio — ignorada.')
            return

        stage_key = self._resolver_stage(dados['stage'], stage_map, etapa_padrao)
        valor = self._parse_valor(dados['valor'])

        contato = self._criar_contato(dados, tenant_id)
        negocio = self._criar_negocio(contato, stage_key, valor, tenant_id, usuario_id)
        self._disparar_side_effects(contato, negocio, tenant_id)

        resultado.criados += 1

    def _extrair_dados_linha(self, row: dict) -> dict:
        """Extrai e normaliza dados de uma linha do CSV."""
        return {
            'nome': (row.get('nome') or '').strip(),
            'tel': (row.get('telefone') or row.get('tel') or '').strip(),
            'email': (row.get('email') or '').strip().lower(),
            'empresa': (row.get('empresa') or '').strip(),
            'origem': (row.get('origem') or '').strip(),
            'seg': (row.get('segmento') or row.get('seg') or '').strip(),
            'stage': (row.get('etapa') or '').strip(),
            'valor': (row.get('valor') or '0').strip(),
        }

    def _resolver_stage(self, stage: str, stage_map: dict, etapa_padrao: str) -> str:
        """Resolve a etapa do lead (usa padrao se invalida)."""
        return stage if stage in stage_map else etapa_padrao

    def _parse_valor(self, raw: str) -> Decimal:
        """Converte string BRL para Decimal."""
        if not raw:
            return Decimal(0)
        try:
            return parse_brl(raw)
        except (ValueError, ArithmeticError):
            return Decimal(0)

    def _criar_contato(self, dados: dict, tenant_id: int) -> Contato:
        """Cria o contato no banco."""
        return Contato.objects.create(
            nome=dados['nome'],
            tel=dados['tel'] or '—',
            email=dados['email'] or '—',
            empresa=dados['empresa'] or '',
            seg=dados['seg'],
            origem=dados['origem'] or 'Importacao',
            tenant_id=tenant_id,
        )

    def _criar_negocio(self, contato: Contato, stage: str, valor: Decimal, tenant_id: int, usuario_id: int | None):
        """Cria o negocio associado ao contato."""
        negocio = criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant_id)
        if usuario_id:
            negocio.responsavel_id = usuario_id
            negocio.save(update_fields=['responsavel'])
        registrar_movimentacao(negocio, '', stage, usuario_id)
        return negocio

    def _disparar_side_effects(self, contato: Contato, negocio, tenant_id: int) -> None:
        """Dispara automacoes e atualiza score."""
        disparar('contato_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        disparar('negocio_criado', tenant_id=tenant_id, contato=contato, negocio=negocio)
        atualizar_score(contato)
