# Spec: cadastro local de Vales e contatos

**Status:** aguardando revisão escrita do usuário

**Data:** 2026-10-11

## Objetivo

Disponibilizar o cadastro de Vales e seus contatos no único banco ativo do CRM: o PostgreSQL Docker `saldabritanea`. Cada Vale deve permitir registrar os dados de Secretaria e Tesouraria, incluindo nome, e-mail e telefone, e consultar esses contatos na listagem e na confirmação de exclusão.

O banco Docker ativo e o banco Docker de origem `gprbr` não possuem a tabela `prefeitura`. O CRUD atual depende do repositório SQL GPRB, cuja conexão está desativada. Este trabalho substituirá essa dependência **somente para o CRUD de Vales**, sem consultar ou importar dados da instância PostgreSQL externa.

## Decisões confirmadas

- A persistência será local, no banco Docker `saldabritanea`.
- A nova tabela começa vazia. Os Vales existentes serão recadastrados manualmente; nenhum dado da instância externa será importado.
- Nesta etapa, Vale não terá vínculos locais com Loja ou Membro. Contagens de Lojas/Membros e bloqueios de exclusão baseados nesses vínculos ficam adiados.
- Secretaria e Tesouraria serão exibidas com **nome, e-mail e telefone** na consulta e na confirmação de exclusão.
- A tela usa o termo **Delegado** para o responsável do Vale.
- A UI usa **Mensalidade**, mas o usuário autorizou somente a troca de texto: os campos e a semântica anual existentes (`valor_anuidade`, `vencimento_anuidade`) não mudam nesta etapa.
- As telas não devem preencher ou criar registros com os exemplos de e-mail presentes nos placeholders.
- Os e-mails serão armazenados como texto, sem acrescentar um validador mais restritivo; o exemplo fornecido (`farelli@gprbr`) precisa continuar aceito.

## Abordagens consideradas

1. **Modelo Django local `Vale` (selecionada):** criar a tabela local, colocar o CRUD em Django ORM e manter o conector externo desativado. Não exige acesso à instância excluída da migração; os registros começam vazios.
2. **Tabela local separada para os contatos:** criar uma tabela de contatos 1:1 além da tabela Vale. Isso adicionaria joins e manutenção sem necessidade, pois há somente dois cargos conhecidos.
3. **Importar/recriar o schema GPRB no Docker:** preservaria o fluxo SQL legado e possíveis relações externas, mas amplia a migração, exige origem de dados aprovada e contradiz a decisão vigente de não copiar nem conectar a instância externa.

## Desenho aprovado para especificação

### Dados e persistência

- Criar o modelo Django `Vale` no app `contatos`, armazenado na tabela local `vales`.
- Cada registro pertence a um tenant local (`acesso.Tenant`); leituras e escritas devem ser sempre escopadas pelo tenant da sessão.
- Preservar os dados de cadastro necessários às telas atuais: nome, sigla, responsável (chave interna existente `prefeito`), telefone, e-mail, PIX, valor e vencimento existentes, status e timestamps.
- Acrescentar `secretario_nome` e `tesoureiro_nome`; manter os campos existentes de e-mail e telefone de ambos.
- Nomes, e-mails e telefones dos contatos serão opcionais para aceitar cargos ainda não preenchidos, como os demais contatos atuais. **Assunção para revisão:** se os nomes tiverem de ser obrigatórios, ajustar esta spec antes do plano.
- Manter as rotas atuais de Vale (`/contatos/prefeituras/` e `/contatos/prefeitura/...`) para não quebrar bookmarks; não renomear rotas nem chaves internas neste trabalho.
- Aplicar a migration apenas ao banco Docker `saldabritanea`, depois da aprovação do plano e do backup operacional exigido pelo projeto. Nenhum acesso à instância externa.

### Fluxos web

- **Criar e editar:** armazenar os dois novos nomes junto aos e-mails e telefones de Secretaria e Tesouraria. Manter a validação atual do nome do Vale e os rótulos visíveis `Delegado` e `Mensalidade`.
- **Consultar/listar:** ler os dados do modelo local e exibir, para ambos os cargos, nome, e-mail e telefone. Não exibir contagens de lojas/membros que não podem ser obtidas localmente.
- **Excluir:** mostrar os dois contatos completos e excluir somente o Vale local selecionado. Não consultar tabelas externas nem bloquear pela existência de relações GPRB ausentes.
- Reaproveitar autenticação, permissões de edição e isolamento por tenant já aplicados às rotas.
- O acesso SQL GPRB permanece desativado. Telas de outras áreas que dependem de tabelas GPRB não passam automaticamente a funcionar por esta mudança.

