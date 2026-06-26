---
name: sprint-flow
description: Orquestra o planejamento e refinamento de um conjunto de tarefas até a execução, fechando com retrospectiva. O agente PO analisa o backlog, prioriza (MoSCoW), define MVP e fatia o que deve ser implementado por sprint; os Tech Leads (tl-python / tl-frontend / tl-java / tl-go / tl-qa, conforme a stack) detalham tecnicamente cada tarefa produzindo specs DETAIL; a execução de cada tarefa é entregue à skill review-loop; e ao final uma retrospectiva compila os aprendizados na memória local do agente e num doc versionado no repo. Use quando o usuário pedir para "planejar as sprints", "refinar o backlog", "definir o que entra em cada sprint", "detalhar as tarefas", "fazer a retrospectiva" ou disser /sprint-flow <escopo>.
---

# sprint-flow

Orquestra o fluxo **analisar → fatiar por sprint → detalhar → executar → retrospectiva**:

1. **PO** analisa as tarefas, prioriza e define o que deve ser implementado, **separando por sprints**.
2. **Tech Leads** descrevem/detalham tecnicamente cada tarefa da sprint alvo (specs `DETAIL-*`).
3. A **execução** de cada tarefa é feita pela skill **`review-loop`** (implementar → revisar → corrigir em loop, com escalonamento para `spec-*`).
4. **Retrospectiva**: ao fim da sprint, os aprendizados são compilados e gravados em **dois lugares** — na **memória local do agente** e num **doc versionado no repo** (`docs/retrospectivas/sprint-NN.md`).

## Quando usar

Quando o usuário quer transformar um backlog/feature/conjunto de demandas em um **plano de sprints executável** e detalhado, e então tocar a implementação com revisão. O escopo vem como argumento (`/sprint-flow <feature/épico/escopo>`) ou da conversa. Se nenhum escopo for dado, assuma o backlog corrente do projeto (procure por `specs/`, `docs/`, `backlog/`, issues abertas).

## Princípios

- **Você é o orquestrador, não o executor.** Não analise o produto, não detalhe as tarefas, nem implemente você mesmo (loop principal). Delegue: produto → `po`; detalhamento técnico → `tl-*`; execução → skill `review-loop`.
- **Produto antes de engenharia.** O `po` decide *o quê* e *em qual sprint*; os `tl-*` decidem *como*. Não deixe um tech lead redefinir escopo/prioridade de produto sem passar pelo `po`, nem o `po` ditar implementação.
- **Plano antes de código.** Não acione `review-loop` antes de o usuário aprovar o plano de sprints e ter os DETAIL das tarefas da sprint a executar.
- **Continuidade de contexto:** ao reacionar um agente já usado neste fluxo, prefira `SendMessage` a abrir um agente novo.
- **Aprendizado persiste, contexto não.** A sprint só termina quando os aprendizados estiverem persistidos nos **dois destinos** (memória local do agente + doc versionado). O que ficar só no chat é perdido na próxima sessão.
- **Fonte da verdade do projeto.** Leia os documentos de planejamento do repo antes de planejar (backlog, ordem de implementação, entregáveis); o plano deve ser **consistente** com eles (ou apontar e justificar divergências).

## Mapeamento stack → agentes

| Papel no fluxo                 | Agente            |
|--------------------------------|-------------------|
| Produto / priorização / sprint | `po`              |
| Detalhe técnico Python/backend | `tl-python`       |
| Detalhe técnico Frontend/UI/TS | `tl-frontend`     |
| Detalhe técnico Java/backend   | `tl-java`         |
| Detalhe técnico Go/backend     | `tl-go`           |
| Detalhe técnico de qualidade   | `tl-qa`           |

- Identifique a(s) stack(s) de cada tarefa pelos arquivos/módulos que ela toca ou pela natureza do pedido. Na dúvida, inspecione os manifestos do projeto para descobrir a stack dominante.
- Tarefas que tocam **testes, invariantes de negócio, segurança, concorrência, dados ou quality gates** devem ter o `tl-qa` co-detalhando (testabilidade/CAs Gherkin/cobertura).
- Tarefa de stack sem `tl-*` correspondente: informe o usuário e pergunte como proceder.

## Procedimento

