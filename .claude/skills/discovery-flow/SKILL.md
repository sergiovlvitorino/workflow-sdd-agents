---
name: discovery-flow
description: Transforma uma demanda crua (ideia, pedido vago, problema de negócio) em backlog refinado e pronto para planejar. Os agentes de produto (product-owner / po) fazem discovery, decompõem em épicos e user stories com critérios de aceite, priorizam por valor vs. esforço e definem o MVP. É o passo upstream do sprint-flow — não executa código. Use quando o usuário trouxer uma ideia ainda não refinada, pedir para "fazer discovery", "escrever as user stories", "montar o backlog", ou disser /discovery-flow <demanda>.
---

# discovery-flow

Estratégia **upstream do desenvolvimento**: pega uma demanda mal definida e a transforma em **backlog acionável** (épicos → stories com CAs, priorizados, com MVP). Termina onde o `sprint-flow` começa.

## Quando usar

Quando a entrada ainda **não** é uma tarefa clara: "queria algo que faça X", um problema de negócio, um pedido de stakeholder, uma ideia de feature. Vem como argumento (`/discovery-flow <demanda>`) ou da conversa.

> **Se o backlog já existe e está refinado**, pule para o `sprint-flow`. O discovery-flow é para quando ainda falta clareza sobre *o quê* e *por quê*.

## Princípios

- **Problema antes de solução.** Discovery começa pelo problema/usuário/valor, não pela feature. Não deixe a conversa pular para "como implementar".
- **Story pronta = testável.** Uma user story só está pronta quando tem **critérios de aceite verificáveis** (idealmente Gherkin) — vago não entra no backlog.
- **Priorizar é cortar.** Valor vs. esforço e MoSCoW existem para definir um MVP enxuto, não para listar tudo como "Must".
- **Você é o orquestrador.** Discovery e escrita de stories → `product-owner`/`po`; testabilidade dos CAs → `tl-qa` quando útil.

## Mapeamento

| Passo | Agente |
|-------|--------|
| Discovery aprofundado (problema, personas, valor, métricas) | `product-owner` |
| Decompor em épicos/stories, priorizar, definir MVP | `po` |
| Afiar critérios de aceite testáveis (Gherkin) | `tl-qa` (opcional) |

> `product-owner` é o discovery sênior (visão, métricas, roadmap); `po` é o refinamento ágil enxuto (stories, MoSCoW, MVP). Em demandas pequenas, um `po` sozinho pode cobrir os dois papéis.

## Procedimento

### 0. Enquadrar a demanda
1. Capture a demanda crua e o **contexto de negócio**. Se faltar o essencial (quem é o usuário, qual o problema, o que é sucesso), faça 2–3 perguntas antes de acionar os agentes.
2. Crie um TODO: discovery → stories+CAs → priorização/MVP → handoff.

### 1. Discovery (agente `product-owner`)
Acione o `product-owner` para aprofundar: qual o **problema real** e a dor, **quem** sente (personas), o **valor** esperado, **métricas de sucesso**, restrições e riscos, e o que está **fora de escopo**. Saída: um resumo de discovery (problema, usuários, valor, métricas, premissas/riscos).

Em demandas pequenas/claras, esta etapa pode ser enxuta ou fundida com a próxima.

### 2. Decomposição e priorização (agente `po`)
Acione o `po` (passando o discovery) para:
- Decompor em **épicos** e **user stories** no formato "Como `<persona>`, quero `<ação>`, para `<valor>`".
- Para cada story, **critérios de aceite verificáveis** (preferir Gherkin: Dado/Quando/Então).
- Classificar em **MoSCoW** e estimar **valor vs. esforço**.
- Definir o **MVP** (o menor conjunto que entrega valor) e o que fica para depois.
- Saída obrigatória: tabela `Épico | Story | Prioridade MoSCoW | Valor | Esforço | No MVP?` + os CAs por story.

### 3. Afiar testabilidade (agente `tl-qa` — opcional)
Para stories críticas ou de regra de negócio sensível, acione o `tl-qa` para revisar se os **critérios de aceite são executáveis** (sem ambiguidade, com edge cases e cenários negativos). Ressalvas voltam ao `po` para ajuste.

### 4. Handoff
Grave o backlog refinado no local de specs/backlog do projeto (ex.: `docs/`, `specs/`, ou o tracker usado). Apresente ao usuário: o resumo de discovery, a tabela priorizada e o MVP definido. **Proponha encadear um `sprint-flow`** para planejar as sprints a partir deste backlog — o discovery-flow para no backlog pronto.

## Observações
- Não desça para detalhe técnico/implementação aqui — isso é papel dos `tl-*` dentro do `sprint-flow`.
- Resista a inflar o MVP: o `po` deve proteger o escopo mínimo. "Tudo é Must" é sinal de discovery incompleto.
- Critério de saída: cada story do MVP tem CAs verificáveis e prioridade — senão, não está pronta para planejar.
