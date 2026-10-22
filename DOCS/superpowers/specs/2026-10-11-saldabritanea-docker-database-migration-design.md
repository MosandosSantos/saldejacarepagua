# Migração do CRM para o banco Docker `saldabritanea`

**Status:** aprovada e executada em 2026-10-11
**Data:** 2026-10-11

## Objetivo

Manter o CRM em um único banco PostgreSQL ativo, chamado `saldabritanea`, dentro do serviço PostgreSQL Docker já usado pelo projeto. Migrar para ele somente o conteúdo do banco Docker `gprbr`. A instância PostgreSQL externa que também se chama `saldabritanea` permanece intacta e não será acessada pelo aplicativo.

## Estado atual confirmado

- O container `gprbr-db` (`postgres:15-alpine`) está em execução.
- A conexão Django ORM do container da aplicação retorna `current_database() = gprbr`.
- A conexão SQL direta usada pelo código GPRB retorna `current_database() = saldabritanea` em outra instância/host.
- O Compose declara esses caminhos separadamente: `DATABASE_URL` aponta ao serviço `db`; `GPRB_DB_*` aponta a outro host/banco.
- A regra de arquitetura atual já usa o nome `saldabritanea`, mas aponta ORM e SQL cru para a instância externa. A nova base Docker também terá esse nome; as instâncias não devem ser confundidas.

## Decisão de arquitetura

1. Criar um banco lógico novo chamado `saldabritanea` no PostgreSQL Docker existente, sem criar um segundo serviço/container PostgreSQL. Se esse nome já existir dentro desse container, interromper e inspecionar; não sobrescrever.
2. Fazer backup em formato customizado do banco Docker `gprbr` e restaurá-lo no novo `saldabritanea` Docker.
3. Configurar o Django para usar o novo banco Docker como único banco ativo.
4. Remover do ambiente da aplicação a rota de conexão à instância externa `GPRB_DB_*`; recursos que dependem das tabelas GPRB não migradas poderão ficar indisponíveis e serão tratados numa etapa posterior, conforme decisão do usuário.
5. Manter intactos o banco Docker `gprbr`, seu volume e a instância externa `saldabritanea`. Não apagar bancos, volumes ou backups nesta entrega; `gprbr` permanece como origem/rollback até validação explícita.

## Escopo funcional

- O schema e os dados do banco Docker `gprbr` são preservados na cópia.
- Nenhuma tabela ou dado da instância externa `saldabritanea` é importado.
- A instância externa deixa de ser configurada como destino de conexões do processo da aplicação.
- Os problemas funcionais decorrentes de tabelas GPRB ausentes (incluindo `/contatos/`, login externo, telas e indicadores GPRB) ficam explicitamente fora desta etapa e serão resolvidos após o cutover.

## Migração e segurança

1. Inspecionar a existência de `gprbr` e de `saldabritanea` no container `gprbr-db`. Se o destino já existir nesse container, interromper e inspecionar; nunca sobrescrever ou apagar automaticamente. A instância externa de mesmo nome não é o destino.
2. Gerar e verificar um `pg_dump -Fc` de `gprbr` em caminho protegido e fora do versionamento.
3. Criar o novo banco Docker `saldabritanea` somente se ainda não existir e restaurar o dump sem alterar a origem.
4. Comparar o catálogo de tabelas e contagens de linhas de origem e destino; investigar divergências antes de apontar o aplicativo.
5. Alterar o Compose para que a aplicação e os healthchecks usem o banco Docker `saldabritanea`. Não usar `docker compose down -v`, não recriar o volume e não modificar o container `esfera-postgres`.
6. Não ler, copiar ou exibir credenciais de `.env.txt`; usar a configuração de ambiente já aprovada para o container.

O parâmetro `POSTGRES_DB` é aplicado pelo container oficial somente na inicialização de um diretório de dados vazio. Como o volume atual já existe, criar/restaurar `saldabritanea` explicitamente no PostgreSQL em execução; apenas trocar a variável no Compose não cria nem renomeia o banco.

## Configuração e documentação

- Atualizar `docker-compose.yml`, o exemplo de ambiente e os defaults do Django para nomear o banco Docker ativo como `saldabritanea`.
- Remover do ambiente da aplicação as variáveis de conexão ao host externo GPRB; não remover agora as telas/código dependentes, que ficam para a etapa funcional posterior.
- Atualizar a constituição e a documentação técnica para diferenciar o novo banco Docker da instância externa antiga de mesmo nome.
- Preservar alterações não relacionadas já existentes no workspace; revisar os diffs dos arquivos antes de editá-los.

## Verificação de aceite

- O novo banco lógico `saldabritanea` existe no PostgreSQL Docker e contém o schema/dados de `gprbr`.
- `SELECT current_database()` pela conexão Django retorna `saldabritanea` no container Docker.
- O processo da aplicação não conecta ao host da antiga instância externa `saldabritanea`.
- O banco Docker `gprbr` e seu volume permanecem intactos como origem/rollback.
- Nenhuma tabela ou dado foi copiado da instância externa.
- Problemas nas rotas/telas GPRB causados pela ausência das tabelas externas ficam registrados para correção posterior; não bloqueiam o cutover do banco.
- Testes focados e verificações Django passam; os testes não usam bases reais de origem.

## Fora de escopo

- Migrar dados ou tabelas da instância externa `saldabritanea`.
- Corrigir as funcionalidades de produto que dependem de tabelas GPRB não presentes na cópia de `gprbr`.
- Apagar ou renomear `gprbr`, remover volumes ou limpar dados antigos.
- Alterar produção/VPS ou o container `esfera-postgres`.
- Renomear a marca ou outros identificadores do produto além do banco.
