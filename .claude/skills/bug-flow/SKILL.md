---
name: bug-flow
description: Corrige um bug de forma dirigida por teste. Primeiro o QA reproduz o defeito com um teste que falha (a Definition of Done), depois a correção é entregue à skill review-loop (implementar → revisar → corrigir, com escalonamento para o especialista). Encerra só quando o teste de regressão passa e nada mais quebra. Use quando o usuário relatar um bug, pedir uma correção "com teste de regressão", ou disser /bug-flow <descrição do bug>.
---

# bug-flow

Estratégia de **correção dirigida por teste**: nenhum bug é considerado resolvido sem um teste que reproduz a falha **antes** do fix e passa **depois**. Reutiliza o `review-loop` como motor de execução.

## Quando usar

Quando há um bug report (stack trace, comportamento errado, regressão) e o usuário quer a correção com rede de segurança. A descrição vem como argumento (`/bug-flow <bug>`) ou da conversa. Difere do `sprint-flow`: sem PO nem fatiamento — entra direto pela reprodução.

## Princípios

- **Reproduza antes de corrigir.** O primeiro passo é sempre um teste que **falha** demonstrando o bug. Sem reprodução confirmada, não acione a correção — você estaria adivinhando.
- **Teste a causa, não o sintoma.** O teste de regressão deve travar a *causa-raiz*, não mascarar o sintoma; senão a regressão volta.
- **Escopo mínimo.** Corrija o bug e nada mais. Refactors oportunistas viram tarefa separada (ver `debt-flow`).
- **Você é o orquestrador.** Delegue reprodução ao `qa`, correção+revisão ao `review-loop`.

## Mapeamento

| Passo | Agente |
|-------|--------|
| Reproduzir (teste que falha) | `qa` (ou `qa-automator` para setup de teste mais elaborado) |
| Investigar causa-raiz (se obscura) | `Explore` (read-only) |
| Corrigir + revisar + escalar | skill `review-loop` |

## Procedimento

### 0. Preparação
1. Capture o relato: sintoma, passos de reprodução, ambiente, severidade. Se faltar o essencial para reproduzir, faça 1–2 perguntas objetivas.
2. Crie um TODO: reproduzir → localizar causa → corrigir via review-loop → confirmar regressão verde.

### 1. Reprodução (agente `qa`)
Acione o `qa` para **escrever um teste que falha** reproduzindo o bug, na suíte e framework do projeto. Instrua-o a:
- Reproduzir o defeito de forma **determinística** (sem flaky).
- **Não corrigir o código de produção** nesta etapa — só demonstrar a falha.
- Retornar o teste, o comando para rodá-lo e a saída mostrando a falha (a asserção que quebra).

Se o teste **não** falhar como esperado, o bug não foi reproduzido — refine o relato com o usuário antes de seguir (talvez seja ambiente, dado ou expectativa equivocada).

### 2. Localizar a causa (opcional — agente `Explore`)
Se a causa-raiz não for óbvia, acione o `Explore` (read-only) para mapear o caminho do código envolvido e candidatos à origem. Não corrija aqui — só levante o diagnóstico que vai no prompt da correção.

### 3. Correção (skill `review-loop`)
Invoque a skill **`review-loop`** passando como tarefa: "corrigir o bug X de modo que o teste de regressão `<arquivo::teste>` (que hoje falha) passe, sem quebrar a suíte existente". Inclua o teste de reprodução e o diagnóstico da etapa 2. O `review-loop` cuida de implementar → revisar (`tl-*` + `tl-qa`) → corrigir, escalando para o `spec-*` da stack em 3 falhas.

- A **Definition of Done** da tarefa é: o teste de regressão passa **e** a suíte relevante continua verde (execução real, não revisão por leitura).

### 4. Encerramento
Resuma: o teste de regressão criado (caminho), a causa-raiz, a correção (arquivos), o resultado da suíte (passed/failed/skipped) e se houve escalonamento para especialista. Sinalize qualquer efeito colateral observado.

## Observações
- Se durante a correção surgir dívida estrutural maior, **não a resolva aqui** — registre e proponha um `debt-flow` separado.
- Se o bug for de produção e urgente, considere o `hotfix-flow` (caminho rápido com SRE) em vez deste.
- Nunca feche o bug sem a suíte rodando de verdade e verde.
