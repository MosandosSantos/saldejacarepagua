---
name: criar-crm
description: |
  Guia você, passo a passo, a construir um CRM profissional completo do zero, sem precisar programar.
  Você descreve, a equipe constrói. A skill conduz cada etapa na ordem certa: primeiro o sistema
  completo na tela (dashboard, funil, leads, agenda), depois a memória de verdade (banco de dados),
  depois o sistema com a sua cara (arrastar cartão + seu nicho), e no fim publicar na internet.
  Use quando disser "/criar-crm", "criar meu CRM", "construir um CRM", "quero fazer um sistema de gestão de clientes".
---

# Criar CRM — o seu sistema de gestão de clientes, do zero

Esta skill te conduz na construção de um CRM completo e profissional, do jeito RedPro: você descreve o que quer, a equipe (Claude Code) constrói. Você não vai escrever código. Você vai conduzir.

O CRM é construído seguindo **as aulas do curso, numa ordem específica**. Cada aula entrega uma vitória concreta e prepara a próxima. **Nunca pule etapas** e **nunca antecipe uma vitória de uma aula futura** (por exemplo: não implemente arrastar cartão na Aula 2, isso é da Aula 4). A ordem existe pra você entender cada parte antes de somar a próxima.

## O mapa do curso

| Etapa | O que faz | Vitória |
|-------|-----------|---------|
| **Aula 1** | Boas-vindas, o mapa e checagem do ambiente | Tudo pronto pra construir |
| **Aula 2** | O sistema completo na tela: Dashboard, Funil, Leads e Agenda — com visual premium e populado com dados de exemplo | Um CRM inteiro na sua frente, igual aos caros |
| **Aula 3** | A memória: troca os dados de exemplo por um banco de dados real (Supabase) | O sistema para de esquecer — **Marco 1** |
| **Aula 4** | A sua cara: arrastar cartão com o mouse + adaptar o sistema pro seu nicho | Deixou de ser demo, virou o SEU sistema |
| **Aula 5** | A publicação: colocar no ar (Vercel) + acabamento final | Um link que você manda pra qualquer um — **Marco 2** |
| **🎁 Presente** | A personalização pra QUALQUER nicho, quantas vezes quiser | Você não tem um CRM: você constrói CRM pra qualquer empresa |

> **A escada em uma frase:** na Aula 2 você tem um **protótipo lindo**. Nas Aulas 3, 4 e 5 esse protótipo vira um **sistema de verdade** — ganha memória (3), ganha a sua cara e o seu mouse (4), e vai pro ar (5).

> **Regra de ouro da ordem (não negociável):** cada aula só entrega o que é dela. A skill NUNCA implementa um recurso antes da aula correspondente. Se o usuário pedir pra pular ("já coloca pra arrastar", "já conecta o banco"), explique com gentileza que aquilo vem na Aula X e que a ordem é o que faz ele entender o sistema, e siga a etapa atual.

> **⚠️ CONTRATO GRAVADO — a Aula 1 do evento já foi gravada e prometeu esta ordem exata. A skill OBEDECE, nunca contraria:**
> - **Aula 2 (terça):** o sistema inteiro nasce na tela, completo e bonito, com dados de exemplo — e o aluno SENTE o problema (aperta F5, tudo some). O problema é a amnésia, ele fica sem solução até quarta. **Aqui os cartões movem por botão/menu, NUNCA por arrastar.**
> - **Aula 3 (quarta):** RESOLVE o problema do F5. É "o dia que separa um brinquedo de um sistema de verdade". A solução é dar memória ao CRM = Supabase. (NÃO é drag&drop.)
> - **Aula 4 (quinta):** o CRM "ganha vida" = o aluno "mexe nele com o mouse" (drag&drop estreia AQUI, nunca antes) + deixa "com a cara do negócio que escolher".
> - **Aula 5 (sexta):** publica na internet, sai com um link no ar.

> **Sobre o 🎁 Presente:** a personalização profunda pra QUALQUER nicho NÃO é percorrida durante as aulas do evento. Ela fica guardada pra você rodar sozinho depois, quantas vezes quiser, pra adaptar o CRM a qualquer negócio/cliente. É o presente do Red pra você seguir voando sozinho.

---

## ⚖️ Princípios inegociáveis (valem em TODAS as aulas)

Estes dois princípios são a alma da skill. Nunca os quebre, em nenhuma aula.

### 1. O aluno nunca faz trabalho técnico na mão
O aluno **não escreve no terminal, não escreve SQL, não mexe em configuração de servidor, não edita arquivo de código**. Tudo que for técnico ele resolve **falando em português com o Antigravity** (o Claude Code faz o trabalho).

**PROIBIDO a skill pedir ao aluno:**
- ❌ "Abra o terminal e rode este comando"
- ❌ "Cole este SQL no editor do Supabase / crie a tabela na mão"
- ❌ "Edite o arquivo tal / mude essa linha do código"
- ❌ "Copie este CSS / cole este JavaScript"
- ❌ "Configure o deploy nas settings / mexa no painel técnico do serviço"

**O jeito certo:** o aluno descreve o que quer em linguagem natural, e o Claude Code executa. Exemplo: em vez de "rode o SQL para criar a tabela contatos", o aluno diz ao Claude "cria as tabelas que esse CRM precisa e liga tudo", e o Claude faz.

> Se em algum ponto parecer que o aluno precisa fazer algo técnico manualmente, PARE e reformule: como isso pode ser feito pelo Claude Code via linguagem natural? Sempre há um jeito. O único trabalho manual permitido é do tipo "clicar e copiar" (ver princípio 2).

### 2. Serviços externos entram por API key, e o Claude faz o resto
Sempre que um serviço externo for necessário (Supabase para o banco, Vercel para publicar, e qualquer outro que venha), o padrão é **sempre o mesmo**:

1. O aluno **cria uma conta** no serviço (grátis).
2. O aluno **copia a API key** (e a URL, quando o serviço pedir as duas). Isso é a única coisa que ele faz na mão: clicar e copiar.
3. O aluno **cola a key no Antigravity** e pede pro Claude fazer o trabalho.
4. **O Claude faz todo o resto** com a key: cria projeto, cria tabelas, conecta, configura, publica. Sozinho.

> A API key é a chave que dá poder pro Claude trabalhar no lugar do aluno. O aluno é o dono que entrega a chave e diz "faz aí". Ele não precisa entender o que a chave faz por dentro, só saber que é ela que libera o trabalho.

**Regra de segurança (a skill avisa o aluno):** a API key é como a senha de um cofre. Nunca postar print da key em lugar público (grupo, redes). Nas aulas gravadas, o Red usa sempre uma conta/projeto descartável.

---

## 📎 Sobre os blocos de código que existem nesta skill

Esta skill contém, na **Aula 2**, alguns blocos de código de referência (tokens de cor, a função do gráfico de funil 3D, e a lista de dados de exemplo).

> **⚠️ Esse código é MATERIAL DE TRABALHO DO CLAUDE. O aluno NUNCA vê, NUNCA copia, NUNCA digita, NUNCA cola nada disso.**
>
> Ele existe porque algumas partes visuais (principalmente o gráfico de funil em 3D) são detalhadas demais pra serem descritas em português sem sair diferente do que o aluno viu na propaganda. Então o Claude aplica o código exato, em vez de improvisar.
>
> **O aluno faz uma coisa só: manda o pedido em português.** O Claude, ao executar o pedido, consulta estes blocos aqui dentro da skill e usa. Se o aluno perguntar "e esse código aí?", a resposta é: *"Isso é ferramenta da equipe, não sua. Você descreve, a equipe monta."*

---

# AULA 1 — Boas-vindas, o mapa e o ambiente

> **Objetivo:** dar as boas-vindas, mostrar como a jornada funciona e garantir que o ambiente do aluno está pronto pra construir a partir da Aula 2. Nesta etapa **não se constrói nada** ainda — é preparação.

## Como conduzir (fale com o usuário)

**Passo 1 — Boas-vindas e o que é esta skill:**
Apresente-se. Explique, de forma simples, que esta skill vai guiar ele a construir um CRM profissional do zero, aula por aula, e que ele não precisa saber programar. A regra é "você descreve, a equipe constrói". Diga que vocês vão pela ordem certa, e que cada aula soma uma peça nova.

**Passo 2 — Mostrar o mapa:**
Apresente o mapa do curso (a tabela acima) em linguagem de conversa: hoje é preparar o terreno; na próxima o sistema inteiro nasce na tela com um pedido só — dashboard, funil, leads e agenda, com dados de exemplo, do jeito que ele viu; depois ele ganha memória de verdade; depois ganha o mouse e a cara do negócio dele; e no fim vai pro ar com um link. E que sobra um presente pra ele personalizar pra qualquer cliente, sozinho.

Deixe claro, já aqui, a regra que vale a semana toda: **ele nunca vai precisar escrever código ou mexer em coisa técnica na mão.** Tudo é conversa em português com o Antigravity. Quando um serviço de fora entrar (pra guardar dados, pra publicar), ele só vai criar uma conta e copiar uma chave, e o Claude faz o resto. O papel dele é ser o dono que descreve e delega, não o técnico que executa.

**Passo 3 — Checar o ambiente:**
Confirme com o usuário que ele tem as duas ferramentas prontas:
- **Google Antigravity** instalado (a bancada de trabalho).
- **Extensão do Claude Code** instalada e ativa dentro do Antigravity (a equipe de especialistas).

Oriente:
- Se faltar alguma, aponte pro material de instalação ("Prepare seu ambiente" — vídeo + checklist do grupo) e ajude a resolver o que der.
- Um teste simples pra confirmar que está tudo funcionando: peça pro Claude Code fazer algo trivial, tipo "crie uma página com o meu nome escrito grande". Se abrir no navegador, o ambiente está pronto.

**Passo 4 — Fechar a Aula 1:**
Confirme que o ambiente está pronto. Avise que a construção de verdade começa na Aula 2, quando o sistema inteiro nasce com um único pedido bem descrito. **Não comece a construir o CRM agora** — a Aula 1 termina aqui.

## Se o usuário quiser pular direto pra construção
Explique que a Aula 1 é curtinha e serve só pra garantir que a base tá pronta, e que sem o ambiente certo a Aula 2 não funciona. Se ele confirmar que já tem tudo instalado e testado, pode seguir pra Aula 2.

---

# AULA 2 — O sistema completo na tela

