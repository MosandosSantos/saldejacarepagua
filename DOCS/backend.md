# Backend (Django)

Stack: **Django ≥5.2**, `psycopg` (PostgreSQL), `python-dotenv`, `PyJWT`,
`email-validator`, `cryptography`, `reportlab`, `qrcode`. Ver `requirements.txt`.

## Apps e modelos

### acesso — empresa, usuários e papéis

- `Tenant` — empresa/negócio: `nome`, `slug` (único), `nicho`, `meta_mensal`,
  `dono` (FK), `token_captura`/`captura_ativa` (formulário de captura),
  `softphone_schema`/`softphone_dominio`, `pix_chave`/`pix_recebedor`/`pix_cidade`.
- `Usuario` — `nome`, `email` (único), `senha` (hash), `role`, `tenant` (FK, pode ser null).
  Papéis: `admin_saas`, `admin_company`, `operacional`, `viewer`
  (`ROLES_QUE_EDITAM` = saas + company + operacional).
- `MetaVendedor` — meta mensal por vendedor (`usuario`, `mes`, `valor`).
- `Convite` — convite por e-mail com token, papel, expiração (`expira_em`), uso/cancelamento.

### contatos — cadastro, negócios e CRM

- `Carteira` — carteira de contatos (nome, descrição, tenant).
- `Tag` — etiqueta colorida (nome, cor, tenant).
- `Contato` — dados cadastrais (nome, empresa, `tel_normalizado` indexado, e-mail,
  segmento, origem, pagamento, nascimento, CPF/CNPJ/razao/CNAE/endereço,
  `lead_score`, `carteira` FK, `tags` M2M, tenant).
- `Negocio` — oportunidade: `contato` FK, `stage`, `valor`, `principal`,
  `responsavel` FK, tenant.
- `CampoPersonalizado` / `ValorCampoPersonalizado` — campos extras por tenant
  (texto/número/lista/data etc.) e seus valores por contato.
- `Nota` — anotações no contato.
- `Movimentacao` — histórico de movimentações do contato.

### agendamentos

- `Agendamento` — `contato` FK, `hora` (HH:MM), `offset_dias` (dias a partir de hoje),
  `tipo`/`tipo_label`.

### funil

- `EtapaFunil` — etapa do pipeline: `key` (chave interna salva em `Negocio.stage`),
  `nome`, `cor`, `ordem`, `peso` (probabilidade), `sistema` (etapas padrão protegidas).
  Etapas reservadas: `fechado`, `perdido`.

### emails

- `ModeloEmail` — modelo com `assunto` e `corpo` (com variáveis `{{contato.*}}`).
- `EmailEnviado` — envio rastreado: `status`, `token` (pixel), `aberto_em`,
  `cliques`, `convertido_em`, `campanha` FK.

### tarefas

- `Tarefa` — `titulo`, `descricao`, `contato` FK, `responsavel` FK,
  `prioridade` (baixa/média/alta), `vencimento`, `concluida`/`concluida_em`,
  `criado_por` FK, tenant.

### automacoes

- `Automacao` — regra no-code: `trigger` + `parametros` (JSON), `ativa`,
  `ultima_execucao`, `total_execucoes`.
  Gatilhos: `contato_criado`, `negocio_criado`, `negocio_movido`, `negocio_estagnado`.
- `PassoAutomacao` — ação em ordem: `tarefa`, `nota`, `tag`, `email` (parâmetros JSON).
- `RegistroExecucao` — log por execução (`ok`/`erro`, mensagem).

### campanhas

- `Campanha` — `nome`, `descricao`, `canal` (`email`), `ativa`, tenant.

### discador

- `Script` — roteiro de atendimento (`conteudo` com variáveis `{{contato.*}}`).
- `Fila` — `carteira` FK, `script` FK, `ordem` (score/data/aleatória), `ativa`.
- `Chamada` — `fila`, `contato`, `operador` FK, `status` (discada/realizada/…),
  `observacao`, `retorno_em` (agendamento de retorno), tenant.

### acordos

- `RegraDesconto` — desconto por `modalidade` + `parcelas` (ex.: à vista 30%).
- `Acordo` — `contato`, `chamada`, `valor_original`, `modalidade`, `parcelas`,
  `percentual_desconto`, `desconto`, `valor_final`,
  `status` (proposta/aceito/pix_gerado/enviado/pago/recusado),
  `pix_payload` (BR Code), `pago_em`, tenant.

### relatorios

- Sem modelos — lê dos apps existentes (chamadas, acordos, contatos).

### dashboard

- Sem modelos — agrega dos apps existentes (KPIs, funil, timeline, metas).

## Camada de views web (funções)

Padrão: view = função que (1) valida sessão com decorators, (2) monta o escopo com
`filtro_tenant`, (3) renderiza `templates/<app>/<tela>.html`.

Decorators (em `acesso/decorators.py`):
- `web_login_required` — exige sessão; redireciona para `/login/`.
- `web_requer_admin` — exige admin (da empresa ou da plataforma); senão → dashboard.
- `web_requer_edicao` — exige permissão de edição (viewer volta para a origem).
- `filtro_tenant(request, qs)` — escopa o queryset para o tenant da sessão.

## Comandos de gerenciamento

| Comando | App | Descrição |
|---|---|---|
| `python manage.py seed_usuarios` | acesso | Cria os usuários de seed (admin, dona Aurora, recepção) |
| `python manage.py verificar_estagnados` | automacoes | Dispara automações de negócios estagnados |
| `python manage.py enviar_relatorio [--tenant <id>] [--periodo hoje\|7\|30\|mes]` | relatorios | Gera o PDF do relatório por empresa e envia aos admins (sem SMTP: modo simulação) |

## Serviços auxiliares

- `emails/servico.py` — renderização de templates (`{{contato.*}}`), reescrita de
  links com tracking, pixel de abertura, envio (SMTP real ou modo simulação),
  marcação de conversões.
- `contatos/importador.py` — importação de contatos via CSV (com modelo baixável).
- `contatos/scoring.py` — cálculo do `lead_score`.
- `contatos/orcamento.py` — geração do orçamento em PDF (reportlab).
- `discador/softphone.py` — montagem da URI de chamada (sip:/tel:) por empresa.
- `acordos/servico.py` — simulação de opções de acordo e regras de desconto.
- `acordos/pix.py` — montagem do payload PIX (BR Code, EMV/TLV + CRC16) e QR Code SVG.
- `automacoes/engine.py` — motor de execução das automações (gatilho → ações).
- `core/segredos.py` — criptografia AES-256-GCM de segredos (chave derivada de
  `SECRET_KEY`/`CRYPTO_KEY`).
