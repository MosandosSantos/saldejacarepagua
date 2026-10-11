# Especificação: isolamento de dados por Vale

**Status:** rascunho para revisão do usuário
**Data:** 2026-10-11
**Escopo aprovado em conversa:** um tenant por Vale; Loja e Membro locais sem importação; candidaturas locais até a conversão em Membro; arquivar Vales sem apagar dados.

## Objetivo

Cada Vale deve ser uma unidade de isolamento no CRM. Ao cadastrar um Vale, o sistema provisiona seu tenant usando a sigla do Vale. Lojas, Membros e candidaturas passam a ser armazenados localmente e ficam restritos ao tenant correspondente. Um usuário de um Vale não pode consultar ou alterar dados de outro.

O `admin_saas` continua sendo uma identidade global sem tenant próprio. Pode consultar a lista global de Vales, mas precisa selecionar um tenant para operar dados daquele Vale. A criação de um novo Vale é a exceção: ela cria o tenant e, ao concluir, seleciona esse tenant na sessão do `admin_saas`.

## Evidência do estado atual

- O modelo `Vale` existe em `contatos.models` e hoje tem `ForeignKey` para `Tenant`; vários Vales podem compartilhar um tenant.
- O banco Docker ativo foi consultado em modo somente leitura durante a descoberta: existem 3 tenants e 0 Vales locais.
- Há 0 registros locais de `Candidato` e 0 registros locais de `LojaPdf` no momento da descoberta.
- Não existem modelos Django locais para Loja e Membro. Suas telas e consultas usam o repositório GPRB; o conector externo permanece desativado.
- O cadastro de candidato ainda consulta opções de Vale/Loja via endpoints GPRB. A conversão de candidato aprovado deve ser preservada no fluxo local.
- A especificação anterior `2026-10-11-local-vale-contacts-design.md` explicitamente adiava relações locais de Loja/Membro. Esta nova decisão a amplia e substitui esse limite para o escopo descrito abaixo.

As contagens são uma fotografia da descoberta, não uma autorização para descartar dados futuros. Antes de qualquer migration no banco ativo, as contagens devem ser verificadas novamente.

## Decisões confirmadas

1. **Um Vale corresponde a exatamente um tenant.** Um tenant pode existir sem Vale por compatibilidade com os três tenants atuais, mas não pode possuir mais de um Vale.
2. **Sigla obrigatória e única.** A sigla do Vale será o nome visível do tenant e a base de seu `slug`. Siglas/identificadores conflitantes devem produzir erro claro, sem criar tenant órfão.
3. **Provisionamento atômico.** Criar Tenant e Vale na mesma transação. Em caso de falha, nenhum dos dois fica parcialmente criado.
4. **Sem contas automáticas.** O registro de Membro não cria automaticamente um `Usuario` ou credencial. Contas continuam no fluxo de usuários existente e recebem o tenant explicitamente.
5. **Lojas e Membros locais.** Criar e usar modelos Django locais, sem importar dados do GPRB.
6. **Candidaturas locais.** O fluxo de aprovação continua e um candidato iniciado vira Membro local no mesmo tenant.
7. **Arquivamento seguro.** A ação atualmente chamada “Excluir Vale” passa a inativar/arquivar o Vale. Tenant, contas, lojas, membros, candidatos e arquivos são preservados. Somente `admin_saas` pode reativar um Vale arquivado.
8. **Nenhuma conexão/importação GPRB.** Não consultar nem alterar a instância PostgreSQL externa, não importar dados externos e manter o conector GPRB desativado.
9. **Tenants existentes preservados.** Os três tenants atuais não serão convertidos, renomeados, removidos nem associados automaticamente a um Vale.

## Alternativas consideradas

1. **Tenant por Vale (selecionada):** reaproveita o isolamento, a sessão e as permissões multi-tenant existentes. Exige migrar telas e fluxos locais de Loja/Membro/candidato.
2. **Vários Vales dentro de um tenant:** exigiria acrescentar um segundo escopo por Vale a consultas e permissões; usuários do mesmo tenant poderiam compartilhar dados entre Vales, contrariando o isolamento desejado.
3. **Banco ou schema separado por Vale:** oferece isolamento físico, mas aumenta significativamente o custo operacional e de migrations sem necessidade demonstrada.

## Modelo e persistência

### Tenant e Vale

