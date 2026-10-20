# Teste de carga com Locust

O serviço Locust é opcional e só inicia com o perfil `load-test`. Ele simula
usuários autenticados percorrendo páginas somente de leitura do CRM.

1. Configure `LOCUST_USERNAME`, `LOCUST_PASSWORD` e `LOCUST_TURNSTILE_TOKEN` no
   `.env` com uma conta de teste. Não use credenciais de produção. Para um
   ambiente local com as chaves oficiais de teste do Turnstile, use
   `LOCUST_TURNSTILE_TOKEN=XXXX.DUMMY.TOKEN.XXXX`.
2. Inicie o Locust (o Compose também inicia a aplicação e suas dependências, se
   necessário):

   ```sh
   docker compose --profile load-test up -d locust
   ```

3. Abra <http://localhost:8089>, informe o número de usuários e a taxa de subida
   e inicie o teste. A interface mostra latência, requisições por segundo e
   falhas.
4. Ao terminar, pare o serviço:

   ```sh
   docker compose --profile load-test stop locust
   ```

O cenário faz login uma vez por usuário e então acessa `/dashboard/`,
`/iniciacao/`, `/tarefas/` e `/contatos/` com requisições GET. O usuário e senha
são lidos de `LOCUST_USERNAME`, `LOCUST_PASSWORD` e `LOCUST_TURNSTILE_TOKEN`; os
dados de login não ficam gravados no código.
