# 007 — Test Strategy

**Status:** Rascunho
**Versão:** 0.1.0
**Data:** AAAA-MM-DD
**Responsável:** QA
**Constitution:** v1.0.0

> Preencha e mova para `specs/007-test-strategy.md`. Define a pirâmide, os gates e a matriz de risco. Os pisos da constitution (P-07) são mínimos; aqui o QA ajusta para cima. Ver `docs/lessons/qa.md`.

## 1. Pirâmide de testes

| Nível | Escopo | Ferramenta | Proporção alvo |
|---|---|---|---|
| Unit | domínio puro, branches | <pytest/JUnit/Vitest> | maioria |
| Integration | adapters, db, RLS, idempotência | <testcontainers/moto> | alguns |
| E2E | fluxos do usuário | <Playwright> | poucos |

## 2. Quality gates

| Gate | Regra | Onde roda |
|---|---|---|
| Cobertura (ratchet) | só sobe; piso por categoria (P-07) | CI |
| Mutation | <alvo> em módulos críticos | CI/nightly |
| Flaky | zero tolerância; flaky = P1 | CI |
| Lint/format | linter **pinado** do projeto | pre-commit + CI |
| Secret-scan | bloqueante | CI |

## 3. Matriz de risco

| Área | Risco | Impacto | Teste que prova |
|---|---|---|---|
| Isolamento multi-tenant | vazamento cross-tenant | máximo | "tenant A não vê dado de B" |
| Idempotência | efeito duplicado | alto | mesma key → mesma resposta; payload divergente → 409 |
| Máquina de estados | transição inválida | alto | transição barrada levanta erro tipado |

## 4. Contract tests

<Fixtures gravados por integração externa; como são versionados e atualizados.>

## 5. Anti-falso-verde (checklist)

- Rota nova tem teste HTTP **real** (não só unit do handler).
- Teste roda sob a role da aplicação, não superuser.
- Regressão **nasce vermelha** (red-green) antes do fix.
- Execução cobre o wiring de DI, não só a função isolada.