- Alterar a relação `Vale.tenant` para `OneToOneField` (ou `ForeignKey` com unicidade equivalente), preservando `db_column='tenant_id'` e a tabela `vales`.
- Tornar `Vale.sigla` obrigatória e única entre Vales.
- Provisionar `Tenant(nome=sigla, slug=slugify(sigla))` e o Vale associado dentro de `transaction.atomic()`.
- Validar colisões de sigla/slug antes de persistir. Não truncar silenciosamente nem sobrescrever tenant existente.
- Somente `admin_saas` pode provisionar um novo Vale/tenant. Depois do commit, gravar o novo ID em `admin_tenant_id` da sessão e redirecionar para a área do Vale.
- Os três tenants existentes permanecem sem alteração e podem continuar sendo usados pelos demais módulos do CRM.

### Loja e Membro

- Criar modelos locais Django para Loja e Membro no banco Docker ativo.
- Cada modelo terá FK direta para `Tenant`, permitindo filtros e validações consistentes com o padrão `filtro_tenant` existente.
- Preservar os campos editáveis e operações CRUD expostos nas telas atuais de Loja e Membro, incluindo endereço, contatos, situação, dados pessoais, datas e campos ritualísticos. Indicadores que dependem de histórico GPRB seguem a regra de indisponibilidade abaixo.
- Cada Membro poderá estar associado a nenhuma ou várias Lojas, como permite a tela atual. Todas as Lojas associadas devem pertencer ao mesmo tenant do Membro; validar no serviço/formulário e cobrir com testes.
- CPF, quando preenchido, será único por tenant para Membros, sem bloquear o mesmo CPF em tenants diferentes.
- Manter o bloqueio de exclusão de Loja quando houver Membros associados. A exclusão/inativação de Membro preservará o comportamento atual onde aplicável.
- Adicionar criação manual de Membro, além da criação pelo fluxo de candidato aprovado, para completar o CRUD local.
- Reassociar `LojaPdf` à Loja local por FK/OneToOne, mantendo limite de 10 MB, validação de PDF, substituição e remoção do arquivo.

### Candidato e conversão em Membro

- Manter `Candidato.tenant` como fonte do escopo.
- Substituir a seleção textual externa de Vale/Loja por relações locais. Como existe exatamente um Vale por tenant, o Vale é derivado do tenant; a Loja escolhida deve pertencer a esse mesmo tenant.
- Remover o fallback `tenant_gprb()` dos fluxos de criação/alteração de candidatos. Nenhuma escrita pode escolher um tenant implícito.
- Substituir os endpoints que consultam o GPRB por opções locais tenant-scoped para Vale/Loja, preservando os contratos de resposta necessários à interface.
- Ao iniciar um candidato aprovado, criar o Membro local e atualizar o estado do candidato na mesma transação. Associar o Membro à Loja do candidato quando aplicável.
- Impedir conversão duplicada e CPF duplicado dentro do tenant; retornar mensagem de validação clara sem deixar candidato ou Membro parcialmente atualizado.
- Mapear para Membro os dados do candidato já coletados pelo formulário/portal. Não criar automaticamente uma conta de login.
- A migração de campos textuais antigos de candidatos só pode removê-los se o preflight confirmar que continuam sem dados. Se houver candidatos entre a revisão da spec e a migration, interromper e preparar mapeamento explícito; nunca descartar os textos silenciosamente.

## Permissões e isolamento

- Usuários comuns consultam e alteram somente registros do tenant associado à sua sessão/conta.
- Todas as buscas, filtros, endpoints JSON, detalhes, edição, exclusão/arquivamento, PDFs e associações de Membro-Loja devem aplicar o escopo do tenant no servidor, sem confiar em `tenant_id` recebido do cliente.
- IDs de objetos de outro tenant devem resultar em 404 ou resposta equivalente que não revele a existência do objeto.
- `admin_saas` pode consultar a lista global de Vales sem tenant selecionado. Para abrir e alterar dados de um Vale existente, precisa selecionar o tenant correspondente.
- Criar Vale é a única operação sem tenant pré-selecionado; ela provisiona um tenant novo e o seleciona após sucesso.
- Lojas, Membros e candidaturas nunca usam fallback para um tenant arbitrário quando a sessão do `admin_saas` está em “Todos os tenants”.
- Vale arquivado não aceita novas alterações nem novos candidatos. Usuários comuns não acessam as rotas daquele Vale; o `admin_saas` pode consultar o histórico e reativá-lo.

## Interface e compatibilidade

