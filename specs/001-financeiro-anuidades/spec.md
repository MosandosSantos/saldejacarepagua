# Feature Specification: Financeiro — Anuidades e Mensalidades

**Feature Branch**: `001-financeiro-anuidades`

**Created**: 2026-10-02

**Status**: Draft

**Input**: User description: "Módulo Financeiro real substituindo o placeholder `/contatos/financeiro/`: gestão de anuidades de membros e mensalidades de lojas sobre as tabelas payment/payment_period/payment_status, com resumo de recebíveis, registro de pagamentos e períodos de cobrança."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visão consolidada de recebíveis (Priority: P1)

A tesouraria abre a tela Financeiro e enxerga, num único painel, a situação financeira da organização no período atual: total recebido, total em aberto, quantidade de membros devedores de anuidade e quantidade de lojas devedoras de mensalidade — podendo filtrar por período, loja, potência e status.

**Why this priority**: é o valor central do módulo — responder "para quem falta cobrar e quanto já entrou" sem cruzar planilhas. Sozinha, esta história já substitui o controle manual atual.

**Independent Test**: com pagamentos cadastrados manualmente, a tela exibe totais e listas de devedores consistentes com os dados; pode ser demonstrada com dados de exemplo.

**Acceptance Scenarios**:

1. **Given** existem 3 membros com anuidade em aberto e 2 lojas com mensalidade em aberto no período, **When** a tesouraria acessa o Financeiro, **Then** o resumo mostra "3 devedores de anuidade", "2 lojas devedoras" e os totais de valor recebido e em aberto daquele período.
2. **Given** a tesouraria filtra por uma loja específica, **When** aplica o filtro, **Then** as listas e totais refletem apenas membros/lojas daquela loja (respeitando o vínculo N:N membro↔lojas).
3. **Given** um usuário com papel `viewer`, **When** acessa o Financeiro, **Then** vê todos os dados em modo somente leitura e não consegue registrar nem alterar pagamentos.

---

### User Story 2 - Registrar pagamento (Priority: P2)

A tesouraria registra o pagamento da anuidade de um membro ou da mensalidade de uma loja: escolhe o pagador (membro/loja), o período de cobrança, valor, forma de pagamento e data; o registro passa a contar como pago no resumo e sai das listas de devedores (ou reduz o valor devido, se parcial).

**Why this priority**: é a ação operacional diária do módulo; sem ela a visão consolidada não se mantém atualizada. Depende apenas da existência de períodos, não das outras histórias.

**Independent Test**: registrar um pagamento e verificar que o pagador sai da lista de devedores e o total recebido aumenta no valor registrado.

**Acceptance Scenarios**:

1. **Given** um membro devedor da anuidade do período atual, **When** a tesouraria registra o pagamento completo (valor integral, forma e data), **Then** o membro sai da lista de devedores e o status dele no período passa a "pago".
2. **Given** uma loja devedora da mensalidade do mês, **When** é registrado um pagamento **parcial**, **Then** o registro fica com status "parcial" com o valor pago destacado e a loja permanece na lista de devedores com o saldo remanescente.
3. **Given** um pagamento registrado por engano, **When** a tesouraria o estorna, **Then** o pagador volta a constar como devedor e o histórico preserva quem estornou e quando.

---

### User Story 3 - Gerenciar períodos de cobrança (Priority: P3)

A tesouraria cria e edita os períodos de cobrança que organizam os pagamentos: um período de **anuidade** por exercício (ex.: "Anuidade 2027") e períodos de **mensalidade** por mês de loja. O valor de referência da mensalidade (regular e remido) vem do cadastro da loja; anuidade de membro tem valor definido no período.

**Why this priority**: estrutura os dados e permite preparar exercícios futuros, mas o módulo já entrega valor com períodos criados sob demanda — por isso vem depois das histórias 1 e 2.

**Independent Test**: criar um período de anuidade para o próximo exercício e vê-lo disponível nos seletores de registro de pagamento e filtro.

**Acceptance Scenarios**:

1. **Given** que não existe período para o próximo exercício, **When** a tesouraria cria o período "Anuidade 2027" com valor de referência, **Then** ele aparece nos seletores do registro de pagamento e no filtro do resumo.
2. **Given** um período sem nenhum pagamento vinculado, **When** a tesouraria o edita (valor/rótulo), **Then** a alteração é aplicada e refletida em todas as telas.
3. **Given** um período com pagamentos já registrados, **When** a tesouraria tenta excluí-lo, **Then** o sistema impede a exclusão e explica o motivo (integridade dos pagamentos existentes).

---

### Edge Cases

