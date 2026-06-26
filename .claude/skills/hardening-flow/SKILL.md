---
name: hardening-flow
description: Faz uma revisão de segurança orientada a risco e corrige os achados por severidade. Um painel (tl-qa + tl-* da stack + sre) audita a superfície de ataque, os achados são triados por severidade/exploitabilidade, e cada correção bloqueante é executada via review-loop com teste que prova a vulnerabilidade fechada. Use quando o usuário pedir "revisão de segurança", "hardening", "corrigir vulnerabilidades", "análise OWASP", ou disser /hardening-flow <escopo>.
---

# hardening-flow

Estratégia de **segurança orientada a risco**: audita a superfície de ataque, prioriza por severidade real e corrige com prova (teste que falha antes do fix). Reutiliza `review-loop` para executar as correções.

## Quando usar

Quando o objetivo é reduzir risco de segurança: revisão pré-release, hardening de uma área sensível (auth, multi-tenant, pagamentos, upload, deserialização), resposta a um achado de scanner, ou auditoria periódica. Vem como argumento (`/hardening-flow <escopo>`) ou da conversa.

> Se o projeto já tem uma skill de `security-analysis` própria, use-a na etapa de auditoria e deixe o hardening-flow orquestrar a **triagem + correção**.

## Princípios

- **Risco real, não checklist cego.** Severidade = impacto × exploitabilidade no *contexto deste sistema*. Um teórico sem caminho de exploração não prioriza sobre um explorável.
- **Provar a falha antes de corrigir.** Cada vulnerabilidade bloqueante ganha um **teste que a demonstra** (negativo de segurança) e que passa só depois do fix — senão a regressão volta.
- **Defesa, não ofensa.** O foco é fechar brechas e validar defensivamente. Não produza exploits prontos para uso malicioso; PoC de validação fica no mínimo necessário para provar/testar a correção.
- **Não rebaixar postura.** Suprimir um achado (`# nosec`, allowlist) só com justificativa explícita e revisada pelo `tl-qa`/`sre` — nunca para "passar o gate".

## Mapeamento

| Passo | Agente |
|-------|--------|
| Mapear superfície de ataque / entrypoints | `Explore` (read-only) |
| Auditoria de segurança (painel, em paralelo) | `tl-qa` (invariantes/abuso), `tl-*` da stack (vulns de código), `sre` (config/infra/segredos/deps) |
| Triagem por severidade | orquestrador (consolida e prioriza) |
| Corrigir cada achado bloqueante | skill `review-loop` (com teste de prova) |

## Procedimento

### 0. Escopo e modelo de ameaça
1. Defina o **escopo** (módulo, endpoint, fluxo, ou app inteiro) e o que se está protegendo (dados sensíveis, isolamento entre tenants, dinheiro, disponibilidade). Confirme que é uso **autorizado/defensivo** (revisão do próprio projeto). Se ambíguo, pergunte.
2. Crie um TODO: mapear → auditar → triar → corrigir (por severidade) → reverificar.

### 1. Superfície de ataque (agente `Explore`)
`Explore` (read-only) levanta os **entrypoints** e a superfície: rotas/handlers, parsers de input, fronteiras de confiança, autenticação/autorização, acesso a dados (incl. isolamento multi-tenant), segredos, dependências e pontos de I/O externo. Saída: o mapa que orienta a auditoria.

### 2. Auditoria (painel em paralelo)
Acione **em paralelo** (um bloco com múltiplas chamadas `Agent`), cada um com lente distinta:
- **`tl-*` da stack:** vulnerabilidades de código — injeção (SQL/cmd/template), XSS, deserialização insegura, path traversal, SSRF, controle de acesso quebrado, tratamento de erro que vaza, criptografia mal usada.
- **`tl-qa`:** invariantes de negócio e segurança sob abuso — bypass de autorização, isolamento entre tenants, idempotência/replay, condições de corrida, e se há **testes negativos** protegendo isso.
- **`sre`:** configuração e infra — segredos versionados, permissões excessivas, headers/TLS, dependências vulneráveis (CVEs), exposição de superfície, logging de dados sensíveis.

Cada agente retorna achados com: descrição, **localização** (arquivo/linha), **caminho de exploração** plausível, impacto e correção sugerida.

### 3. Triagem por severidade
Consolide os achados (dedup entre as três lentes) e classifique cada um por **severidade** (Crítico/Alto/Médio/Baixo) combinando impacto × exploitabilidade no contexto real. Separe:
- **Bloqueantes** (Crítico/Alto, ou Médio explorável) → corrigir nesta rodada.
- **Aceitos/adiados** (Baixo, teórico sem caminho) → registrar com justificativa.

Apresente a triagem ao usuário antes de corrigir se o volume/risco for relevante.

### 4. Correção por severidade (skill `review-loop`)
Para cada achado bloqueante, **na ordem de severidade**, invoque a skill **`review-loop`** com a tarefa: "fechar a vulnerabilidade X" e a exigência de **um teste que a prova** (falha antes do fix, passa depois). O `review-loop` executa `dev-*`/`spec-*` → `tl-*`+`tl-qa`, com escalonamento para o `spec-*` em 3 falhas. O `tl-qa` confirma que o teste negativo de segurança trava a causa.

### 5. Encerramento
Resuma: a superfície auditada, a tabela de achados por severidade (corrigidos vs. aceitos/adiados com justificativa), os testes de prova adicionados, e o risco residual. Para achados adiados, **proponha tarefas de follow-up** no backlog. Se a auditoria revelar dívida estrutural, encadeie um `debt-flow`.

## Observações
- Mantenha-se no contexto **defensivo/autorizado**. Recuse derivar para técnicas ofensivas de uso malicioso; o PoC existe só para provar e testar a correção.
- Severidade é contextual: replique o juízo de exploitabilidade ao *seu* sistema, não a um CVSS genérico.
- Nunca feche um achado bloqueante sem o teste de regressão de segurança rodando e verde.
