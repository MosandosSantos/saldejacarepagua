---
name: GPRBRCRM (GEOD-CEOD)
description: CRM multi-tenant de gestao — painel escuro "piano" (azul-marinho profundo) com acentos azul-ceu, glassmorphism e tipografia Manrope + Fraunces + JetBrains Mono.
colors:
  hazon-night: "#0a1e3d"
  hazon-abyss: "#081830"
  hazon-deep: "#0f2a52"
  hazon-surface: "#0e2540"
  hazon-mid: "#0c2245"
  hazon-primary: "#1a5fb4"
  hazon-primary-dark: "#1450a0"
  hazon-accent: "#5b8def"
  hazon-text: "#f4fafb"
  hazon-muted: "#bcd3da"
  hazon-dim: "#a6bfc7"
  hazon-success: "#4ade80"
  hazon-success-bright: "#22c55e"
  hazon-warn: "#fbbf24"
  hazon-danger: "#fca5a5"
  hazon-danger-solid: "#ef4444"
  hazon-info: "#93b8f7"
  hazon-orange: "#fb923c"
  hazon-blue: "#5b8def"
  hazon-slate: "#94a3b8"
  hazon-pink: "#f472b6"
typography:
  display:
    fontFamily: "Fraunces, Georgia, serif"
    fontWeight: 600
    fontSize: "28px"
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Manrope, Segoe UI, sans-serif"
    fontWeight: 600
    fontSize: "13.5px"
    lineHeight: 1.25
  body:
    fontFamily: "Manrope, Segoe UI, sans-serif"
    fontWeight: 400
    fontSize: "13px"
    lineHeight: 1.5
  label:
    fontFamily: "Manrope, Segoe UI, sans-serif"
    fontWeight: 700
    fontSize: "10px"
    letterSpacing: "0.12em"
  mono:
    fontFamily: "JetBrains Mono, monospace"
    fontWeight: 700
    fontSize: "34px"
    lineHeight: 1
rounded:
  sm: "0.75rem"
  md: "1rem"
  lg: "1.5rem"
  icon: "11px"
  full: "9999px"
spacing:
  btn-pad: "0.5rem 1rem"
  form-pad: "6px 10px"
  card-pad: "1.5rem"
  cell-pad: "0.875rem 1.25rem"
components:
  button-primary:
    backgroundColor: "{colors.hazon-primary}"
    textColor: "#ffffff"
    typography: "{typography.title}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
  button-primary-hover:
    backgroundColor: "{colors.hazon-primary-dark}"
  button-ghost:
    backgroundColor: "rgba(255,255,255,0.05)"
    textColor: "{colors.hazon-muted}"
    typography: "{typography.title}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
  button-ghost-hover:
    backgroundColor: "rgba(255,255,255,0.10)"
    textColor: "#ffffff"
  button-danger:
    backgroundColor: "rgba(252,165,165,0.10)"
    textColor: "{colors.hazon-danger}"
    typography: "{typography.title}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 1rem"
  card:
    backgroundColor: "rgba(255,255,255,0.05)"
    textColor: "{colors.hazon-text}"
    rounded: "{rounded.md}"
    padding: "{spacing.card-pad}"
  card-sm:
    backgroundColor: "rgba(255,255,255,0.05)"
    textColor: "{colors.hazon-text}"
    rounded: "{rounded.md}"
    padding: "{spacing.card-pad}"
  input:
    backgroundColor: "rgba(255,255,255,0.06)"
    textColor: "{colors.hazon-text}"
    typography: "{typography.body}"
    rounded: "8px"
    padding: "{spacing.form-pad}"
    height: "34px"
  input-focus:
    backgroundColor: "rgba(255,255,255,0.10)"
  chip:
    backgroundColor: "rgba(116,179,198,0.22)"
    textColor: "{colors.hazon-accent}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "0.125rem 0.625rem"
  search:
    backgroundColor: "rgba(255,255,255,0.05)"
    textColor: "{colors.hazon-text}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0.625rem 1rem 0.625rem 2.5rem"
  th:
    textColor: "{colors.hazon-dim}"
    typography: "{typography.label}"
    padding: "{spacing.cell-pad}"
  td:
    textColor: "{colors.hazon-muted}"
    typography: "{typography.body}"
    padding: "{spacing.cell-pad}"
