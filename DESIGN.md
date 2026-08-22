---
name: CRMCronos.Cloud (HAZON)
description: CRM multi-tenant de vendas — painel escuro translúcido (vidro jateado) sobre gradiente teal, com tipografia Manrope + Fraunces.
colors:
  hazon-night: "#0b2029"
  hazon-abyss: "#072026"
  hazon-deep: "#0e3a44"
  hazon-surface: "#0d2a33"
  hazon-mid: "#112530"
  hazon-primary: "#0b6f74"
  hazon-primary-dark: "#075b60"
  hazon-accent: "#74b3c6"
  hazon-text: "#f4fafb"
  hazon-muted: "#bcd3da"
  hazon-dim: "#6f8a93"
  hazon-success: "#7fe3c4"
  hazon-success-bright: "#4ade80"
  hazon-warn: "#fbbf24"
  hazon-danger: "#fca5a5"
  hazon-danger-solid: "#ef4444"
  hazon-info: "#c084fc"
  hazon-orange: "#fb923c"
  hazon-blue: "#60a5fa"
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
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
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

# Design System: CRMCronos.Cloud (HAZON)

## Overview

**Creative North Star: "O Vidro Jateado"**

O HAZON é um painel escuro onde toda superfície é vidro fosco flutuando sobre um gradiente teal profundo. A profundidade vem da translucidez (`rgba(255,255,255,0.05–0.15)` + `backdrop-filter: blur(24px)`), não de sombras; o silêncio visual é a marca. O acento `hazon-accent` (#74b3c6) aparece com parcimônia para sinalizar interatividade, etapa ativa e valores em destaque.

É um sistema **Operate** (painel de trabalho diário): escaneabilidade, consistência e expectativas familiares vêm antes de expressão. Os números — dinheiro, contagens, scores — são sempre monoespaçados e gordos, para leitura rápida de KPI. Os títulos de página são os únicos momentos serif (Fraunces), ancorando cada tela.

A confiança tátil mora nos detalhes: botões primários em gradiente teal, cartões KPI que sobem (`-translate-y-1`) e ganham borda accent no hover, coluna kanban que acende um anel accent ao receber um card. Tudo o resto é contido.

**Key Characteristics:**
- Superfícies translúcidas com `backdrop-blur` sobre gradiente teal/night — nunca painéis opacos sólidos.
- Um único acento interativo: `hazon-accent` (#74b3c6); raridade é o ponto.
- Tipografia binária: Fraunces (display, só títulos/logo/avatars) + Manrope (todo o resto).
- Valores numéricos sempre em `font-mono` bold — KPIs, somas, scores, contadores.
- Hierarquia por opacidade do branco (text → muted → dim), não por novas cores.
- Cores semânticas e categóricas (stages/segments/scores) aplicadas como *tintes* (cor + `1a` = 10% alpha), nunca como blocos saturados.
- Tema claro opcional (`data-tema="claro"`) inverte o sistema mantendo os mesmos tokens.

## Colors

Paleta única nomeada `hazon-*` (família teal/night + semânticos). Os tokens são a fonte da verdade; descreva o uso, não reinvente o hex.

### Primary
- **hazon-primary** (#0b6f74): cor de marca. Base do gradiente de botões primários, logo e avatar.
- **hazon-primary-dark** (#075b60): fim do gradiente (topo `#2aa1a8` → base `#075b60` no logo/avatar) e estado hover/pressionado.
- **hazon-accent** (#74b3c6): **o único acento interativo.** Etapa ativa na nav, bordas/glow de foco, valor monetário em destaque, links hover, anel da coluna kanban ao receber card.

### Neutral
- **hazon-night** (#0b2029): fundo base do `body`.
- **hazon-abyss** (#072026): header (`/70` + blur) e superfícies mais escuras.
- **hazon-deep** (#0e3a44) / **hazon-mid** (#112530): stops do gradiente de fundo.
- **hazon-surface** (#0d2a33): cartões sólidos quando se precisa de opacidade total.
- **hazon-text** (#f4fafb): texto primário (branco quente).
- **hazon-muted** (#bcd3da): texto secundário (células de tabela, descrições).
- **hazon-dim** (#6f8a93): labels uppercase, captions, texto de apoio.
- **Branco translúcido** (`rgba(255,255,255,0.05/0.10/0.15)`): superfícies, bordas e hover. É a matéria-prima do "vidro".

### Semantic & Categorical
- **hazon-success** (#7fe3c4) / **hazon-success-bright** (#4ade80): fechado, score "quente", variação positiva.
- **hazon-warn** (#fbbf24): negócios estagnados, score "morno", avisos.
- **hazon-danger** (#fca5a5) / **hazon-danger-solid** (#ef4444): perdido, botões de exclusão (contorno vs. sólido).
- **hazon-info** (#c084fc), **hazon-orange** (#fb923c), **hazon-blue** (#60a5fa), **hazon-slate** (#94a3b8), **hazon-pink** (#f472b6): corescategóricas de stages/segments (`core/dominio.py`), aplicadas sempre como tinte (`color: X; background: X1a`).

### Named Rules
**A Regra do Vidro.** Toda superfície de conteúdo é branco translúcido sobre o gradiente, com `backdrop-filter: blur(24px)` e borda `rgba(255,255,255,0.10)`. Nunca use um painel opaco sólido (exceto `hazon-surface` quando a legibilidade de um modal/drawer exigir).
**A Regra do Acento Único.** `hazon-accent` é o único sinal de interatividade/destaque. Não introduza um segundo acento; se precisa de variação, use opacity/tinte do próprio accent.
**A Regra do Tinte.** Cores categóricas (stage/segment/score) entram como `color: <hue>; background: <hue>1a` (10% alpha). Nunca como bloco saturado de fundo.

## Typography

**Display Font:** Fraunces (fallback: Georgia, serif)
**Body Font:** Manrope (fallback: Segoe UI, sans-serif)
**Mono Font:** `ui-monospace` system stack (para valores numéricos)

**Character:** Fraunces dá peso editorial e calidez aos títulos; Manrope é neutra e legível em densidade alta. O contraste serif×sans×mono cria três camadas claras: página (serif), interface (sans), dado (mono).

### Hierarchy
- **Display** (Fraunces, 600, 28px, line-height 1.1, letter-spacing -0.01em): títulos de página (`.hazon-titulo`) e logo "CRMCronos.Cloud".
- **Title** (Manrope, 600, 13.5px, 1.25): nomes em cards kanban, itens de nav, texto de botões, labels de seção.
- **Body** (Manrope, 400, 13px, 1.5): texto corrido, células de tabela, descrições, placeholders.
- **Label** (Manrope, 700, 10px, letter-spacing 0.12em, UPPERCASE): rótulos micro (`.hazon-label`), headers de tabela (`.hazon-th`), captions de KPI, chips.
- **Mono** (system mono, 700, 34px, 1): números de KPI. Reduz para 12.5–17px em somas, scores, contadores e badges.

### Named Rules
**A Regra do Título Serif.** Fraunces aparece somente em títulos de página, logo e avatares. Qualquer texto de interface, dado ou rótulo é Manrope ou mono.
**A Regra do Número Mono.** Todo valor numérico de negócio (dinheiro, contagem, soma de coluna, score, percentual) é `font-mono` bold. Número em Manrope é erro.

## Layout

- **Container:** `max-w-[1640px]` centralizado, `px-4 sm:px-8`.
- **Header:** sticky `top-0`, altura `h-16` (64px), `bg-hazon-abyss/70 backdrop-blur-xl`, borda inferior `white/15`. Nav central com itens `rounded-[11px] px-4 py-2.5`; item ativo = `bg-accent/15 text-accent`.
- **Main:** `py-8` abaixo do header.
- **Fundo global:** `#bg-fundo` fixo (`-z-10`) com dois radial-gradients teal/mid + linear-gradient `deep → mid → night`.
- **Grade de KPIs:** `grid gap-4 sm:grid-cols-2 xl:grid-cols-4`.
- **Kanban:** `flex overflow-x-auto`, colunas fixas `w-[290px] shrink-0`, máx. 30 cards visíveis por coluna (excesso vira aviso "+N não exibidos").
- **Ritmo:** Tailwind default; blocos de seção separados por `mb-6`/`mb-7`; internamente `gap-2.5`–`gap-4`.
- **Responsivo:** mobile-first; nav e detalhes do usuário colapsam em telas pequenas (`hidden md:flex`).

## Elevation & Depth

Profundidade por **camadas tonais translúcidas + blur**, não por sombras. O gradiente de fundo mostra-se através dos cartões, criando a sensabilidade de vidro fosco.

### Shadow Vocabulary
- **Glow Accent** (`0 0 8px rgba(116,179,198,0.44)`): foco/destaque de elementos accent (definido em `--hazon-glow-accent`).
- **Logo/Avatar** (`shadow-lg shadow-[#74b3c6]/30`): os únicos elementos com sombra estrutural — reforçam a marca.
- **Soft** (`0 8px 30px -12px rgba(0,0,0,0.40)`): cartões elevados / drawers quando necessários.
- **Inset ring** (`inset 0 0 0 2px rgba(116,179,198,0.45)` + bg accent 8%): coluna kanban sob `dragover` (`.kanban-col.is-over`).

### Named Rules
**A Regra das Camadas, não Sombras.** Superfícies são planas em repouso. Sombras aparecem só em marca (logo/avatar) ou como resposta de estado (hover com lift, drop-target com anel inset). Nunca sombreie um cartão parado "para destacar".

## Shapes

- **Raios:** `sm` 12px (botões, inputs, search, badges quadrados), `md` 16px (cartões), `lg` 24px (cartões grandes / banners), `full` 9999px (chips, avatares, badges de nav).
- **Contêineres de ícone:** `rounded-[11px]` com borda accent 35% + bg accent 10% — assinatura recorrente em KPIs e nav.
- **Bordas:** sempre `1px solid rgba(255,255,255,0.10–0.15)` em superfícies; `1px` accent (~0.35–0.55) em foco/ativo.
- **Linguagem formal:** cantos arredondados suaves em tudo; nada de cantos vivos. Cards de alerta (estagnados) usam `rounded-2xl`.

## Components

Para cada componente: sentença de caráter, depois shape, cor, estados, comportamento.

### Buttons (`.hazon-btn`)
Táteis e confiantes: `rounded-sm` (12px), `padding 0.5rem 1rem`, `font-size 13px / weight 600`, `transition all 0.15s`.
- **Primary** (`.hazon-btn-primary`): gradiente `linear-gradient(to bottom right, primary, primary-dark)` + borda accent 50%, texto branco. Hover = `filter: brightness(1.1)`.
- **Ghost** (`.hazon-btn-ghost`): bg `white/5` + borda `white/15` + texto muted. Hover = bg `white/10` + texto branco.
- **Danger** (`.hazon-btn-danger`): bg `danger/10` + borda `danger/30` + texto `#fca5a5`. Hover = bg `danger/20` + branco.
- **Danger Solid** (`.hazon-btn-danger-solid`): bg `#ef4444/90` + borda `danger/40` + branco. Hover = `brightness(1.1)`.

### Cards (`.hazon-card`, `-sm`, `-lg`)
Vidro jateado: bg `white/5` + borda `white/10` + `backdrop-blur(24px)`, raio md (16px) ou lg (24px).
- **KPI card** (`.hazon-card-sm p-6`): ícone em caixa `rounded-[11px]` (borda accent 35% + bg accent 10%), label uppercase dim, número mono 34px bold, badge de variação em pill (success ou accent). Hover = `-translate-y-1` + `border-accent/40`.
- **Kanban card**: `.hazon-card-sm p-3.5`, nome (title white) → empresa (body dim) → linha de chips (segmento + score) → rodapé (nível uppercase + valor mono accent). Hover = `border-accent/40 + bg-white/10`. States: `.dragging` (opacity 0.35), `.card-entrou` (animação scale/opacity 0.35s).

### Inputs / Fields (`form.hazon-form`)
Contidos: `width 100%`, `height 34px`, `padding 6px 10px`, raio 8px, bg `white/6`, borda `white/12`, `font-size 12.5px`. Focus = borda `accent/40` + bg `white/10`. Options herdam `hazon-night`. Textarea = `resize: vertical`.

### Search (`.hazon-search`)
Caixa com ícone à esquerda (`absolute left-3.5`), `padding-left 2.5rem`, raio sm (12px), bg `white/5`. Focus = borda `accent/40` + bg `white/10`.

### Chips (`.hazon-chip`)
Pill full: `padding 0.125rem 0.625rem`, `font-size 10px / weight 700`, `white-space: nowrap`. Cor sempre tinte: `color: <hue>; background: <hue>1a`. Variante marcada em forms (`.tag-check:checked + .tag-chip`) = accent 55% borda + accent 22% bg.

### Kanban Column (`.kanban-col`) — assinatura
`w-[290px] shrink-0`, `.hazon-card` (translúcida). Cabeçalho: dot colorido `h-2.5 w-2.5` com `box-shadow: 0 0 8px <color>70` (glow da etapa), nome stage (title muted), contador pill mono. Corpo: `gap-2.5 p-3`. Rodapé: "Soma:" + valor mono bold. State `.is-over` = anel inset accent + bg accent 8%.

### Tables (`.hazon-th` / `.hazon-td`)
Header uppercase dim (`10px / 700 / tracking 0.12em`), célula body muted (`12.5px`), ambos `padding 0.875rem 1.25rem`. Sem zebrado; separação por espaço e opacidade.

### Navigation (header)
Logo: `rounded-[11px]` gradiente `#2aa1a8 → #075b60` + SVG de alvos concêntricos; wordmark "CRMCronos.Cloud" (Fraunces) com "CRM" em accent. Itens: `rounded-[11px] px-4 py-2.5`, ativo `bg-accent/15 text-accent`, inativo `text-muted hover:bg-white/10 hover:text-white`. Badge de tarefas: pill `bg-red-400/90` mono 10px. Avatar: `rounded-full` gradiente com iniciais (Fraunces).

### Page Title (`.hazon-titulo`)
Fraunces 28px/600, `letter-spacing -0.01em`, `color text`. Sub (`p.hazon-sub` ou classe): `14px dim`.

## Do's and Don'ts

### Do:
- **Do** construir superfícies com branco translúcido + `backdrop-blur(24px)` sobre o gradiente (a Regra do Vidro).
- **Do** usar `hazon-accent` (#74b3c6) como único sinal de interatividade, etapa ativa e valor em destaque.
- **Do** render números de negócio (R$, contagens, scores, somas, %) em `font-mono` bold.
- **Do** aplicar cores categóricas como tinte (`color: X; background: X1a`), nunca como bloco sólido.
- **Do** dar feedback tátil: hover com `brightness(1.1)` no primário, `-translate-y-1` em KPI cards, anel inset na coluna kanban alvo.
- **Do** prefixar novas classes de sistema com `hazon-` e registrá-las em `theme/static_src/src/styles.css`.
- **Do** manter o tema claro via `body[data-tema="claro"]` usando os mesmos tokens invertidos.

### Don't:
- **Don't** introduza um segundo acento — variações vêm de opacity/tinte do próprio `hazon-accent`.
- **Don't** use Fraunces fora de títulos de página, logo e avatares.
- **Don't** sombreie cartões em repouso "para destacar"; profundidade vem de camadas tonais.
- **Don't** invente hex novos — a paleta `hazon-*` é fechada; estenda `core/dominio.py` para cores categóricas.
- **Don't** use blocos de cor saturada de fundo para stages/segments/scores — sempre tinte 10%.
- **Don't** troque Manrope por outra sans sem trocar em `tailwind.config.js`, `styles.css` e no `<link>` do `base/basic.html` juntos.
