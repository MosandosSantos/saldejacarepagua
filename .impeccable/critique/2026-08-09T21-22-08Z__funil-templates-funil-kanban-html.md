---
target: kanban do funil (funil/templates/funil/kanban.html)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-08-09T21-22-08Z
slug: funil-templates-funil-kanban-html
---
Method: dual-agent (A: design-review · B: detector CLI; browser indisponível — fallback signal)

# Critique — Kanban do Funil (funil/templates/funil/kanban.html)

## Design Health Score

| # | Heurística | Nota | Achado-chave |
|---|-----------|------|--------------|
| 1 | Visibilidade de status | 3 | Drop otimista atualiza contadores/somas/total + animação `card-entrou`; sem toast de sucesso; select faz reload completo |
| 2 | Match mundo real | 4 | pt-BR fluente, "pacientes", "Soma", "parado há N dias" — linguagem de clínica |
| 3 | Controle e liberdade | 2 | Sem undo após mover; select com `onchange submit` instantâneo sem cancelar; reload perde scroll do board |
| 4 | Consistência e padrões | 3 | HAZON aplicado com rigor; emoji ⏳ vs. ícones SVG; `title="Lead scoring"` em inglês numa UI pt-BR |
| 5 | Prevenção de erro | 2 | Mover para "fechado"/"perdido" é instantâneo e silencioso; sem confirmação em ação de alta aposta |
| 6 | Reconhecimento vs. lembrança | 3 | Cores de etapa + chips auxiliam; select de mover oculto no hover exige lembrar onde está |
| 7 | Flexibilidade e eficiência | 2 | Dois caminhos (drag + select), nenhum rápido: sem atalhos, sem batch, select exige 3+ passos |
| 8 | Estética e minimalismo | 3 | Vidro lindo e contido; card carrega ~6 itens e três números mono com papéis diferentes |
| 9 | Recuperação de erros | 1 | Drop com falha = `location.reload()` — perde posição do board, sem mensagem do que falhou |
| 10 | Ajuda e documentação | 1 | Única instrução é "Arraste os cards..."; sem ajuda para estagnados, sem empty state rico, sem onboarding |
| **Total** | | **24/40** | **Acceptable** — melhorias significativas antes de o usuário ficar feliz |

## Design Specificity Verdict

**Parcialmente autoral.** O mundo visual é inconfundivelmente HAZON: vidro jateado teal, acento único, Fraunces só no título, dinheiro em mono. Mas a camada de interação é padrão de categoria: colunas Trello, chips, contadores, soma. O que ancora o produto é o domínio: relabeling por nicho ("Funil de pacientes"), o alerta de estagnados (aging de negócio) e as somas ponderadas. Oportunidade perdida: o alerta de estagnados mostra o número mas não o custo ("R$ X parados em risco"); o funil não comunica velocidade (tempo médio por etapa).

**Deterministic scan (detect.mjs)**: 12 achados — 9 advisories de font-size fora da rampa do DESIGN.md (11px, 11.5px, 17px, 22px, 8.5px — 8 no kanban, 4 no basic.html), 2 warnings "overused-font" para Fraunces (FALSO POSITIVO: Fraunces é a display font oficial do DESIGN.md), 1 advisory de cor #33545e fora da paleta (cor de inversão do tema claro, intencional mas não documentada). O detector confirma a maior queixa do review: deriva sistemática de tamanhos de fonte fora da rampa tipográfica.

**Browser**: indisponível nesta sessão — agente de navegação falhou na inicialização (navigation tools e parâmetros de formulário indisponíveis). Fallback: revisão de código-fonte + detector CLI. Nenhum overlay user-visible foi injetado.

## Overall Impression

Sistema visual excelente e fiel ao HAZON. O problema não é beleza — é que a ação primária (mover) não funciona para teclado/touch e não tem arrependimento, a acessibilidade tem falhas WCAG objetivas (`outline-none`, contraste do dim), e o card carrega informação demais para 290px. A maior oportunidade: transformar o mover de card em uma interação acessível, com undo e feedback claro.

## What's Working