- Preservar as rotas públicas atuais de Vale, Loja e Membro sempre que possível para não quebrar links existentes.
- Substituir chamadas do repositório GPRB por ORM local nas telas cobertas: listagem, busca, detalhe, criação, edição, exclusão/inativação, associação membro-loja e upload de PDF.
- A tela de Loja deixa de pedir um Vale arbitrário: o tenant ativo determina o Vale. A tela deve mostrar claramente qual Vale está selecionado.
- A seleção de Loja no fluxo de candidato apresenta somente Lojas do tenant ativo.
- Na listagem de Vales, cada célula de Secretaria e Tesouraria mostra o nome em uma linha e e-mail/telefone abaixo, com quebra segura em larguras menores, conforme pedido do usuário.
- Colunas e filtros dependentes de histórico GPRB que não terá fonte local nesta etapa (por exemplo, presenças e histórico de anuidades) não podem mostrar zeros fictícios. Devem ser omitidos ou claramente marcados como indisponíveis até especificação própria.

## Arquivamento

- Substituir a exclusão física de Vale por transição para `INATIVA`, preservando Tenant e todos os dados relacionados.
- O arquivo/inativação deve ser idempotente e não remover PDFs nem contas.
- Vale inativo fica fora dos seletores de operação normal. O `admin_saas` pode encontrá-lo na área/lista de arquivados e reativá-lo explicitamente.
- Enquanto inativo, usuários comuns não acessam as rotas do Vale e operações de escrita/criação de candidatos são bloqueadas. A interface do `admin_saas` informa que o Vale está arquivado e oferece reativação; nenhum dado relacionado é apagado.

## Migração e segurança operacional

- Aplicar migrations somente ao banco Docker ativo `saldabritanea`; não tocar no banco Docker de origem `gprbr`, em `esfera-postgres` ou na instância externa homônima.
- Manter `GPRB_DB_ENABLED=False` e não adicionar credenciais/host GPRB ao app.
- Antes de qualquer migration no banco ativo: confirmar `gprbr-app`/`gprbr-db` saudáveis, `current_database() = saldabritanea`, volume atual preservado e criar/validar backup custom-format fora do Git.
- Revalidar contagens de Vales, candidatos e PDFs. Se os dados deixaram de estar vazios, parar a migration que removeria/reinterpretaria campos e atualizar o plano de dados antes de prosseguir.
- Não executar `docker compose down -v` nem remover volumes. Não resetar `test_saldabritanea` nem bases de produção; somente o banco isolado `test_saldabritanea_vales` pode ser criado/recriado pelo runner de testes explícito.

## Testes e critérios de sucesso

1. Criar Vale como `admin_saas` sem tenant ativo cria Tenant e Vale atomicamente, com sigla obrigatória/única, e seleciona o novo tenant.
2. Sigla duplicada, falha de validação ou erro de persistência não deixa Tenant órfão.
3. Um Tenant não pode ter mais de um Vale; Vale e Tenant ficam ligados 1:1.
4. CRUD de Loja/Membro funciona no ORM local e não chama o conector GPRB.
5. Usuários de um tenant não listam, leem, alteram, excluem nem associam registros de outro tenant.
6. Membro sem Loja é permitido; múltiplas Lojas do mesmo tenant são permitidas; associação cruzada entre tenants é rejeitada.
7. Candidato usa opções locais do tenant e candidato aprovado gera exatamente um Membro no mesmo tenant, preservando dados mapeados.
8. Upload, substituição, remoção e validação de PDFs continuam funcionando com Loja local e isolamento por tenant.
9. Arquivar Vale preserva Tenant, contas, Loja, Membros, candidatos e arquivos; bloqueia escrita; reativar restaura operação.
10. As telas não exibem contagens ou indicadores GPRB como se fossem dados locais disponíveis.
11. `python manage.py check`, `makemigrations --check --dry-run` e testes focados passam usando somente banco de teste isolado e local.
12. A migration operacional aplica-se apenas a `saldabritanea`, após backup validado; nenhum dado externo é lido ou importado.

## Fora de escopo nesta etapa

- Importar/sincronizar Vales, Lojas, Membros, presença, pagamentos ou outros dados do GPRB.
- Reativar conexões externas ou alterar qualquer banco externo.
- Criar automaticamente contas de login a partir de Membros.
- Reimplementar histórico de presença, ledger de anuidades, ranking e relatórios que dependem de tabelas GPRB sem fonte local já aprovada.
- Alterar módulos gerais de CRM não relacionados ao escopo de Vale/Loja/Membro/candidatura.

## Próxima etapa após aprovação

Após aprovação deste documento pelo usuário, criar um plano de implementação ordenado por migrations/modelos, CRUD local, candidaturas, testes de isolamento e rollout seguro. Nenhum código ou DDL deve ser aplicado antes da aprovação do plano e do preflight operacional.