> **Objetivo desta aula:** o aluno sai com o CRM INTEIRO na frente dele — as 4 telas (Dashboard, Funil, Leads e Agenda), visual premium preto-e-dourado, gráfico de funil em 3D, 7 etapas coloridas — e **já populado com 20 leads e 8 agendamentos de exemplo**, pra ele ver o sistema cheio, funcionando, do jeito que aparece na propaganda. Nesta aula os dados ficam só na memória do navegador (quando recarregar a página, eles somem — isso é de propósito, a gente resolve na Aula 3).

## O que esta aula FAZ
- **4 telas** com menu no topo pra navegar entre elas:
  1. **Dashboard** — 4 indicadores (negócios ativos, valor no funil, fechados, taxa de conversão), gráfico de linha de novos leads dos últimos 30 dias, faixa de conversão por etapa, **gráfico de funil em 3D**, e lista de movimentações recentes.
  2. **Funil (Kanban)** — 7 colunas coloridas, cada negócio é um cartão, contador e soma de valor por coluna, busca. Mover de etapa **por botão ou menu** (NÃO por arrastar).
  3. **Leads** — tabela com todos os contatos: nome, empresa, telefone, e-mail, etapa, segmento e valor. Com busca. Clicar numa linha abre a ficha do contato.
  4. **Agenda** — lista de reuniões/calls/demos marcadas, agrupadas por dia.
- **Cadastrar, editar e excluir contato** — botão "+ Novo contato" com formulário completo. O aluno consegue colocar os dados dele no sistema desde hoje (em memória — some no F5, e é justamente isso que dói).
- **7 etapas de funil coloridas:** Novo Lead, Em Contato, Qualificado, Proposta, Negociação, Fechado, Perdido.
- **Dados de exemplo já dentro:** 20 leads e 8 agendamentos (é o que faz o sistema parecer vivo em vez de vazio).
- **Visual premium:** fundo preto piano com brilho dourado difuso, cards de vidro fosco, detalhe dourado champagne, três fontes (Fraunces / DM Sans / JetBrains Mono).

## O que esta aula NÃO FAZ (é das próximas aulas — NÃO antecipar)
- ❌ Arrastar cartão (drag & drop) → é da **Aula 4**
- ❌ Adaptar o sistema pro nicho do aluno → **Aula 4**
- ❌ Banco de dados / dados que sobrevivem ao recarregar → **Aula 3**
- ❌ Colocar no ar / link público → **Aula 5**

## ⚠️ Aviso obrigatório: os dados são FICTÍCIOS
A skill DEVE avisar o aluno, com estas palavras (ou equivalentes), logo depois de o sistema abrir:

> "Esses 20 contatos e essas 8 reuniões são **inventados**. Nenhum deles existe. Eles estão aí de propósito, por um motivo: um CRM vazio não mostra nada. Com o sistema cheio você vê o funil desenhado, os números batendo, os gráficos com forma — você vê o sistema **funcionando**.
>
> Quando você for usar de verdade, ou for mostrar pra um cliente, é só pedir: **'limpa todos os dados de exemplo e deixa o sistema zerado'**. O Claude apaga tudo em segundos e o sistema fica pronto pra receber os seus contatos de verdade."

## Como conduzir o usuário nesta aula

**Passo 1 — Enquadrar (fale com o usuário):**
Diga que agora ele vai construir o sistema inteiro com um único pedido bem descrito, e que descrever bem é a habilidade que importa (não programar). Explique rápido que o pedido é como um briefing pra uma equipe: quanto mais claro, melhor o resultado. Avise que o sistema vem populado com dados de exemplo, e por quê (ver o aviso acima).

**Passo 2 — Usar o pedido de construção abaixo.** Este é o pedido oficial da Aula 2. Instrua o usuário a usá-lo (ou, se estiver conduzindo o Claude Code diretamente, execute-o). Ele constrói exatamente o escopo desta aula.

```
Crie um CRM web completo chamado Aurum, em um único arquivo HTML
(com o CSS e o JavaScript dentro dele), todo em português. Sem
framework, sem build, só HTML, CSS e JavaScript puro. A navegação
entre as telas é por hash na URL (#/dashboard, #/funil, etc.).

Ele precisa ter 4 TELAS, com um menu fixo no topo pra navegar:

1) DASHBOARD (tela inicial)
- Quatro indicadores no topo, lado a lado: Negócios ativos (quantos
  estão no funil em aberto), Valor no funil (soma em R$ dos negócios
  em aberto), Fechados no mês (quantidade em destaque e o valor
  embaixo) e Taxa de conversão (quantos fecharam, sobre todos os
  contatos que não foram perdidos).
- Um gráfico de linha mostrando quantos leads novos entraram por dia
  nos últimos 30 dias, com área preenchida em degradê dourado.
- Abaixo do gráfico, uma faixa "Conversão por etapa" com uma célula
  para cada passagem de etapa (ex: Novo Lead → Em Contato), mostrando
  a porcentagem.
- Ao lado, um GRÁFICO DE FUNIL EM 3D: fatias empilhadas que vão
  afunilando de cima pra baixo, cada uma com a cor da sua etapa, com
  face lateral dando profundidade, sombra embaixo, e a contagem de
  negócios escrita dentro de cada fatia. Ao lado do desenho, uma
  legenda com o nome de cada etapa, a contagem e a porcentagem.
- Embaixo, largura total, uma lista de "Movimentações recentes" com
  os últimos negócios (iniciais do contato, nome, empresa, valor e
  etapa).

2) FUNIL (KANBAN)
- Um quadro com 7 colunas, uma por etapa: Novo Lead, Em Contato,
  Qualificado, Proposta, Negociação, Fechado e Perdido.
- Cada coluna tem: uma bolinha na cor da etapa, o nome, um contador
  de quantos cartões tem nela, e no rodapé a soma em R$ dos cartões
  daquela coluna.
- Cada negócio é um cartão mostrando o nome do contato, a empresa,
  uma etiqueta colorida com o segmento e o valor em R$.
- No cartão, um botão ou menu pra mover o negócio pra outra etapa
  (NÃO precisa arrastar, só um botão ou menu).
- Um campo de busca que filtra os cartões por nome ou empresa.
- No canto, o total em R$ de tudo que está no funil.

3) LEADS
- Uma tabela com todos os contatos, com as colunas: Contato,
  Empresa, Telefone, E-mail, Etapa (etiqueta colorida), Segmento
  (etiqueta colorida) e Valor.
- Campo de busca que filtra por nome ou empresa, e um contador de
  quantos contatos apareceram.
- Clicar numa linha abre uma janela (modal) com a ficha do contato:
  nome, empresa, valor em destaque, etapa, segmento, telefone e
  e-mail. Fecha no X, clicando fora ou apertando Esc.
- Um botão dourado "+ Novo contato" no topo da tela. Clicando nele,
  abre um formulário (na mesma janela modal) com os campos: nome,
  empresa, telefone, e-mail, segmento (lista de opções), valor do
  negócio em R$ e etapa do funil (lista de opções, começando em
  "Novo Lead"). Ao salvar, o contato aparece na tabela, vira um
  cartão no funil e os números do dashboard se atualizam.
- Na ficha de um contato existente, dois botões: "Editar" (abre o
  mesmo formulário preenchido) e "Excluir" (pede confirmação).

4) AGENDA
- Uma lista das reuniões marcadas, agrupadas por dia, com um título
  por dia escrito por extenso (ex: "quinta-feira, 14 de agosto").
- As datas são SEMPRE calculadas a partir do dia de hoje (hoje, amanhã
  e daqui a alguns dias úteis) — nunca datas fixas no código. A agenda
  precisa parecer viva em qualquer semana que o sistema for aberto.
- Cada item mostra: a hora em destaque, a data, o nome do contato,
  a empresa e o tipo de compromisso (Call, Reunião ou Demonstração)
  com um ícone.

DADOS
- Já deixe o sistema populado com dados de exemplo (contatos,
  negócios e reuniões inventados), pra eu ver o sistema cheio e
  funcionando em vez de uma tela vazia. Use exatamente a lista de
  dados de exemplo que está na skill criar-crm.
- Guarde os dados apenas na memória da aplicação enquanto ela está
  aberta. Não use localStorage, não use banco de dados e não salve
  em arquivo.
- Use a moeda em formato brasileiro (R$ 1.500,00).

VISUAL (siga à risca, é o que dá a cara premium)
- Tema escuro sofisticado: fundo preto bem profundo, quase preto
  piano, com um leve brilho dourado difuso no fundo, bem sutil,
  pra dar atmosfera (nada de preto chapado).
- Todos os cards e painéis com efeito de vidro fosco: fundo branco
  bem translúcido, com uma borda fininha clara em volta (senão o
  card some no escuro) e cantos bem arredondados.
- Cor de destaque dourada champagne nos botões, nos valores em
  dinheiro e na etapa ativa do menu.
- Tipografia com três fontes do Google Fonts: títulos em "Fraunces"
  (serifada elegante), textos e botões em "DM Sans" (sem serifa
  limpa), e todos os números e valores em "JetBrains Mono".
- Header fixo no topo com o nome do sistema, um selo/ícone dourado
  ao lado, o menu de navegação e um avatar redondo à direita.
- Layout responsivo: em tela pequena os indicadores empilham e o
  menu vira só ícones.
- Deixe com cara de sistema caro, que empresa paga assinatura pra
  ter, não de projetinho.

Use como referência técnica os blocos de código que estão na skill
criar-crm (tokens de cor, função do funil 3D e dados de exemplo).
Aplique esses blocos exatamente como estão, não invente versões
diferentes.

Quando terminar, rode o projeto e me diga o endereço pra eu
abrir no navegador.
```

---

## 🔧 MATERIAL TÉCNICO DA AULA 2 — só o Claude usa

> **O aluno NÃO vê, NÃO copia e NÃO digita nada daqui.** São três blocos que o Claude aplica ao executar o pedido acima, porque descrevê-los em português produziria um resultado diferente do que o aluno viu na propaganda.

### Bloco A — Tokens visuais (cores, fontes, atmosfera)

Aplicar exatamente estes valores no `:root` e no `body`:

