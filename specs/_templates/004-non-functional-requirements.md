# 004 — Non-Functional Requirements

**Status:** Rascunho
**Versão:** 0.1.0
**Data:** AAAA-MM-DD
**Responsável:** SRE
**Constitution:** v1.0.0

> Preencha e mova para `specs/004-non-functional-requirements.md`. RNFs viram SLOs, alarmes e gates — não ficção. Cada um deve ser **mensurável**.

## 1. Requisitos não-funcionais

| ID | Categoria | Requisito | Como verificar |
|---|---|---|---|
| RNF-P-01 | Performance | <p99 de `POST /v1/x` ≤ 300 ms> | métrica RED em dashboard |
| RNF-A-01 | Disponibilidade | <SLO 99,9% mensal> | error budget |
| RNF-S-01 | Segurança | <…> | |
| RNF-E-01 | Escalabilidade | <…> | |

## 2. SLOs / SLIs

| SLO | SLI (como medido) | Meta | Janela | Alarme |
|---|---|---|---|---|
| | | | | |

## 3. Observabilidade (P-05)

- **Logs:** <formato estruturado, campos obrigatórios, mascaramento de PII>
- **Métricas:** RED por endpoint + métricas de negócio
- **Traces:** <propagação, amostragem>
- **Auditoria:** <eventos imutáveis, retenção>

## 4. Capacidade e custo

<Volumetria esperada, picos, perfil de custo (lean vs HA — ver `docs/lessons/sre.md`).>

## 5. Confiabilidade

<Estratégia de retry/backoff, idempotência (P-03), durabilidade (outbox), DLQ, RTO/RPO.>
