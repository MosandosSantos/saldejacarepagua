# Banco de dados — `saldabritanea` Docker (runtime)

> Único banco ativo do CRM: banco lógico `saldabritanea` no serviço Docker `gprbr-db` (PostgreSQL 15).
> É uma cópia integral do banco Docker `gprbr`; o banco de origem e o volume são preservados.
> Existe outra instância PostgreSQL, externa ao Compose, que também se chama `saldabritanea`; ela não é o destino e não é acessada pelo app.

## Resumo

| Instância | Conteúdo |
|-----------|----------|
| Docker `gprbr` (origem) | 37 tabelas públicas; schema e dados copiados integralmente |
| Docker `saldabritanea` (destino) | 37 tabelas públicas no restore inicial, antes de migrations posteriores |
| PostgreSQL externo `saldabritanea` | Não migrado, não alterado e fora do runtime |

## 1. Modelo GPRB externo (13 tabelas, fora do destino)

Estas tabelas permanecem somente na instância externa antiga e **não** são copiadas para o novo banco Docker. A conexão GPRB direta fica desativada durante esta migração; as telas que dependem delas serão tratadas posteriormente.

| Tabela | Papel | Observações |
|--------|-------|-------------|
| `tenant` | Tenants | Seed: código **`GPRB`** |
| `user` | Login (bcrypt) | `loginIdentifier`, `name`, `email` |
| `member` | Membros | **Sem `class_id`**; `lojaId` **nullable** (loja principal); `situacao` ATIVO/INATIVO; `anuidade`; `ritoId`; `potenciaId` (sem FK física) |
| `member_loja` | **N:N membro ↔ lojas** | PK composta (`memberId`,`lojaId`) + `dataInclusao` date NOT NULL DEFAULT CURRENT_DATE + `createdAt`/`updatedAt`; índice em `lojaId` |
| `loja` | Lojas | `"prefeituraId"` (1:N Potência), `"deputadoMestreId"` (Presidente), `"nomeFantasia"`, `numero`, mensalidades, banco/pix |
| `prefeitura` | **Potência** (tela) | **Sem `regiao`** (coluna removida); `prefeito` = Grão-Mestre; status ATIVA |
| `potencia` | Potência maçônica de **origem** | GOB, COMAB, CSMB, GLMMMRJ (seed 4) |
| `rito` | Ritos | Seed: Adonhiramita, Emulation, Escocês Retificado, York |
| `payment` | Pagamentos | |
| `payment_period` | Períodos de cobrança | |
| `payment_status` | Status de pagamento | |
| `meeting` | Sessões/reuniões | `data`, `tipo`, `lojaId` |
| `attendance` | Presenças | Liga meeting ↔ member |

**Excluídos de propósito** (sem uso real no código): `class`, `inventory_item`, `inventory_movement`, `Categoria`, `lancamento`, `chancelaria_document*`, `dues_charge`, `member_payment`, `payment_audit_log`, `audit_log`, `auth_attempt`, `refresh_token`, `service_token`, `external_api_audit_log`, `kpi_snapshot`, `password_invite_token`, `_prisma_migrations`.

**Colunas removidas**: `member.class_id`, `prefeitura.regiao`.

## 2. Tabelas presentes no banco Docker `gprbr` (37 tabelas)

`automacoes`, `automacoes_execucoes`, `automacoes_passos`, `campanhas`, `campos_personalizados`, `candidato`, `candidato_observacao`, `carteiras`, `chamadas`, `contatos`, `contatos_tags`, `convites`, `django_content_type`, `django_migrations`, `django_session`, `emails_enviados`, `etapas_funil`, `eventos`, `filas`, `gestao_campanha`, `gestao_capitulo`, `gestao_congressista`, `gestao_inscricao`, `gestao_pagamento`, `gestao_tipo_inscricao`, `loja_pdf`, `metas_vendedores`, `modelos_email`, `movimentacoes`, `negocios`, `notas`, `scripts`, `tags`, `tarefas`, `tenants`, `usuarios`, `valores_campos_personalizados`.

O restore copia o schema e os dados dessas tabelas de `gprbr`; as migrations Django rodam na inicialização da aplicação.

## 3. Conexões durante o cutover

| Caminho | Configuração | Estado |
|---------|-------------|--------|
| ORM Django | `DATABASE_URL` / `PG*` apontando ao serviço Docker `db`, banco `saldabritanea` | Ativo |
| SQL cru psycopg 3 | `GPRB_DB_ENABLED=False`; variáveis externas `GPRB_DB_*` removidas do app Compose | Desativado até a etapa funcional posterior |

- A instância externa antiga, embora tenha o mesmo nome de banco, não é consultada nem alterada pelo app.
- Recursos que dependem das tabelas GPRB ausentes no destino podem ficar indisponíveis até a correção posterior.

## 4. Dados de origem e rollback

O conteúdo do destino é determinado pelo banco Docker `gprbr` no momento do dump. Não importar dados da instância externa de mesmo nome. Manter `gprbr` e o volume intactos até validação explícita do cutover.

## 5. Operação

```bash
# Backup e restore são executados dentro do serviço Docker `gprbr-db`.
# Guardar o dump fora do repositório; consultar o plano de migração aprovado.
docker exec gprbr-db pg_dump -U gprbr -Fc -d gprbr -f /tmp/gprbr-to-saldabritanea.dump
docker exec gprbr-db createdb -U gprbr saldabritanea
docker exec gprbr-db pg_restore --exit-on-error --no-owner -U gprbr -d saldabritanea /tmp/gprbr-to-saldabritanea.dump
```

- A variável `POSTGRES_DB` é inicializada somente em volume vazio; no volume existente, criar o destino explicitamente como acima.
- Nunca usar `docker compose down -v` e nunca sobrescrever um destino `saldabritanea` que já exista dentro do container.
- Backups dos bancos antigos: `backups/saldogprb_backup_20261002.dump` + `backups/esferasda_crm_20261002.dump`.
- A instância externa `saldabritanea` e o container `esfera-postgres` não são origem nem destino desta migração.
- `esferasda`: **outro sistema (obras) — nunca tocar**.

## 6. Pontos de atenção

- `potencia.nome` foi alargado para `varchar(50)` no banco novo (no antigo era `varchar(6)` e 'GLMMMRJ' não cabia).
- `session` (tabela de sessões de loja) **nunca existiu** nem no banco antigo — `proximas_sessoes`/`agendamento_lojas` do dashboard falham silenciosamente (`_safe`) e os painéis ficam vazios.
- Toda query GPRB nova deve passar pelos **repositórios** (`repositories/gprb_repository.py`, `dashboard/repositories/gprb_repository.py`) — views não montam SQL.
