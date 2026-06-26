# Guia da Trilha SDD — percorra o ciclo com o blog-tutorial

> **Para quem clonou este projeto-base e não sabe por onde começar.** Este guia é a F008 do blog-tutorial: ele te leva, em ordem, pela espinha dorsal do fluxo de agentes — **discovery → design → sprint → review-loop → retrospectiva** — apontando **qual skill acionar em cada etapa** e **qual artefato cada passo produz**. O blog (posts, publicar, listar) é só o pretexto: o valor está no caminho percorrido.

Cada etapa abaixo aponta para artefatos **reais** já produzidos neste repositório — abra-os enquanto lê; são o seu exemplo canônico.

---

## A espinha dorsal em uma figura

```
ideia crua
   │  /discovery-flow            (agentes de produto: product-owner / po)
   ▼
backlog refinado ──────────────► specs/backlog-blog-tutorial.md
   │  /design-flow               (painel de tl-* + síntese em ADR)
   ▼
decisões registradas ──────────► specs/adr/ADR-0001 … ADR-0006
   │  /sprint-flow               (PO fatia → TLs detalham → executa → retro)
   ├── plano de sprint ────────► tabela Sprint|Task|MoSCoW|Depende|Estimativa
   ├── DETAILs ────────────────► specs/tasks/sprint-NN/DETAIL-T-*.md
   │     │  /review-loop         (dev-* implementa → tl-* + tl-qa revisam → corrige)
   │     ▼
   ├── código + testes verdes ─► backend/ , frontend/ (gates mordendo)
   └── retrospectiva ──────────► docs/retrospectivas/sprint-NN.md
                                  + memória local do agente
                                  + docs/lessons/<papel>.md (o que é generalizável)
```

---

## Etapa 1 — Discovery: da ideia ao backlog

**Skill:** `/discovery-flow <demanda>` · **Agentes:** `product-owner` / `po`

Transforma um pedido vago num backlog pronto para planejar: épicos, user stories com critérios de aceite (Gherkin), priorização **MoSCoW** e definição de **MVP**. Não escreve código.

**Artefato produzido:** [`specs/backlog-blog-tutorial.md`](../specs/backlog-blog-tutorial.md) — veja os épicos E1–E4, as stories F001–F010, a tabela priorizada (§7) e o MVP (§8). Note que F009/F010 são **Won't v1** — escopo cortado de propósito, registrado para evitar escopo implícito.

> **Lição de produto:** cada story só entra se ensina um princípio da constituição ou exercita um passo do fluxo. O PO **corta** para proteger o tempo de desenvolvimento.

---

## Etapa 2 — Design: decida antes de codar

**Skill:** `/design-flow <decisão>` · **Agentes:** 2–3 `tl-*` em paralelo (ângulos divergentes) → síntese em ADR

Para cada decisão com mais de um caminho plausível e custo de reverter alto, gere abordagens **independentes**, compare por critérios explícitos e registre a escolha num **ADR versionado**. Não produz código — produz a decisão que alimenta o sprint.

**Artefatos produzidos:** [`specs/adr/`](../specs/adr/) — neste projeto:
- **ADR-0001** stack (FastAPI + Angular, polyglot para ensinar contract test cross-language)
- **ADR-0002** paginação keyset/cursor vs offset
- **ADR-0003** persistência SQLite vs in-memory
- **ADR-0004** publicar **sem autenticação** (transição de estado aberta; P-04 via allowlist de leitura)
- **ADR-0005** codegen de tipos do frontend a partir do OpenAPI
- **ADR-0006** observabilidade local mínima (log estruturado + request_id)

> **Lição de design:** o ADR registra **alternativas, critérios e consequências** — e ganha uma **§8 de refinamentos** quando o painel de revisão endurece a decisão. Decisão que fica só no chat se perde.

---

## Etapa 3 — Sprint: do backlog ao código revisado

**Skill:** `/sprint-flow <escopo>` · **Agentes:** `po` (fatia) → `tl-*` (detalham) → `review-loop` (executa) → retrospectiva

O `sprint-flow` é o guarda-chuva. Ele encadeia quatro sub-passos — e é onde a **separação de papéis** acontece: **PO decide o quê/quando, TL decide como, o review-loop faz acontecer (com revisão), a retrospectiva aprende.**

### 3a. Fatiamento (PO)
O PO prioriza (MoSCoW), define o MVP e aloca cada tarefa a uma sprint, respeitando dependências.
**Artefato:** a tabela `Sprint | Task | Papel/Stack | MoSCoW | Depende de | Estimativa`. Antes de abrir uma sprint, feche a anterior com **aceite formal** → [`specs/governance/aceite-po-sprint-01.md`](../specs/governance/).

### 3b. Detalhamento técnico (Tech Leads)
Cada `tl-*` (e o `tl-qa` para testes/invariantes/gates) detalha tecnicamente as tarefas da sprint, produzindo specs **DETAIL** com design, impacto em testes/gates, riscos e uma **Definition of Done verificável**.
**Artefatos:** [`specs/tasks/sprint-02/`](../specs/tasks/sprint-02/) e [`specs/tasks/sprint-03/`](../specs/tasks/sprint-03/) — um `DETAIL-T-*.md` por tarefa **técnica** (tarefas puramente de doc/produto, como este próprio guia F008, não têm DETAIL técnico).

