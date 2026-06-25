# DETAIL — T-FNNN-NN — <Título da tarefa>

**Sprint:** NN
**Tamanho:** S | M | L _(estimativa)_
**Papel:** <BE | FE | QA | SRE> (+ TL revisão)
**Depende de:** <T-…>
**Bloqueia:** <T-…>

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

<O que esta tarefa entrega e por quê. Em uma frase, o valor.>

## 2. CAs / RNs cobertos

- **CA-FNNN-NN:** <…>
- **RN-FNNN-NN:** <…>

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/...` | criar | <…> |
| `tests/...` | criar | <cobertura alvo> |

## 4. Design da solução

<Assinaturas/esqueleto, contratos, decisões e trade-offs. Diagramas se ajudar. Decisão não óbvia → ADR.>

```text
<pseudocódigo / assinaturas / esquema>
```

## 5. Impacto em testes e quality gates

- Testes novos: <unit/integration/e2e>
- Cobertura esperada: <…>
- Gates afetados: <ratchet, mutation, contract>

## 6. Riscos

<Armadilhas conhecidas, pontos de contaminação de ambiente, dependências externas.>

## 7. Definition of Done (verificável)

- [ ] CAs automatizados e verdes (execução real).
- [ ] Cobertura ≥ piso da categoria (P-07).
- [ ] Métricas/logs instrumentados quando aplicável (P-05).
- [ ] Sem regressão na suíte existente.
- [ ] Revisão aprovada (tl-* + tl-qa) sem ressalvas.
