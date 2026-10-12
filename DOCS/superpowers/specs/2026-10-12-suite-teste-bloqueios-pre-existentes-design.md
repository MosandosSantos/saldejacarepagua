# Bloqueios pré-existentes da suíte de testes (Django 6 + papéis aposentados)

**Date:** 2026-10-12
**Status:** Rascunho — aguardando revisão.

## Contexto

A suíte de testes do repositório não roda com a configuração padrão
(`pytest.ini` → `core.settings_vale_test`, `--reuse-db`). Ao validar a correção de
isolamento de Vale/kanban (`85a98f9`) foi preciso rodar pytest com
`-o addopts='' --no-migrations --create-db` para contornar bloqueios que **não têm
relação com aquela correção**. Este documento descreve esses bloqueios, as causas
e a proposta de correção, para serem tratados num trabalho à parte.

## Evidências

- `python manage.py migrate --noinput` do zero falha:
  `ValueError: Related model 'contatos.loja' cannot be resolved`
  (aplicando `agenda.0001_initial`; o mesmo erro aparece em `contatos.0017+`).
- `python manage.py check` passa (0 issues) — o problema é só no caminho de migrations.
- Banco de teste existente (`test_saldabritanea_vales`) estava desatualizado:
  só `contatos.0001_initial` aplicada (de 24 migrations locais de `contatos`).
- Vários módulos de teste não coletam: `ImportError: cannot import name
  'ROLE_GRANDE_PRIOR' from 'acesso.models'`.
- Falhas de teste que persistem com ou sem a correção `85a98f9` (confirmado
  revertendo-a): `test_kanban_views::test_mover_negocio_atualiza_stage`,
  `test_kanban_views::test_excluir_negocio`,
  `test_kanban_prefeitura::test_kanban_view_select_prefeitura_inclui_opcoes`,
  `test_vale_labels::test_prefeitura_entity_no_longer_uses_potencia_in_templates`.

## Causas-raiz e correções propostas

### A. Migrations referenciam modelos em minúsculas (quebra `migrate` no Django 6)

Migrations serializadas com o rótulo lowercase, que o Django 6.0.8 não resolve
via `StateApps`:

- `contatos/migrations/0017_loja_membro_locais.py` — `to='contatos.loja'` (2×)
- `contatos/migrations/0018_loja_pdf_required.py` — `to='contatos.loja'` (1×)
- `contatos/migrations/0023_filiacao_lojacargo_historicocargo_and_more.py` —
  `to='contatos.loja'` (3×) e `to='contatos.lojacargo'` (2×)
- `agenda/migrations/0001_initial.py` — `to='contatos.loja'` (1×)

**Correção:** capitalizar o nome do modelo nas referências
(`contatos.loja` → `contatos.Loja`, `contatos.lojacargo` → `contatos.LojaCargo`).
É uma troca semanticamente neutra (mesmo modelo), que só restaura a resolução do
nome.

**Riscos/observações:**
- `agenda/0001_initial.py` é um arquivo **já versionado** e provavelmente aplicado
  em ambientes existentes; como o Django não guarda checksum das migrations
  aplicadas, alterar a string não reexecuta nada nesses bancos e não muda o schema.
- `contatos/0016..0023` estão **não versionadas** (parte do WIP atual).
- Validação: `makemigrations --check`, `migrate` em banco descartável e a suíte.

### B. Papéis aposentados/renomeados nos testes

- `ROLE_GRANDE_PRIOR` foi removido; a migração de dados `acesso.0020_rename_roles`
  mapeia `grande_prior → ADM`. Hoje existe `ROLE_ADM`.
- Arquivos que importam/usam `ROLE_GRANDE_PRIOR`:
  `teste/test_potencia_web.py`, `teste/test_vale_templates.py`,
  `teste/test_vale_archive.py`, `teste/test_loja_local.py`,
  `teste/test_membro_local.py`, `teste/test_loja_pdf_local.py`.
- `teste/conftest.py` cria `usuario_operacional` com o papel `operacional`, que
  também foi aposentado (`acesso.0019_retire_admin_company_operacional`).

**Atenção:** não é rename mecânico. Em `contatos/views/vales.py` o `ROLE_ADM` é
tratado como admin global (vê todos os Vales ativos), enquanto testes como
`test_list_vales_is_tenant_scoped` esperam escopo de tenant. O papel substituto
precisa refletir a intenção de cada teste (ex.: `ROLE_VIEWER` ou `ROLE_DELEGADO`),
não apenas o valor renomeado.

**Correção:** definir o papel atual correto por teste, atualizar imports e
setup (`conftest.usuario_operacional`), e revalidar as expectativas de permissão
(mover/excluir negócio, listar/editar Vale).

### C. Rótulos de template desatualizados nos testes

- `teste/test_vale_labels.py` espera `Excluir Vale` em
  `contatos/templates/contatos/prefeitura_excluir.html`; o template diz
  `Arquivar Vale` (o fluxo arquiva, não exclui).
- `teste/test_kanban_prefeitura.py::test_kanban_view_select_prefeitura_inclui_opcoes`
  espera `Todas as Prefeituras`; o `<select id="filtro-prefeitura">` em
  `recepcao/templates/recepcao/kanban.html` (linhas ~20-24) não tem opção
  placeholder.

**Correção:** decidir, por item, se o artefato correto é o teste (atualizar a
expectativa) ou o template (adicionar a opção placeholder `Todas as Prefeituras`).
Recomenda-se atualizar `test_vale_labels` para `Arquivar Vale` e adicionar a opção
placeholder no select do kanban (melhora de UX + coerência com o teste).

## Infra de teste

- Há **dois** PostgreSQL escutando na porta 5432 da máquina: um nativo do Windows
  (17, em `127.0.0.1`) e o `gprbr-db` do Docker (em `::1`). O `settings_vale_test`
  exige usuário `gprbr` (alvo Docker) **ou** `postgres` em `/gprbr_test` (alvo CI).
- As credenciais `gprbr/securepassword123` do `.env` não autenticam por host no
  `gprbr-db` (o container só aceita via `local`/`127.0.0.1` internos); o
  superusuário `postgres` autentica no servidor nativo.
- Foi criado o banco `gprbr_test` no servidor nativo `127.0.0.1:5432` (alvo CI já
  previsto em `settings_vale_test`), usado para rodar a suíte.

**Correção sugerida:** alinhar a senha do papel `gprbr` ao `.env`, ou documentar
oficialmente o alvo CI `gprbr_test` como caminho suportado para rodar testes no
host. Avaliar se a divergência Docker `::1` × nativo `127.0.0.1` deve ser
consolidada.

## Objetivos

- `python manage.py migrate` (do zero) funciona no Django 6.0.8.
- `pytest` roda com a configuração padrão (`--reuse-db`) sem workarounds.
- Todos os módulos de teste coletam e a suíte fica verde.

## Não-objetivos

- Mudanças de comportamento de produto.
- Redesenho de papéis/permissões (apenas refletir o estado atual nos testes).
- Consolidar/reconfigurar o ambiente Docker/Postgres da máquina.

## Validação

```powershell
python manage.py check
# banco descartável para provar migrate do zero:
python -m pytest -o addopts='' --create-db teste/
```

Rodar a suíte ampla (todos os `teste/test_*.py`) após cada correção de item.

## Rollback

- Item A: reverter a capitalização das referências de modelo (volta ao estado atual).
- Itens B/C: alterações isoladas em arquivos de teste/template, revertíveis por arquivo.
