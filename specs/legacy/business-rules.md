# Regras de negócio — SAL DA BRITÂNEA CRM (legado/atual)

> Fonte da verdade das regras. Se código e este documento divergirem, **corrigir o código** e/ou atualizar o documento na mesma mudança.

## 1. Nomenclatura de negócio

| Na interface | Tabela/coluna real | Termo antigo (proibido na UI) |
|--------------|--------------------|-------------------------------|
| **Potência** | `prefeitura` | Prefeitura |
| **Grão-Mestre** (da Potência) | `prefeitura.prefeito` | Prefeito |
| **Presidente** (da loja) | `loja."deputadoMestreId"` → `member` | Deputado Mestre |
| **Situação** | `member.situacao` | Classe (MX/EN/CBCS) |

- Interface e novos códigos usam **exclusivamente** os termos novos.
- Tela de Potências lista `prefeitura`; a tabela `potencia` é outro conceito (item 4).

## 2. Membros e lojas (N:N)

1. Um membro pode pertencer a **N lojas**; uma loja tem **N membros** — ponte `member_loja` (PK composta `memberId`+`lojaId`, coluna `dataInclusao`).
2. A **primeira** loja na seleção é a **principal** e é espelhada em `member."lojaId"`.
3. `member."lojaId"` é **nullable** — membro sem loja é válido (POST sem `lojas` → NULL).
4. `definir_lojas_membro(member_id, loja_ids, datas_inclusao=None)` **preserva** as datas de inclusão de lojas já vinculadas; novas lojas recebem `dataInclusao` informada ou `CURRENT_DATE`.
5. Consultas de membros por loja consideram a união `member."lojaId" = l.id OR member_loja` (ponte + legado).

## 3. Situação do membro (sem classes)

- `member.situacao`: **`ATIVO`** / **`INATIVO`** — única dimensão de estado.
- **Classes (MX/EN/CBCS) e graus foram eliminados do produto**: sem tabela `class`, sem `member.class_id`, sem filtro/coluna/grau em nenhuma tela ou relatório.
- Contador **BAII** do dashboard = membros por situação (ATIVO × INATIVO).
- Contagens e rankings por loja descontam `INATIVO` onde aplicável (`situacao = 'ATIVO'` no JOIN).

## 4. Potência organizacional vs potência maçônica

| Conceito | Tabela | Uso |
|----------|--------|-----|
| Potência **organizacional** (tela Potências) | `prefeitura` | Agrupa lojas (`loja."prefeituraId"`, 1:N) |
| Potência **maçônica de origem** | `potencia` | GOB, COMAB, CSMB, GLMMMRJ — ligada a `member`/`candidato` (sem FK física) |

- Não confundir nem misturar os dois conceitos em telas.
- **Sem coluna `regiao`** em `prefeitura` (removida do banco, CRUD e templates).

## 5. Ritos

- `rito` catálogo de ritos maçônicos; seed: Adonhiramita, Emulation e Aperfeiçoamento, Escocês Retificado, York.
- `member` referencia rito (conforme formulário).

## 6. Multi-tenant

1. Toda consulta web é escopada por `tenant_id` da sessão — **dados nunca cruzam tenants**.
2. `admin_saas` (sem tenant) enxerga todos.
3. Tenant operacional atual: código **`GPRB`** (ID fixo usado pelos repositórios GPRB via `_obter_tenant_gprb()`).

## 7. Autenticação

1. Login por identificador (ex.: telefone `21999…`) + senha.
2. Ordem: `user` GPRB (**bcrypt**) → cria/usa **espelho local** em `usuarios` (tenant + papel) → fallback `usuarios` Django (`make_password`).
3. Rate limit: **5 tentativas** por identificador (cache Django) — pode bloquear testes repetidos em sequência.
4. Papéis: `admin_saas`, `admin_company`, `operacional`, `viewer` (viewer = somente leitura, sem POST).

## 8. Funil comercial (motor herdado)

1. Etapas fixas por chave: `interessado`, `avaliacao_agendada`, `avaliacao_feita`, `orcamento`, `fechado`, `perdido` — cores fixas (`STAGES` em `core/dominio.py`); **rótulos adaptados por nicho**.
2. Receita projetada = Σ `valor × PESOS_ETAPA` (10% → 100%; `perdido` = 0%).
3. Nichos: `saude` (padrão), `odonto`, `imob`, `educacao`, `servicos`, `outro` — novo nicho é re-rotulação, não código.
4. Segmentos e listas fixas (`ORIGENS`, `PAGAMENTOS`) em `core/dominio.py`.

## 9. Convenções de dados

- Campos vazios exibidos como `'—'` (nunca string vazia na UI).
- `createdAt`/`updatedAt` em toda tabela GPRB; `updatedAt` = `NOW()` a cada UPDATE.
- IDs do modelo GPRB: UUID (texto); núcleo Django: PK padrão Django.
- Valor monetário default `0`.

## 10. Fronteiras do sistema (não voltar atrás)

- ❌ Sem classes/graus, sem `regiao` em Potência, sem inventário/chancelaria/lancamentos.
- ❌ Sem multi-banco em runtime — só `saldabritanea` (ORM e SQL GPRB no mesmo banco).
- ❌ Sem espelho/sincronização Prisma.
- Exclusão física dos bancos antigos (`saldogprb`, `esferasda_crm`) só após validação do usuário; `esferasda` é de **outro sistema — nunca tocar**.
