# Projeto-base — Spec-Driven Development com time de agentes

Este repositório é um **projeto-base (template)**. Projetos novos nascem a partir dele já com o mesmo **rigor técnico de zero**: Spec-Driven Development (SDD), um time de agentes versionado, skills de orquestração e playbooks de engenharia destilados. Copie/clone este repositório, renomeie e comece a preencher as specs — a estrutura de qualidade já vem montada.

## O que vem dentro

| Diretório | O que é |
|---|---|
| [`specs/`](specs/) | SDD: a [constitution](specs/000-constitution.md) (princípios invioláveis, já vigente) + templates de overview, domínio, RFs, NFRs, contrato de API, arquitetura, test-strategy, features (Gherkin), ADRs e tarefas (DETAIL). |
| [`.claude/skills/`](.claude/skills/) | 9 fluxos de orquestração multi-agente: `discovery-flow`, `sprint-flow`, `review-loop`, `bug-flow`, `coverage-flow`, `debt-flow`, `design-flow`, `hardening-flow`, `hotfix-flow`. |
| [`.claude/agents/`](.claude/agents/) | Time de agentes (PO, Tech Leads, Devs, QA, SRE, especialistas) — ver [agents/README](.claude/agents/README.md). |
| [`docs/lessons/`](docs/lessons/) | Playbooks de engenharia destilados (process, python, qa, security, sre) — o piso de rigor, consumido pelos agentes e evoluído nas retrospectivas. |
| [`docs/retrospectivas/`](docs/retrospectivas/), [`docs/runbooks/`](docs/runbooks/), [`docs/quality/`](docs/quality/) | Templates de retrospectiva, runbook operacional e baseline de mutation. |

## Como começar um projeto a partir daqui

1. **Clone e renomeie** este repositório.
2. Leia a [`000-constitution.md`](specs/000-constitution.md) — ela já vale. Adicione princípios do seu domínio como **emendas versionadas**, nunca enfraquecendo um piso.
3. Rode `discovery-flow` para transformar a ideia em backlog refinado (épicos + user stories + critérios de aceite).
4. Copie os templates de `specs/_templates/` para a raiz de `specs/` e preencha overview → domínio → RFs → API → arquitetura → test-strategy.
5. Rode `sprint-flow` para planejar, detalhar (DETAIL) e executar via `review-loop`, fechando com retrospectiva.
6. Decisões de arquitetura saem de `design-flow` → viram ADR em `specs/adr/`.

## O ciclo de trabalho (skills)

```
ideia crua ──discovery-flow──▶ backlog refinado
                                   │
            design-flow ◀──────────┤ (decisões de arquitetura → ADR)
                                   │
backlog ──sprint-flow──▶ plano + DETAIL ──review-loop──▶ implementado+revisado
                                   │                          │
                                   └──── retrospectiva ◀───────┘
                                          │
                          aprendizados → docs/lessons/ + memória local
```

Fluxos de manutenção: `bug-flow` (correção dirigida por teste), `coverage-flow` (subir cobertura), `debt-flow` (refactor preservando comportamento), `hardening-flow` (segurança), `hotfix-flow` (incidente em produção).

---

# Guia das ferramentas (para novos desenvolvedores)

> Regra de ouro: **você quase nunca orquestra na mão.** Descreva o objetivo e deixe a **skill** acionar os **agentes** certos, que por sua vez leem as **lições** e produzem/consomem os **documentos** dos templates. Abaixo, como usar cada peça.

## 1. Skills — os fluxos de orquestração

Uma skill é um fluxo multi-agente pronto. **Como acionar:** digite o comando barra (ex.: `/sprint-flow pagamentos recorrentes`) **ou** simplesmente descreva a intenção em linguagem natural ("vamos planejar a próxima sprint") — o Claude reconhece e aciona a skill. Todas pedem **aprovação do plano antes de escrever código**.

### Espinha dorsal (o caminho feliz de uma entrega)

| Skill | Use quando… | Como acionar | Entra → Sai |
|---|---|---|---|
| **`discovery-flow`** | tem uma ideia/demanda crua ainda não refinada | `/discovery-flow <demanda>` | ideia → backlog: épicos + user stories + critérios de aceite + MVP |
| **`design-flow`** | precisa decidir arquitetura / comparar abordagens antes de codar | `/design-flow <decisão>` | dúvida técnica → **ADR** versionado em `specs/adr/` (painel de Tech Leads) |
| **`sprint-flow`** | quer planejar, fatiar por sprint, detalhar e executar | `/sprint-flow <escopo>` | backlog → plano (MoSCoW) + specs **DETAIL** → execução → **retrospectiva** |
| **`review-loop`** | quer implementar uma tarefa **com revisão** até zerar ressalvas | `/review-loop <tarefa ou DETAIL>` | DETAIL → código implementado, revisado (tl-* + tl-qa) e com testes verdes |