1. **Execução fiel do HAZON**: translucidez + blur + acento único + números mono — o pipeline é legível de relance; soma por coluna + total = status financeiro instantâneo. Craft de Operate real.
2. **Glow do dot de etapa** (`0 0 8px cor70`) + chips em tinte: o pipeline é reconhecível por cor sem ler — reconhecimento puro.
3. **Comportamento responsável de dados**: drag otimista reconciliado pelo servidor (contadores/somas voltam da API), teto de 30 cards com "+N não exibidos" — decisão de produto madura.

## Priority Issues

**P1 — Mover card: drag-only como primário + select oculto no hover = inacessível para teclado, touch e primeira vez.**
- O único caminho alternativo ao drag (`hidden group-hover:block`) é `display:none` até o hover — fora do tab order, invisível para leitor de tela e impossível no touch. HTML5 drag não funciona em touch: usuário de tablet (recepção!) não move card.
- Correção: menu de mover sempre visível (kebab → "Mover para..."), teclado (setas trocam de coluna com card focado, Enter escolhe etapa), drag vira acelerador. → `$impeccable adapt` + `$impeccable harden`.

**P1 — Sem undo/confirmação numa ação de alta aposta.**
- Mover para "fechado"/"perdido" é instantâneo e irreversível; select auto-submete no primeiro clique (um erro = reload + mudança).
- Correção: toast de undo (5–10s) após o drop; confirmação só para "perdido". → `$impeccable harden`.

**P1 — Acessibilidade: `outline-none` nos selects, contraste do dim, controles sem label.**
- Os dois selects (dias e etapa) têm `outline-none` → sem foco visível (WCAG 2.4.7); `text-[#6f8a93]` (dim ~3:1) em 11–11.5px falha AA; select sem `<label>`/aria-label; nível do score em 10px.
- Correção: focus ring accent, aria-labels, subir contraste do dim, piso de 12px para corpo. → `$impeccable audit`.

**P2 — Densidade do card (~6 itens em 290px).**
- Nome, empresa, chip segmento, chip score, label nível uppercase, valor + select oculto.
- Correção: fundir nível no chip de score ("quente · 78"), truncar empresa, teto de 4 itens. → `$impeccable distill`.

**P2 — Empty state "Vazio": 6 colunas ocas para tenant novo.**
- Correção: CTA de onboarding ("Adicionar primeiro contato"). → `$impeccable onboard`.

**P3 — ⏳ emoji quebra linguagem de ícones SVG; `title="Lead scoring"` em inglês; copy "Mostrar parados há +" ambíguo; sem affordance de drag (grip); 9 font-sizes fora da rampa do DESIGN.md.** → `$impeccable clarify` + `$impeccable polish`.

## Persona Red Flags

**Alex (power user)**: sem atalhos de teclado para mover (nem setas, nem hotkey); select oculto exige hover → clicar → escolher → auto-submit (4 passos de mouse); sem batch; clique errado no select recarrega a página e perde a posição do scroll do board — a recepção no meio da triagem perde o lugar.

**Sam (acessibilidade)**: drag é só mouse; select alternativo é `display:none` até hover → inalcançável por teclado/leitor de tela; `outline-none` nos dois selects = foco invisível; `text-[#6f8a93]` 11px falha contraste AA; select de etapa sem label associado (só `name="stage"`); cards `draggable` sem alternativa de teclado.

## Minor Observations

- Search mantém `q` ativo no recálculo pós-drop (bom), mas sem indicador de "filtro ativo" nem limpar visível.
- Soma da coluna no rodapé × total no toolbar: os dois números mais importantes da tela ficam em cantos opostos.
- Select "dias" auto-submete e recarrega (perde scroll) — mesmo problema do select de etapa.

## Questions to Consider

- "E se o card mostrasse só o que muda com a etapa (valor + tempo nela), em vez de tudo que o contato sabe?"
- "Quando a recepção erra e move para 'Perdido', existe algum arrependimento possível hoje?"
- "A soma da coluna e o total são o número mais importante da tela — por que não estão numa barra de receita contínua no topo?"