- Membro sem loja vinculada: permanece cobrável de anuidade (anuidade é por membro, não por loja).
- Membro INATIVO: não entra como devedor em novos períodos por padrão, mas pagamentos retroativos dele permanecem visíveis.
- Loja com `mensalidadeAtiva` desligada: sai das listas de mensalidade em aberto, preservando histórico.
- Valor pago maior que o devido: sistema impede registro acima do devido e orienta lançar como adiantamento/donativo em observações (v1).
- Pagador duplicado no mesmo período (anuidade já paga): sistema impede novo registro de anuidade para o mesmo membro/período.
- Acesso por `viewer`: todas as ações de escrita bloqueadas com mensagem clara.
- Sem períodos cadastrados: tela exibe estado vazio orientando criar o primeiro período, sem erro.
- Valores nulos/zerados exibidos conforme convenção do sistema (`'—'` para vazio, `R$ 0,00` quando zero).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST exibir, na tela Financeiro, um resumo consolidado por período de cobrança com: total recebido, total em aberto, contagem de membros devedores de anuidade e contagem de lojas devedoras de mensalidade.
- **FR-002**: O sistema MUST listar membros com anuidade em aberto por período, com busca por nome e filtro por loja/potência (considerando o vínculo N:N membro↔lojas).
- **FR-003**: O sistema MUST listar lojas com mensalidade em aberto por período, com filtro por potência e status.
- **FR-004**: O sistema MUST permitir registrar pagamento de anuidade (membro + período/ano) e de mensalidade (loja + período/ano-mês) informando valor, forma de pagamento, data, referência e observações.
- **FR-005**: O sistema MUST permitir marcar/alterar o status de um pagamento (pago, parcial, cancelado) preservando quem registrou/alterou e quando.
- **FR-006**: O sistema MUST permitir criar e editar períodos de cobrança com tipo (anuidade/mensalidade), exercício/mês, rótulo e valor de referência; exclusão só quando não houver pagamentos vinculados.
- **FR-007**: O sistema MUST impedir pagamento de anuidade duplicado para o mesmo membro no mesmo período e pagamento acima do valor devido.
- **FR-008**: O sistema MUST respeitar papéis: `viewer` somente leitura; registro/estorno apenas para papéis com permissão de edição.
- **FR-009**: O sistema MUST escopar todos os dados financeiros ao tenant da sessão (isolamento multi-tenant).
- **FR-010**: O sistema MUST exibir valores monetários em reais e aplicar a convenção de dados do sistema (vazio = `'—'`).
- **FR-011**: O sistema MUST substituir o conteúdo placeholder da rota Financeiro pela implementação real, mantendo a rota e o item de menu atuais.

### Key Entities *(include if feature involves data)*

- **Pagamento**: movimento financeiro unitário — pagador (membro ou loja), tipo (anuidade/mensalidade), período (exercício e, para mensalidade, mês), valor, forma de pagamento, data do pagamento, status, referência, observações, quem registrou. Pertence a um tenant.
- **Período de cobrança**: agrupador temporal dos pagamentos — tipo (anuidade/mensalidade), exercício/mês, rótulo, valor de referência (para anuidade); mensalidade de loja usa o valor do cadastro da loja (regular/remido).
- **Situação do pagador no período**: consolidação por membro/período — status (em aberto, parcial, pago), valor devido/pago, forma e data do último pagamento, observações.
- **Membro / Loja**: pagadores; membro cobrável por anuidade (ativo), loja cobrável por mensalidade (quando mensalidade ativa).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A tesouraria identifica todos os devedores de um período em menos de 30 segundos (abrir tela → lista filtrada), sem usar planilha externa.
- **SC-002**: Registrar um pagamento leva menos de 1 minuto (selecionar pagador → período → valor/forma → confirmar) e o resumo se atualiza imediatamente.
- **SC-003**: 100% dos pagamentos registrados aparecem no resumo com totais exatos (zero divergência entre lista e totalizador).
- **SC-004**: Nenhum dado financeiro de outro tenant é visível em nenhuma condição (verificação por teste automatizado).
- **SC-005**: Usuário `viewer` consegue consultar tudo mas zero ações de escrita ficam disponíveis (verificação por teste).

## Assumptions

- V1 é **registro manual** de pagamentos (dinheiro, PIX, transferência, boleto — forma informada livremente). Integração com gateway/PIX automático **fora do escopo** da v1 (decisão do dono do produto, 2026-10-02) — candidato a feature futura.
- Cobranças são criadas **sob demanda** (registro individual por pagador). Geração em lote de pendências **fora do escopo** da v1 (default recomendado confirmado por omissão) — feature futura.
- Sem emissão de recibo/comprovante em PDF na v1 (default recomendado confirmado por omissão); a referência e observações do pagamento servem de registro. Feature futura.
- Papéis existentes (admin_saas/admin_company/operacional/viewer) são reutilizados sem novo papel de "tesoureiro" na v1.
- Os períodos e status existentes no modelo de dados (catálogo) são reutilizados; a primeira configuração de períodos faz parte da operação pós-implantação.
