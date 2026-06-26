# Agentes do projeto

Time de agentes versionado **dentro do repositório** (`.claude/agents/`). Como este é um projeto-base, todo projeto que nascer dele já vem com este time — sem depender de configuração global da máquina. O Claude Code descobre cada agente pelo `subagent_type` (o nome da pasta) e as skills de orquestração (`.claude/skills/`) os acionam automaticamente.

## Como são usados

- **Diretamente:** invoque pelo `subagent_type` (ex.: acionar `tl-python` para um code review backend).
- **Via skills:** os fluxos em `.claude/skills/` (`sprint-flow`, `review-loop`, `bug-flow`, …) já mapeiam a stack da tarefa para o agente certo. Prefira acionar a skill — ela orquestra o time.
- **Conhecimento compartilhado:** os agentes leem os playbooks destilados em [`docs/lessons/`](../../docs/lessons/) antes de decidir, e confrontam cada lição com o código atual.

## Time disponível

### Tech Leads — arquitetura, code review, mentoria (model: opus)
| subagent_type | Stack / foco |
|---|---|
| `tl-python`   | Backend Python: pipelines, automação, segurança, PEP 8, pytest |
| `tl-java`     | Spring Boot, JPA/Hibernate, DDD, Clean Architecture |
| `tl-go`       | APIs Go, concorrência, performance, padrões idiomáticos |
| `tl-frontend` | Performance, a11y (WCAG), OWASP, Web Vitals |
| `tl-qa`       | Estratégia de testes, quality gates, testabilidade, governança |

### Desenvolvedores — implementação, testes, refatoração (model: sonnet)
| subagent_type | Stack |
|---|---|
| `dev-python`   | Automação, pipelines, serverless, pytest |
| `dev-java`     | Spring Boot, JPA, APIs REST, testes |
| `dev-go`       | net/http, AWS SDK, Lambda, testes |
| `dev-frontend` | Angular/TS, signals, RxJS, testes |

### Especialistas — escalonamento após 3 ciclos sem sucesso (model: opus)
| subagent_type | Stack |
|---|---|
| `spec-python` · `spec-java` · `spec-go` · `spec-frontend` · `spec-qa` | mesma stack do `dev-*`/`qa`, com mandato de destravar |

### Produto & Qualidade
| subagent_type | Foco |
|---|---|
| `product-owner` | Discovery completo, roadmap, métricas, PRD (opus) |
| `po`            | Refinamento rápido, stories, MoSCoW, MVP (opus) |
| `qa-automator`  | Testes automatizados, edge cases, Vitest/Playwright (opus) |
| `qa`            | Testes multi-stack, planos de teste, cobertura (sonnet) |

### Infraestrutura
| subagent_type | Foco |
|---|---|
| `sre` | AWS, Terraform, CI/CD, observabilidade, hardening (opus) |

## Convenções

- **Um papel por pasta.** O `AGENT.md` é o system prompt do agente; o nome da pasta é o `subagent_type`.
- **Não paralelize agentes que escrevem no mesmo repo + banco** (ver [`docs/lessons/process.md`](../../docs/lessons/process.md)). Serialize ou isole com worktree.
- **Lições são in-repo** (`docs/lessons/`) e evoluem na retrospectiva de cada sprint (ver `sprint-flow` §4).
