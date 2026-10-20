# Tenant SCG33REAA, rota Iniciação e marca SAL DA AMORIO

**Data:** 2026-10-10  
**Status:** Aguardando revisão do usuário.

## Objetivo

Renomear o tenant principal atualmente identificado como `GPRB` para
`SCG33REAA`, preservando o mesmo registro e sua chave. Tornar `/iniciacao/` o
endereço canônico do fluxo de iniciação e aplicar a marca **SAL DA AMORIO** nas
telas de autenticação e nos e-mails enviados pelo sistema.

## Decisões confirmadas

- A troca `GPRB` → `SCG33REAA` é a renomeação do tenant existente, não a seleção
  de outro tenant. O `id` do registro permanece igual.
- Usar uma configuração central para o código do tenant em consultas de leitura
  e escrita, em vez de substituir manualmente literais dispersos.
- `/iniciacao/` será a rota canônica para a página e suas subrotas.
- O menu mostrará **Iniciação** e o título principal **Flow de Iniciação**.
- A marca será **SAL DA AMORIO** nas mensagens de autenticação e nos e-mails
  automáticos.
- Os containers serão reconstruídos/reiniciados ao final das alterações e
  verificados.

## Estado atual e limpeza já realizada

- A base externa conectada é `saldabritanea`; nela o registro de tenant atual
  tem código `GPRB`. `SCG33REAA` ainda não existia como código.
- O código da aplicação contém defaults `GPRB` em vários módulos; a variável
  `GPRB_TENANT_ID` não é usada para selecionar essas consultas.
- Antes da limpeza foi criado e validado o backup
  `backups/gprb_pre_bulk_delete_20261010_212731.dump`.
- A pedido do usuário, foram removidos em todos os seis tenants: 100 membros,
  308 vínculos `member_loja`, 11 lojas e 9 vales (`prefeitura`). As seis linhas
  de tenant e a única conta de usuário foram preservadas. As tabelas de
  pagamentos, presenças, status de pagamento e reuniões estavam vazias; a conta
  de usuário não tinha vínculo com loja ou vale.
- Essa limpeza está concluída e **não deve ser repetida** durante a troca do
  código de tenant.

## Código central do tenant

Criar `GPRB_TENANT_CODE` como configuração central, carregada do ambiente e
exposta pelo Django e pelo Docker Compose, com valor principal
`SCG33REAA`. Todos os consumidores do código externo devem usar essa
configuração: consultas do dashboard, membros, vales, lojas, usuários,
autenticação, ranking e comunicações. Atualizar também os SQLs que hoje fixam
`GPRB` diretamente. Os testes configuram explicitamente `GPRB` quando usam
fixtures com esse código.

No banco externo, atualizar somente a coluna `tenant.code` do registro cujo
código é `GPRB`, verificando antes que `SCG33REAA` não exista. A atualização
deve ser transacional e preservar o `id` do tenant, as demais linhas de tenant
e a conta de usuário. Se a verificação encontrar zero ou mais de um registro
`GPRB`, ou se `SCG33REAA` já existir, interromper sem atualizar e apresentar o
conflito.

Os testes devem configurar explicitamente o código de tenant usado por suas
fixtures; nenhum teste deve depender implicitamente do tenant de produção.

## Rota e navegação

- Montar todas as rotas do fluxo sob `/iniciacao/`; as referências Django com
  namespace `recepcao` passam a gerar o endereço novo. Links, formulários e
  requisições AJAX gerados pelo aplicativo devem usar o prefixo canônico.
- Manter `/recepcao/` e as subrotas existentes como alias compatível para os
  mesmos handlers, incluindo os endpoints usados por formulários e requisições
  POST. O alias serve a mesma funcionalidade e não altera o método HTTP; usar
  um namespace legado distinto para evitar ambiguidade na reversão de URLs.
- Alterar o rótulo de navegação de **Candidatos** para **Iniciação** e o título
  visível da página para **Flow de Iniciação**.
- Não renomear o namespace Python `recepcao` nem os nomes internos de funções.

## Autenticação e e-mails

- Definir `APP_BRAND_NAME = "SAL DA AMORIO"` em uma configuração central e
  disponibilizá-la ao header existente, às telas de autenticação e aos e-mails.
  O remetente conserva o endereço atual, mas usa o nome de exibição configurado.
- Usar `SAL DA AMORIO` no título e na marca visível da tela de login e da tela
  de ativação de conta; usar `logow.webp` nessas telas de autenticação.
- O logout hoje limpa a sessão e redireciona para o login sem mensagem. Exibir
  após o logout uma confirmação curta, por exemplo: “Você saiu da conta SAL DA
  AMORIO.”
- Aplicar `SAL DA AMORIO` como nome de exibição do remetente para todos os
  e-mails do sistema, preservando o endereço de e-mail e a configuração SMTP
  existentes.
- Atualizar assunto, corpo e assinatura do e-mail de ativação. Nas notificações
  de candidatos, usar `SAL DA AMORIO` na assinatura, preservando o nome formal
  do Grande Priorado onde ele identifica a instituição. Atualizar também a
  marca e a imagem do convite HTML de candidato para `logow.webp`.
- Não reescrever assuntos ou corpos de campanhas criados pelos usuários; apenas
  o nome de exibição do remetente será centralizado.

## Critérios de aceite

1. O registro de tenant que tinha código `GPRB` passa a ter código
   `SCG33REAA`, conservando o mesmo `id`.
2. Consultas de leitura e escrita da aplicação usam `GPRB_TENANT_CODE`, sem
   defaults ou SQLs operacionais fixados em `GPRB`.
3. As rotas sob `/iniciacao/` funcionam e os endpoints correspondentes sob
   `/recepcao/` continuam acessíveis como aliases.
4. O menu exibe **Iniciação** e a página exibe **Flow de Iniciação**.
5. Login e ativação exibem **SAL DA AMORIO**; o logout apresenta a confirmação
   e volta para a tela de login.
6. E-mails automáticos usam **SAL DA AMORIO** como nome de remetente; os e-mails
  de ativação e notificações de candidatos mostram a marca prevista, mantendo
  endereço de remetente, identidade formal do Grande Priorado e conteúdo de
  campanha personalizados.
7. Os registros de tenant e usuário permanecem intactos; a limpeza de membros,
   vínculos, lojas e vales não é repetida.
8. Após a reconstrução/reinicialização, os containers ficam saudáveis, a rota
   canônica responde e o asset `logow.webp` é servido.

## Plano de verificação

- Testar a configuração central de tenant e a seleção correta de dados em
  consultas de leitura e escrita.
- Testar a atualização transacional de `tenant.code`, inclusive colisão e
  ausência do código esperado.
- Testar a reversão de rotas, aliases antigos, métodos POST e rótulo do menu.
- Testar a marca de login, mensagem de logout, remetente de e-mail, e-mail de
  ativação e assinatura das notificações de candidatos.
- Executar `python manage.py check` e os testes focados; executar a suíte do
  projeto e registrar falhas não relacionadas já presentes no ambiente.
- Reconstruir/reiniciar os containers ativos do Compose e verificar status,
  resposta HTTP da aplicação e disponibilidade do logo.

## Limites de escopo

- Não alterar o conteúdo das campanhas escrito pelos usuários.
- Não remover os outros cinco tenants, usuários ou qualquer linha de tenant.
- Não repetir a limpeza de membros, vínculos, lojas ou vales já executada.
- Não renomear módulos, namespaces Python, nomes internos de funções ou
  identificadores do produto fora das telas de autenticação e mensagens de
  e-mail descritas acima.
