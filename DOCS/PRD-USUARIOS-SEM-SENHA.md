# PRD — Criação de usuário do sistema sem senha (ativação por link 72h)

> **Data:** 2026-09-03 · **Status:** Proposta refinada pelo dono do produto (aguarda só a lista exata de valores de perfil)
> **Escopo:** contas de **usuário do sistema** (login no GPRBRCRM) para o **Tenant de todos** (âmbito que
> engloba a organização — ver §10). **Não** envolve o cadastro de "membros" do diretório GPRB (`saldogprb.member`).

## 1. Visão geral

Hoje o admin cria usuário digitando a **senha ele mesmo** (`acesso/views.py::equipe`) ou envia um
**convite por link** de 7 dias (`Convite`), no qual a pessoa informa nome + senha na página pública.

Queremos o fluxo de "conta criada pela administração, senha escolhida pelo próprio usuário":

1. Uma pessoa autorizada cria o usuário informando **nome + e-mail + celular + perfil** — **sem senha**.
2. O sistema cria a conta **imediatamente** no tenant de abrangência ("Tenant de todos") em estado `pendente` (sem acesso).
3. Um **e-mail automático** vai ao usuário com um **link de ativação único válido por 72 horas**.
4. Dentro do prazo, o usuário abre o link, **define e confirma a senha** (política vigente) e passa a ter acesso.
5. Após 72h **sem uso**, o link perde a validade (pode ser reenviado por quem tem permissão).

O vocabulário de perfis é o do sistema RER (oficialato). Só **Grão Prior, Grande Chanceler, Grande
Tesoureiro, Prefeito, Deputado e TI** podem criar/reenviar usuários.

## 2. Perfis (usuários do sistema)

Pendência de dados: valores exatos a confirmar na tabela de usuários do sistema (banco RER).
Perfis definidos pelo dono do produto para esta versão:

| Perfil (rótulo) | Permite criar/reenviar usuários? |
|---|---|
| Grão Prior | ✅ Sim |
| Grande Chanceler | ✅ Sim |
| Grande Tesoureiro | ✅ Sim |
| Prefeito | ✅ Sim |
| Deputado | ✅ Sim |
| TI | ✅ Sim |
| (demais perfis do RER — a completar) | ❌ Não, salvo indicação |

Observações:
- "Perfil" aqui é o papel de **usuário do sistema** (permissões de acesso ao CRM), **não** cargo de
  membro no diretório GPRB.
- Enquanto a lista do RER não for fornecida, o sistema usa uma constante `ROLES_USUARIO` com os
  três perfis acima + espaço para os demais; **aceite final exige** a lista real (ver Pendências).

## 3. Fluxo atual (para referência)

| Hoje | Onde | Observação |
|---|---|---|
| Criar usuário com senha | `equipe()` (POST nome/email/senha/papel) | senha digitada pelo admin |
| Convite por link (7 dias) | `config()` → `Convite` + página pública `convidar/<token>/` | usuário também digita o **nome** |
| Perfis atuais | `admin_saas`, `admin_company`, `operacional`, `viewer` | vocabulário CRM atual |

O novo fluxo **substitui** a criação com senha digitada pelo admin na tela de usuários.

## 4. Fluxo proposto (passo a passo)

### 4.1 Criar usuário (quem pode: Grão Prior, Grande Chanceler, Grande Tesoureiro, Prefeito, Deputado, TI)
- Página de Usuários mostra formulário: **Nome \* · E-mail \* · Celular · Perfil \*** (sem campo de senha).
- Validações: e-mail válido; e-mail **não pode** já existir (ativo ou pendente); perfil pertence à
  lista permitida; quem cria precisa ter perfil autorizado (senão o formulário nem aparece).
- Ao salvar:
  - `Usuario` criado com `status='pendente_senha'`, sem senha utilizável, `criado_por` registrado;
  - gera `token_ativacao = secrets.token_urlsafe(32)` e `ativacao_expira_em = agora + 72h`;
  - dispara e-mail com o link `https://<host>/usuario/ativar/<token>/`.
- Sem SMTP configurado (dev), o envio roda em **modo simulação** (log/console com o link), igual ao
  padrão de `emails/servico.enviar_mensagem`.

