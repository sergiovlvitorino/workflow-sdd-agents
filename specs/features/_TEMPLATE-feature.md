# F0NN — <Nome da feature>

**ID:** F0NN
**Prioridade:** Must · _(MoSCoW)_
**Status:** rascunho · _(rascunho → em revisão → aprovado)_
**RFs cobertos:** RF-00N, RF-00N
**Constitution:** v1.0.0

---

## User Story

**Como** <persona/papel>
**Quero** <capacidade>
**Para que** <benefício/resultado de negócio>

## Descrição funcional

<O que a feature faz, do ponto de vista do produto. Endpoints/telas envolvidos. Modo síncrono/assíncrono se relevante.>

## Pré-condições

- <Estado/autorização exigidos antes de usar a feature.>

## Fluxo principal

1. <Passo a passo do caminho feliz.>
2. …

## Fluxos alternativos

- **A1. <condição>:** <comportamento esperado>
- **A2. <condição>:** <comportamento esperado>

## Regras de negócio

> Cada RN vira teste; invariantes negativas viram teste negativo (P-07).

- **RN-F0NN-01:** <…>
- **RN-F0NN-02:** <…>

## Critérios de aceitação (Gherkin)

```gherkin
Funcionalidade: <nome>

Cenário: CA-F0NN-01 <título do caso>
  Dado <contexto>
  Quando <ação>
  Então <resultado verificável>
  E <asserção adicional>

Cenário: CA-F0NN-02 <caso negativo / erro>
  Dado <contexto>
  Quando <ação inválida>
  Então a resposta é <código>
  E o corpo contém erro "<code>"
```

## Observabilidade

<Métricas RED específicas, eventos de auditoria emitidos, logs relevantes (P-05).>

## Fora de escopo

<O que esta feature deliberadamente não cobre.>
