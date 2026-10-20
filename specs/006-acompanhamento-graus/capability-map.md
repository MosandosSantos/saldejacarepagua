# Capability Map: Acompanhamento de Membros e Graus

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `degree-history` | Manter um registro por membro/grau (4º–33º), com a data de obtenção; remover as três datas antigas de iniciação/passagem/elevação do modelo `Membro`. | Modelos locais existentes (`Grau`, `GrauMembro`, `Membro`) |
| `attendance-indicator` | Reutilizar o cálculo oficial da presença e definir a apresentação do limite de 50%. | `tarefas.PresencaServico` |
| `accompaniment-table` | Página tenant-scoped com membro, Vale, Lojas, 30 datas de graus, filtros e ordenação. | `degree-history`, `attendance-indicator` |
| `navigation` | Trocar o item de navegação “Financeiro” por “Acompanhamento”, mantendo o módulo financeiro e suas rotas. | `accompaniment-table` |
| `static-assets` | Compilar o bundle Tailwind usado pela nova página dentro da imagem Docker e coletá-lo no diretório servido pelo WhiteNoise. | `accompaniment-table` |
| `ci-verification` | Corrigir o YAML quebrado, construir a imagem e executar checks/testes/scans no CI existente. | Todos os módulos acima |

Ordem de entrega: `degree-history` → `attendance-indicator` e `accompaniment-table` → `navigation` → `static-assets` → `ci-verification`.

O acompanhamento e a troca de navegação formam uma única entrega de produto, mas os limites acima permitem testar e revisar cada capacidade separadamente.
