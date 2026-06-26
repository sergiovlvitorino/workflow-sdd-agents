---
name: review-loop
description: Orquestra um ciclo de implementação + code review até não haver ressalvas. Dispara os agentes desenvolvedores (dev-python / dev-frontend / dev-java / dev-go / qa, conforme a stack) para implementar a tarefa e, em seguida, os tech leads correspondentes (tl-*) + o tech lead de QA (tl-qa) para revisar. Repete o ciclo enquanto houver ressalvas; após 3 falhas do mesmo agente, escala para o especialista (spec-*). Use quando o usuário pedir para implementar algo "com revisão", "em loop de review", ou disser /review-loop <tarefa>.
---

# review-loop

Orquestra um ciclo **implementar → revisar → corrigir** até a revisão dos Tech Leads não apontar mais ressalvas. É o **motor de execução** reutilizado por outras skills (sprint-flow, bug-flow, debt-flow, etc.).

## Quando usar

Quando o usuário pede para implementar uma tarefa/feature/correção e quer que ela passe por code review automático em loop antes de ser considerada pronta. A tarefa vem como argumento (`/review-loop <descrição da tarefa>`) ou da conversa atual.

## Princípios

- **Não implemente nem revise você mesmo (loop principal).** Seu papel é de **orquestrador**: você delega a implementação aos agentes desenvolvedores e a revisão aos tech leads, e decide quando o loop termina.
- **Não pare no primeiro ciclo.** Só encerre quando TODOS os tech leads acionados retornarem aprovação sem ressalvas (ou apenas sugestões opcionais/nice-to-have explicitamente marcadas como não bloqueantes).
- **Continuidade de contexto:** ao reacionar um agente que já rodou neste loop, prefira `SendMessage` (passando o ID/nome do agente) para preservar o contexto, em vez de abrir um agente novo do zero.
- **Escalone quando o agente empacar.** Se o mesmo agente implementador falhar **3 ciclos** em satisfazer as ressalvas bloqueantes, a tarefa é transferida ao **agente especialista** da stack (ver mapeamento). Insistir com o mesmo agente após 3 tentativas tende a repetir o mesmo erro — o especialista entra com olhar fresco. Ver etapa §3.1.

## Mapeamento stack → agentes

| Stack envolvida        | Implementador   | Tech Lead (revisor) | Especialista (escala em 3 falhas) |
|------------------------|-----------------|---------------------|-----------------------------------|
| Python / backend       | `dev-python`    | `tl-python`         | `spec-python`                     |
| Frontend / UI / TS     | `dev-frontend`  | `tl-frontend`       | `spec-frontend`                   |
| Java / backend         | `dev-java`      | `tl-java`           | `spec-java`                       |
| Go / backend           | `dev-go`        | `tl-go`             | `spec-go`                         |
| Quality Assurance      | `qa`            | `tl-qa`             | `spec-qa`                         |

**Revisor de qualidade transversal:** `tl-qa` (Tech Lead de QA) — independente da stack. Revisa testes, força de asserts, determinismo (flaky), proteção das invariantes de negócio do projeto e os **quality gates** (cobertura/ratchet, mínimos por módulo, CAs/Gherkin executáveis). O `tl-qa` **não rebaixa gates** — se faltar cobertura, a ressalva é "escrever o teste", não "baixar o piso".

> **Especialista = escalonamento, não rotina.** O `spec-*` (modelo `fable`) só entra quando o agente regular da mesma stack falhar 3 ciclos — ver Princípios e §3.1. Caso uma stack não tenha especialista correspondente, ao atingir 3 falhas **reporte ao usuário** as ressalvas em aberto e pergunte como proceder.

Regras:
- Identifique a(s) stack(s) afetada(s) pela tarefa (pelos arquivos/diretórios tocados ou pela natureza do pedido). Na dúvida sobre a stack dominante, inspecione o projeto (linguagem dos arquivos, manifestos como `pyproject.toml`/`package.json`/`go.mod`/`pom.xml`).
- Se a tarefa cruzar mais de uma stack (ex.: API backend + tela frontend), acione **os dois pares**. Os implementadores podem rodar em paralelo (um único bloco com múltiplas chamadas `Agent`); cada tech lead revisa o código da sua própria stack.
- **Acione `tl-qa` em paralelo ao(s) tech lead(s) de stack** sempre que a tarefa: (a) adicionar/alterar testes; (b) tocar invariantes de negócio, segurança, concorrência ou dados; (c) impactar cobertura ou qualquer quality gate. Para tarefas puramente cosméticas/de docs sem código testável, o `tl-qa` é opcional.
- Para uma stack sem par dev/tl correspondente na tabela, informe o usuário e pergunte como proceder.

## Procedimento

### 0. Preparação
1. Confirme a tarefa a implementar. Se a descrição for ambígua a ponto de impedir a implementação, faça 1–2 perguntas objetivas antes de iniciar o loop.
2. Determine a(s) stack(s) e selecione o(s) par(es) de agentes conforme a tabela.
3. Crie um TODO com: implementação inicial e um item por ciclo de revisão.
4. Defina um teto de segurança de **5 iterações**. Se atingir o teto sem aprovação, pare e reporte ao usuário as ressalvas remanescentes (não fique em loop infinito).
5. Mantenha um **contador de falhas por agente implementador** (cada `dev-*` e também o `qa`). Uma falha = um ciclo que termina com `VEREDITO: RESSALVAS` bloqueantes (ou em que o agente nem conseguiu rodar a verificação) para aquele agente. Ao chegar a **3 falhas** do mesmo agente, **escale para o especialista** da stack (§3.1). O contador é por agente: se a tarefa cruza duas stacks, cada par regular/especialista tem o seu.

