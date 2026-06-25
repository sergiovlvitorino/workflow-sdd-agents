# ADRs — Architecture Decision Records

> Registro de decisões arquiteturais e de design (P-14 ADR-lite). Cada ADR documenta o **contexto**, as **alternativas consideradas**, a **decisão** e suas **consequências**, preservando a rastreabilidade para auditoria futura. **Arquivar, não remover.**

## Índice

| ID | Título | Status | Data | Autor |
|---|---|---|---|---|
| [ADR-0001](ADR-0001-stack-python-backend-angular-frontend.md) | Stack do blog-exemplo: backend Python (FastAPI) + frontend Angular | Aceito | 2026-06-24 | design-flow (`tl-python`/`tl-frontend`/`tl-qa`) |
| [ADR-0002](ADR-0002-paginacao-keyset-vs-offset.md) | Paginação de `GET /v1/posts`: keyset/cursor vs offset | Aceito | 2026-06-24 | sprint-flow (`tl-python`/`tl-qa`) |
| [ADR-0003](ADR-0003-persistencia-sqlite-vs-in-memory.md) | Persistência local: SQLite vs in-memory | Aceito | 2026-06-25 | design-flow (`tl-python`/`tl-qa`) |
| [ADR-0004](ADR-0004-publicacao-sem-autenticacao.md) | Modelo de "publicar" sem autenticação | Aceito | 2026-06-25 | design-flow (`po`/`tl-python`/`tl-qa`) |
| [ADR-0005](ADR-0005-contrato-tipos-frontend-openapi.md) | Contrato de tipos Frontend↔Backend: codegen a partir do OpenAPI | Aceito | 2026-06-25 | design-flow (`tl-frontend`/`tl-qa`/`tl-python`) |
| [ADR-0006](ADR-0006-observabilidade-local-minima.md) | Observabilidade local mínima: logging estruturado + request_id | Aceito | 2026-06-25 | design-flow (`sre`/`tl-python`/`tl-qa`) |

## Convenções

- **Nomenclatura:** `ADR-NNNN-slug-curto.md` (numeração sequencial de 4 dígitos).
- **Status:** `Proposto` → `Aceito` → (`Substituído por ADR-XXXX` | `Rejeitado`). Um ADR nunca é apagado; quando superado, registra-se o ADR que o substitui.
- **Estrutura mínima:** Contexto · Alternativas · Critérios · Decisão · Consequências · Gatilhos de revisão · Aprovações.
- **Aprovação:** um ADR só passa a `Aceito` após a assinatura dos revisores requeridos listados em seu cabeçalho.
- **Origem:** ADRs nascem normalmente de um `design-flow` (painel de Tech Leads) ou de um trade-off não óbvio descoberto em implementação.

## Template

Use [`_TEMPLATE-adr.md`](_TEMPLATE-adr.md). Copie, renumere e preencha; depois adicione a linha correspondente ao índice acima.