```css
:root{
  --bg-piano:#080808;
  --surface:rgba(255,255,255,0.03);
  --glass:rgba(255,255,255,0.05);
  --glass-hover:rgba(255,255,255,0.08);
  --border:rgba(255,255,255,0.08);
  --accent:#e8d5b7;
  --accent-dim:rgba(232,213,183,0.10);
  --accent-soft:rgba(232,213,183,0.18);
  --text:#f5f5f5;
  --text-secondary:#a3a3a3;
  --text-muted:#525252;
  --success:#4ade80;
  --danger:#ef4444;
  --font-display:'Fraunces',Georgia,serif;
  --font-ui:'DM Sans',sans-serif;
  --font-mono:'JetBrains Mono',monospace;
}
body{
  min-height:100vh;
  background:var(--bg-piano);
  background-image:
    radial-gradient(ellipse 70% 50% at 15% 0%, rgba(232,213,183,0.06) 0%, transparent 55%),
    radial-gradient(ellipse 55% 45% at 88% 85%, rgba(232,213,183,0.045) 0%, transparent 55%),
    radial-gradient(ellipse 40% 40% at 50% 40%, rgba(232,213,183,0.02) 0%, transparent 60%);
  background-attachment:fixed;
  -webkit-font-smoothing:antialiased;
}
```

Cards de vidro fosco (base reutilizada em KPI, painel, coluna, cartão, modal):

```css
.card{
  background:var(--glass);
  border:1px solid var(--border);
  border-radius:16px;
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  box-shadow:0 8px 32px rgba(0,0,0,0.30);
}
```

Fontes (Google Fonts, no `<head>`):

```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600;9..144,700&family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
```

### Bloco B — Gráfico de funil 3D (SVG procedural)

**Este é o bloco mais importante da skill.** É o que aparece nos criativos. Aplicar a função como está — a forma do funil é geométrica pura (100% no topo → 18% na base), independente dos números; os dados aparecem na contagem dentro da fatia e na legenda ao lado.

HTML do painel:

```html
<div class="funnel3d-wrap">
  <div class="funnel3d-svg"><svg id="funnel3d" viewBox="0 0 340 600"></svg></div>
  <div class="funnel3d-legend" id="funnel3dLegend"></div>
</div>
```

CSS:

```css
.funnel3d-wrap{display:flex;gap:22px;align-items:center}
.funnel3d-svg{flex:0 0 42%;min-width:0}
.funnel3d-svg svg{display:block;width:100%}
.funnel3d-legend{flex:1;display:flex;flex-direction:column;gap:6px}
.f3-item{display:flex;align-items:center;gap:11px;padding:9px 12px;border-radius:11px;
  background:var(--surface);border:1px solid var(--border);transition:all .18s;cursor:default}
.f3-item:hover{background:var(--accent-dim);border-color:var(--accent-soft)}
.f3-dot{width:9px;height:9px;border-radius:3px;flex-shrink:0}
.f3-name{flex:1;font-size:12.5px;font-weight:500;color:var(--text-secondary);letter-spacing:0.01em}
.f3-count{font-family:var(--font-mono);font-weight:700;font-size:13.5px;color:var(--text);min-width:22px;text-align:right}
.f3-pct{font-family:var(--font-mono);font-size:11px;color:var(--accent);min-width:42px;text-align:right}
@media(max-width:1120px){
  .funnel3d-wrap{flex-direction:column;align-items:stretch}
  .funnel3d-svg{flex:none}
}
```

JavaScript (a função e sua auxiliar `shade`):

```javascript
/* ══════════════ FUNIL GRÁFICO 3D (fatias afuniladas) ══════════════ */
function renderFunnel3d(){
  var svg = document.getElementById('funnel3d');
  var legend = document.getElementById('funnel3dLegend');
  if(!svg || !legend) return;

  var steps = STAGES.map(function(s){
    return { key:s.key, name:s.name, color:s.color, count:leadsInStage(s.key).length };
  });
  var topCount = steps[0].count || LEADS.length || 1;

  var W = 340, H = 600, sliceH = 62, gap = 5, depthX = 22, depthY = 14, topY = 16;
  var cx = W / 2;
  var n = steps.length;

  var defs = '<defs>';
  steps.forEach(function(s, i){
    var dark = shade(s.color, -0.42);
    defs += '<linearGradient id="f3g' + i + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + s.color + '" stop-opacity="0.98"/>' +
      '<stop offset="100%" stop-color="' + dark + '" stop-opacity="0.9"/></linearGradient>';
    defs += '<linearGradient id="f3s' + i + '" x1="0" y1="0" x2="1" y2="0">' +
      '<stop offset="0%" stop-color="' + dark + '" stop-opacity="0.78"/>' +
      '<stop offset="100%" stop-color="' + dark + '" stop-opacity="0.32"/></linearGradient>';
  });
  defs += '</defs>';

  var c = defs;
  var shadowY = topY + n * (sliceH + gap) + depthY + 10;

  // sombra base elíptica
  c += '<ellipse cx="' + (cx + depthX * 0.4).toFixed(1) + '" cy="' + shadowY.toFixed(1) +
       '" rx="' + (cx * 0.5).toFixed(1) + '" ry="' + (depthY * 0.9).toFixed(1) + '" fill="rgba(0,0,0,0.4)"/>';

  var maxHalf = cx * 0.92; // largura máx da meia-boca

  steps.forEach(function(s, i){
    // funil real: boca LARGA em cima, afunila FORTE pra baixo. 100% (topo) → 18% (base).
    // Forma pura de funil — não mistura com os dados, por isso parece funil de verdade.
    // Os dados aparecem na contagem dentro da fatia + na legenda.
    var fracTop    = 1 - (i / n) * 0.82;
    var fracBottom = 1 - ((i + 1) / n) * 0.82;

    var wTop = fracTop * maxHalf;
    var wBot = fracBottom * maxHalf;

    var y1 = topY + i * (sliceH + gap);
    var y2 = y1 + sliceH;
    var fl = cx - wTop, fr = cx + wTop;
    var nl = cx - wBot, nr = cx + wBot;

    // face frontal
    c += '<polygon points="' + fl.toFixed(1) + ',' + y1.toFixed(1) + ' ' + fr.toFixed(1) + ',' + y1.toFixed(1) + ' ' +
      nr.toFixed(1) + ',' + y2.toFixed(1) + ' ' + nl.toFixed(1) + ',' + y2.toFixed(1) + '" fill="url(#f3g' + i + ')"/>';
    // face lateral (profundidade)
    c += '<polygon points="' + fr.toFixed(1) + ',' + y1.toFixed(1) + ' ' + (fr + depthX).toFixed(1) + ',' + (y1 - depthY).toFixed(1) + ' ' +
      (nr + depthX).toFixed(1) + ',' + (y2 - depthY).toFixed(1) + ' ' + nr.toFixed(1) + ',' + y2.toFixed(1) + '" fill="url(#f3s' + i + ')"/>';
    // aresta brilho topo
    c += '<line x1="' + fl.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + fr.toFixed(1) + '" y2="' + y1.toFixed(1) +
      '" stroke="rgba(255,255,255,0.24)" stroke-width="1.2"/>';
    // contagem dentro da fatia
    c += '<text x="' + cx.toFixed(1) + '" y="' + (y1 + sliceH/2 + 4).toFixed(1) +
      '" text-anchor="middle" font-size="14" font-weight="700" font-family="JetBrains Mono, monospace" fill="#fff" opacity="0.92">' + s.count + '</text>';
    // tampa elíptica dourada no topo
    if(i === 0){
      var ecx = (fl + fr + depthX) / 2;
      var erx = (fr + depthX - fl) / 2;
      c += '<ellipse cx="' + ecx.toFixed(1) + '" cy="' + y1.toFixed(1) + '" rx="' + erx.toFixed(1) +
        '" ry="' + (depthY * 0.75).toFixed(1) + '" fill="' + s.color + '" opacity="0.95"/>';
      c += '<ellipse cx="' + ecx.toFixed(1) + '" cy="' + y1.toFixed(1) + '" rx="' + erx.toFixed(1) +
        '" ry="' + (depthY * 0.75).toFixed(1) + '" fill="none" stroke="#e8d5b7" stroke-width="1.4" opacity="0.6"/>';
    }
  });

  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + (shadowY + 8));
  svg.innerHTML = c;

  // legenda lateral
  legend.innerHTML = steps.map(function(s){
    var pct = topCount ? Math.round((s.count / topCount) * 100) : 0;
    return '<div class="f3-item">' +
      '<span class="f3-dot" style="background:' + s.color + ';box-shadow:0 0 8px ' + s.color + '70"></span>' +
      '<span class="f3-name">' + s.name + '</span>' +
      '<span class="f3-count">' + s.count + '</span>' +
      '<span class="f3-pct">' + pct + '%</span>' +
    '</div>';
  }).join('');
}

/* Escurece/clareia uma cor hex por um fator (-1..1) — pra face 3D */
function shade(hex, factor){
  var h = hex.replace('#','');
  if(h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
  var r = parseInt(h.substring(0,2),16);
  var g = parseInt(h.substring(2,4),16);
  var b = parseInt(h.substring(4,6),16);
  function mix(c){
    if(factor < 0) return Math.round(c * (1 + factor));
    return Math.round(c + (255 - c) * factor);
  }
  function h2(v){ var s = Math.max(0,Math.min(255,v)).toString(16); return s.length === 1 ? '0'+s : s; }
  return '#' + h2(mix(r)) + h2(mix(g)) + h2(mix(b));
}
```

### Bloco C — Dados de exemplo (fictícios)

Estrutura de dados obrigatória: 7 etapas, 7 segmentos, 20 leads, 8 agendamentos e a série de 30 dias da timeline. **Não inventar outros nomes/valores** — estes são os que aparecem nos criativos do curso.

