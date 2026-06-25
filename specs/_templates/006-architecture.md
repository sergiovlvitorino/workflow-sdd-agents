# 006 — Architecture

**Status:** Rascunho
**Versão:** 0.1.0
**Data:** AAAA-MM-DD
**Responsável:** TL
**Constitution:** v1.0.0

> Preencha e mova para `specs/006-architecture.md`. Descreve *como* o sistema realiza as specs. Decisões não óbvias viram ADR (`adr/`). Origem recomendada: um `design-flow`.

## 1. Estilo e princípios

<Hexagonal/Clean/em camadas? O domínio é puro (sem framework/I/O)? Portas e adapters (P-12)?>

## 2. Stack

| Camada | Tecnologia | Por quê (ADR) |
|---|---|---|
| Linguagem/runtime | | ADR-NNNN |
| Persistência | | |
| Mensageria/fila | | |
| Infra/deploy | | |

## 3. Componentes e fronteiras

```
[cliente] ──▶ [API] ──▶ [casos de uso] ──▶ [domínio]
                          │
                          └──▶ [portas] ──▶ [adapters externos]
```

<Diagrama de componentes; responsabilidade e limite de cada um.>

## 4. Decisões transversais

- **Isolamento de dados (P-04):** <RLS multi-tenant / autorização — ver `docs/lessons/security.md`>
- **Idempotência (P-03):** <onde a chave é persistida; janela; colisão>
- **Durabilidade:** <outbox transacional, retry, DLQ — ver `docs/lessons/python.md`>
- **Observabilidade (P-05):** <wiring de logs/métricas/traces>

## 5. ADRs relacionados

| ADR | Decisão | Status |
|---|---|---|
| | | |

## 6. Estrutura de pastas (repo layout)

```
src/<app>/domain/        # domínio puro
src/<app>/application/    # casos de uso
src/<app>/infrastructure/# adapters, db, mensageria
src/<app>/interfaces/     # http, eventos
tests/unit | integration | e2e
```