### Exemplo de contrato do modelo (ilustrativo)

```python
class Vale(models.Model):
    tenant = models.ForeignKey('acesso.Tenant', on_delete=models.CASCADE)
    nome = models.CharField(max_length=160)
    secretario_nome = models.CharField(max_length=160, blank=True, default='')
    secretario_email = models.CharField(max_length=254, blank=True, default='')
    secretario_telefone = models.CharField(max_length=40, blank=True, default='')
    tesoureiro_nome = models.CharField(max_length=160, blank=True, default='')
    tesoureiro_email = models.CharField(max_length=254, blank=True, default='')
    tesoureiro_telefone = models.CharField(max_length=40, blank=True, default='')
```

O trecho não define toda a classe; os outros campos existentes serão modelados sem alterar a semântica dos valores anuais.

## Comandos e verificação

- Testes locais: `python -m pytest teste/test_vale_local.py teste/test_vale_views.py -q`
- Verificação Django: `python manage.py check`
- Consistência das migrations: `python manage.py makemigrations --check --dry-run`
- Aplicação local após aprovação operacional: `docker exec gprbr-app python manage.py migrate --noinput`

Testes não podem usar a base de produção, a base Docker de origem `gprbr` nem a instância externa. Testes de ORM usam somente o banco de teste local; isolamento GPRB não será ativado.

## Estrutura prevista

- `contatos/models.py` e nova migration Django: modelo e tabela local `vales`.
- `contatos/views/` (ou módulo atual das rotas de prefeitura): CRUD ORM tenant-scoped.
- `contatos/urls.py`: preservar nomes e URLs atuais.
- `contatos/templates/contatos/prefeituras.html`, `prefeitura_nova.html`, `prefeitura_editar.html`, `prefeitura_excluir.html`: entrada, consulta, edição e confirmação com os contatos.
- `teste/`: testes de modelo, isolamento por tenant, CRUD e apresentação dos contatos.

## Estilo e padrões

- Seguir Django 5.2 e o padrão de modelos/migrations já usado em `contatos/models.py`.
- Usar chaves estrangeiras e migrations Django; não criar DDL manual nem SQL para dados locais.
- Manter as views enxutas, validar dados nos formulários/views existentes e respeitar os decorators de login, tenant e edição.
- Testar regras de persistência, isolamento e saída dos templates com pytest-django; fixtures não conectam ao GPRB externo.

## Limites

- **Sempre:** gravar no banco Docker ativo; preservar escopo por tenant; fazer backup antes de DDL; manter os nomes/e-mails/telefones existentes; deixar os novos campos vazios nos registros recém-criados até preenchimento pelo usuário.
- **Pedir nova aprovação:** importar dados externos, reativar `GPRB_DB_*`, criar relações locais com Lojas/Membros, tornar campos obrigatórios ou alterar a semântica/frequência dos valores rotulados como Mensalidade.
- **Nunca:** consultar ou alterar a instância PostgreSQL externa `saldabritanea`, importar dados dela nesta feature, remover volumes, tocar `esfera-postgres` ou usar o banco `esferasda`.

## Critérios de sucesso

1. Uma migration cria a tabela `vales` no banco Docker local e não consulta qualquer banco externo.
2. Criar, consultar, editar e excluir Vale funcionam no CRUD ORM e são escopados por tenant.
3. `secretario_nome` e `tesoureiro_nome` persistem junto aos e-mails/telefones em criação e edição.
4. A listagem e a confirmação de exclusão exibem nome, e-mail e telefone de Secretaria e Tesouraria.
5. O endereço local-domain `farelli@gprbr` é aceito e preservado sem validação nova.
6. Os formulários podem deixar os contatos vazios e não preenchem valores de exemplo automaticamente.
7. A tabela começa vazia; nenhum registro externo é copiado.
8. Conector GPRB permanece desligado e não há alterações às bases ou volumes de origem.
9. Testes focados, `manage.py check` e verificação de migrations passam.

## Fora de escopo

- Importar ou sincronizar Vales da instância externa.
- Reconstruir tabelas de GPRB, Lojas ou Membros.
- Relacionar Vale a Lojas/Membros locais ou recuperar seus contadores.
- Alterar a lógica anual de cobrança/vencimento, apesar dos rótulos UI atuais.
- Renomear rotas, contratos internos GPRB ou todas as nomenclaturas legadas do projeto.

## Questões para revisão escrita

- Confirmar que os nomes de Secretaria/Tesouraria são opcionais.
- Confirmar a omissão temporária de contagens de Lojas/Membros e da validação de exclusão baseada em lojas externas.
- Confirmar a preservação dos nomes internos legados e dos campos anuais apesar do rótulo `Mensalidade`.