```javascript
/* Etapas do funil */
var STAGES = [
  { key:'novo',        name:'Novo Lead',    color:'#94a3b8' },
  { key:'contato',     name:'Em Contato',   color:'#60a5fa' },
  { key:'qualificado', name:'Qualificado',  color:'#38bdf8' },
  { key:'proposta',    name:'Proposta',     color:'#e8d5b7' },
  { key:'negociacao',  name:'Negociação',   color:'#fbbf24' },
  { key:'fechado',     name:'Fechado',      color:'#4ade80' },
  { key:'perdido',     name:'Perdido',      color:'#ef4444' }
];
var STAGE_MAP = {}; STAGES.forEach(function(s){ STAGE_MAP[s.key] = s; });

/* Segmentos (nichos variados) */
var SEG = {
  clinica:    { label:'Clínica',      color:'#4ade80' },
  imobiliaria:{ label:'Imobiliária',  color:'#60a5fa' },
  advocacia:  { label:'Advocacia',    color:'#e8d5b7' },
  varejo:     { label:'Varejo',       color:'#fbbf24' },
  agencia:    { label:'Agência',      color:'#c084fc' },
  industria:  { label:'Indústria',    color:'#38bdf8' },
  educacao:   { label:'Educação',     color:'#fb923c' }
};

/* LEADS — cada um é um contato ligado a um negócio (valor + etapa) — TODOS FICTÍCIOS */
var LEADS = [
  { id:1,  nome:'Mariana Fontes',    empresa:'Clínica Vitalys',           tel:'(11) 98421-3390', email:'mariana@vitalys.com.br',      seg:'clinica',     stage:'proposta',    valor:14500 },
  { id:2,  nome:'Ricardo Almeida',   empresa:'Almeida Advogados',         tel:'(21) 99187-4402', email:'ricardo@almeidaadv.com.br',   seg:'advocacia',   stage:'negociacao',  valor:22800 },
  { id:3,  nome:'Juliana Prado',     empresa:'Prado Imóveis',             tel:'(31) 98765-1120', email:'juliana@pradoimoveis.com.br', seg:'imobiliaria', stage:'novo',        valor:9800  },
  { id:4,  nome:'Fernando Rocha',    empresa:'RochaTech Distribuidora',   tel:'(41) 99340-8871', email:'fernando@rochatech.com.br',   seg:'varejo',      stage:'contato',     valor:6400  },
  { id:5,  nome:'Camila Bittencourt',empresa:'Studio Bitt Marketing',     tel:'(11) 97655-2213', email:'camila@studiobitt.com.br',    seg:'agencia',     stage:'fechado',     valor:18700 },
  { id:6,  nome:'Thiago Nogueira',   empresa:'Nogueira Metalúrgica',      tel:'(51) 98230-6654', email:'thiago@nogueirametal.com.br', seg:'industria',   stage:'proposta',    valor:24500 },
  { id:7,  nome:'Patrícia Lemos',    empresa:'Espaço Lemos Odonto',       tel:'(85) 99123-7788', email:'patricia@lemosodonto.com.br', seg:'clinica',     stage:'novo',        valor:3200  },
  { id:8,  nome:'Gustavo Siqueira',  empresa:'Siqueira & Cia Contábil',   tel:'(11) 98900-3345', email:'gustavo@siqueiracia.com.br',  seg:'advocacia',   stage:'contato',     valor:5600  },
  { id:9,  nome:'Beatriz Antunes',   empresa:'Antunes Cursos Livres',     tel:'(19) 99450-1198', email:'beatriz@antunescursos.com.br',seg:'educacao',    stage:'qualificado', valor:8100  },
  { id:10, nome:'Rafael Monteiro',   empresa:'Monteiro Auto Center',      tel:'(47) 98112-4471', email:'rafael@monteiroauto.com.br',  seg:'varejo',      stage:'novo',        valor:11200 },
  { id:11, nome:'Larissa Coelho',    empresa:'Coelho Imobiliária Prime',  tel:'(62) 99677-2205', email:'larissa@coelhoprime.com.br',  seg:'imobiliaria', stage:'novo',        valor:16900 },
  { id:12, nome:'Eduardo Vasques',   empresa:'Vasques Digital',           tel:'(11) 98544-9910', email:'eduardo@vasquesdigital.com',  seg:'agencia',     stage:'fechado',     valor:12400 },
  { id:13, nome:'Isabela Freitas',   empresa:'Freitas Estética Avançada', tel:'(81) 99320-6612', email:'isabela@freitasestetica.com', seg:'clinica',     stage:'contato',     valor:7300  },
  { id:14, nome:'Marcelo Tavares',   empresa:'Tavares Advocacia Empres.', tel:'(11) 97880-1123', email:'marcelo@tavaresadv.com.br',   seg:'advocacia',   stage:'qualificado', valor:19500 },
  { id:15, nome:'Aline Barros',      empresa:'Barros Moda & Estilo',      tel:'(21) 98455-7789', email:'aline@barrosmoda.com.br',     seg:'varejo',      stage:'novo',        valor:2800  },
  { id:16, nome:'Vinícius Duarte',   empresa:'Duarte Engenharia',         tel:'(31) 99012-3348', email:'vinicius@duarteeng.com.br',   seg:'industria',   stage:'negociacao',  valor:25000 },
  { id:17, nome:'Carolina Neves',    empresa:'Neves Idiomas',             tel:'(11) 98233-4471', email:'carolina@nevesidiomas.com.br',seg:'educacao',    stage:'perdido',     valor:4900  },
  { id:18, nome:'Bruno Carvalho',    empresa:'Carvalho Imóveis Litoral',  tel:'(13) 99188-5560', email:'bruno@carvalholitoral.com.br',seg:'imobiliaria', stage:'proposta',    valor:13600 },
  { id:19, nome:'Renata Machado',    empresa:'Machado Odontologia',       tel:'(41) 98700-2214', email:'renata@machadoodonto.com.br', seg:'clinica',     stage:'contato',     valor:6800  },
  { id:20, nome:'Leandro Pires',     empresa:'Pires Performance Ads',     tel:'(11) 99544-8823', email:'leandro@piresads.com.br',     seg:'agencia',     stage:'qualificado', valor:15300 }
];

/* AGENDAMENTOS — datas SEMPRE relativas ao dia em que o aluno rodar.
   Nunca hardcodar data: o sistema tem que parecer vivo em qualquer semana.
   Offsets em dias úteis a partir de hoje (0 = hoje). */
var APPT_SEED = [
  { leadId:1,  hora:'09:00', offset:0, tipo:'demo',    tipoLabel:'Demonstração' },
  { leadId:2,  hora:'11:30', offset:0, tipo:'reuniao', tipoLabel:'Reunião' },
  { leadId:6,  hora:'14:00', offset:0, tipo:'call',    tipoLabel:'Call' },
  { leadId:10, hora:'16:30', offset:0, tipo:'call',    tipoLabel:'Call' },
  { leadId:11, hora:'10:00', offset:1, tipo:'reuniao', tipoLabel:'Reunião' },
  { leadId:16, hora:'13:00', offset:1, tipo:'demo',    tipoLabel:'Demonstração' },
  { leadId:14, hora:'15:30', offset:1, tipo:'call',    tipoLabel:'Call' },
  { leadId:18, hora:'09:30', offset:4, tipo:'reuniao', tipoLabel:'Reunião' }
];

var MESES = ['janeiro','fevereiro','março','abril','maio','junho',
             'julho','agosto','setembro','outubro','novembro','dezembro'];
var SEMANA = ['domingo','segunda-feira','terça-feira','quarta-feira',
              'quinta-feira','sexta-feira','sábado'];

function pad2(n){ return (n < 10 ? '0' : '') + n; }

/* Soma N dias úteis a partir da base, pulando sábado e domingo.
   A base é normalizada pro próximo dia útil ANTES de somar — senão,
   se o aluno rodar num fim de semana, offset 0 e offset 1 cairiam
   na mesma segunda e a agenda perderia o agrupamento por dia. */
function diaUtil(base, n){
  var d = new Date(base.getTime());
  while(d.getDay() === 0 || d.getDay() === 6){ d.setDate(d.getDate() + 1); }
  var somados = 0;
  while(somados < n){
    d.setDate(d.getDate() + 1);
    if(d.getDay() !== 0 && d.getDay() !== 6) somados++;
  }
  return d;
}

var HOJE = new Date();
var APPTS = APPT_SEED.map(function(a){
  var d = diaUtil(HOJE, a.offset);
  return {
    leadId: a.leadId, hora: a.hora, tipo: a.tipo, tipoLabel: a.tipoLabel,
    data: pad2(d.getDate()) + '/' + pad2(d.getMonth() + 1),
    dia:  SEMANA[d.getDay()] + ', ' + d.getDate() + ' de ' + MESES[d.getMonth()]
  };
});

/* Estado do funil em memória — inicializa da etapa de cada lead */
var boardState = {};
LEADS.forEach(function(l){ boardState[l.id] = l.stage; });

/* Timeline — novos leads nos últimos 30 dias, terminando HOJE.
   Volume fixo (mesma curva sempre), datas relativas. Leve crescimento
   no fim = sensação de tração. */
var TIMELINE_V = [1,0,2,1,0,2,1,3,2,1,0,2,3,2,4,2,3,1,3,4,2,5,3,4,5,3,2,5,4,6];
var DAILY_LEADS = TIMELINE_V.map(function(v, i){
  var d = new Date(HOJE.getTime());
  d.setDate(d.getDate() - (TIMELINE_V.length - 1 - i));
  return { d: pad2(d.getDate()) + '/' + pad2(d.getMonth() + 1), v: v };
});
```

**Regras de cálculo que o Claude aplica com esses dados:**
- **Negócios ativos** = leads que não estão em "Perdido" nem em "Fechado".
- **Valor no funil** = soma do valor desses negócios ativos.
- **Fechados** = leads em "Fechado" (quantidade + soma do valor). O rótulo do KPI é "Fechados no mês" — os dados de exemplo não têm data de fechamento, então o número é o total em "Fechado". Manter o rótulo assim mesmo.
- **Taxa de conversão** = fechados ÷ (total de leads exceto "Perdido"), arredondado. Com os dados de exemplo isso dá **11%**. (O briefing em português diz "fechados sobre o total de ativos" — **esta regra técnica é a que vale**, para todos os alunos darem o mesmo número.)
- **Conversão por etapa** = sempre **em relação à etapa anterior**, e **nunca passa de 100%**. **"Perdido" NÃO entra na cadeia de conversão** (é um lead que saiu, não que avançou) — a cadeia vai de Novo Lead até Fechado, gerando exatamente **5 células**.
- **Movimentações recentes** = os **8** leads de maior `id`, em ordem decrescente. Quando um cartão é movido de etapa, ele vai pro topo da lista. (Os dados não têm data de atualização — esta é a regra, para não variar entre alunos.)
- **Cartão movido de etapa** atualiza tudo: KPIs, funil 3D, contadores e somas das colunas, conversão por etapa e movimentações recentes.

---

### Bloco D — Gráfico de linha, conversão por etapa e KPIs (colar como está)

> Estas três partes também são visuais e precisam sair iguais em todos os alunos.
> O CSS entra junto com o Bloco A; as funções entram junto com as do Bloco B.

