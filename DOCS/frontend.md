# Frontend (Django Templates + Tailwind)

## Visão geral

O frontend é renderizado no servidor com **Django Templates (DTL)** e estilizado com
**Tailwind CSS** (django-tailwind, app `theme`). Não há framework JS de SPA: as telas
são HTML servido + pequenos scripts inline por página (kanban, dashboard, importador).

## Estrutura

```text
theme/
├── static_src/
│   ├── src/styles.css      Design system (tokens + componentes hazon-*)
│   └── tailwind.config.js  Paleta teal e caminhos de conteúdo
├── templates/base.html     Template base (layout com nav, tema escuro)
templates/base/basic.html   Template básico (páginas públicas)
static/                     Arquivos estáticos do projeto
```

O CSS compilado fica em `theme/static/css/dist/styles.css` (gerado por
`python manage.py tailwind build`).

## Base e navegação

- `theme/templates/base.html` — layout padrão das telas internas: header com nav
  (Dashboard, Funil, Contatos, Agenda, E-mails, Tarefas, Automações, Campanhas,
  Discador, Acordos, Relatórios), menu do usuário (Configurações, Equipe, Sair).
- `templates/base/basic.html` — layout simples para páginas públicas
  (login, onboarding, convite, captura).
- Context processor `acesso.context_processors.web_sessao` disponibiliza o usuário
  logado e o nicho em todos os templates.

## Telas existentes

| Rota | Template | App |
|---|---|---|
| `/login/`, `/onboarding/`, `/logout/` | `acesso/login.html`, `acesso/onboarding.html` | acesso |
| `/equipe/`, `/config/`, `/convidar/<token>/` | `acesso/equipe.html`, `acesso/config.html`, `acesso/convidar.html` | acesso |
| `/dashboard/` | `dashboard/index.html` + `partials/_*.html` (KPIs, funil, timeline, conversão, metas, melhores, recentes, atividade, tarefas) | dashboard |
| `/funil/` | `funil/kanban.html` (drag & drop) | funil |
| `/contatos/`, `/contatos/<id>/`, `novo/`, `editar/`, `excluir/`, `importar/`, `carteiras/`, `campos/` | `contatos/*.html` | contatos |
| `/agenda/` | `agendamentos/agenda.html` | agendamentos |
| `/emails/`, `/emails/campanha/` | `emails/lista.html`, `emails/campanha.html`, `emails/form_modelo.html` | emails |
| `/tarefas/` | `tarefas/lista.html` + `partials/_linha.html`, `_secao.html` | tarefas |
| `/automacoes/` | `automacoes/lista.html`, `automacoes/formulario.html` | automacoes |
| `/campanhas/` | `campanhas/lista.html`, `campanhas/detalhe.html`, `campanhas/form.html` | campanhas |
| `/discador/` | `discador/operador.html`, `discador/filas.html`, `discador/scripts.html` + forms | discador |
| `/acordos/` | `acordos/lista.html`, `acordos/detalhe.html`, `acordos/simular.html` | acordos |
| `/relatorios/` | `relatorios/index.html` | relatorios |
| `/captura/<token>/` | `contatos/captura.html` (página pública de captura) | contatos |

## Gráficos

Os gráficos são **SVG gerados em Python** (sem biblioteca JS), seguindo o mesmo visual
do dashboard:

- `dashboard/views.py` — `_funnel_svg` (funil por etapa), `_timeline_svg`
  (linha do tempo com áreas), barras de conversão.
- `relatorios/views.py` — `_linhas_svg` (série diária multi-série, área suave,
  pontos com tooltip e legenda) e barras de valor recuperado por operador.

## Interações JS (inline por página)

- **Kanban** (`funil/kanban.html`) — drag & drop de cards, move via POST.
- **Dashboard** — troca de períodos, tooltips dos gráficos.
- **Importador** — preview do CSV.
- **Config** — tabs, geração de link de convite, copiar para a área de transferência.
- **Discador** — controle do softphone (abrir chamada, registrar resultado).

## Boas práticas aplicadas

- Classes utilitárias Tailwind + componentes do design system (`hazon-card`,
  `hazon-btn`, `hazon-form`, `hazon-th`/`hazon-td`, `hazon-chip`, `hazon-search`).
- Textos em **português brasileiro** em todas as telas.
- Acessibilidade básica: `title` em ícones/ações, contraste alto no tema escuro.
