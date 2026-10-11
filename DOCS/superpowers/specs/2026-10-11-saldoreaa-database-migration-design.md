# Migração do CRM para o banco `saldoreaa`

**Status:** aguardando revisão do usuário  
**Data:** 2026-10-11

## Objetivo

Manter o CRM em um único banco PostgreSQL, `saldoreaa`, hospedado no serviço PostgreSQL Docker já usado pelo projeto. Migrar para ele somente o conteúdo do banco `gprbr`. O aplicativo não deve mais abrir conexões nem executar consultas em `saldabritanea`.

## Estado atual confirmado

- O container `gprbr-db` (`postgres:15-alpine`) está em execução.
- A conexão Django ORM do container da aplicação retorna `current_database() = gprbr`.
- A conexão SQL direta usada pelo código GPRB retorna `current_database() = saldabritanea`.
- O Compose declara esses caminhos separadamente: `DATABASE_URL` aponta ao serviço `db`; `GPRB_DB_*` aponta a outro host/banco.
- A regra de arquitetura atual e parte da documentação exigem `saldabritanea` como banco único. Elas precisam ser atualizadas para refletir esta decisão aprovada.

## Decisão de arquitetura

1. Criar `saldoreaa` como um banco lógico no PostgreSQL Docker existente, sem criar um segundo serviço/container PostgreSQL.
2. Fazer backup em formato customizado de `gprbr` e restaurá-lo em `saldoreaa`.
3. Configurar o Django para usar `saldoreaa` como único banco ativo.
4. Remover do caminho de execução do aplicativo a conexão externa `GPRB_DB_*` e os fluxos que dependem das tabelas GPRB de `saldabritanea` (incluindo autenticação externa e telas/indicadores GPRB identificados no código).
5. Manter `gprbr` e `saldabritanea` sem alterações durante a migração. Não apagar bancos, volumes ou backups nesta entrega; `gprbr` permanece como origem/rollback até validação explícita.

## Escopo funcional

- Continuam disponíveis as funcionalidades cujo armazenamento já está no banco Django `gprbr`.
- Os recursos que exigem consultas GPRB externas devem ser desativados de forma explícita e segura; não devem permanecer acessíveis como se os dados estivessem disponíveis.
- O login deixa de tentar autenticar no banco externo e usa somente as contas locais persistidas no Django.
- Scripts operacionais não devem continuar apontando implicitamente para `saldabritanea`.

## Migração e segurança

1. Inspecionar a existência de `gprbr` e `saldoreaa` no container. Se `saldoreaa` já existir, interromper e inspecionar; nunca sobrescrever ou apagar automaticamente.
2. Gerar e verificar um `pg_dump -Fc` de `gprbr` em caminho protegido e fora do versionamento.
3. Criar `saldoreaa` somente se ainda não existir e restaurar o dump sem alterar a origem.
4. Comparar o catálogo de tabelas e contagens de linhas de origem e destino; investigar divergências antes de apontar o aplicativo.
5. Alterar o Compose para que a aplicação e os healthchecks usem `saldoreaa`. Não usar `docker compose down -v`, não recriar o volume e não modificar o container `esfera-postgres`.
6. Não ler, copiar ou exibir credenciais de `.env.txt`; usar a configuração de ambiente já aprovada para o container.

O parâmetro `POSTGRES_DB` é aplicado pelo container oficial somente na inicialização de um diretório de dados vazio. Como o volume atual já existe, criar/restaurar `saldoreaa` explicitamente no PostgreSQL em execução; apenas trocar a variável no Compose não cria nem renomeia o banco.

## Configuração e documentação

- Atualizar `docker-compose.yml`, o exemplo de ambiente e os defaults do Django para nomear o banco ativo como `saldoreaa`.
- Remover do ambiente da aplicação as variáveis de conexão externa GPRB que deixariam possível consultar `saldabritanea`.
- Atualizar a constituição e a documentação técnica sobre a arquitetura de banco único e sobre os recursos GPRB desativados.
- Preservar alterações não relacionadas já existentes no workspace; revisar os diffs dos arquivos antes de editá-los.

## Verificação de aceite

- O banco `saldoreaa` existe no serviço PostgreSQL Docker e contém o schema/dados de `gprbr`.
- `SELECT current_database()` pela conexão Django retorna `saldoreaa`.
- O processo da aplicação não estabelece conexão nem executa consultas em `saldabritanea`.
- `gprbr` e seu volume permanecem intactos como origem/rollback.
- As rotas e telas dependentes do banco GPRB estão claramente desativadas; as funcionalidades Django restantes seguem funcionando.
- Testes focados e verificações Django passam; os testes não usam bases reais de origem.

## Fora de escopo

- Migrar dados ou tabelas de `saldabritanea`.
- Apagar ou renomear `gprbr`, remover volumes ou limpar dados antigos.
- Alterar produção/Railway ou o container `esfera-postgres`.
- Renomear a marca ou outros identificadores do produto além do banco.