> `sprint-flow` já chama `review-loop` por dentro para cada tarefa; use `review-loop` direto quando tem **uma** tarefa pontual já especificada.

### Manutenção (cada uma entra com uma postura diferente)

| Skill | Use quando… | Como acionar | Postura |
|---|---|---|---|
| **`bug-flow`** | relatou um bug e quer fix **com teste de regressão** | `/bug-flow <bug>` | QA reproduz com teste **vermelho** primeiro → fix via `review-loop` |
| **`debt-flow`** | quer **refatorar/pagar dívida** sem mudar comportamento | `/debt-flow <alvo>` | testes de caracterização fixam o comportamento → refactor não pode alterá-los |
| **`coverage-flow`** | precisa **subir cobertura** de um módulo até o gate | `/coverage-flow <alvo>` | só adiciona testes (prioriza risco); não toca código de produção |
| **`hardening-flow`** | quer **revisão de segurança** e correção por severidade | `/hardening-flow <escopo>` | painel audita superfície de ataque → corrige bloqueantes com teste que prova a falha fechada |
| **`hotfix-flow`** | há **incidente em produção** e o tempo-até-mitigação manda | `/hotfix-flow <incidente>` | SRE diagnostica → fix mínimo → 1 ciclo enxuto → deploy; dívida registrada para depois |

## 2. Agentes — o time que as skills acionam

Os agentes vivem em [`.claude/agents/`](.claude/agents/) e são identificados pelo `subagent_type` (nome da pasta). **Na prática você não precisa chamá-los** — as skills mapeiam a stack da tarefa para o agente certo. Acione um **direto** só para um pedido pontual fora de fluxo (ex.: "peça ao `tl-python` um code review deste módulo").

| Papel | Agentes | Decide / faz |
|---|---|---|
| **Produto** | `po`, `product-owner` | *o quê* e *quando*: discovery, stories, MoSCoW, MVP |
| **Tech Leads** | `tl-python` · `tl-java` · `tl-go` · `tl-frontend` · `tl-qa` | *como*: arquitetura, DETAIL, code review, gates |
| **Desenvolvedores** | `dev-python` · `dev-java` · `dev-go` · `dev-frontend` | implementação + testes |
| **Qualidade** | `qa`, `qa-automator` | testes automatizados, edge cases, planos de teste |
| **Infra** | `sre` | AWS/Terraform/CI-CD, observabilidade, hardening |
| **Especialistas** | `spec-python` · `spec-java` · `spec-go` · `spec-frontend` · `spec-qa` | destravam após 3 ciclos sem sucesso (escalonamento automático do `review-loop`) |

Detalhe e modelos em [`.claude/agents/README.md`](.claude/agents/README.md). Cuidado: **não paralelize** dois agentes que escrevem no mesmo repo+banco (ver lições).

## 3. Lições — o conhecimento que os agentes carregam

[`docs/lessons/`](docs/lessons/) são playbooks de engenharia destilados, **lidos pelos agentes antes de decidir**. Você também deve lê-los antes de uma decisão não trivial — e **confrontar cada lição com o código atual** (lições envelhecem).

| Playbook | Cobre |
|---|---|
| [`process.md`](docs/lessons/process.md) | orquestração, auditoria de specs, **higiene de commit**, paralelismo de agentes |
| [`qa.md`](docs/lessons/qa.md) | quality gates, anti-falso-verde, anti-flaky, red-green |
| [`python.md`](docs/lessons/python.md) | backend: RLS multi-tenant, idempotência, outbox, webhooks, paginação keyset |
| [`security.md`](docs/lessons/security.md) | autorização multi-tenant, secret-scanning, trust store/PKIX |
| [`sre.md`](docs/lessons/sre.md) | IaC, observabilidade, custo (lean vs HA), scheduler/jobs |

As lições **crescem sozinhas**: o passo de retrospectiva do `sprint-flow` destila o que foi aprendido e promove para o playbook do papel (regras em [`docs/lessons/README.md`](docs/lessons/README.md)).

## 4. Documentos & templates — o que preencher e quando

A spec é a fonte da verdade. Cada necessidade tem um template; copie, renomeie e preencha.