### 1. Implementação (agentes implementadores)
Acione o(s) `dev-*` (ou `qa`, para tarefas de teste) com um prompt que contenha:
- A descrição completa da tarefa.
- Contexto relevante do projeto (arquivos/módulos alvo, padrões a seguir — leia os guias do repo, ex.: `CLAUDE.md`/`README`/`CONTRIBUTING`).
- Instrução explícita de: implementar a solução, escrever/atualizar testes, rodar lint/type-check/testes quando aplicável, e **retornar um resumo objetivo das mudanças** (arquivos alterados, decisões tomadas, comandos de verificação executados e seus resultados).

Aguarde a conclusão. Registre os arquivos tocados — eles são o escopo da revisão.

### 2. Revisão (agentes tech leads)
Acione **em paralelo** (um único bloco com múltiplas chamadas `Agent`) o(s) `tl-*` de stack e, quando aplicável, o `tl-qa`. Cada um com um prompt que contenha:
- A descrição original da tarefa (o que deveria ser feito).
- O resumo das mudanças entregue pelo implementador e a lista de arquivos alterados.
- Instrução para fazer **code review READ-ONLY focado** nesses arquivos:
  - **`tl-*` de stack:** correção, aderência à arquitetura e padrões do projeto, segurança, tratamento de erros e simplicidade.
  - **`tl-qa`:** qualidade e força dos testes, determinismo (sem flaky), proteção das invariantes de negócio com testes negativos, e conformidade com os quality gates.
- Instrução de **formato de saída obrigatório**:
  - Primeira linha do veredito: `VEREDITO: APROVADO` **ou** `VEREDITO: RESSALVAS`.
  - Se `RESSALVAS`: uma lista numerada de itens **bloqueantes**, cada um com arquivo/linha, o problema e a ação corretiva esperada. Itens meramente opcionais devem ser marcados como `(opcional)` e NÃO contam como ressalva bloqueante.

### 3. Decisão do loop
- Se **todos** os tech leads acionados (de stack **e** o `tl-qa`, quando presente) retornarem `VEREDITO: APROVADO` (ou apenas itens `(opcional)`): **encerre o loop** e vá para a etapa 4.
- Caso contrário: consolide as ressalvas bloqueantes e volte à etapa 1, reacionando o(s) implementador(es) — de preferência via `SendMessage` para o mesmo agente — passando a lista de ressalvas e pedindo as correções. Depois revise novamente (etapa 2). Incremente o contador de iterações **e o contador de falhas do agente** que ainda tem ressalvas.
- **Se um agente implementador atingir 3 falhas, não o reaccione: escale para o especialista (§3.1) antes de seguir.**
- Atualize o TODO a cada ciclo.

### 3.1 Escalonamento para o especialista (após 3 falhas)
Quando um agente implementador (`dev-*` ou `qa`) acumula **3 ciclos** sem resolver as ressalvas bloqueantes, transfira a tarefa ao `spec-*` da mesma stack (`dev-python`→`spec-python`, `dev-frontend`→`spec-frontend`, `dev-java`→`spec-java`, `dev-go`→`spec-go`, `qa`→`spec-qa`):

- **Agente novo, contexto limpo:** acione o especialista com um agente **novo** (NÃO use `SendMessage` para o agente que falhou — o ponto é trocar de perspectiva, não herdar o contexto enviesado). Para o `spec-*` que assume, prefira `SendMessage` apenas nas iterações subsequentes do próprio especialista.
- **Prompt do especialista:** inclua (a) a descrição original da tarefa e o spec/critérios; (b) a lista atual de ressalvas bloqueantes; (c) um **diagnóstico curto do porquê os 3 ciclos anteriores falharam** (o que o agente regular tentou e por que não satisfez os TLs); (d) os arquivos tocados. Instrua-o a reanalisar o problema desde a raiz, não apenas remendar a última tentativa.
- **Stack sem especialista:** se a stack não tiver `spec-*`, pare, reporte ao usuário as ressalvas em aberto e o histórico de falhas, e pergunte como proceder.
- **Teto preservado:** a escalada **não reseta** o contador de iterações. O especialista assume as iterações restantes dentro do mesmo teto de 5; se ele também não aprovar até o teto, encerre pela etapa 4 reportando as ressalvas remanescentes.
- A revisão (etapa 2) continua igual: os mesmos `tl-*`/`tl-qa` revisam o que o especialista entregar.

### 4. Encerramento
Quando não houver mais ressalvas (ou ao atingir o teto), apresente ao usuário um resumo final:
- Número de ciclos executados e se houve escalonamento para especialista.
- Resumo das mudanças finais (arquivos alterados).
- Histórico resumido das ressalvas e como foram resolvidas em cada ciclo.
- Resultado das verificações (lint/type-check/testes), se executadas.
- Veredito final de cada tech lead.
- Se parou por teto de iterações: as ressalvas que permanecem em aberto, claramente sinalizadas.

## Observações
- Nunca declare a tarefa concluída sem pelo menos um ciclo completo de revisão aprovado.
- **Revisão estática não basta: execute os testes de verdade antes de encerrar.** Quando a tarefa tem testes executáveis, a suíte relevante precisa ser **rodada de fato** (infra real do projeto: banco, serviços, variáveis de ambiente) e estar verde — não apenas aprovada por leitura. Só conte como verde com execução real (registre as contagens passed/failed/skipped). O `tl-qa` deve ele mesmo executar e medir cobertura, não só revisar por leitura.
- Reporte fielmente: se testes falharam ou uma etapa foi pulada, diga isso explicitamente.
- Mantenha as mudanças no escopo da tarefa; não deixe os implementadores expandirem o escopo sem necessidade.
