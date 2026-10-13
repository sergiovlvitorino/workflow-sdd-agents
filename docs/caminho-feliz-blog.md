# Caminho feliz — da ideia ao blog em produção

A espinha dorsal do projeto: **`discovery-flow → design-flow → sprint-flow`** (com `review-loop` como motor e a retrospectiva fechando cada sprint). Os fluxos de manutenção só entram **depois** do MVP, quando surge um bug, dívida ou incidente.

```mermaid
flowchart TB
  classDef idea    fill:#f5f7fa,stroke:#79828f,stroke-width:2px,color:#171b22
  classDef product fill:#e6f4f1,stroke:#0c8577,stroke-width:2px,color:#171b22
  classDef design  fill:#efeafc,stroke:#6741d9,stroke-width:2px,color:#171b22
  classDef sprint  fill:#eef1fd,stroke:#3b5bdb,stroke-width:2px,color:#171b22
  classDef engine  fill:#e6f4f1,stroke:#0c8577,stroke-width:1.5px,color:#171b22
  classDef done    fill:#171b22,stroke:#171b22,stroke-width:2px,color:#ffffff
  classDef maint   fill:#fcefe7,stroke:#d9480f,stroke-width:1.5px,color:#171b22
  classDef learn   fill:#fff9db,stroke:#e8590c,color:#171b22

  IDEIA["💡 <b>Ideia crua</b><br/>'quero um blog-tutorial<br/>de Spec-Driven Development'"]:::idea

  %% ---------- 1. DISCOVERY ----------
  subgraph DISC["1 · discovery-flow — o QUÊ"]
    direction TB
    D1["<b>po / product-owner</b><br/>discovery + decomposição"]:::product
    D2["Backlog refinado<br/>épicos · user stories · CAs<br/>MoSCoW + <b>MVP</b>"]:::product
    D1 --> D2
  end

  %% ---------- 2. DESIGN ----------
  subgraph DES["2 · design-flow — o COMO (arquitetura)"]
    direction TB
    G1["<b>Painel de tl-*</b> (2–3 em paralelo)<br/>abordagens independentes → síntese"]:::design
    G2["ADRs versionados<br/>0001 stack · 0002 keyset · 0003 sqlite<br/>0004 sem-auth · 0005 contrato OpenAPI · 0006 observabilidade"]:::design
    G1 --> G2
  end

  %% ---------- 3. SPRINT ----------
  subgraph SPR["3 · sprint-flow — planejar → executar → aprender"]
    direction TB
    S1["<b>po</b> fatia por sprint<br/>prioriza · aloca · define ordem"]:::sprint
    S2["<b>tl-*</b> + <b>tl-qa</b> detalham<br/>specs DETAIL (design + DoD)"]:::sprint

    subgraph RL["review-loop — motor de execução (por tarefa)"]
      direction LR
      R1["<b>dev-*</b> implementa<br/>+ testes"]:::engine --> R2["<b>tl-*</b> + <b>tl-qa</b><br/>revisam (READ-ONLY)"]:::engine
      R2 -->|"RESSALVAS"| R1
      R2 -->|"3 falhas"| R3["<b>spec-*</b><br/>olhar fresco"]:::engine
      R3 --> R2
    end

    S3["🔁 <b>Retrospectiva</b><br/>memória local + docs/retrospectivas/sprint-NN.md<br/>promove lições → docs/lessons/"]:::learn

    S1 --> S2 --> RL --> S3
  end

  MVP["✅ <b>Blog MVP</b><br/>backend FastAPI (164 testes · 100% cobertura)<br/>frontend Angular 19 · observabilidade · guia da trilha"]:::done

  %% ---------- caminho feliz ----------
  IDEIA --> DISC
  DISC -->|"backlog aprovado"| DES
  DES -->|"decisões travadas"| SPR
  SPR -.->|"S1 fundações → S2 domínio/persistência → S3 frontend+obs"| SPR
  SPR --> MVP

  %% ---------- manutenção: só DEPOIS do MVP ----------
  subgraph MNT["Manutenção — reusa o review-loop, entra sob demanda"]
    direction LR
    M1["bug-flow"]:::maint
    M2["debt-flow"]:::maint
    M3["coverage-flow"]:::maint
    M4["hardening-flow"]:::maint
    M5["hotfix-flow"]:::maint
  end
  MVP -.->|"bug · dívida · gap de cobertura · vuln · incidente"| MNT
  MNT -.->|"cada correção fecha com aprendizado"| S3
```

## Como ler o diagrama

| Etapa | Skill | Produz | Papel decisor |
|-------|-------|--------|----------------|
| **1** | [`discovery-flow`](../.claude/skills/discovery-flow/SKILL.md) | Backlog refinado + MVP (`specs/features/`) | `po` decide **o quê** |
| **2** | [`design-flow`](../.claude/skills/design-flow/SKILL.md) | ADRs versionados (`specs/adr/`) — decisão **antes** do código | painel de `tl-*` decide **como** |
| **3** | [`sprint-flow`](../.claude/skills/sprint-flow/SKILL.md) | Sprints executadas + retrospectiva | `po` fatia · `tl-*` detalham · `review-loop` faz acontecer |
| motor | [`review-loop`](../.claude/skills/review-loop/SKILL.md) | Código + testes verdes, revisado | `dev-*` implementa · `tl-*`/`tl-qa` revisam |

**Regras do caminho feliz** (do [`CLAUDE.md`](../CLAUDE.md)):

- **Sequência, não pulo:** só entra em `design-flow` com backlog aprovado; só entra em `sprint-flow` com as decisões travadas em ADR; só aciona `review-loop` com o plano aprovado e os DETAIL prontos.
- **Produto antes de engenharia:** o `po` decide *o quê/quando*, o `tl-*` decide *como* — um não redefine o escopo do outro.
- **Cada sprint fecha aprendendo:** a retrospectiva grava nos dois destinos e promove o generalizável para `docs/lessons/` (ver [`loop-aprendizado.md`](loop-aprendizado.md)).
- **Manutenção é ramo, não tronco:** `bug-/debt-/coverage-/hardening-/hotfix-flow` reusam o `review-loop`, entram sob demanda depois do MVP e também fecham com aprendizado.

## O blog, concretamente (3 sprints)

- **Sprint 1** — fundações: contrato da API + esqueleto (`F001`, `F003`).
- **Sprint 2** — domínio e persistência: adapter SQLite, publish (interface/aplicação), read-by-id, 1º ratchet de cobertura backend.
- **Sprint 3** — entrega do MVP: frontend Angular 19 (codegen de tipos do OpenAPI vivo — `ADR-0005`), observabilidade (`ADR-0006`), healthcheck e o guia da trilha.

---

**Fontes:** [`specs/adr/`](../specs/adr/) · [`specs/tasks/`](../specs/tasks/) · [`docs/retrospectivas/`](retrospectivas/) · [`CLAUDE.md`](../CLAUDE.md)