### 0. Preparação
1. Confirme o escopo a planejar. Leia o backlog relevante e a alocação de sprints atual do projeto.
2. Se o escopo for ambíguo a ponto de impedir o planejamento, faça 1–3 perguntas objetivas antes de começar.
3. Crie um TODO: análise PO, detalhamento por TL, um item por tarefa a executar via review-loop e **um item de retrospectiva**.

### 1. Análise de produto e fatiamento por sprint (agente `po`)
Acione o `po` com um prompt contendo:
- O escopo e os documentos-fonte do projeto.
- Instrução para produzir um **plano de sprints**:
  - Decompor/agrupar as tarefas e classificá-las em **MoSCoW** (Must / Should / Could / Won't).
  - Definir o **MVP** e **alocar cada tarefa a uma sprint**, respeitando **dependências** e a ordem existente.
  - Para cada sprint: objetivo, tarefas (com IDs), ordem de execução e a saída/demo esperada.
  - Apontar conflitos com o planejamento atual e justificar.
- **Formato de saída obrigatório:** uma tabela `Sprint | Task | Papel/Stack | Prioridade MoSCoW | Depende de | Estimativa` mais o objetivo de cada sprint.

Apresente o plano ao usuário e **obtenha aprovação** (ou ajuste) antes de seguir. Defina **qual sprint** será detalhada/executada agora (default: a próxima do MVP).

### 2. Detalhamento técnico das tarefas (agentes `tl-*`)
Para as tarefas da sprint alvo, acione **em paralelo** o(s) tech lead(s) por stack — e o `tl-qa` para tarefas com testes/invariantes/gates. Cada `tl-*` com um prompt contendo:
- As tarefas da sua stack (ID, descrição-resumo, CAs/RNs cobertos, dependências).
- Instrução para **detalhar tecnicamente** cada tarefa, produzindo um spec `DETAIL` no mesmo formato dos existentes no projeto: objetivo e valor, design da solução (arquivos/módulos, contratos, decisões e trade-offs), impacto em testes e quality gates, riscos e uma **Definition of Done** verificável.
- Instrução para gravar cada DETAIL no diretório de specs do projeto e **retornar um resumo** (caminho, decisões-chave, dependências e ordem sugerida).
- Aderência aos padrões do projeto (leia `CLAUDE.md`/guias do repo).

Consolide os DETAIL e confirme com o usuário a ordem de execução (respeitando dependências).

### 3. Execução de cada tarefa (skill `review-loop`)
Para cada tarefa da sprint, **na ordem de dependências**, invoque a skill **`review-loop`** passando como tarefa o `DETAIL` correspondente (caminho + ID). O `review-loop` cuida do ciclo implementar → revisar (tl-* + tl-qa) → corrigir até não haver ressalvas, incluindo a **execução real dos testes** antes de declarar verde.

- **Escalonamento automático para especialista:** se um agente implementador (`dev-*` ou `qa`) falhar **3 ciclos**, o `review-loop` transfere a tarefa ao **especialista** da stack (`spec-python` / `spec-frontend` / `spec-java` / `spec-go` / `spec-qa`). Você não precisa acionar isso manualmente — é responsabilidade do `review-loop` (§3.1 daquela skill). Apenas **registre no relatório** quando uma tarefa exigiu escalonamento — é sinal útil para a retrospectiva (estimativa furada, complexidade subestimada).
- Execute as tarefas **uma a uma** (ou em paralelo apenas quando independentes e o usuário concordar), respeitando o grafo de dependências.
- Ao concluir cada tarefa, atualize o TODO e só avance para a dependente quando a anterior estiver aprovada.

### 4. Retrospectiva — compilar e armazenar os aprendizados
Após executar as tarefas da sprint, conduza uma **retrospectiva** e **persista os aprendizados nos dois destinos**: a **memória local do agente** e um **doc versionado no repo**. Esta etapa **não é opcional**.

> **Por que dois lugares.** A memória do agente fica no perfil do usuário, **fora do repositório** — não vai para o git, mas é o que o Claude Code lê na recall de sessões futuras nesta máquina. O `docs/retrospectivas/sprint-NN.md` fica **dentro do repo**, é versionado e revisável em PR. Os dois devem ficar **coerentes**.

**4.1. Coletar os aprendizados.** Reúna insights da sprint: vereditos e ressalvas recorrentes dos `review-loop`, gotchas técnicos, divergências plano-vs-realidade, falhas de processo e o que funcionou bem. Você pode acionar o `po` (ângulo processo/produto) e o `tl-qa` (ângulo técnico/qualidade) pedindo listas curtas — mas a **curadoria e a gravação na memória são do orquestrador**.

**4.2. Filtrar o que merece virar memória.** Registre apenas o que é **não-óbvio, reutilizável e durável**. **Não** salve o que o repositório já guarda (estrutura de código, histórico git, `CLAUDE.md`/specs/docs) nem o que só vale para esta conversa.

**4.3. Gravar na memória local do agente.** Use o diretório de memória do projeto para esta máquina (o mesmo indexado pelo `MEMORY.md` da recall). Um **fato por arquivo** com frontmatter padrão (`name`, `description`, `metadata.type: feedback|project|reference`); para `feedback`/`project`, siga com **Why:** e **How to apply:**. Antes de criar, procure um arquivo existente e **atualize-o** em vez de duplicar; atualize o índice `MEMORY.md` com uma linha por memória nova.

**4.3.1. Promover o que é generalizável aos playbooks do projeto.** Para cada aprendizado, decida explicitamente: é **específico desta entrega** (fica só na memória local — 4.3) ou é um **princípio de engenharia generalizável** que valeria em outra frente da mesma classe? Se for generalizável, **destile** (remova os specifics — nomes de tarefa, entidade de domínio, integração externa) e **anexe ao playbook de papel** em `docs/lessons/<papel>.md` (`qa` / `python` / `sre` / `security` / `process`), seguindo as regras do `docs/lessons/README.md`: princípio load-bearing, datado, deduplicado contra o que já existe, sem contradizer lição anterior. É assim que os agentes ficam mais inteligentes em **todo** o projeto, não só nesta tarefa. Na dúvida entre específico e geral, fique no local (a memória local é barata; poluir o playbook degrada agentes em toda parte).

**4.4. Gravar o doc versionado no repo.** Crie/atualize `docs/retrospectivas/sprint-NN.md`. Template:

```markdown
# Retrospectiva — Sprint NN (<épico/escopo>)

> Data: <AAAA-MM-DD> · Tarefas: <IDs>

## ✅ O que funcionou (repetir)
## ⚠️ O que melhorar
## 🧠 Aprendizados técnicos (gotchas)
## 📐 Plano vs. realidade
## 🔗 Memórias do agente geradas
- `<slug>` — <uma linha>
```

- **Mantenha coerência com a memória:** todo aprendizado que virou memória deve aparecer resumido neste doc, e vice-versa.
- Se `docs/retrospectivas/` não existir, crie-o. Se já houver retrospectiva da sprint, **atualize** em vez de duplicar.

**4.5. Reportar.** Liste ao usuário: (a) memórias locais criadas/atualizadas/removidas e (b) o doc de retrospectiva versionado — lembrando que o doc do repo entra no commit/PR da sprint.

### 5. Encerramento
Apresente um resumo: plano aprovado (tabela) e sprint executada; DETAILs gerados; status de cada tarefa via review-loop (ciclos, escalonamentos, veredito final, resultado dos testes); aprendizados persistidos nos dois destinos; e tarefas planejadas porém **não executadas** nesta sessão, claramente sinalizadas.

## Observações
- **Separação de responsabilidades é o ponto da skill:** PO define *o quê/quando*, TL define *como*, review-loop faz *acontecer* (com revisão) e a retrospectiva *aprende*. Não pule a aprovação do plano, os DETAIL antes de executar, nem a gravação dos aprendizados nos dois destinos.
- O plano e os DETAIL devem ser **consistentes com a documentação do projeto**; ao divergir, explicite a divergência e o motivo.
- Não infle escopo: o `po` deve cortar para o MVP e proteger o tempo de desenvolvimento.
- Reporte fielmente: se uma tarefa não couber na sprint, faltar agente de stack, ou uma execução falhar/for pulada, diga isso explicitamente.
- Para o detalhe do ciclo de implementação+revisão, ver a skill `review-loop`.
