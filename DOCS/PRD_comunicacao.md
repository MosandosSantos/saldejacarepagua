# PRD — Módulo de Comunicação (CEOD CRM)

**URL:** `/comunicacao/` (view `gestao:comunicacoes`, exige login)
**Objetivo:** enviar comunicações em massa (ou individuais) por **E-mail** ou **WhatsApp** para congressistas do evento ativo, listas importadas ou contatos avulsos, com personalização por destinatário e histórico auditável.

---

## 1. Visão Geral

Painel único com 3 áreas:
1. **Status da conexão WhatsApp** (painel colapsável, só aparece ao selecionar canal ZAP) — mostra badge Conectado/Desconectado, QR Code para pareamento inicial e botão "Gerar novo QR Code".
2. **Formulário de envio** — canal, origem, filtros, assunto/corpo, botão Enviar.
3. **Histórico de comunicações** — tabela das últimas 30 campanhas (canal, conteúdo, origem, enviados, falhas, status, data).

---

## 2. Canais de Envio

| Canal | Campos obrigatórios | Transporte | Particularidades |
|-------|---------------------|------------|-----------------|
| EMAIL | assunto + corpo | SMTP (Django `send_mail` / `common/emails.py`) | corpo aceita HTML; placeholders aplicados |
| ZAP   | apenas corpo (texto) | PyWhatKit (WhatsApp Web no navegador padrão) | intervalo mínimo **90s** entre envios (política WA); pareamento via QR no navegador padrão |

---

## 3. Origens de Destinatários

Duas opções no select **Destino** (vale para E-mail e WhatsApp):

- **Individual** (`individual`) — uma pessoa: `ind_nome` (opcional) + `ind_contato` (e-mail ou celular).
- **Coletivo** (`prefeituras`) — Prefeituras / Lojas, com dois níveis de seleção:

### 3.1 Select de Prefeitura (coletivo — obrigatório)
- Opção **"Todas as prefeituras"** (padrão) ou uma prefeitura específica do banco GPRB (`listar_prefeituras`).

### 3.2 Select de Loja (opcional — só aparece com prefeitura específica)
- Lista as lojas da prefeitura escolhida (`listar_lojas` / endpoint `contatos:prefeitura_lojas_json`).
- A opção em branco ("— Prefeito da prefeitura —") mantém o envio para o Prefeito.

### 3.3 Regra de destinatário
- **Prefeitura** (Todas ou específica, sem loja) → contato do **Prefeito**: `prefeitura.prefeito` (nome), `prefeitura.email` (E-mail) e `prefeitura.telefone` (WhatsApp).
- **Loja** selecionada → contato do **Deputado Mestre** da loja: `loja."deputadoMestreId"` aponta para um `member` da própria loja (nome/e-mail/celular vêm do `member`).
- Linhas sem o contato exigido pelo canal são ignoradas e reportadas nos erros.

### 3.4 Colunas novas no banco GPRB (schema compartilhado — operador cria)
```sql
ALTER TABLE prefeitura ADD COLUMN IF NOT EXISTS email VARCHAR(200);
ALTER TABLE loja ADD COLUMN IF NOT EXISTS "deputadoMestreId" UUID REFERENCES member(id);
```
- Tela: **Prefeituras** (novo/editar) ganhou o campo "E-mail do Prefeito"; **Lojas** (editar) ganhou o select "Deputado Mestre" com os membros ativos da loja.
- Sem as colunas, as consultas degradam com mensagem amigável apontando este item.

---

## 4. Personalização (Placeholders)

No corpo da mensagem:
- `{{NOME}}` → nome do destinatário
- `{{EMAIL}}` → e-mail
- `{{CELULAR}}` → telefone

Aplicados via `common/emails.py::_aplicar_placeholders(corpo, destinatario)`.

---

## 5. Modelo de Dados — `Campanha` (`common/models.py`)

```python
class Campanha(models.Model):
    CANAIS = [("EMAIL","E-mail"), ("ZAP","WhatsApp")]
    ORIGENS = [("prefeituras","Coletivo (Prefeituras / Lojas)"), ("individual","Individual (uma pessoa)")]
    STATUS = [("rascunho",...), ("enviando",...), ("enviada",...), ("falha","Falha parcial")]

    canal, assunto, corpo
    origem, filtros(JSON), destinatarios(JSON list of {nome,email|zap})
    total_enviados, total_falhas, status
    criado_por, criado_em, enviado_em
```
- `destinatarios` é snapshot da lista no momento do envio (auditoria).
- `filtros` guarda os filtros aplicados.