**CSS:**
```css
/* KPIs */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:30px}
.kpi{background:var(--glass);border:1px solid var(--border);border-radius:16px;
  padding:24px 26px;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  transition:all .2s;position:relative;overflow:hidden}
.kpi:hover{border-color:var(--accent-soft);transform:translateY(-3px)}
.kpi-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.kpi-icon{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;
  justify-content:center;background:var(--accent-dim);border:1px solid var(--accent-soft)}
.kpi-icon svg{width:19px;height:19px;stroke:var(--accent);fill:none;stroke-width:1.8;
  stroke-linecap:round;stroke-linejoin:round}
.kpi-trend{font-size:11px;font-weight:600;font-family:var(--font-mono);padding:3px 9px;border-radius:20px}
.kpi-trend.up{color:var(--success);background:rgba(74,222,128,0.10);border:1px solid rgba(74,222,128,0.20)}
.kpi-trend.flat{color:var(--text-muted);background:var(--glass);border:1px solid var(--border)}
.kpi-label{font-size:11px;font-weight:600;letter-spacing:0.10em;text-transform:uppercase;
  color:var(--text-muted);margin-bottom:10px}
.kpi-value{font-family:var(--font-mono);font-weight:700;font-size:34px;line-height:1;
  letter-spacing:-0.02em;color:var(--text)}
.kpi-value.gold{color:var(--accent);text-shadow:0 0 28px rgba(232,213,183,0.25)}
.kpi-sub{font-size:12px;color:var(--text-muted);margin-top:8px}

/* Grid do dashboard e painéis */
.dash-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;align-items:stretch}
.dash-grid .panel{display:flex;flex-direction:column}
.dash-grid .timeline-wrap{flex:1;display:flex;align-items:center}
.panel{background:var(--glass);border:1px solid var(--border);border-radius:16px;
  padding:26px 28px;backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
.panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}
.panel-title{font-family:var(--font-display);font-weight:600;font-size:19px;
  letter-spacing:-0.01em;color:var(--text)}
.panel-note{font-size:12px;color:var(--text-muted)}

/* Gráfico de linha */
.timeline-wrap{width:100%;overflow-x:auto}
.timeline-wrap svg{display:block;width:100%;min-width:520px}

/* Conversão por etapa */
.conv-head{font-size:11px;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;
  color:var(--text-muted);margin:22px 0 12px;display:flex;align-items:center;gap:8px}
.conv-head::before{content:'';width:3px;height:12px;border-radius:2px;background:var(--accent)}
.conv-row{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}
.conv-cell{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:13px 12px;display:flex;flex-direction:column;gap:7px}
.conv-cell-label{font-size:9.5px;line-height:1.35;color:var(--text-muted);text-transform:uppercase;
  letter-spacing:0.04em;font-weight:600;min-height:26px}
.conv-cell-pct{font-family:var(--font-mono);font-size:21px;font-weight:700;
  letter-spacing:-0.5px;line-height:1}
```

**JavaScript:**
```javascript
/* Gráfico de linha — 30 dias, área em degradê dourado + pontos + brilho */
function renderTimeline(){
  var el = document.getElementById('timelineChart');
  if(!el) return;
  var days = DAILY_LEADS;
  var max = days.reduce(function(m,d){ return Math.max(m, d.v); }, 1);
  var W = 660, H = 190, PAD_X = 28, PAD_T = 22, PAD_B = 30;
  var pts = days.map(function(d, i){
    var x = PAD_X + (i / (days.length - 1)) * (W - PAD_X * 2);
    var y = (H - PAD_B) - (d.v / max) * (H - PAD_T - PAD_B);
    return { x:x, y:y, v:d.v, d:d.d };
  });
  var pathD = pts.map(function(p, i){ return (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ' ' + p.y.toFixed(1); }).join(' ');
  var areaD = pathD + ' L' + pts[pts.length-1].x.toFixed(1) + ' ' + (H - PAD_B) + ' L' + pts[0].x.toFixed(1) + ' ' + (H - PAD_B) + ' Z';
  var labels = pts.filter(function(_, i){ return i % 5 === 0 || i === pts.length - 1; }).map(function(p){
    return '<text x="' + p.x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="9.5" font-family="JetBrains Mono, monospace" fill="#525252">' + p.d + '</text>';
  }).join('');
  var dots = pts.filter(function(p){ return p.v > 0; }).map(function(p){
    return '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="3" fill="#e8d5b7" stroke="#080808" stroke-width="1"><title>' + p.v + ' leads em ' + p.d + '</title></circle>';
  }).join('');
  el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" width="100%">' +
    '<defs>' +
      '<linearGradient id="tlArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#e8d5b7" stop-opacity="0.25"/><stop offset="100%" stop-color="#e8d5b7" stop-opacity="0"/></linearGradient>' +
      '<filter id="tlGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
    '</defs>' +
    '<path d="' + areaD + '" fill="url(#tlArea)"/>' +
    '<path d="' + pathD + '" fill="none" stroke="#e8d5b7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" filter="url(#tlGlow)"/>' +
    dots + labels +
    '</svg>';
}

/* Conversão por etapa — 5 células, "Perdido" fora da cadeia */
function renderConvRow(){
  var el = document.getElementById('convRow');
  if(!el) return;
  var steps = STAGES.filter(function(s){ return s.key !== 'perdido'; }).map(function(s){
    return { name:s.name, color:s.color, count:leadsInStage(s.key).length };
  });
  var cells = [];
  for(var i=1;i<steps.length;i++){
    var prev = steps[i-1], cur = steps[i];
    var pct = prev.count > 0 ? Math.min(100, Math.round((cur.count / prev.count) * 100)) : 0;
    cells.push('<div class="conv-cell">' +
      '<div class="conv-cell-label">' + prev.name + ' &rarr; ' + cur.name + '</div>' +
      '<div class="conv-cell-pct" style="color:' + cur.color + '">' + pct + '%</div>' +
    '</div>');
  }
  el.innerHTML = cells.join('');
}
```

**Os 4 KPIs — ícone, badge e rótulos exatos (o Claude monta o HTML assim):**

| # | Ícone (SVG path) | Badge | Rótulo | Sub |
|---|---|---|---|---|
| 1 | `M3 3v18h18` + `M7 14l4-4 3 3 5-6` | `+12%` (up) | NEGÓCIOS ATIVOS | no funil agora |
| 2 | `M12 1v22` + `M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6` | `+8%` (up) | VALOR NO FUNIL | negócios em aberto |
| 3 | `M22 11.08V12a10 10 0 1 1-5.93-9.14` + `polyline 22 4 12 14.01 9 11.01` | `+3` (up) | FECHADOS NO MÊS | R$ X fechados |
| 4 | `M4 21V10M12 21V4M20 21v-7` | `estável` (flat) | TAXA DE CONVERSÃO | lead → fechado |

Os KPIs 2 e 3 usam `.kpi-value.gold` (dourado). Os badges são estáticos — não são calculados.

**Header (estrutura exata):** selo dourado quadrado com estrela à esquerda + nome "Aurum" com o subtítulo "SALES CRM" embaixo em maiúsculas pequenas + menu de navegação ao centro + campo de busca e avatar redondo dourado à direita.

**Títulos das telas:** Dashboard = "Visão geral" / "Resumo do seu pipeline de vendas em tempo real." · Funil = "Funil de vendas" / **"Use o menu do cartão para mover cada negócio de etapa."** · Leads = "Leads & contatos" / "Todos os contatos capturados e seus respectivos negócios." · Agenda = "Agenda de reuniões" / "Suas calls, demos e reuniões marcadas com leads."

> ⚠️ **A legenda do Funil muda na Aula 4.** Na Aula 2 ela diz "use o menu do cartão", porque arrastar ainda não existe — se disser "arraste", o aluno tenta, não consegue, e acha que construiu errado. Na Aula 4, quando o drag & drop estreia, a legenda passa a ser "Arraste os cards entre as etapas para atualizar cada negócio."

---

### Bloco E — Helpers e HTML do dashboard (colar como está)

> ⚠️ **Sem este bloco os Blocos B e D não rodam.** As funções `renderFunnel3d()` e
> `renderConvRow()` chamam `leadsInStage()`, que é definida aqui. Cole este bloco
> ANTES das funções de render.

**Funções auxiliares (obrigatórias):**
```javascript
/* A etapa ATUAL de um lead vive em boardState — não em l.stage.
   l.stage é só o valor inicial; boardState é o que muda quando o cartão é movido.
   Toda leitura de etapa passa por aqui. */
function stageOf(lead){ return boardState[lead.id]; }
function leadsInStage(key){ return LEADS.filter(function(l){ return boardState[l.id] === key; }); }

function brl(n){ return 'R$ ' + n.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2}); }
function brlShort(n){
  if(n >= 1000) return 'R$ ' + (n/1000).toFixed(1).replace('.0','').replace('.',',') + 'k';
  return 'R$ ' + n;
}
function initials(name){
  var p = name.trim().split(' ');
  return (p[0][0] + (p.length>1 ? p[p.length-1][0] : '')).toUpperCase();
}

/* Escapa texto antes de jogar no HTML. Os dados de exemplo têm "&"
   ("Siqueira & Cia", "Barros Moda & Estilo") e o aluno pode digitar
   aspas no cadastro — sem isso a tela corrompe. */
function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* Busca sem acento e sem caso: quem digita "clinica" acha "Clínica". */
function norm(s){
  return String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
}
function buscaBate(lead, termo){
  var t = norm(termo).trim();
  if(!t) return true;
  return norm(lead.nome).indexOf(t) !== -1 || norm(lead.empresa).indexOf(t) !== -1;
}

/* ID de novo contato: sempre o maior existente + 1.
   Regra fixa — na Aula 3 esse id vira a chave do banco, então todos
   os alunos precisam gerar da mesma forma. Nunca usar Date.now(). */
function proximoId(){
  return LEADS.reduce(function(m,l){ return Math.max(m, l.id); }, 0) + 1;
}

/* Ordem das "Movimentações recentes".
   Começa pelos 8 maiores ids; quem for mexido (movido, criado ou
   editado) pula pro topo. Sem essa lista separada, as duas regras
   se contradizem. */
var recentOrder = LEADS.map(function(l){ return l.id; }).sort(function(a,b){ return b - a; });
function bumpRecent(id){
  recentOrder = [id].concat(recentOrder.filter(function(x){ return x !== id; }));
}
function recentes(){
  return recentOrder.slice(0, 8).map(function(id){
    return LEADS.filter(function(l){ return l.id === id; })[0];
  }).filter(Boolean);
}
```