---

# Design System: GPRBRCRM (GEOD-CEOD)

## Overview

**Creative North Star: "O Piano Azul-Marinho"**

O GEOD-CEOD e um painel escuro onde toda superficie e vidro fosco flutuando sobre um gradiente azul-marinho profundo (piano). A profundidade vem da translucidez (`rgba(255,255,255,0.06-0.18)` + `backdrop-filter: blur(20px)`), nao de sombras; o silencio visual e a marca. O acento `hazon-accent` (#5b8def) aparece com parcimonia para sinalizar interatividade, etapa ativa e valores em destaque.

E um sistema **Operate** (painel de trabalho diario): escaneabilidade, consistencia e expectativas familiares vem antes de expressao. Os numeros — dinheiro, contagens, scores — sao sempre monoespacados e gordos, para leitura rapida de KPI. Os titulos de pagina sao os unicos momentos serif (Fraunces), ancorando cada tela.

**Key Characteristics:**
- Superficies translucidas com `backdrop-blur` sobre gradiente piano blue/night — nunca paineis opacos solidos.
- Um unico acento interativo: `hazon-accent` (#5b8def); raridade e o ponto.
- Tipografia ternaria: Fraunces (display, so titulos/logo/avatars) + Manrope (todo o resto) + JetBrains Mono (valores/codigos).
- Valores numericos sempre em `font-mono` bold — KPIs, somas, scores, contadores.
- Hierarquia por opacidade do branco (text -> muted -> dim), nao por novas cores.
- Cores semanticas e categoricas (stages/segments/scores) aplicadas como *tintes* (cor + `1a` = 10% alpha), nunca como blocos saturados.
- Tema claro opcional (`data-tema="claro"`) inverte o sistema mantendo os mesmos tokens.

## Colors

Paleta unica nomeada `hazon-*` (famiglia piano blue/night + semanticos). Os tokens sao a fonte da verdade; descreva o uso, nao reinvente o hex.

### Primary
- **hazon-primary** (#1a5fb4): cor de marca. Base do gradiente de botoes primarios, logo e avatar.
- **hazon-primary-dark** (#1450a0): fim do gradiente (topo `#3b7ded` -> base `#1a5fb4` no logo/avatar) e estado hover/pressionado.
- **hazon-accent** (#5b8def): **o unico acento interativo.** Etapa ativa na nav, bordas/glow de foco, valor monetario em destaque, links hover, anel da coluna kanban ao receber card.

### Neutral
- **hazon-night** (#0a1e3d): fundo base do `body`.
- **hazon-abyss** (#081830): header (`/70` + blur) e superficies mais escuras.
- **hazon-deep** (#0f2a52) / **hazon-mid** (#0c2245): stops do gradiente de fundo.
- **hazon-surface** (#0e2540): cartoes solidos quando se precisa de opacidade total.
- **hazon-text** (#f4fafb): texto primario (branco quente).
- **hazon-muted** (#bcd3da): texto secundario (celulas de tabela, descricoes).
- **hazon-dim** (#a6bfc7): labels uppercase, captions, texto de apoio.
- **Branco translucido** (`rgba(255,255,255,0.06/0.10/0.18)`): superficies, bordas e hover. E a materia-prima do "vidro".

### Semantic & Categorical
- **hazon-success** (#4ade80) / **hazon-success-bright** (#22c55e): fechado, score "quente", variacao positiva.
- **hazon-warn** (#fbbf24): negocios estagnados, score "morno", avisos.
- **hazon-danger** (#fca5a5) / **hazon-danger-solid** (#ef4444): perdido, botoes de exclusao (contorno vs. solido).
- **hazon-info** (#93b8f7), **hazon-orange** (#fb923c), **hazon-blue** (#5b8def), **hazon-slate** (#94a3b8), **hazon-pink** (#f472b6): cores categoricas de stages/segments (`core/dominio.py`), aplicadas sempre como tinte (`color: X; background: X1a`).

### Named Rules
**A Regra do Vidro.** Toda superficie de conteudo e branco translucido sobre o gradiente, com `backdrop-filter: blur(20px)` e borda `rgba(255,255,255,0.10)`. Nunca use um painel opaco solido (exceto `hazon-surface` quando a legibilidade de um modal/drawer exigir).
**A Regra do Acento Unico.** `hazon-accent` e o unico sinal de interatividade/destaque. Nao introduza um segundo acento; se precisa de variacao, use opacity/tinte do proprio accent.
**A Regra do Tinte.** Cores categoricas (stage/segment/score) entram como `color: <hue>; background: <hue>1a` (10% alpha). Nunca como bloco saturado de fundo.

## Typography

**Display Font:** Fraunces (fallback: Georgia, serif)
**Body Font:** Manrope (fallback: Segoe UI, sans-serif)
**Mono Font:** JetBrains Mono (fallback: monospace) — para valores numericos e codigos

**Character:** Fraunces da peso editorial e calidez aos titulos; Manrope e neutra e legivel em densidade alta; JetBrains Mono garante legibilidade em valores e codigos. O contraste serif x sans x mono cria tres camadas claras: pagina (serif), interface (sans), dado (mono).

### Hierarchy
- **Display** (Fraunces, 600, 28px, line-height 1.1, letter-spacing -0.01em): titulos de pagina (`.hazon-titulo`) e logo "GPRBRCRM".
- **Title** (Manrope, 600, 13.5px, 1.25): nomes em cards kanban, itens de nav, texto de botoes, labels de secao.
- **Body** (Manrope, 400, 13px, 1.5): texto corrido, celulas de tabela, descricoes, placeholders.
- **Label** (Manrope, 700, 10px, letter-spacing 0.12em, UPPERCASE): rotulos micro (`.hazon-label`), headers de tabela (`.hazon-th`), captions de KPI, chips.
- **Mono** (JetBrains Mono, 700, 34px, 1): numeros de KPI. Reduz para 12.5-17px em somas, scores, contadores e badges.

### Named Rules
**A Regra do Titulo Serif.** Fraunces aparece somente em titulos de pagina, logo e avatares. Qualquer texto de interface, dado ou rotulo e Manrope ou mono.
**A Regra do Numero Mono.** Todo valor numerico de negocio (dinheiro, contagem, soma de coluna, score, percentual) e `font-mono` bold. Numero em Manrope e erro.

## Layout

- **Container:** `max-w-[1640px]` centralizado, `px-4 sm:px-8`.
- **Header:** sticky `top-0`, altura `h-16` (64px), `bg-hazon-abyss/70 backdrop-blur-xl`, borda inferior `white/18`. Nav central com itens `rounded-[11px] px-4 py-2.5`; item ativo = `bg-accent/15 text-accent`.
- **Main:** `py-8` abaixo do header.
- **Fundo global:** `#bg-fundo` fixo (`-z-10`) com dois radial-gradients blue/mid + linear-gradient `deep -> mid -> night`.
- **Grade de KPIs:** `grid gap-4 sm:grid-cols-2 xl:grid-cols-4`.
- **Kanban:** `flex overflow-x-auto`, colunas fixas `w-[290px] shrink-0`, max. 30 cards visiveis por coluna (excesso vira aviso "+N nao exibidos").
- **Ritmo:** Tailwind default; blocos de secao separados por `mb-6`/`mb-7`; internamente `gap-2.5`-`gap-4`.
- **Responsivo:** mobile-first; nav e detalhes do usuario colapsam em telas pequenas (`hidden md:flex`).

## Elevation & Depth

Profundidade por **camadas tonais translucidas + blur**, nao por sombras. O gradiente de fundo mostra-se atraves dos cartoes, criando a sensabilidade de vidro fosco.

### Shadow Vocabulary
- **Glow Accent** (`0 0 8px rgba(91,141,239,0.44)`): foco/destaque de elementos accent (definido em `--hazon-glow-accent`).
- **Logo/Avatar** (`shadow-lg shadow-[#5b8def]/30`): os unicos elementos com sombra estrutural — reforcam a marca.
- **Soft** (`0 8px 30px -12px rgba(0,0,0,0.40)`): cartoes elevados / drawers quando necessarios.
- **Inset ring** (`inset 0 0 0 2px rgba(91,141,239,0.45)` + bg accent 8%): coluna kanban sob `dragover` (`.kanban-col.is-over`).

### Named Rules
**A Regra das Camadas, nao Sombras.** Superficies sao planas em repouso. Sombras aparecem so em marca (logo/avatar) ou como resposta de estado (hover com lift, drop-target com anel inset). Nunca sombreie um cartao parado "para destacar".

## Shapes

- **Raios:** `sm` 12px (botoes, inputs, search, badges quadrados), `md` 16px (cartoes), `lg` 24px (cartoes grandes / banners), `full` 9999px (chips, avatares, badges de nav).
- **Conteineres de icone:** `rounded-[11px]` com borda accent 35% + bg accent 10% — assinatura recorrente em KPIs e nav.
- **Bordas:** sempre `1px solid rgba(255,255,255,0.10-0.18)` em superficies; `1px` accent (~0.35-0.55) em foco/ativo.
- **Linguagem formal:** cantos arredondados suaves em tudo; nada de cantos vivos. Cards de alerta (estagnados) usam `rounded-2xl`.

## Components

Para cada componente: sentenca de carater, depois shape, cor, estados, comportamento.

### Buttons (`.hazon-btn`)
Tateis e confiantes: `rounded-sm` (12px), `padding 0.5rem 1rem`, `font-size 13px / weight 600`, `transition all 0.15s`.
- **Primary** (`.hazon-btn-primary`): gradiente `linear-gradient(145deg, #3b7ded, #1a5fb4)` + borda accent 50%, texto branco. Hover = `filter: brightness(1.1)`.
- **Ghost** (`.hazon-btn-ghost`): bg `white/6` + borda `white/18` + texto muted. Hover = bg `white/10` + texto branco.
- **Danger** (`.hazon-btn-danger`): bg `danger/10` + borda `danger/30` + texto `#fca5a5`. Hover = bg `danger/20` + branco.
- **Danger Solid** (`.hazon-btn-danger-solid`): bg `#ef4444/90` + borda `danger/40` + branco. Hover = `brightness(1.1)`.

### Cards (`.hazon-card`, `-sm`, `-lg`)
Vidro fosco: bg `white/6` + borda `white/10` + `backdrop-blur(20px)`, raio md (16px) ou lg (24px).
- **KPI card** (`.hazon-card-sm p-6`): icone em caixa `rounded-[11px]` (borda accent 35% + bg accent 10%), label uppercase dim, numero mono 34px bold, badge de variacao em pill (success ou accent). Hover = `-translate-y-1` + `border-accent/40`.
- **Kanban card**: `.hazon-card-sm p-3.5`, nome (title white) -> empresa (body dim) -> linha de chips (segmento + score) -> rodape (nivel uppercase + valor mono accent). Hover = `border-accent/40 + bg-white/10`. States: `.dragging` (opacity 0.35), `.card-entrou` (animacao scale/opacity 0.35s).

### Inputs / Fields (`form.hazon-form`)
Contidos: `width 100%`, `height 34px`, `padding 6px 10px`, raio 8px, bg `white/6`, borda `white/18`, `font-size 12.5px`. Focus = borda `accent/40` + bg `white/10`. Options herdam `hazon-night`. Textarea = `resize: vertical`.

### Search (`.hazon-search`)
Caixa com icone a esquerda (`absolute left-3.5`), `padding-left 2.5rem`, raio sm (12px), bg `white/6`. Focus = borda `accent/40` + bg `white/10`.

### Chips (`.hazon-chip`)
Pill full: `padding 0.125rem 0.625rem`, `font-size 10px / weight 700`, `white-space: nowrap`. Cor sempre tinte: `color: <hue>; background: <hue>1a`. Variante marcada em forms (`.tag-check:checked + .tag-chip`) = accent 55% borda + accent 22% bg.

### Kanban Column (`.kanban-col`) — assinatura
`w-[290px] shrink-0`, `.hazon-card` (translucida). Cabecalho: dot colorido `h-2.5 w-2.5` com `box-shadow: 0 0 8px <color>70` (glow da etapa), nome stage (title muted), contador pill mono. Corpo: `gap-2.5 p-3`. Rodape: "Soma:" + valor mono bold. State `.is-over` = anel inset accent + bg accent 8%.

### Tables (`.hazon-th` / `.hazon-td`)
Header uppercase dim (`10px / 700 / tracking 0.12em`), celula body muted (`12.5px`), ambos `padding 0.875rem 1.25rem`. Sem zebrado; separacao por espaco e opacidade.

### Navigation (header)
Logo: `rounded-[11px]` gradiente `#3b7ded -> #1a5fb4` + SVG de alvos concetricos; wordmark "GPRBRCRM" (Fraunces) com "RCRM" em accent. Itens: `rounded-[11px] px-4 py-2.5`, ativo `bg-accent/15 text-accent`, inativo `text-muted hover:bg-white/10 hover:text-white`. Badge de tarefas: pill `bg-red-400/90` mono 10px. Avatar: `rounded-full` gradiente com iniciais (Fraunces).

### Page Title (`.hazon-titulo`)
Fraunces 28px/600, `letter-spacing -0.01em`, `color text`. Sub (`p.hazon-sub` ou classe): `14px dim`.

## Do's and Don'ts

### Do:
- **Do** construir superficies com branco translucido + `backdrop-blur(20px)` sobre o gradiente (a Regra do Vidro).
- **Do** usar `hazon-accent` (#5b8def) como unico sinal de interatividade, etapa ativa e valor em destaque.
- **Do** render numeros de negocio (R$, contagens, scores, somas, %) em `font-mono` bold (JetBrains Mono).
- **Do** aplicar cores categoricas como tinte (`color: X; background: X1a`), nunca como bloco solido.
- **Do** dar feedback tactile: hover com `brightness(1.1)` no primario, `-translate-y-1` em KPI cards, anel inset na coluna kanban alvo.
- **Do** prefixar novas classes de sistema com `hazon-` e registrá-las em `theme/static_src/src/styles.css`.
- **Do** manter o tema claro via `body[data-tema="claro"]` usando os mesmos tokens invertidos.

### Don't:
- **Don't** introduza um segundo acento — variacoes vêm de opacity/tinte do proprio `hazon-accent`.
- **Don't** use Fraunces fora de titulos de pagina, logo e avatares.
- **Don't** sombreie cartoes em repouso "para destacar"; profundidade vem de camadas tonais.
- **Don't** invente hex novos — a paleta `hazon-*` e fechada; estenda `core/dominio.py` para cores categoricas.
- **Don't** use blocos de cor saturada de fundo para stages/segments/scores — sempre tinte 10%.
- **Don't** troque Manrope por outra sans sem trocar em `tailwind.config.js`, `styles.css` e no `<link>` do `base/basic.html` juntos.
