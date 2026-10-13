# Spec: acesso global do Admin SaaS a membros

**Status:** aguardando revisão do usuário  
**Data:** 2026-10-13

## Objetivo

Permitir que `admin_saas`, identidade sem tenant próprio, consulte e gerencie membros de qualquer tenant sem selecionar contexto no cabeçalho. A criação de membro continua exigindo um destino explícito: o Admin SaaS escolhe o Vale no formulário. O papel `ADM` permanece restrito ao tenant associado à conta.

Esta spec altera somente o fluxo de membros. Ela não muda o acesso a Lojas, Vales ou outros módulos.

## Relação com as specs existentes

Esta decisão **substitui somente** a regra para membros em `2026-10-11-vale-tenant-isolation-design.md` que exige tenant selecionado para abrir e alterar dados de um Vale existente. Em membros, o contexto global do Admin SaaS continua global mesmo se houver uma seleção no cabeçalho. As regras restantes de isolamento continuam valendo: não confiar em IDs de tenant enviados pelo cliente, não permitir associações de lojas entre tenants e manter dados de Vale arquivado sem escrita até reativação.

## Regras por papel

| Papel | Listar/consultar membros | Criar | Editar/excluir ou inativar |
|---|---|---|---|
| `admin_saas` | Todos os tenants, sem seleção no cabeçalho; inclui membros sem Vale e histórico arquivado | Escolhe um Vale ativo no formulário; o tenant é derivado desse Vale | Pode localizar o membro globalmente; escrita permitida somente se o Vale do membro estiver ativo |
| `ADM` | Somente o tenant associado à conta | No tenant da conta | Somente membros do tenant da conta e com Vale ativo |
| Demais perfis | Mantém as permissões e o escopo atuais | Sem alteração | Sem alteração |

O Admin SaaS nunca recebe um tenant artificial na identidade ou na sessão. A seleção do Vale no formulário de criação vale somente para aquela operação e não modifica `admin_tenant_id`. Editar e excluir usam o tenant persistido no membro; IDs de lojas continuam validados contra esse tenant.

## Fluxos e validação

- As rotas canônicas permanecem em `/membros/...`; as rotas antigas `/contatos/membro/...` continuam como aliases.
- A lista global do Admin SaaS pode abrir qualquer detalhe usando o ID do membro, sem contexto pré-selecionado. O detalhe funciona também quando o tenant não tem Vale ou seu Vale está arquivado; nesse caso, a interface não presume um Vale ativo.
- No detalhe, editar e excluir, o tenant é derivado do próprio registro do membro. Essas escritas só são permitidas quando o tenant tem Vale ativo. Os IDs de Loja enviados no formulário são aceitos somente quando pertencem ao mesmo tenant.
- O formulário de novo membro apresenta ao Admin SaaS um seletor de Vales ativos. Sem Vale selecionado, não cria membro. As lojas disponíveis são limitadas ao tenant daquele Vale.
- Usuários com tenant associado continuam limitados a esse tenant; objeto de outro tenant retorna 404 ou resposta equivalente sem revelar sua existência.
- Vale arquivado permanece somente para consulta histórica do Admin SaaS; não aceita criar, editar, excluir ou inativar membros relacionados até o Vale ser reativado.
- Um tenant sem Vale ativo não é um destino válido para criação nem escrita de membros.

## Fora de escopo

- Alterar permissões de Admin SaaS em Loja, Vale, tarefas, agenda ou outros módulos.
- Alterar o tenant associado a um usuário `ADM`.
- Criar tenant ou Vale durante o cadastro de membro.
- Mudar modelos ou schema do banco.

## Critérios de aceitação

1. Admin SaaS sem `admin_tenant_id` consegue listar e consultar membros de tenants diferentes, inclusive tenant sem Vale ou com Vale arquivado.
2. Admin SaaS consegue editar e excluir/inativar um membro de qualquer tenant com Vale ativo; a ação usa o tenant do membro e não um ID fornecido pelo cliente.
3. Admin SaaS consegue consultar membro de Vale arquivado ou tenant sem Vale, mas escrita fica bloqueada até haver Vale ativo.
4. A criação por Admin SaaS exige Vale ativo de destino e limita as lojas a esse tenant; ausência de seleção não cria registros órfãos.
5. `ADM` continua limitado ao tenant da conta; outros papéis mantêm as regras atuais.
6. Rotas novas `/membros/...` funcionam e aliases `/contatos/membro/...` continuam resolvendo.
7. Testes cobrem tenant isolation, seleção de Vale no cadastro e o bloqueio de escrita em Vale arquivado.
