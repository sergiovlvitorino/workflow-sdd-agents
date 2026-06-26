# 004 — Non-Functional Requirements

**Status:** Rascunho mínimo _(escopo Sprint 1)_
**Versão:** 0.2.0
**Data:** 2026-06-24
**Responsável:** SRE (rascunho por `tl-python` no sprint-flow)
**Constitution:** v1.0.0

> **Rascunho mínimo de propósito** (princípio enxuto/didático): o blog é exemplo de ensino, **não serve tráfego** (ADR-0001) — performance/escala têm peso baixo e são registradas como dívida honesta. Esta versão fixa só os RNFs verificáveis úteis a Sprint 1. SLOs/dashboards completos entram com F005 (observabilidade, Sprint 2), de responsabilidade do SRE.

## 1. Requisitos não-funcionais

| ID | Categoria | Requisito | Como verificar |
|---|---|---|---|
| RNF-S-01 | Segurança | Nenhum segredo no repo/filesystem; `content`/`title` são input externo e devem ser escapados ao renderizar (front), não no armazenamento. | secret-scan no CI (P-10); review |
| RNF-Q-01 | Qualidade | Cobertura por-stack ratchet (não média global) — piso P-07; gate `pytest --cov` separado do front. | CI gate por-stack (ADR-0001) |
| RNF-R-01 | Confiabilidade | Criação idempotente: mesma `Idempotency-Key` não duplica (P-03). | teste de idempotência (CA-F001-02) |
| RNF-C-01 | Compatibilidade | Contrato `/v1` extensível; mudança aditiva = minor; quebra = major + ADR (P-08). | review de contrato vs `005` |

## 2. SLOs / SLIs

> **N/A no MVP** — exemplo didático sem tráfego real (ADR-0001, critério "performance = baixo"). SLOs/SLIs definidos pelo SRE quando F005 entrar. Registrado para evitar ficção de SLO.

## 3. Observabilidade (P-05)

> Entregável de F005 (Sprint 2). A arquitetura já reserva o ponto de wiring (middleware ASGI único para RED + `request_id` — `006` §4). Sprint 1 não instrumenta RED. Quando entrar: log estruturado com `request_id`, sem segredo/PII (P-09).

## 4. Capacidade e custo

> Irrelevante (didático). Roda local/in-memory. Sem perfil de capacidade — dívida honesta registrada em ADR-0001.

## 5. Confiabilidade

- **Idempotência (P-03):** chave + resposta persistida (ADR-0001); ver `006` §4 e DETAIL-T-F001-01.
- **Durabilidade/outbox/DLQ:** N/A no MVP (sem side-effect externo — sem outbox, ADR-0001).
- **Falha explícita (P-11):** toda borda ambígua (sem chave, payload inválido, cursor corrompido) retorna erro tipado Problem Details, nunca fallback silencioso (`005` §4).