### 4.2 Ativar senha (o usuário)
- Página pública `ativar/<token>/`:
  - token inválido → mensagem de erro;
  - token **expirado** (>72h) → aviso "link expirou — peça um novo";
  - token **já usado** → aviso "conta já ativada — faça login";
  - válido → formulário **Nova senha + Confirmação** (política `AUTH_PASSWORD_VALIDATORS`);
  - confirma → grava hash, `status='ativo'`, limpa token, faz login automático e redireciona ao dashboard.
- Reenvio: quem pode criar também pode **reenviar** o e-mail de um usuário pendente (novo token, +72h).

### 4.3 E-mail de ativação
- Assunto: "Ative seu acesso ao GPRBRCRM".
- Corpo: nome, link, validade **72 horas**, aviso "se você não pediu, ignore".
- Enviado via `emails/servico.enviar_mensagem` (rotina única criada no PRD 4.1).

## 5. Regras de segurança

- Token de ativação: `token_urlsafe(32)` → 256 bits, uso **único**, sem armazenamento em log.
- Expiração **72h** rígida; link expirado não ativa.
- Senha: política atual (mín. 8, validators `acesso.validators`), nunca definida pela administração.
- Reenvio com throttle/limite (ex.: máximo 3 por usuário pendente) para evitar spam de e-mail.
- Login de usuário `pendente_senha`: bloqueado (não autentica até ativar).
- Auditoria: `criado_por`, `criado_em`, `ativado_em` gravados no usuário.
- CSRF + validação de e-mail na página pública de ativação (mesmos padrões do convite atual).

## 6. Fora de escopo (nesta versão)

- Recuperação de senha por e-mail (fluxo separado, se desejado).
- Criação de usuários pela API (manter somente web nesta versão).
- Qualquer escrita em "membros" do banco GPRB/saldogprb.
- Papéis/convites do funil de captura.

## 7. Impacto e compatibilidade

- `acesso/models.py::Usuario`: novos campos `status`, `token_ativacao`, `ativacao_expira_em`,
  `ativado_em`, `criado_por` (ou tabela de ativação à parte — decidir na implementação).
- `acesso/views.py::equipe` (tela de Usuários): deixa de pedir senha → passa a criar pendente + e-mail.
- Página pública nova `ativar` + rotas de reenvio (admin).
- `Convite` (7 dias) permanece? **Decisão:** manter apenas se ainda for usado por outro fluxo; caso
  contrário, marcar como legado e remover em sprint seguinte (evitar duplicidade — PRD 3.3).
- Menu "Usuários" já existe (renomeado de Configurações) — hospeda a gestão.

## 8. Sprint de implementação (proposta)

| # | Tarefa | Esforço |
|---|---|---|
| 1 | Model: campos de ativação + migração; constantes de perfis `ROLES_USUARIO` e de quem pode criar | M |
| 2 | Criar usuário sem senha (validações, criado_por, token) + tela/rotas (substitui o fluxo de `equipe`) | M |
| 3 | E-mail de ativação via `enviar_mensagem` (modo simulação OK) | P |
| 4 | Página pública `ativar/<token>/`: expirado/útil/usado + definir senha + login automático | M |
| 5 | Reenvio de link (novo token 72h) com limite | P |
| 6 | Permissão: só Chanceler/TI/Grão Prior veem o formulário (gate por papel no `_nav_itens`/view) | P |
| 7 | Bloquear login de `pendente_senha`; auditoria | P |
| 8 | Testes: criação, validade 72h, expirado, reuso, permissões, senha sem admin | M |
| 9 | Docs: atualizar `DOCS/architecture.md` (fluxo de acesso) | P |

## 9. Critérios de aceite

1. Criar usuário pede apenas nome, e-mail, celular e perfil — **sem senha**.
2. E-mail sai automaticamente com link; em dev (sem SMTP) o link aparece na simulação.
3. Link ativa somente dentro de **72h**; expirado mostra aviso e não ativa.
4. Token tem uso único e não fica em logs.
5. Usuário pendente **não** consegue logar antes de ativar.
6. Só **Grão Prior, Grande Chanceler, Grande Tesoureiro, Prefeito, Deputado e TI** conseguem criar/reenviar.
7. A senha é definida **pelo usuário** na página do link, com a política vigente.
8. `manage.py check` limpo; suíte de testes relevante passando (baseline conhecida).

