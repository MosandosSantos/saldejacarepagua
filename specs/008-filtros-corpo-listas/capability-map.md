# Capability Map: Filtros de Corpo nas Listas

| Module id | Responsibility | Depends on |
|---|---|---|
| `loja-body-category` (existing) | Persist the five fixed Loja bodies and expose them through Loja CRUD. | — |
| `loja-body-list-filter` | Filter the Loja list by selected `Loja.corpo` values, preserving existing search and tenant scope. Selected bodies combine by OR; no selection means all bodies. | `loja-body-category` |
| `member-body-list-filter` | Filter the member list by the bodies of linked Lojas; a member matches when any linked Loja has a selected body. Combine body values by OR, preserve other filters with AND, and avoid duplicate members. | `loja-body-category` |

## Build order

`loja-body-category` is already implemented by `specs/007-corpo-loja/spec.md`. The two new list filters depend only on that stored field and can be specified and verified independently:

1. `loja-body-list-filter`
2. `member-body-list-filter`

Each list keeps its current tenant and permission scope. Body selection applies immediately, matching the existing Acompanhamento filter interaction.
