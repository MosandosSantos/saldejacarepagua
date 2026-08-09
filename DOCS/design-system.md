# Design system

O design system vive em `theme/static_src/src/styles.css` (camada `@layer
components`) com **tokens CSS** e **componentes `hazon-*`**, usado em todas as telas
internas sobre o tema escuro do Tailwind.

## Tokens

Tema escuro "hazon" (teal profundo):

```css
--hazon-night:       #0b2029;   /* fundo mais escuro */
--hazon-abyss:       #072026;   /* fundo profundo */
--hazon-deep:        #0e3a44;   /* primária escura / profundidade */
--hazon-surface:     #0d2a33;   /* superfícies de card */
--hazon-mid:         #112530;   /* superfícies intermediárias */
--hazon-primary:     #0b6f74;   /* ação principal */
--hazon-primary-dark:#075b60;   /* hover/gradiente da primária */
--hazon-accent:      #74b3c6;   /* destaque / foco */
--hazon-text:        #f4fafb;   /* texto principal */
--hazon-muted:       #bcd3da;   /* texto secundário */
--hazon-dim:         #6f8a93;   /* texto terciário / rótulos */
--hazon-success:     #7fe3c4;   /* sucesso */
--hazon-success-bright: #4ade80;
--hazon-warn:        #fbbf24;   /* aviso */
--hazon-danger:      #fca5a5;   /* perigo */
--hazon-info:        #c084fc;   /* informação */
--hazon-orange:      #fb923c;
--hazon-blue:        #60a5fa;
--hazon-slate:       #94a3b8;
--hazon-pink:        #f472b6;
--hazon-white-05 / -10 / -15:   /* fundos translúcidos de card */
--hazon-font-sans:    'Manrope', 'Segoe UI', sans-serif;
--hazon-font-display: 'Fraunces', Georgia, serif;  /* títulos */
--hazon-radius-sm: 0.75rem; --hazon-radius-md: 1rem; --hazon-radius-lg: 1.5rem;
--hazon-glow-accent: 0 0 8px rgba(116, 179, 198, 0.44);
```

## Componentes

| Componente | Uso |
|---|---|
| `.hazon-card`, `.hazon-card-sm`, `.hazon-card-lg` | Cartões (borda translúcida, fundo `white-05`, blur em card/lg) |
| `.hazon-titulo` | Título de página (Fraunces, 28px) |
| `.hazon-sub` | Subtítulo (14px, cor `dim`) |
| `.hazon-label` | Rótulo micro em caixa alta (10px, letter-spacing) |
| `.hazon-btn` | Botão base (inline-flex, radius-sm, 13px semibold) |
| `.hazon-btn-primary` | Ação principal (gradiente `primary → primary-dark`, texto branco) |
| `.hazon-btn-ghost` | Ação secundária (fundo translúcido, texto muted) |
| `.hazon-btn-danger` | Ação de perigo translúcida (borda/vermelho suave, hover mais forte) |
| `.hazon-btn-danger-solid` | Ação de perigo sólida (fundo vermelho, texto branco) |
| `form.hazon-form input/select/textarea` | Campos de formulário padronizados (fundo `white-06`, foco accent) |
| `.hazon-search` | Campo de busca com espaço para ícone (18rem) |
| `.hazon-chip` | Etiqueta pequena arredondada (10px bold) |
| `.hazon-th`, `.hazon-td` | Células de tabela padronizadas (th: uppercase 10px; td: 12.5px) |
| `.tag-check` + `.tag-chip` | Chips de tags selecionáveis em formulários |

## Regras de uso

- **Botões primários**: sempre `hazon-btn hazon-btn-primary` (nunca gradientes
  manuais — migração S8).
- **Ações destrutivas** (excluir, cancelar convite, encerrar sessão):
  `hazon-btn hazon-btn-danger` (ou `-solid` quando a ação é a principal da tela).
- **Formulários**: a classe `hazon-form` no `<form>` já estiliza inputs/selects/
  textareas — não repetir CSS inline.
- **Tabelas**: `hazon-th` no cabeçalho e `hazon-td` nas células.
- **Títulos de página**: `hazon-titulo` + `hazon-sub`.
- Sempre em **português brasileiro**.

## Tailwind

- `theme/static_src/tailwind.config.js` define a paleta teal e os caminhos de
  conteúdo (templates). O bundle final é `theme/static/css/dist/styles.css`.
- Rebuild: `python manage.py tailwind build` (ou `tailwind start` em dev).
- Classes utilitárias Tailwind são usadas para espaçamento/tamanhos em cima dos
  componentes `hazon-*`.