---

## 6. Fluxo de Envio (Backend)

1. POST do formulário → valida corpo (e assunto se EMAIL) e monta `destinatarios`.
2. Cria `Campanha(status="rascunho")`.
3. Dispara `_enviar_campanha_async(campanha.id)` — **thread daemon** (não bloqueia o request).
4. Thread: `status="enviando"` → `enviar_campanha(campanha)` → ao fim, `status="enviada"` (ou `"falha"` em exceção, logada via `logger.error`).

### 6.1 `enviar_campanha` (em `gestao/comunicacao.py`)
- Para cada destinatário aplica placeholders e despacha:
  - EMAIL → `emails.servico.enviar_mensagem(...)` (SMTP real ou 'simulado' sem SMTP)
  - ZAP → `whatsapp.enviar_lote(destinatarios, corpo, intervalo=90)`
- Atualiza `total_enviados` / `total_falhas`.

---

## 7. Integração WhatsApp (`gestao/whatsapp.py`)

- **Motor:** PyWhatKit (`pywhatkit.sendwhatmsg_instantly`) — abre `https://web.whatsapp.com/send?phone=+55...&text=...` no **navegador padrão** da máquina e pressiona Enter (pyautogui). A conta precisa estar pareada nesse navegador (abrir web.whatsapp.com e escanear o QR uma única vez).
- **`verificar_conexao()`** → `{configurado, conectado, detalhe, erro}` — o pywhatkit não expõe o estado da sessão; `configurado` reflete a disponibilidade do pacote e `detalhe` orienta o pareamento.
- **`obter_qr_code()`** → `{logado, qr_base64, erro}` — sem imagem (o QR é gerado pelo próprio WhatsApp Web no navegador do operador); `detalhe` traz o passo a passo.
- **`enviar_lote(envios, intervalo=90)`** → para cada `{numero, texto}`: `_limpar_numero` (DDI 55) e envio via pywhatkit; falha individual é contada e logada (nunca aborta o lote).
- **Rate limit:** `time.sleep(90)` entre envios (exceto último).
- **Lock:** `_LOCK` (threading) impede lotes simultâneos.
- **Degradação graciosa:** sem pywhatkit/internet, `configurado=False` e a campanha ZAP vira `falha` com log — o painel nunca quebra.

---

## 8. Endpoints

| Rota | View | Método | Retorno |
|------|------|--------|---------|
| `/comunicacao/` | `comunicacoes` | GET/POST | página / cria campanha |
| `/comunicacao/zap-status/` | `zap_status` | GET | JSON `{configurado, conectado, detalhe, erro}` |
| `/comunicacao/zap-qrcode/` | `zap_qrcode` | GET | JSON `{logado, qr_base64, erro}` |

---

## 9. Requisitos de Infra

- Chromium + Xvfb + python3-xlib instalados na imagem (Dockerfile).
- `BROWSER="chromium --no-sandbox %s"` (navegador padrão do pywhatkit) e CMD sob `xvfb-run -a` (display para o pyautogui).
- `pywhatkit`, `openpyxl` no `requirements.txt`.
- Container com acesso a saída HTTPS (web.whatsapp.com) — sem bloqueio de rede (o import do pywhatkit checa internet).

---

## 10. Regras de Negócio / Validações

- Corpo obrigatório sempre.
- Assunto obrigatório só para EMAIL.
- Cadastrados: ignora quem não aceita comunicação (`aceita_comunicacao=False`) e quem não tem o campo de contato.
- Sem destinatários → erro e não cria campanha.
- ZAP: respeita 90s entre envios (pode levar muito tempo para lotes grandes — por isso envio em thread).

---

## 11. Histórico / Auditoria

- Tabela mostra últimas 30 `Campanha` (`Campanha.objects.all()[:30]`).
- Cada criação registra em `Auditoria` (`criar_campanha`).

---

## 12. Melhorias Sugeridas (fora do escopo MVP)

- Template de mensagens salvas.
- Agendamento (enviar em data/hora).
- Preview da mensagem personalizada antes de enviar.
- Webhook de bounce/open para e-mail.
- Filas com Celery em vez de thread daemon (mais robusto para lotes grandes).
