---
name: design-flow
description: Toma uma decisão de arquitetura antes de escrever código, via painel de Tech Leads. Aciona 2–3 tl-* em paralelo, cada um propondo uma abordagem independente; o orquestrador (ou um TL sênior) sintetiza num ADR versionado, enxertando o melhor de cada. Não produz código de produção — produz a decisão que alimenta um sprint-flow depois. Use quando o usuário pedir para "decidir a arquitetura", "comparar abordagens", "escrever um ADR/RFC", ou disser /design-flow <decisão>.
---

# design-flow

Estratégia de **decisão antes do código**: gera múltiplas abordagens independentes, compara com critérios explícitos e registra a escolha num ADR versionado. Reduz o risco de comprometer a implementação com a primeira ideia.

## Quando usar

Quando há uma decisão de design/arquitetura com mais de um caminho plausível e consequências duráveis: escolha de padrão, modelagem de dados, contrato de API, estratégia de concorrência, build-vs-buy, fronteira de módulos. Vem como argumento (`/design-flow <decisão>`) ou da conversa.

> **Não** use para decisões triviais ou de mão única (custo de errar baixo) — nesses casos, decida e siga. O design-flow vale quando reverter sairia caro.

## Princípios

- **Divergir antes de convergir.** Gere abordagens **independentes** (cada TL não vê a do outro) para evitar ancoragem numa única solução.
- **Critérios explícitos.** A escolha se justifica contra critérios declarados (ex.: simplicidade, performance, custo, risco, prazo, reversibilidade), não por preferência.
- **Decisão registrada, não só conversada.** O artefato final é um **ADR versionado** no repo — decisões que ficam só no chat se perdem.
- **Você é o orquestrador-sintetizador.** Acione os TLs para divergir; a síntese é sua (ou de um TL sênior), enxertando o melhor de cada proposta.

## Mapeamento

| Passo | Agente |
|-------|--------|
| Levantar contexto/restrições do código | `Explore` (read-only) |
| Propor abordagem (painel, em paralelo) | 2–3 `tl-*` por ângulo/stack (`tl-python`, `tl-frontend`, `tl-java`, `tl-go`, `fullstack-tech-lead`, `java-tech-lead`) |
| Síntese e ADR | orquestrador, ou um `tl` sênior / `fullstack-tech-lead` |

## Procedimento

### 0. Enquadrar a decisão
1. Formule a **questão de decisão** em uma frase, as **restrições** (técnicas, prazo, time) e os **critérios** de avaliação. Se ambíguo, faça 1–3 perguntas.
2. (Opcional) `Explore` levanta o contexto relevante do código atual e o que já está comprometido.
3. Crie um TODO: enquadrar → painel → síntese → ADR.

### 1. Painel de abordagens (2–3 `tl-*` em paralelo)
Acione **em paralelo** (um único bloco com múltiplas chamadas `Agent`) 2–3 tech leads, cada um instruído a propor **uma** abordagem distinta. Para diversidade real, atribua **ângulos diferentes**, por exemplo:
- **MVP-first:** o caminho mais simples que entrega valor já.
- **Risk-first:** o que minimiza risco/acoplamento/reversão custosa.
- **Performance/escala-first:** o que aguenta o crescimento esperado.

Cada TL deve retornar: a abordagem, como satisfaz os critérios, trade-offs honestos (o que ela piora), custo/esforço estimado e riscos. Instrua-os a **não** convergir — cada um defende sua proposta.

### 2. Síntese
Compare as propostas contra os critérios numa **matriz** (`Abordagem × Critério`). Escolha uma vencedora — ou uma **combinação**, enxertando o melhor de cada (ex.: estrutura da A com a estratégia de testes da B). Se a decisão for relevante e o usuário quiser, apresente a matriz antes de fechar o ADR.

### 3. ADR versionado
Grave a decisão em `docs/adr/ADR-NNNN-<slug>.md` (use o padrão de ADR do projeto se já existir; senão, o template abaixo). Numere sequencialmente.

```markdown
# ADR-NNNN: <título da decisão>

> Status: Aceito · Data: <AAAA-MM-DD>

## Contexto
<o problema, as restrições e os critérios de decisão>

## Opções consideradas
- **A — <nome>:** <resumo> · prós/contras
- **B — <nome>:** <resumo> · prós/contras
- **C — <nome>:** <resumo> · prós/contras

## Decisão
<a abordagem escolhida (ou combinação) e por que vence pelos critérios>

## Consequências
<o que isso habilita, o que custa, o que fica para revisitar; riscos aceitos>
```

### 4. Encerramento
Aponte o ADR gravado (caminho) e a decisão em uma linha. Quando a decisão implicar implementação, **proponha encadear um `sprint-flow`** (ou `review-loop`) usando o ADR como entrada — o design-flow para na decisão.

## Observações
- Não deixe o painel virar implementação: aqui não se escreve código de produção, só se decide.
- Se as propostas convergirem para a mesma coisa, a decisão é fácil — registre e siga; não force divergência artificial.
- Se faltar informação para decidir, o resultado pode ser um **spike** (PoC time-boxed) antes do ADR — sinalize isso ao usuário.