## 10. Pendências (bloqueiam a implementação)

1. **Lista exata de valores de perfil do banco RER** — o dono vai colar os valores como estão na
   tabela de usuários do sistema (ex.: `GRAO_PRIOR`, `GRANDE_CHANCELER`, `GRANDE_TESOUREIRO`,
   `PREF`, `DEP`/`DEPUTADO`, `TI`…). Hoje não existem em banco acessível local.
2. **"Tenant de todos"**: confirmar o escopo do tenant onde a conta é criada — (a) plataforma/global
   (sem tenant, como `admin_saas`) que enxerga todos os dados; (b) o tenant único GPRB do CRM; ou
   (c) outro tenant especial. Afeta o RBAC (menu, `web_requer_*`) e o isolamento multi-tenant.
3. Os perfis RER **substituem** os atuais (`admin_company`/`operacional`/`viewer`) ou **coexistem**?
   (afeta RBAC existente, seed e telas que dependem de `role`).
4. Destino do fluxo `Convite` atual (7 dias) e da tela antiga com senha: substituir de vez ou manter
   em paralelo durante transição.
5. Confirmação de que o "celular" entra no formulário de criação e também no perfil/contato do usuário.

---

## 11. Registro de execução (2026-09-03)

**Status: IMPLEMENTADO** (Sprint 1–5), com as premissas abaixo; falta apenas colar a lista real de
perfis do banco RER para renomear as constantes placeholder.

**Premissas aplicadas no código** (fáceis de ajustar depois):
1. Perfis placeholder: `grao_prior`, `grande_chanceler`, `grande_tesoureiro`, `prefeito`, `deputado`, `ti`
   (`ROLE_*` em `acesso/models.py`), **coexistindo** com `admin_company`/`operacional`/`viewer`.
2. Quem pode criar/reenviar: `ROLES_GESTORES_USUARIOS` = oficialato (6 perfis) + `admin_company`
   legado (para não quebrar a gestão atual de equipe). Papéis atribuíveis ao criar:
   `ROLES_ATRIB_CRIACAO` = oficialato + papéis legados de tenant.
3. Criação no **tenant do gestor da sessão** (mesmo isolamento multi-tenant de hoje); para um
   gestor "sem tenant" o escopo seria global — não aplicável até os perfis RER existirem de fato.
4. Fluxo legado `Convite` (7 dias) **mantido** em paralelo na página Usuários, só para `admin_company`.

**O que entrou** (verificado por testes):
- `acesso/ativacao.py` — rotinas únicas: `criar_usuario_pendente`, `reenviar_ativacao`
  (limite 3, token novo), `enviar_email_ativacao` (via `emails.servico.enviar_mensagem`;
  em dev/sem SMTP loga o link — modo simulação) e `ativar_senha`.
- `Usuario`: `status` (`ativo`/`pendente_senha`), `token_ativacao`, `ativacao_expira_em` (72h),
  `ativado_em`, `criado_por`, `reenvios_ativacao`, `celular` — migração `0015`.
- Views: `equipe()` e a ação `criar_usuario` do `config()` criam **sem senha** (nome/e-mail/celular/perfil);
  ação `reenviar_ativacao` nas duas telas. View pública nova `ativar_conta` (rota
  `usuario/ativar/<token>/`) com estados válido/expirado/usado + login automático.
- Login de pendente **bloqueado** nos 3 caminhos (CRM local, fallback GPRB, Saldorer).
- Menu/nav: item Equipe visível para gestores; labels dos 6 perfis em `ROLE_LABELS`;
  oficialato pode editar (`ROLES_QUE_EDITAM`).
- Templates: `equipe.html` e `config.html` sem campo de senha + situação "Aguardando ativação/Ativo"
  + botão Reenviar; `ativar.html` novo (mesmo padrão visual do convite).

**Testes**: `teste/test_ativacao_web.py` (6/6) e `teste/test_equipe.py` (20/20 na área de equipe;
  a falha de `test_operacional_nao_ve_botao_excluir` é pré-existente da sessão anterior — lista
  `/contatos/` virou membros GPRB e não foi tocada neste fluxo).

**Pendências ainda abertas** (decisões de produto): lista exata dos valores RER (renomear
constantes), destino do `Convite` legado, e expor ou não o fluxo para `admin_company` no fim.
