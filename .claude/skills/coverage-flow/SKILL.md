---
name: coverage-flow
description: Eleva a cobertura de testes de um módulo/área até a meta (ratchet/gate) sem alterar o código de produção. O qa-automator escreve os testes faltantes priorizando caminhos de risco, e o tl-qa revisa força das asserções, determinismo e conformidade com os quality gates. Use quando o usuário pedir para "aumentar a cobertura", "cobrir o módulo X", "fechar o gate de cobertura", "backfill de testes", ou disser /coverage-flow <alvo>.
---

# coverage-flow

Estratégia de **backfill de testes**: aumenta a cobertura de uma área existente até a meta, **sem mudar o comportamento** do código. Foca risco, não só o número.

## Quando usar

Quando há um déficit de cobertura a fechar: um módulo legado sem testes, um gate/ratchet que está abaixo do piso, ou uma área crítica subtestada. Vem como argumento (`/coverage-flow <módulo/alvo>`) ou da conversa.

> **Cobertura é meio, não fim.** O objetivo é *risco coberto* (caminhos que quebrariam o negócio), não inflar a porcentagem com testes triviais. Não use isto para escrever código novo — só testes sobre o que já existe.

## Princípios

- **Priorize por risco, não por linha fácil.** Caminhos críticos, edge cases, ramos de erro e invariantes valem mais que getters. Mire onde uma falha doeria.
- **Não toque no código de produção.** Se um trecho é intestável sem refactor, isso é um achado → vira `debt-flow`, não se força aqui.
- **Asserção forte, teste determinístico.** Teste que passa com qualquer saída não cobre nada; teste flaky é dívida. O `tl-qa` barra ambos.
- **Não rebaixar gate.** A resposta a "falta cobertura" é escrever o teste, nunca baixar o piso.

## Mapeamento

| Passo | Agente |
|-------|--------|
| Medir cobertura atual e achar lacunas de risco | `qa-automator` (ou `qa`) |
| Escrever os testes faltantes | `qa-automator` → `spec-qa` (escala em 3 falhas) |
| Revisar força/determinismo/gates | `tl-qa` |

## Procedimento

### 0. Preparação
1. Defina o **alvo** (módulo/pacote/área) e a **meta** (piso do gate, % alvo, ou "cobrir os caminhos críticos"). Se não houver meta explícita, use o ratchet/gate do projeto ou combine uma com o usuário.
2. Crie um TODO: medir → priorizar lacunas → escrever testes → revisar → confirmar meta.

### 1. Diagnóstico de cobertura (agente `qa-automator`)
Acione o `qa-automator` para **rodar a cobertura atual** do alvo e produzir um mapa das lacunas, **ordenadas por risco** (não por facilidade): ramos de erro, edge cases, regras de negócio, concorrência, fronteiras. Saída: relatório com cobertura atual, linhas/ramos descobertos e a fila priorizada.

### 2. Escrever os testes (loop dirigido pelo `qa-automator`)
Acione o `qa-automator` para escrever os testes faltantes seguindo a fila de risco, em iterações:
- Testes **independentes**, determinísticos, com asserções fortes; `parametrize`/table-driven para variações.
- **Sem alterar produção.** Se um trecho exigir refactor para ser testável, **registre** e siga — não force.
- A cada lote, **rodar a suíte e remedir a cobertura** (execução real), reportando o avanço rumo à meta.

Aplique a regra de escalonamento do `review-loop`: se o `qa`/`qa-automator` empacar **3 vezes** num conjunto de testes (não consegue cobrir de forma determinística e forte), escale para o **`spec-qa`** com diagnóstico do impedimento.

### 3. Revisão de qualidade (agente `tl-qa`)
Acione o `tl-qa` para revisar (READ-ONLY) os testes adicionados:
- **Força das asserções** (nada de teste que sempre passa), **determinismo** (sem flaky/sleep/relógio/rede real), e se os **caminhos de risco** certos foram cobertos (não só o número subiu).
- Conformidade com os **quality gates** do projeto. Formato de veredito igual ao `review-loop` (`APROVADO`/`RESSALVAS`). Ressalvas voltam à etapa 2.

### 4. Encerramento
Resuma: cobertura **antes → depois** (medida de verdade), quais caminhos de risco passaram a estar cobertos, número de testes adicionados, e se a **meta/gate foi atingida**. Liste eventuais trechos intestáveis que viraram candidatos a `debt-flow` e qualquer escalonamento para `spec-qa`.

## Observações
- Se a meta exigir refactor de produção para ser alcançável, **pare e proponha um `debt-flow`** antes — misturar refactor aqui quebra a premissa de "não tocar produção".
- Cuidado com a métrica enganando: 90% de linhas com asserções fracas é pior que 70% protegendo o que importa. O `tl-qa` é o juiz disso.