**HTML do Dashboard (estrutura dos painéis — os ids são obrigatórios):**
```html
<!-- 4 KPIs. Repetir o bloco .kpi 4x, trocando ícone/badge/rótulo conforme a tabela acima.
     Os KPIs 2 e 3 levam a classe .gold no .kpi-value. -->
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-top">
      <div class="kpi-icon"><svg viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-6"/></svg></div>
      <div class="kpi-trend up">+12%</div>
    </div>
    <div class="kpi-label">Negócios ativos</div>
    <div class="kpi-value" id="kpiDeals">—</div>
    <div class="kpi-sub">no funil agora</div>
  </div>
  <!-- ... os outros 3 KPIs na mesma estrutura ... -->
</div>

<!-- Linha principal: gráfico + conversão à esquerda, funil 3D à direita -->
<div class="dash-grid">
  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">Novos leads</div>
      <div class="panel-note">últimos 30 dias</div>
    </div>
    <div class="timeline-wrap" id="timelineChart"></div>
    <div class="conv-head">Conversão por etapa</div>
    <div class="conv-row" id="convRow"></div>
  </div>
  <div class="panel">
    <div class="panel-head">
      <div class="panel-title">Funil de vendas</div>
      <div class="panel-note">por etapa</div>
    </div>
    <div class="funnel3d-wrap">
      <div class="funnel3d-svg"><svg id="funnel3d" viewBox="0 0 340 600"></svg></div>
      <div class="funnel3d-legend" id="funnel3dLegend"></div>
    </div>
  </div>
</div>

<!-- Movimentações recentes, largura total -->
<div class="panel" style="margin-top:18px">
  <div class="panel-head">
    <div class="panel-title">Movimentações recentes</div>
    <div class="panel-note">últimos negócios</div>
  </div>
  <div id="recentList"></div>
</div>
```

**Desambiguação do KPI 3 (Fechados no mês):** o **valor grande é a QUANTIDADE** (ex: `2`) e o **sub é o dinheiro** (ex: `R$ 31.100,00 fechados`). Mesmo sendo um número puro, o valor leva `.gold` — é o padrão do Aurum.

---

**Passo 2.5 — ⚠️ O Claude confere o próprio trabalho ANTES de entregar (não pular):**
Antes de dizer "pronto, abre no navegador", o Claude deve verificar o que construiu. Um sistema que abre quebrado na frente do aluno mata a aula.

Checagem obrigatória, feita pelo Claude (o aluno não faz nada disso):
1. **Abrir o arquivo no navegador e olhar o console.** Tem que estar limpo — zero erro em vermelho. Se houver erro, corrigir antes de entregar.
2. **Conferir que as 4 telas renderizam** (navegar por cada uma) e que o funil 3D **desenhou** (não pode ficar um quadrado vazio).
3. **Conferir os números:** com os dados de exemplo, os KPIs têm que dar exatamente **17 negócios ativos**, **R$ 213.300,00 no funil**, **2 fechados** e **11% de conversão**. Se der diferente, algum cálculo saiu errado — revisar as regras acima.
4. **Testar um cadastro:** criar um contato de teste, ver ele aparecer na tabela e no funil, e depois excluir. Se o ciclo funciona, o formulário está certo.

> Só depois de tudo isso, entregar o endereço pro aluno. Se algo falhou, consertar em silêncio e conferir de novo — o aluno não precisa ver o processo, ele precisa ver o sistema funcionando.

**Passo 3 — Abrir e passear pelas 4 telas (oriente o usuário a):**
- Abrir o endereço no navegador.
- Ver o **Dashboard**: os 4 indicadores, o gráfico de linha, o funil 3D com as fatias coloridas.
- Ir no **Funil**: as 7 colunas com os cartões espalhados.
- Ir em **Leads**: a tabela cheia. Clicar numa linha e ver a ficha abrir.
- Ir na **Agenda**: as reuniões agrupadas por dia.
- Voltar no Funil e **mover um cartão de etapa pelo botão/menu**. Voltar no Dashboard e ver os números terem mudado.

> Aqui é o momento de dizer o aviso dos **dados fictícios** (texto acima). Não deixar passar.

**Passo 4 — Cadastrar um contato de verdade (o aluno põe a mão):**
Peça pro aluno ir em **Leads**, clicar em **"+ Novo contato"** e cadastrar **um cliente real ou possível cliente dele** — alguém que ele conheça de verdade, do negócio dele ou de um negócio que ele gostaria de atender. Nome, empresa, telefone, um valor, uma etapa.

Depois de salvar, oriente a conferir: o contato aparece na tabela, vira um cartão no funil, e os números do dashboard mudaram. O sistema deixou de ser só uma demonstração — tem informação dele ali dentro.

> Este passo é importante e não deve ser pulado. Ele muda a relação do aluno com o sistema: até aqui era "o CRM do curso", agora tem um dado dele. É o que faz o próximo passo doer de verdade.

**Passo 5 — O momento de ensino (a "amnésia"):**
Agora, com o contato dele cadastrado na tela, peça pra ele **apertar F5** (recarregar a página).

O contato que ele acabou de cadastrar **some**. Tudo volta ao estado original, com os 20 fictícios de novo, como se ele nunca tivesse mexido.

Explique que isso é de propósito: nesta aula os dados vivem só na memória do navegador, então a cada recarregada o sistema "acorda" do zero. E deixe claro o tamanho do problema — um CRM que esquece o cliente que você acabou de cadastrar não serve pra empresa nenhuma. Diga que na Aula 3 o sistema vai ganhar uma memória de verdade e nunca mais esquecer. **Não resolva isso agora** — é a vitória da Aula 3.

> Frame pro aluno: *"Você tem hoje um protótipo lindo. Amanhã ele vira um sistema."*

**Passo 6 — Fechar a aula:**
Confirme que ele tem as 4 telas funcionando, o funil 3D desenhado, os 20 leads e as 8 reuniões visíveis, o cadastro funcionando e o visual premium. Se sim, a Aula 2 está completa. A Aula 3 (memória/banco de dados) só deve começar quando ele pedir ou quando estiver na aula correspondente.

## Se o usuário pedir algo fora do escopo
- "Coloca pra arrastar o cartão" → "Isso é a Aula 4, quando o sistema ganha o seu mouse. Por enquanto move pelo botão, porque a ordem é o que faz você entender cada parte."
- "Faz salvar os dados" / "conecta um banco" → "É a Aula 3, a próxima. Hoje o sistema nasce inteiro na tela; amanhã ele ganha memória."
- "Coloca isso no ar pra eu mandar pro meu cliente" → "Publicar é a Aula 5. E vale a pena esperar: você não quer publicar um sistema que esquece tudo no F5."
- "Troca os nomes dos leads pelos meus clientes" → "Cadastrar você já pode, e é a tarefa de hoje: use o botão '+ Novo contato' e coloque quantos quiser. Só saiba que hoje eles somem no F5 — amanhã, na Aula 3, tudo passa a ficar salvo. Se preferir, apaga os 20 de exemplo e começa limpo: é só pedir."
- "Muda as etapas pro meu ramo" → "Adaptar o sistema pro seu nicho é a Aula 4. Hoje todo mundo constrói o mesmo, pra você aprender a base."

---

# AULA 3 — A memória (Supabase)

> **Objetivo desta aula:** transformar o protótipo da Aula 2 em um sistema de verdade. Resolver o problema que o aluno sentiu ontem (o F5 que apaga tudo): os dados saem da memória do navegador e passam a viver num **banco de dados real**. Depois desta aula, o aluno mexe no CRM, aperta F5, e está tudo como ele deixou. É "o dia que separa um brinquedo de um sistema de verdade" (promessa gravada na Aula 1). **Marco 1.**

## O que esta aula FAZ
- Conecta o CRM a um **banco de dados real** (Supabase), usando o fluxo de **API key**.
- Cria as tabelas necessárias (contatos/leads, negócios/etapas, agendamentos) — feito pelo Claude, não pelo aluno.
- **Migra os dados de exemplo pra dentro do banco**: os mesmos 20 leads e 8 agendamentos, que antes estavam escritos dentro da página, agora ficam guardados no banco. O sistema continua igual na tela — mas agora está lendo do banco.
- Faz o CRM **salvar** toda alteração no banco: cadastrar um contato novo, mover um cartão de etapa, editar, excluir.
- **Prova visual:** move um cartão, aperta F5, ele continua onde foi deixado.

## O que esta aula NÃO FAZ (é das próximas aulas — NÃO antecipar)
- ❌ Arrastar cartão (drag & drop) → **Aula 4**
- ❌ Adaptar pro nicho do aluno → **Aula 4**
- ❌ Publicar na internet → **Aula 5**

## ⚠️ Como o aluno interage com o Supabase (LEIA — princípios 1 e 2)
O aluno **NUNCA** escreve SQL, **NUNCA** cria tabela na mão, **NUNCA** mexe no editor ou nas configurações técnicas do Supabase. A única coisa que ele faz no site do Supabase é: **criar a conta, criar um projeto (clicando), e copiar duas coisas** (a URL do projeto e a chave). O resto é tudo o Claude, comandado por linguagem natural.

## Como conduzir o usuário nesta aula

**Passo 1 — Reconhecer o problema (fale com o usuário):**
Relembre o F5 da Aula 2: você mexeu no funil, o dashboard mudou, e aí bastou recarregar pra tudo voltar ao começo. Explique em linguagem leiga: o CRM hoje é como alguém com memória de curto prazo — esquece tudo quando "pisca". Hoje a gente dá pra ele uma memória permanente, um lugar seguro onde os dados ficam guardados pra sempre. Esse lugar chama banco de dados, e a gente vai usar um serviço gratuito chamado Supabase.

**Passo 2 — Criar a conta e pegar as chaves (a única parte manual, "clicar e copiar"):**
Oriente o usuário a:
1. Entrar no site do Supabase e **criar uma conta grátis**.
2. **Criar um projeto novo** (só clicar em "novo projeto", dar um nome, e esperar ficar pronto).
3. **Copiar duas informações** que o Supabase mostra nas configurações do projeto (a skill/Red mostra na tela onde ficam):
   - a **URL do projeto**
   - a **chave** (a chave pública/anon key)