> **Lição de processo:** se a decisão real do código divergir do DETAIL (ex.: `add` virou UPSERT na T-S2-04), **reconcilie a spec ao código aprovado** — divergência spec×código é bug (P-02).

### 3c. Execução de cada tarefa
Ver a Etapa 4 (review-loop).

### 3d. Retrospectiva
Ver a Etapa 5.

> **Regra de ouro do sprint-flow:** plano antes de código. Não acione o review-loop antes de o plano de sprint estar aprovado e os DETAIL escritos.

---

## Etapa 4 — Review-loop: implementar → revisar → corrigir

**Skill:** `/review-loop <tarefa>` · **Agentes:** `dev-*` (ou `qa`) implementa → `tl-*` + `tl-qa` revisam → repete até zero ressalvas

É o **motor de execução** (reusado por bug-flow, debt-flow, etc.). Para cada DETAIL, na ordem de dependências:
1. O **desenvolvedor** da stack implementa + escreve testes + roda lint/typecheck/testes.
2. Os **tech leads** (de stack + `tl-qa`) fazem code review **read-only** e dão veredito `APROVADO` / `RESSALVAS`.
3. Enquanto houver ressalva bloqueante, volta ao passo 1. Após **3 falhas** do mesmo agente, escala para o **especialista** (`spec-*`).

**O que o review-loop pega que a cobertura sozinha não pega** (exemplos reais deste projeto):
- write-once de idempotência quebrado no adapter in-memory (P-03);
- race de concorrência: dois adapters com locks separados na mesma conexão SQLite;
- colisão de chave de idempotência entre rotas (`POST` vs `PUT publish`);
- gate de CI **inerte** (workflow na subpasta errada; o GitHub só lê a raiz);
- gate de contrato **teatro** (codegen lia um JSON à mão, não o app vivo);
- fixture **infiel ao wire** (campo `total` que o contrato keyset não tem) escondida por falta de gate `tsc`.

> **Regra de ouro do review-loop:** revisão estática não basta — **rode os testes de verdade**, cobrindo o **wiring de produção** (não um dublê). Só conte como verde com execução real.

---

## Etapa 5 — Retrospectiva: o aprendizado persiste

**Parte do `/sprint-flow`** · **Curadoria:** o orquestrador (com insumo de `po` e `tl-qa`)

Ao fim da sprint, os aprendizados vão para **dois destinos coerentes entre si**:
1. **Memória local do agente** (fora do repo, lida na recall de sessões futuras) — um fato por arquivo.
2. **Doc versionado no repo** → [`docs/retrospectivas/`](retrospectivas/) (`sprint-01.md`, `sprint-02.md`, `sprint-03.md`).

E o que for **generalizável** (valeria em outro projeto da mesma classe) é **destilado e promovido** para os playbooks de papel → [`docs/lessons/`](lessons/) (`qa.md`, `python.md`, `sre.md`, `process.md`, `security.md`), seguindo as regras do [`lessons/README.md`](lessons/README.md).

> **Regra de ouro da retrospectiva:** o que é específico do projeto fica na memória local; só o **princípio load-bearing** sobe para o playbook global (poluir o global degrada agentes em toda parte).

---

## Checklist de aprendizado (M4) — você entendeu o essencial?

Ao concluir a trilha, você deve conseguir explicar, com suas palavras:

- [ ] **Quality gate ratchet:** o piso de cobertura **só sobe, nunca desce** sem ADR; nasce no **patamar realmente atingido** (folga ≤1pp), não num número redondo; e é medido **por categoria/arquivo de risco**, não só na média global (senão um módulo fraco se esconde na média). Veja `backend/coverage-gates.sh` e os thresholds por-arquivo em `frontend/vitest.config.ts`.
- [ ] **Por que a regressão nasce vermelha (red-green):** todo fix/feature começa por um teste que **falha antes** e passa depois. A prova de que um teste vale é a **mutação-âncora**: reverter o código de produção tem de deixar o teste **vermelho** — e a mutação precisa atacar a invariante que o teste *alega* proteger.
- [ ] **Gate que morde ≠ gate inerte:** um gate só conta quando aparece **rodando no CI** e **reprova de verdade** quando a violação é plantada (prove red-green). Workflow na pasta errada, sentinela morta sob `set -e`, ou `ruff format` no lugar de `ruff check` são gates que *parecem* existir e não existem.
- [ ] **Anti-falso-verde:** a suíte pode estar verde sem provar nada — assert sobre **estado/efeito** (não só status HTTP), teste o **wiring de produção** (não um dublê), e desconfie de fixture que espelha o contrato **errado**.
- [ ] **A spec manda (P-02):** comportamento muda → a spec muda **antes**; divergência código×spec é bug.

Se você consegue defender esses cinco pontos olhando os artefatos reais deste repo, percorreu a trilha. 🎓

---

## Atalho: comandos na ordem

```bash
/discovery-flow <sua ideia>      # → backlog refinado
/design-flow <decisão aberta>    # → ADR(s) versionado(s)   (repita por decisão)
/sprint-flow <escopo>            # → plano + DETAILs + execução + retrospectiva
   # dentro dele, por tarefa:
   /review-loop <DETAIL>         # → código revisado, testes verdes, gates mordendo
```

Manutenção (fora do fluxo de feature): `/bug-flow`, `/debt-flow`, `/coverage-flow`, `/hardening-flow`, `/hotfix-flow`.
