# Sprint — Reproduzir Módulo de Comunicação (CEOD CRM)

Meta: reconstruir do zero o módulo `/comunicacao/` (Django + Selenium/Zap + SMTP) conforme o PRD.

Stack alvo: Django 5.2 + PostgreSQL + Selenium/Chromium + SMTP.
Tempo estimado: ~5 dias (1 dev).

---

## Etapa 0 — Setup do projeto (0.5 dia)
- [ ] Projeto Django + app `comunicacao` (ou `gestao`).
- [ ] `requirements.txt`: `django`, `selenium`, `openpyxl`, `psycopg2`, `python-decouple`.
- [ ] Dockerfile instala `chromium`, `chromedriver`, `fonts`.
- [ ] Volume Docker para `/app/whatsapp_profile`.
- [ ] Settings: `EMAIL_BACKEND`, `EMAIL_HOST`, `ZAP_PROFILE_DIR`, `CHROMEDRIVER_PATH`.

## Etapa 1 — Modelo `Campanha` (0.5 dia)
- [ ] Criar `Campanha` (ver PRD §5) com `CANAIS/ORIGENS/STATUS`.
- [ ] Migration inicial.
- [ ] Adicionar campo `aceita_comunicacao` (Boolean, default True) em `Congressista` se não existir.

## Etapa 2 — Parser de planilha (0.5 dia)
- [ ] `_parsear_planilha(arquivo)` → CSV (`csv.DictReader`) e XLSX (`openpyxl`).
- [ ] Mapear colunas: nome/name, email/e-mail/e_mail, zap/whatsapp/celular/phone/telefone/tel.
- [ ] Testes unitários com fixture CSV e XLSX.

## Etapa 3 — Envio de E-mail (0.5 dia)
- [ ] `common/emails.py`: `_aplicar_placeholders(corpo, dest)` substituindo `{{NOME}} {{EMAIL}} {{CELULAR}}`.
- [ ] `enviar_email(destinatarios, assunto, corpo)` via `send_mail` em loop.
- [ ] Tratar falhas individualmente (append em `falhas`).

## Etapa 4 — Integração WhatsApp (1.5 dias)
- [x] `gestao/whatsapp.py`: envio via **PyWhatKit** (`sendwhatmsg_instantly` — abre o WhatsApp Web no navegador padrão e pressiona Enter).
- [x] `verificar_conexao()`/`obter_qr_code()` (contrato JSON; orientam pareamento no navegador padrão).
- [x] `_limpar_numero()` (DDI 55 + `+` exigido pelo pywhatkit), `_enviar_um()`, `enviar_lote(intervalo=90)` com falha individual logada.
- [x] `_LOCK` para serializar lotes; degradação graciosa sem pywhatkit/internet.
- [x] Testes unitários com pywhatkit mockado + testes manuais (conta WA real pareada no navegador padrão).

## Etapa 5 — View `comunicacoes` (1 dia)
- [ ] GET: renderiza form + histórico (`Campanha.objects.all()[:30]`).
- [ ] POST: validar → montar `destinatarios` por origem (cadastrados/externos/individual).
- [ ] Criar `Campanha`, disparar `_enviar_campanha_async` (thread daemon).
- [ ] `zap_status` e `zap_qrcode` (JSON).
- [ ] `enviar_campanha()` orquestra EMAIL vs ZAP.

## Etapa 6 — Template `comunicacoes.html` (1 dia)
- [ ] Painel status WhatsApp (badge, QR area, botão gerar QR).
- [ ] Form: canal (EMAIL/ZAP), origem (cadastrados/externos/individual), filtros, assunto, corpo, submit.
- [ ] JS: `mudarCanal()`, `mudarOrigem()`, `verificarZap()` (fetch zap_status), `gerarQR()` (fetch zap_qrcode).
- [ ] Tabela de histórico (canal, conteúdo, origem, enviados, falhas, status, data).

## Etapa 7 — Segurança e robustez (0.5 dia)
- [ ] `@login_required` em todas as views.
- [ ] CSRF token no form.
- [ ] Sanitizar corpo de e-mail (escapar ou permitir HTML conscientemente — ver regra de segurança: NUNCA `|safe` em dados de usuário; aqui o corpo é do operador logado, mas ainda assim evitar XSS em preview).
- [ ] Rate limit: ZAP respeita 90s (já no código).
- [ ] Log de erros via `logger` (não `except: pass`).

## Etapa 8 — Deploy e validação (0.5 dia)
- [ ] Build imagem, push GHCR.
- [ ] `docker service update --force` (sem `--prune` na stack compartilhada).
- [ ] Validar: enviar e-mail teste, parear WA via QR, enviar Zap teste, checar histórico.

---

## Critérios de Aceite
- [ ] Enviar e-mail para lista de cadastrados filtrada por categoria funciona.
- [ ] Enviar Zap para contato individual funciona (após parear QR).
- [ ] Placeholders `{{NOME}}` etc. substituídos corretamente.
- [ ] Histórico mostra enviados/falhas/status.
- [ ] Sem erros JS; sem exceções silenciosas no backend.

## Riscos
- O pywhatkit abre o navegador padrão e digita/clica via pyautogui: requer display (Xvfb no servidor) e o navegador pareado em web.whatsapp.com.
- Lotes grandes de Zap demoram (90s×N) — considerar Celery no futuro.
- Chromium + Xvfb consomem recursos — isolar em container com limite de memória.