| Preciso de… | Template | Vai para |
|---|---|---|
| Visão de produto / MVP / métricas | [`specs/_templates/001-overview.md`](specs/_templates/001-overview.md) | `specs/001-overview.md` |
| Linguagem ubíqua, entidades, invariantes | [`002-domain-model.md`](specs/_templates/002-domain-model.md) | `specs/002-...` |
| Requisitos funcionais (RF-NNN) | [`003-functional-requirements.md`](specs/_templates/003-functional-requirements.md) | `specs/003-...` |
| SLOs/SLIs, observabilidade, capacidade | [`004-non-functional-requirements.md`](specs/_templates/004-non-functional-requirements.md) | `specs/004-...` |
| Contrato de API (REST/eventos) | [`005-api-contract.md`](specs/_templates/005-api-contract.md) | `specs/005-...` |
| Arquitetura, stack, padrões | [`006-architecture.md`](specs/_templates/006-architecture.md) | `specs/006-...` |
| Estratégia de testes e gates | [`007-test-strategy.md`](specs/_templates/007-test-strategy.md) | `specs/007-...` |
| Uma feature com Gherkin (CA-XXX) | [`features/_TEMPLATE-feature.md`](specs/features/_TEMPLATE-feature.md) | `specs/features/F0NN-<slug>.md` |
| Registrar uma decisão de arquitetura | [`adr/_TEMPLATE-adr.md`](specs/adr/_TEMPLATE-adr.md) | `specs/adr/ADR-NNNN-<slug>.md` |
| Detalhar uma tarefa para execução | [`tasks/_TEMPLATE-DETAIL.md`](specs/tasks/_TEMPLATE-DETAIL.md) | `specs/tasks/sprint-NN/DETAIL-T-FNNN-NN.md` |
| Aceite de PO de um release | [`governance/_TEMPLATE-aceite-po.md`](specs/governance/_TEMPLATE-aceite-po.md) | `specs/governance/` |
| Fechar uma sprint | [`docs/retrospectivas/_TEMPLATE.md`](docs/retrospectivas/_TEMPLATE.md) | `docs/retrospectivas/sprint-NN.md` |
| Procedimento operacional | [`docs/runbooks/_TEMPLATE.md`](docs/runbooks/_TEMPLATE.md) | `docs/runbooks/<op>.md` |
| Baseline de mutation | [`docs/quality/_TEMPLATE-mutation-baseline.md`](docs/quality/_TEMPLATE-mutation-baseline.md) | `docs/quality/` |

> Normalmente você **não cria DETAIL/feature na mão** — o `sprint-flow` (TLs) e o `discovery-flow` (PO) os geram a partir destes templates. Use-os manualmente só para um documento avulso.

## 5. Setup do ambiente

```bash
# 1. Hooks de higiene + secret-scan (uma vez por clone)
pipx install pre-commit        # ou: uv tool install pre-commit / pip install pre-commit
pre-commit install

# 2. (opcional) Reaproveitar agentes globais da máquina via symlink, em vez da cópia in-repo
#    Windows (PowerShell como Admin):
#    New-Item -ItemType SymbolicLink -Path .agents -Target C:\Users\<voce>\.claude\agents
```

As skills e os agentes deste repositório são descobertos automaticamente pelo Claude Code por estarem em `.claude/`. Antes do primeiro commit, confirme que o `pre-commit` está ativo (ele roda secret-scan e higiene de EOL/whitespace).

## 6. Um dia de trabalho, de ponta a ponta

```text
1. "Quero permitir reembolso parcial."         → /discovery-flow  → backlog refinado (stories + CAs)
2. "Reembolso síncrono ou via fila?"           → /design-flow     → ADR-0007 decidido
3. "Planeje e execute a sprint de reembolso."  → /sprint-flow     → DETAILs + review-loop por tarefa
   └─ cada tarefa: dev implementa → tl-* + tl-qa revisam → testes verdes → próxima
4. Fim da sprint                                → retrospectiva    → docs/retrospectivas/ + lições promovidas
— Surgiu um bug em produção?                    → /hotfix-flow (mitiga) e depois /bug-flow (regressão)
```

Cada passo respeita os gates: plano aprovado antes de código, regressão nasce vermelha, cobertura só sobe.

---

## Princípios que este base impõe (resumo)

- **Spec é a fonte da verdade** — código segue spec; divergência é bug.
- **API-First**, **idempotência em escrita**, **isolamento de dados**, **observabilidade dia-1**.
- **Cobertura por categoria de risco** com gate **ratchet** (só sobe).
- **Falha explícita > falha silenciosa**; **decisões registradas** (ADR-lite).

Detalhe completo em [`specs/000-constitution.md`](specs/000-constitution.md). Convenções para agentes/Claude Code em [`CLAUDE.md`](CLAUDE.md).