4. Guardar as duas, que ele vai colar no Antigravity no próximo passo.

> Diga claramente: "essas duas informações são a ponte. Você só precisa copiar e colar. Não precisa entender o que elas fazem por dentro. O Claude usa elas pra fazer todo o trabalho."

**Passo 3 — Entregar as chaves pro Claude e mandar ele conectar (linguagem natural):**
O aluno cola a URL e a chave no Antigravity e pede, com as próprias palavras, algo como:

```
Aqui está a URL e a chave do meu Supabase: [cola as duas].

Conecta o meu CRM a esse banco de dados:
- Cria as tabelas que ele precisa pra guardar os contatos/leads, a
  etapa de cada um no funil, e os agendamentos.
- Passa os dados de exemplo que hoje estão escritos dentro da página
  pra dentro do banco, sem mudar nada na aparência do sistema.
- Faz o sistema ler tudo do banco quando abre, e salvar no banco toda
  vez que eu cadastrar, editar, excluir ou mover um negócio de etapa.
- O sistema tem que continuar sendo um único arquivo HTML, sem
  framework e sem build.

Quando terminar, me diz o que testar pra eu conferir que funcionou.
```

O Claude faz TUDO a partir daí: cria as tabelas, escreve a conexão, migra os dados, ajusta o código do CRM. O aluno só assiste.

> **NUNCA** instrua o aluno a criar as tabelas manualmente no Supabase, colar SQL, ou mexer no painel técnico. Se algo não conectar, o aluno DESCREVE o erro pro Claude ("deu esse erro aqui: [cola]") e o Claude resolve.

> **Nota técnica pro Claude:** manter o CRM como **um único arquivo HTML sem build** — a conexão com o Supabase entra pelo cliente via CDN (`<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2">`) ou por chamadas diretas à API REST do projeto. Isso é obrigatório porque o deploy da Aula 5 depende de o projeto continuar sendo um arquivo estático.

**Passo 4 — A prova (o momento forte):**
Oriente o usuário a:
1. **Mover um cartão** de etapa no funil (ex: puxar alguém de "Proposta" pra "Fechado" pelo botão).
2. **Cadastrar um contato novo** com o nome dele mesmo.
3. (Opcional, se o Red quiser mostrar) ver esse contato aparecendo dentro do painel do Supabase — a prova de que agora tem um banco real por trás.
4. **Apertar F5.** Tudo CONTINUA como ele deixou. O problema da Aula 2 está resolvido.

Marque o momento: **"seu CRM parou de esquecer. Ontem era um protótipo bonito. Agora é um sistema."**

**Passo 5 — Fechar a aula:**
Confirme que as alterações sobrevivem ao F5. Se sim, a Aula 3 está completa (**Marco 1**). A Aula 4 (o mouse + a cara do negócio dele) só começa quando for a hora.

## Se o aluno quiser começar com o banco vazio
É legítimo. Se ele preferir já usar com dados reais, oriente a pedir: *"em vez de migrar os dados de exemplo, cria as tabelas vazias e deixa o sistema pronto pra eu cadastrar os meus contatos"*. Avise só que o dashboard e o funil vão ficar visualmente vazios até ele cadastrar — e que muita gente prefere manter os exemplos durante o evento, justamente pra ver as telas cheias, e limpar depois na Aula 5.

## Segurança (a skill avisa o aluno)
A chave do Supabase é como a senha de um cofre. Não postar print da chave em lugar público. Nas gravações, o Red usa um projeto Supabase descartável.

## Se o usuário pedir algo fora do escopo
- "Já deixa pra arrastar o cartão" → "Isso é amanhã, a Aula 4. Hoje o foco é dar memória. Uma vitória de cada vez."
- "Cria a tabela eu mesmo no Supabase" → "Nem precisa. Você me passa a chave e o Claude cria tudo. Você é o dono, não o técnico."
- "Já publica na internet" → "Amanhã ainda não; sexta. Antes a gente deixa o sistema com a sua cara."

---

# AULA 4 — O sistema com a SUA cara (mouse + nicho)

> **Objetivo desta aula:** o CRM "ganha vida" (promessa gravada na Aula 1: "você vai mexer nele com o mouse, deixar ele com a cara do negócio que você escolher"). Duas entregas: **arrastar cartão com o mouse** (estreia AQUI, nunca antes), e **adaptar o sistema pro nicho que o aluno escolher** — nome, etapas do funil, campos, segmentos. Depois desta aula não é mais "o CRM do curso": é o sistema dele.

## O que esta aula FAZ
- **Arrastar cartão (drag & drop):** o aluno pega o cartão com o mouse e arrasta de uma coluna pra outra. Ao soltar, a nova etapa é **salva no banco** (o do Supabase da Aula 3). F5 → o cartão continua onde foi solto. A coluna que recebe o cartão dá um feedback visual (borda dourada) enquanto ele está por cima.
- **Adaptar pro nicho:** renomear o sistema, renomear/ajustar as etapas do funil pro tipo de venda daquele negócio, ajustar os campos do cadastro pro que aquele ramo precisa, e trocar os segmentos.

## O que esta aula NÃO FAZ (é da próxima — NÃO antecipar)
- ❌ Publicar na internet / link público → **Aula 5**

## Como conduzir o usuário nesta aula

Cada melhoria abaixo é pedida ao Claude **em português, uma de cada vez** (o aluno descreve, o Claude faz). O aluno nunca edita código. Peça na ordem:

**Passo 1 — Arrastar o cartão (a vitória do mouse):**
O aluno pede pro Claude, com as próprias palavras, algo como:

```
Quero poder arrastar os cartões do funil com o mouse, de uma coluna
pra outra. Enquanto eu estiver arrastando por cima de uma coluna, ela
destaca (borda dourada) pra eu saber onde vou soltar. Quando eu soltar
o cartão numa coluna, salva a nova etapa lá no banco de dados, pra não
perder quando recarregar. O botão/menu de mover continua funcionando
também, pra quem estiver no celular.
```

Depois, oriente a testar: arrasta um cartão pra outra coluna, olha o dashboard mudar, aperta F5, ele continua onde foi solto. É a prova de que a vida (mouse) e a memória (banco da Aula 3) estão juntas.

> **Nota pro Claude:** o Aurum usa HTML5 drag and drop nativo — `draggable=true` no cartão, `dragstart` guardando o id do lead no `dataTransfer`, e `dragover`/`dragleave`/`drop` na coluna, com a classe `.drag-over` dando o destaque. O `drop` grava a nova etapa no Supabase e só então re-renderiza.

**Passo 2 — A entrevista do nicho (fale com o usuário):**
Antes de mandar o Claude adaptar, pergunte ao aluno, uma de cada vez:
1. **Que tipo de negócio** esse CRM vai atender? (clínica, imobiliária, escritório, loja, agência, prestador de serviço…)
2. **Como é a jornada de um cliente** nesse negócio, do primeiro contato até fechar? (isso vira as etapas do funil dele)
3. **Que informação** é importante guardar de cada cliente nesse ramo? (isso vira os campos do cadastro)
4. **Qual o nome** que ele quer dar pro sistema?

> Se o aluno não tiver um negócio em mente, ele escolhe um pra treinar. O ponto da aula é ele **exercitar a adaptação**, não acertar de primeira.

**Passo 3 — Adaptar o sistema (com as respostas da entrevista):**
O aluno pede, em português, algo como (exemplo de clínica de estética):

```
Adapta o meu CRM pra uma clínica de estética chamada [nome].
- Troca o nome do sistema no topo pra [nome].
- Renomeia as etapas do funil pra: Interessado, Avaliação agendada,
  Avaliação feita, Orçamento enviado, Fechado e Perdido — mantendo
  cada uma com uma cor própria.
- No cadastro do contato, adiciona um campo de "procedimento de
  interesse" e um de "data da última consulta".
- Troca as etiquetas de segmento pelas que fazem sentido aqui.
- Ajusta o banco de dados pra guardar esses campos novos, e mantém
  tudo que já está salvo.
```

O Claude aplica tudo — inclusive a mudança no banco. O aluno vê o sistema virar a cara do negócio dele.

> **Importante:** o Claude deve ajustar as etapas **e** o banco juntos, pra não quebrar o que já está salvo. Se o aluno mudar de ideia depois, é só pedir de novo.

**Passo 4 — Fechar a aula:**
Confirme que o aluno consegue arrastar cartões (e que a mudança sobrevive ao F5), e que o sistema está com o nome, as etapas e os campos do negócio que ele escolheu. Se sim, a Aula 4 está completa. A Aula 5 (publicar) é a última do evento.

## Se o usuário pedir algo fora do escopo
- "Já joga na internet" → "Publicar é amanhã, a Aula 5, o grande dia. Hoje a gente deixa o sistema com a sua cara pra você publicar algo que é SEU, não uma demo."
- "Quero editar o código pra mudar isso" → "Não precisa tocar em código. Descreve pro Claude o que você quer diferente, e ele muda. Você conduz, ele executa."
- "Quero adaptar pra três clientes diferentes" → "Isso é o 🎁 Presente, que você roda sozinho depois do evento quantas vezes quiser. Hoje escolhe um."

---

# AULA 5 — A publicação (colocar no ar + acabamento)

> **Objetivo desta aula:** o grande dia (promessa gravada na Aula 1: "você pega tudo que construiu e joga na internet, sai com um link no ar"). Acabamento final e deploy na Vercel: o CRM vira um site público com link que ele manda pra qualquer pessoa. **Marco 2.**

## O que esta aula FAZ
- **Higiene dos dados:** decidir o que vai pro ar — os dados fictícios ficam ou o sistema vai limpo.
- **Acabamento:** logo/ícone, título da aba, ajustes finais de texto, conferir que o sistema está bonito no celular.
- **Proteger o banco:** trancar o acesso aos dados antes de o sistema ficar público.
- **Deploy na Vercel:** publica o CRM na internet e devolve um **link público**. Feito pelo fluxo de **API key**.

## Como conduzir o usuário nesta aula

**Passo 1 — ⚠️ A conversa dos dados fictícios (NÃO PULAR):**
Antes de publicar, pergunte ao aluno, com estas palavras (ou equivalentes):

