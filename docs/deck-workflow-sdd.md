---
marp: true
theme: default
paginate: true
size: 16:9
title: workflow-sdd-agents
description: Um repositório-base de Spec-Driven Development operado por um time de agentes de IA
style: |
  :root {
    --ink: #14202b;
    --paper: #eef0f3;
    --accent: #b8862b;      /* ouro de selo / documento oficial */
    --pass: #2f8f63;        /* gate passa */
    --bite: #b8433a;        /* gate morde */
    --muted: #5c6b78;
  }
  section {
    background: var(--paper);
    color: var(--ink);
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 26px;
    padding: 60px 70px;
  }
  h1, h2 {
    font-family: Georgia, "Iowan Old Style", "Times New Roman", serif;
    color: var(--ink);
    letter-spacing: -0.01em;
  }
  h1 { font-size: 52px; line-height: 1.05; }
  h2 { font-size: 40px; border-bottom: 2px solid var(--accent); padding-bottom: 12px; }
  strong { color: var(--accent); }
  code { font-family: "Cascadia Code", ui-monospace, "Consolas", monospace; background: #dfe3e8; padding: 2px 7px; border-radius: 4px; font-size: 0.85em; }
  .eyebrow { font-family: "Cascadia Code", ui-monospace, monospace; text-transform: uppercase; letter-spacing: 0.18em; font-size: 15px; color: var(--accent); }
  section::after { color: var(--muted); font-family: "Cascadia Code", ui-monospace, monospace; }
  table { font-size: 20px; }
  th { color: var(--accent); border-bottom: 2px solid var(--accent); }
  .lead h1 { font-size: 62px; }
  blockquote { border-left: 4px solid var(--accent); color: var(--muted); font-style: italic; }
---

<!-- _class: lead -->

<span class="eyebrow">Spec-Driven Development · time de agentes</span>

# workflow-sdd-agents

### Velocidade **com** rigor — IA operando dentro de um contrato de engenharia.

> "A spec manda."

---

## O problema

Todo mundo já viu IA **gerar** código rápido.

O difícil não é gerar — é **governar**.

- Como garantir que respeita a arquitetura?
- Como garantir cobertura de teste que não é fachada?
- Como respeitar as decisões que o time já tomou?

**Tese:** SDD + time de agentes + quality gates = velocidade *com* rigor, auditável de ponta a ponta.

---

## O que é este repositório

Não é uma aplicação. É um **projeto-base** — um template do qual novos projetos nascem já com rigor de zero.

| Diretório | O que é |
|---|---|
| `specs/` | A fonte da verdade — constituição, ADRs, requisitos |
| `.claude/skills/` | 9 fluxos de orquestração multi-agente |
| `.claude/agents/` | 19 agentes (PO, TLs, devs, QA, SRE, spec-\*) |
| `docs/lessons/` | Playbooks que os agentes leem antes de decidir |
| `backend/` + `frontend/` | App-exemplo `blog-tutorial` (poliglota **de propósito**) |

O blog é pretexto. O cliente real é o **dev-aprendiz**.

---

## A Constituição — a lei do projeto

14 princípios invioláveis. Prevalece sobre qualquer documento. Mudar exige revisão **PO + TL + SRE + QA** e bump major.

- **P-02** — A spec é a fonte da verdade. Divergência código × spec **é bug**.
- **P-07** — Cobertura por categoria de risco, com **gate ratchet** (só sobe).
- **P-03** — Idempotência obrigatória em escrita.
- **P-11** — Falha explícita > falha silenciosa.
- **P-13** — Definition of Done é vinculante.
- **P-14** — Toda decisão vira ADR ("arquivar, não remover").

---

## O ciclo de vida orquestrado

```
ideia crua
  ├─ /discovery-flow  → backlog (épicos, stories, MoSCoW, MVP)
  ├─ /design-flow     → ADR versionado (painel de Tech Leads)
  ├─ /sprint-flow     → plano por sprint + specs DETAIL
  │      └─ /review-loop → código + testes (implementa→revisa→corrige)
  └─ retrospectiva    → docs/ + memória do agente + lessons/
```

Cada **skill** é um fluxo que coordena vários agentes.

---

## As 9 Skills

| Skill | Função |
|---|---|
| **discovery-flow** | demanda crua → backlog |
| **sprint-flow** | fatia, detalha, executa, retrospectiva |
| **review-loop** | implementa → revisa → corrige até zero ressalvas |
| **design-flow** | decisão de arquitetura → ADR |
| **bug-flow** | correção dirigida por teste (regressão nasce vermelha) |
| **debt-flow** | refactor preservando comportamento |
| **coverage-flow** | sobe cobertura sem tocar produção |
| **hardening-flow** | revisão de segurança por risco |
| **hotfix-flow** | caminho rápido para incidente |

`review-loop`: escala ao **especialista após 3 falhas** · exige **execução real** dos testes.

---

## O time de agentes — separação de papéis

```
PO          decide  →  O QUÊ / QUANDO      product-owner, po
Tech Lead   decide  →  O COMO              tl-python · tl-java · tl-go
                                           tl-frontend · tl-qa
Dev / QA    fazem   →  ACONTECER           dev-* · qa · qa-automator
Especialista        →  ESCALADA (3 ciclos) spec-*
SRE                 →  INFRA / INCIDENTE   sre
Retrospectiva       →  APRENDE
```

**Ninguém acumula decisão e execução.**

Regra de ouro: não paralelizar agentes que escrevem no **mesmo repo + banco** (contaminação).

---

## O caminho feliz — da ideia ao código

| # | Skill | Agentes | Artefato |
|---|---|---|---|
| **1** | `/discovery-flow` | product-owner · po · tl-qa | `specs/backlog-blog-tutorial.md` |
| **2** | `/design-flow` | painel tl-python · tl-frontend · tl-qa | `specs/adr/ADR-000X.md` |
| **3** | `/sprint-flow` | po → tl-\* (DETAIL) | `specs/tasks/sprint-NN/DETAIL-*.md` |
| **4** | `/review-loop` | dev-\* → tl-\* · tl-qa → spec-\* | `backend/` + `frontend/` · testes · gates verdes |
| **5** | `↺ retrospectiva` | no `/sprint-flow` · memória + doc | `docs/retrospectivas/` + `docs/lessons/` |

**Prompts de exemplo (o que você digita):**

```
❯ /discovery-flow um blog: autores criam rascunhos e publicam; leitores leem posts
❯ /design-flow paginação da listagem — offset vs keyset/cursor
❯ /sprint-flow planejar a Sprint 2 a partir do backlog
❯ /review-loop implementar Post.publish idempotente (T-S2-05)
❯ /sprint-flow fazer a retrospectiva da Sprint 2
```

---

## Quality Gates — o coração do rigor

Um teste que passa não prova nada se o gate não **morde**.

- **Gate ratchet** — cobertura só sobe; patamar real medido, nunca número redondo.
- **Piso por categoria de risco** — 7 categorias (domínio, idempotência, isolamento, adapter-sqlite, api-router, error-handlers, observabilidade) — **gate AND**, nunca média global.
- **Sentinela anti-glob-vazio** — 0 statements **reprova**, não passa vacuamente.
- **Red-green** — a regressão nasce vermelha *antes* do fix (é a DoD).
- **Contract test cross-language** — drift do OpenAPI quebra o CI.

---

## A aplicação-exemplo — SDD na prática

- **Backend** (`backend/`) — Python + FastAPI, arquitetura **hexagonal**. Post com máquina de estados `draft→published` idempotente, relógio injetado.
- **Frontend** (`frontend/`) — Angular 19 signals, tipos **auto-gerados** do contrato OpenAPI.
- **Poliglota de propósito** (ADR-0001) — duas linguagens para ensinar contract test cross-stack.

O fio que amarra tudo:

`story → ADR → spec DETAIL → código + teste → retrospectiva`

---

## Aprendizado que persiste

O que separa isto de uma automação qualquer: o time **aprende**.

- Toda sprint fecha com **retrospectiva** em dois lugares coerentes — memória do agente + doc versionado.
- O generalizável é destilado e promovido para `docs/lessons/` (`process`, `python`, `qa`, `security`, `sre`).
- Lidos pelos agentes **antes de decidir**. Regra: datar e **confrontar com o código** (lições envelhecem).

---

<!-- _class: lead -->

## Por que isso importa

Não é IA escrevendo código mais rápido.

É IA operando dentro de um **contrato de engenharia** — auditável de ponta a ponta.

1. **A spec manda** — comportamento muda na spec primeiro.
2. **O gate morde** — verde só vale se reprova quando devia.
3. **O time aprende** — cada sprint deixa o próximo mais forte.

---

<!-- _class: lead -->

<span class="eyebrow">Demo ao vivo</span>

# Vamos ver o gate morder

`constitution (P-07)` → `backlog` → `ADR` → `DETAIL` → `código`
→ `pytest` (verde) → `bash coverage-gates.sh`
→ **apagar um teste crítico** → o gate reprova.
