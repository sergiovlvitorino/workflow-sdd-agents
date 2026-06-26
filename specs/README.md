# SDD — Specs do projeto

> **Spec-Driven Development.** A especificação é a fonte da verdade. Código segue spec. Mudança de comportamento exige mudança de spec **antes** de código.
>
> Este é o **scaffolding** de um projeto-base. Os documentos `001`–`007` vivem como **templates em branco** em [`_templates/`](_templates/); ao iniciar um projeto, copie-os para a raiz de `specs/` e preencha. A [`000-constitution.md`](000-constitution.md) já está pronta e vigente — ela vale para qualquer domínio.

---

## Como navegar

### 1. Comece aqui (em ordem)

| # | Documento | O que é | Quem mantém |
|---|---|---|---|
| 0 | [`000-constitution.md`](000-constitution.md) | Princípios invioláveis. Prevalece sobre tudo. | PO + TL + SRE + QA (consenso) |
| 1 | [`_templates/001-overview.md`](_templates/001-overview.md) | Visão de produto, ICP, MVP, métricas. | PO |
| 2 | [`_templates/002-domain-model.md`](_templates/002-domain-model.md) | Linguagem ubíqua, entidades, máquina de estados, invariantes. | PO + TL |
| 3 | [`_templates/003-functional-requirements.md`](_templates/003-functional-requirements.md) | RFs (RF-NNN), prioridade MoSCoW, rastreabilidade para features. | PO |
| 4 | [`_templates/004-non-functional-requirements.md`](_templates/004-non-functional-requirements.md) | RNFs, SLOs/SLIs, observabilidade, capacidade. | SRE |
| 5 | [`_templates/005-api-contract.md`](_templates/005-api-contract.md) | Contratos REST, eventos, idempotência, versionamento. | PO + TL |
| 6 | [`_templates/006-architecture.md`](_templates/006-architecture.md) | Estilo, stack, padrões, referências a ADRs. | TL |
| 7 | [`_templates/007-test-strategy.md`](_templates/007-test-strategy.md) | Pirâmide, riscos, contract tests, métricas e gates. | QA |

### 2. Features (cada uma com Gherkin testável)

- Template: [`features/_TEMPLATE-feature.md`](features/_TEMPLATE-feature.md) — User Story + Regras de Negócio + Critérios de Aceitação em Gherkin (CA-XXX).
- Convenção de arquivo: `features/F0NN-<slug>.md`.

### 3. Decisões arquiteturais (ADRs)

- Índice e convenções: [`adr/README.md`](adr/README.md).
- Template: [`adr/_TEMPLATE-adr.md`](adr/_TEMPLATE-adr.md).

### 4. Tarefas executáveis (DETAIL)

- Template: [`tasks/_TEMPLATE-DETAIL.md`](tasks/_TEMPLATE-DETAIL.md) — produzido pelos `tl-*` no `sprint-flow`, consumido pelo `review-loop`.
- Convenção: `tasks/sprint-NN/DETAIL-T-FNNN-NN.md`.

### 5. Governança

- Template de aceite de PO: [`governance/_TEMPLATE-aceite-po.md`](governance/_TEMPLATE-aceite-po.md).

---

## Fluxo SDD adotado

```
┌──────────────────┐
│ 0. Constitution  │  princípios invioláveis (versionados)
└────────┬─────────┘
         │
┌────────▼─────────┐
│ 1. Overview (PO) │  visão, ICP, MVP, métricas
└────────┬─────────┘
         │
┌────────▼─────────────────────────────┐
│ 2. Domain (PO+TL)                    │
│ 3. RFs (PO)                          │
│ 4. NFRs (SRE)                        │  ──┐
│ 5. API Contract (PO+TL)              │    │  paralelizáveis após 1
│ 6. Architecture (TL)                 │  ──┘
│ 7. Test Strategy (QA)                │
└────────┬─────────────────────────────┘
         │
┌────────▼─────────┐
│ Features F0NN    │  cada feature: User Story + RNs + Gherkin (CA-XXX)
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Tasks (DETAIL)   │  quebra executável a partir do Gherkin → review-loop
└──────────────────┘
```

Este fluxo é orquestrado pelas skills em [`../.claude/skills/`](../.claude/skills/): `discovery-flow` (demanda → backlog) → `sprint-flow` (planejar → detalhar → executar → retrospectiva) → `review-loop` (implementar → revisar → corrigir). Decisões de arquitetura saem de `design-flow` (ADR).

## Convenções de IDs

| Tipo | Formato | Exemplo |
|---|---|---|
| Princípio | `P-NN` | P-04 |
| Requisito funcional | `RF-NNN` | RF-001 |
| Requisito não-funcional | `RNF-X-NN` | RNF-A-01 |
| Regra de negócio (global) | `RN-D-NN` | RN-D-01 |
| Regra de negócio (feature) | `RN-FXXX-NN` | RN-F001-03 |
| Critério de aceitação | `CA-FXXX-NN` | CA-F001-02 |
| Decisão arquitetural | `ADR-NNNN` | ADR-0001 (em `specs/adr/`) |
| Tarefa | `T-FNNN-NN` | T-F001-03 (em `specs/tasks/`) |

## Versionamento das specs

- **Major:** quebra de contrato de API ou mudança de princípio constitucional.
- **Minor:** novo RF, nova feature.
- **Patch:** clarificação sem mudar comportamento.

Cada arquivo carrega `Versão: X.Y.Z` no cabeçalho.

## Definição de pronto (DoD) por spec

Uma spec é considerada pronta quando:

1. Versão ≥ 1.0.0.
2. Sem ambiguidades não documentadas.
3. Toda referência cruzada resolve.
4. Todo CA é executável.
5. Aprovação cruzada (PO + papel responsável + ao menos um par).