> "Antes de colocar no ar: seu sistema ainda está com os 20 contatos e as 8 reuniões de exemplo — a Mariana Fontes, o Ricardo Almeida, aquela turma toda. Eles são inventados. Você quer publicar com eles ou sem eles?
>
> - **Com eles:** bom se você vai usar o link pra MOSTRAR o sistema — pra um cliente, num portfólio, numa proposta. Um sistema cheio impressiona; um sistema vazio parece que não faz nada.
> - **Sem eles:** obrigatório se você vai USAR o sistema de verdade a partir de agora, ou se vai entregar pra um cliente começar a cadastrar os clientes dele."

Se ele quiser limpar, o pedido é simples:

```
Limpa todos os dados de exemplo do meu CRM: apaga os contatos, os
negócios e os agendamentos fictícios do banco, e deixa o sistema
zerado, pronto pra receber os dados de verdade. Mantém as etapas do
funil e a estrutura como estão.
```

> Deixe claro pro aluno que isso não é uma via de mão única: dá pra pedir pro Claude repovoar com exemplos de novo a qualquer momento, se ele precisar do sistema cheio pra uma demonstração.

**Passo 2 — Acabamento:**
```
Coloca um ícone/logo simples no topo do sistema e ajusta o título da
aba do navegador pro nome do sistema. Confere se está bonito e
utilizável no celular também.
```

**Passo 3 — 🔒 Trancar o banco antes de publicar (NÃO PULAR):**
Explique ao aluno em linguagem de dono, sem termo técnico:

> "Mais uma coisa antes de colocar no ar, e é rápida. Até agora o seu sistema rodava só na sua máquina. Quando ele for pra internet, qualquer pessoa que tiver o link consegue abrir. E se a gente não trancar o banco de dados, junto com o sistema vai também a porta dos dados — alguém poderia mexer no que está lá dentro. Hoje são contatos inventados, então não tem drama. Mas no dia que for cliente de verdade, essa porta tem que estar trancada. Então a gente já tranca agora e você nunca mais pensa nisso."

O pedido:

```
Antes de eu publicar esse sistema na internet, protege o meu banco de
dados no Supabase. Configura as regras de acesso pra que os dados não
fiquem abertos pra qualquer pessoa que tenha o endereço do sistema.
Depois me confirma o que você fez, em português simples.
```

> O Claude configura as políticas de acesso (RLS) sozinho. O aluno **não escreve SQL, não mexe no painel do Supabase**. Se o Claude pedir alguma informação, o aluno responde conversando.
>
> **Se der erro depois de proteger** (o sistema parar de carregar os dados), o aluno cola o erro pro Claude: "protegi o banco e agora o sistema não carrega os contatos, resolve". É esperado que possa acontecer e o Claude ajusta.

**Passo 4 — Publicar na internet (deploy na Vercel, fluxo de API key):**
Explique que publicar um site tinha fama de complicado (servidor, hospedagem, configuração), e que agora é o mesmo modelo do Supabase: cria conta, copia a chave, entrega pro Claude.

Oriente o aluno a:
1. **Criar uma conta grátis na Vercel.**
2. **Copiar a chave (token) da Vercel** (a skill/Red mostra onde fica).
3. **Colar a chave no Antigravity** e pedir, em português:
   > "Aqui está a minha chave da Vercel: [cola]. Usa ela pra publicar esse projeto na internet e me devolve o link público pra eu abrir."
4. O Claude publica sozinho e devolve o link. O aluno **não toca em terminal, não usa Git, não configura nada.**

> **NUNCA** instrua o aluno a rodar comando no terminal, mexer em Git/GitHub, ou configurar o deploy nas settings da Vercel. Tudo é a chave + o pedido em português. Se der erro no deploy, o aluno cola o erro pro Claude e o Claude resolve.

> **Por que dá certo:** o CRM é um único arquivo HTML estático. Não tem build, não tem servidor. É por isso que a skill exigiu isso desde a Aula 2 — o deploy vira uma questão de segundos.

**Passo 5 — A prova (Marco 2):**
O aluno abre o link público no navegador (pode abrir no celular pra sentir o peso). Está no ar, na internet, acessível pra qualquer pessoa. Ele mexe no funil pelo celular e vê a alteração aparecer no computador — porque o banco é o mesmo.

Marque: **"não é mais 'pronto pra mostrar pra um cliente'. É 'manda o link pro cliente AGORA'."**

**Passo 6 — Fechar a aula (e o evento):**
Confirme que o aluno tem o sistema no ar, com link público, com memória, protegido e com a cara do negócio dele. Esse é o fim da parte percorrida em conjunto. A partir daqui, sobra o 🎁 Presente, que ele roda sozinho.

## Segurança (a skill avisa o aluno)
A chave da Vercel é como a senha de um cofre. Não postar print da chave em público. Nas gravações, o Red usa uma conta/token descartável.

**Sobre o banco protegido (Passo 3):** trancar o banco antes de publicar não é opcional e não é "coisa de programador" — é a diferença entre entregar um sistema e entregar um sistema com a porta aberta. Quando o aluno for atender um cliente de verdade, é isso que separa profissional de amador. A skill sempre executa o Passo 3 antes do deploy, mesmo que o aluno peça pra pular.

## Se o usuário pedir algo fora do escopo
- "Quero mexer no código do deploy" → "Nem precisa. A chave e o pedido resolvem. O Claude faz o técnico."
- "Quero colocar login e senha pros meus clientes" → "Dá pra fazer, e o Claude faz. Mas isso já é você voando sozinho, depois do evento — o presente te dá a base pra pedir qualquer coisa."

---

# 🎁 PRESENTE — Personalização pra QUALQUER nicho

> **Esta etapa NÃO é percorrida durante as aulas do evento.** Ela é o presente do Red pro aluno seguir voando sozinho. Depois que o aluno terminou as Aulas 2 a 5 e tem um CRM completo, com banco, com a cara de um negócio e publicado, ele roda esta parte pra adaptar o CRM pra QUALQUER outro negócio, quantas vezes quiser. É o que transforma "eu montei UM CRM" em "eu construo CRM pra qualquer empresa" (o marceneiro).

> **Quando ativar:** só quando o aluno já tem o CRM base pronto (Aulas 2 a 5 concluídas) E pede a personalização, ou diz que quer adaptar pra um nicho/cliente específico. Se ele ainda não terminou a base, oriente a terminar primeiro.

> **Diferença pra Aula 4:** na Aula 4 ele adaptou UMA vez, dentro da aula, pra um nicho. Aqui ele aprende a **repetir isso pra qualquer cliente**, do zero, quantas vezes quiser — inclusive tirando uma cópia do sistema pra cada cliente, com banco separado e link separado.

## O que esta etapa FAZ
Adapta o CRM já pronto pro ramo específico que o aluno escolher: renomeia as etapas do funil pra linguagem daquele negócio, ajusta os campos dos cadastros pro que aquele negócio precisa, troca os textos/nomes/segmentos pra ficar com a cara do cliente — e, se for pra outro cliente, cria uma cópia com banco e link próprios. Tudo por conversa, tudo feito pelo Claude.

## Como conduzir (a entrevista de personalização)

**Passo 1 — Entender o negócio (a entrevista):**
Faça ao aluno estas perguntas, uma de cada vez, em linguagem simples:
1. **Que tipo de negócio** esse CRM vai atender? (ex: clínica de estética, imobiliária, escritório de advocacia, loja, agência...)
2. **Como é a jornada de um cliente** nesse negócio, do primeiro contato até fechar? (isso vira as etapas do funil dele)
3. **Que informações** são importantes guardar de cada cliente nesse ramo? (isso vira os campos do cadastro; ex: uma clínica quer "última consulta", uma imobiliária quer "tipo de imóvel procurado")
4. **Qual o nome** que ele quer dar pro sistema?
5. **É pra ele ou pra um cliente?** Se for pra um cliente, o sistema merece uma cópia própria: banco próprio, link próprio, dados separados.

**Passo 2 — Traduzir as respostas num pedido pro Claude:**
Com as respostas, monte (ou oriente o aluno a pedir) uma personalização em linguagem natural. Exemplo, pra uma imobiliária:

```
Faz uma cópia do meu CRM pra um cliente novo: uma imobiliária
chamada [nome].
- Renomeia as etapas do funil pra: Novo interessado, Visita agendada,
  Visita feita, Proposta enviada, Documentação, Fechado e Perdido.
- No cadastro do contato, adiciona "tipo de imóvel procurado",
  "faixa de valor" e "bairro de interesse".
- Troca os segmentos pra: Apartamento, Casa, Comercial, Terreno.
- Muda o nome do sistema pro nome dela.
- Popula com uns 15 contatos fictícios desse ramo pra eu apresentar
  o sistema, e me avisa como limpar depois.
- Usa um projeto novo do Supabase (te passo a chave) e publica num
  link separado do meu.
```

O Claude aplica tudo. O aluno vê o CRM virar a cara do cliente dele.

**Passo 3 — Republicar:**
É o mesmo fluxo da Aula 5: a chave da Vercel já está com ele, é só pedir pro Claude publicar de novo. Se for um cliente novo, um projeto Supabase novo (chave nova, mesmo fluxo da Aula 3) e um link novo.

**Passo 4 — Sobre os dados fictícios (lembrete permanente):**
Toda vez que o aluno popular um CRM com dados de exemplo pra apresentar, ele precisa lembrar de **limpar antes de entregar pro cliente usar**. O pedido é sempre o mesmo: *"limpa todos os dados de exemplo e deixa o sistema zerado"*. E, se ele quiser encher de novo pra outra apresentação: *"popula com contatos fictícios do ramo [x] pra eu demonstrar"*.

**Passo 5 — O recado do presente:**
Reforce a mensagem: agora ele não tem um CRM, ele tem a **capacidade de construir um CRM pra qualquer empresa**. Cada vez que ele rodar essa personalização pra um cliente diferente, ele está entregando um sistema sob medida. É o marceneiro, não o montador de móvel. Esse é o presente: a autonomia de voar sozinho.

## Princípios continuam valendo
Mesmo aqui, o aluno nunca escreve código nem SQL. Ele responde a entrevista, o Claude constrói. Se um serviço externo precisar de chave, é o mesmo fluxo: cria conta, copia chave, entrega pro Claude.

---

*Skill criar-crm · 5 aulas + presente · segue o Contrato Gravado da Aula 1 do LPSG · escada: protótipo completo (A2) → memória (A3) → mouse + nicho (A4) → no ar (A5) · princípios: zero técnico manual + API key + a skill é a estrela.*
