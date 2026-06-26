# ADR-0001 — Stack do blog-exemplo: backend em Python (FastAPI) + frontend em Angular

**Status:** Aceito · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-24
**Autor:** design-flow (orquestrador) · painel: `tl-python`, `tl-frontend`, `tl-qa`
**Revisores requeridos:** Tech Lead Backend + Tech Lead Frontend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** `specs/backlog-blog-tutorial.md` (blog-exemplo didático) · `specs/_templates/006-architecture.md`

---

## 1. Contexto

O projeto-base precisa de um **projeto-exemplo** — um blog simples — cujo propósito **não é servir tráfego**, e sim **ensinar desenvolvedores a usar o fluxo SDD** (specs → contrato → implementação → review-loop → gates → retrospectiva) e a ver o time de agentes atuando. O domínio (Post, Author, Comment) é deliberadamente trivial: a complexidade que se quer exibir é a da **disciplina de engenharia** (princípios P-01 a P-14), não a do negócio.

Por ser material didático, o **critério dominante é clareza pedagógica e mapeamento 1:1 com os princípios da constitution**, não throughput, custo de runtime ou sofisticação. A decisão de stack é durável: reescrever o exemplo depois de o conteúdo de ensino estar montado sairia caro (specs, features, retrospectiva e guias passam a referenciá-lo).

**Restrições:**
- O time de agentes já cobre Python, Angular, Java, Go e QA (`.claude/agents/`).
- O exemplo deve **demonstrar a constitution sem violá-la** — em especial P-01 (API-First), P-03 (idempotência), P-04 (autorização), P-05 (observabilidade), P-07 (cobertura ratchet), P-11 (falha explícita), P-13 (DoD).
- Toolchains devem ser **pinados** (gate de lint/build pinado é bloqueante — `CLAUDE.md`).

## 2. Alternativas consideradas

| Alternativa | Prós (para ENSINO) | Contras (para ENSINO) |
|---|---|---|
| **A. Backend Python/FastAPI + Frontend Angular** _(escolhida)_ | OpenAPI gerado do código (P-01 vivo em `/docs`); cada princípio vira peça pequena e nomeável (dependency de idempotência, middleware RED, portas/Protocol); Angular opinativo dá **forma canônica copiável** (service tipado + interceptor) onde P-01/P-04/P-11 se materializam; ambas altamente testáveis | Repo **polyglot**: duas toolchains e dois gates de CI; Angular é "pesado" para um blog; Python tem tipagem dinâmica (mitigável) |
| **B. Full-stack TypeScript (Node/Nest + Angular/React)** | Uma só linguagem; menos atrito de ambiente; contrato compartilhável em TS | **Perde o contraste poliglota** que o base quer ensinar (SDD independe de linguagem); Nest traz cerimônia de decorators/módulos comparável a Spring; perde a lição de **contract test cross-language** |
| **C. Full-stack Python (FastAPI servindo HTML/SSR)** | Stack única, mínimo build, máxima transparência | Sem camada de serviço tipada no front, a separação UI↔negócio fica por disciplina, não por estrutura; ensina menos arquitetura de app real; perde a costura de contrato entre fronteiras |
| **D. Backend Java/Spring ou Go** | Robustos em produção; `tl-java`/`tl-go` disponíveis | Ratio cerimônia/conceito alto (Spring) ou OpenAPI manual enfraquecendo P-01 (Go); melhor como **segundo exemplo** (mostrar SDD poliglota), não como o primeiro didático |

## 3. Critérios de decisão

Pesos enviesados para o objetivo didático (não para produção):

| Critério | Peso | Por quê |
|---|---|---|
| Clareza pedagógica / densidade conceito-por-linha | **Alto** | O artefato é material de aula; cada princípio deve ser legível numa leitura |
| Aderência à constitution (P-01/03/04/05/11/12) demonstrável | **Alto** | O exemplo existe para *mostrar* os princípios |
| Testabilidade e custo dos quality gates (P-07/P-13) | **Alto** | O exemplo ensina os gates funcionando de verdade |
| Reversibilidade / evolução (P-06/P-12) | Médio | Trocar adapter/integração sem tocar o domínio é, ele mesmo, uma lição |
| Familiaridade do time de agentes | Médio | Reduz atrito de execução nas skills |
| Performance / escala | **Baixo** | Irrelevante para um blog didático — registrado como dívida honesta |

## 4. Decisão

**Escolhida: Alternativa A — backend Python (FastAPI + Pydantic v2 + Uvicorn) + frontend Angular (standalone, signals-first, deliberadamente magro).**

Os três ângulos do painel **convergiram** para esta combinação, cada um por sua razão:

- **Backend FastAPI** porque converte o **máximo de princípios em peças pequenas, nomeáveis e testáveis com o mínimo de cerimônia**: OpenAPI gerado (P-01 vivo em `/docs`), dependency `Idempotency-Key` nas rotas de escrita (P-03), dependency de autor para autorização server-side (P-04), middleware ASGI único para RED + `request_id` (P-05), `422` Pydantic + handler de domínio → *Problem Details* RFC 9457 (P-11), e **portas via `Protocol`** com adapter injetado (P-12). A escolha **não** é "o mais moderno" — é a maior densidade conceito-por-linha para um leitor aprendiz.
- **Frontend Angular** porque, para um **template de ensino reusável**, vale mais ser **opinativo e copiável** do que leve: Angular já impõe DI, `HttpClient` e camada de serviço — exatamente os ganchos onde os princípios se materializam. O **service tipado** é o único ponto que fala HTTP (componente fica "burro" de propósito → empurra o aprendiz a manter negócio na API), e o **HttpInterceptor** traduz HTTP em erro tipado (P-11) e centraliza o prefixo `/v1` (P-08).
- **Polyglot** porque ele **ensina o que um monolito single-stack não consegue**: pirâmide de testes por stack, **contract test entre fronteiras de linguagem**, e DoD que exige verde dos dois lados.

**Inegociável (condições do `tl-qa` que entram como parte da decisão, não como detalhe):**

1. **Gate de cobertura ratchet POR STACK** (`pytest --cov` de um lado, `ng test`/Vitest do outro), barrado separadamente no CI. **Proibida média global combinada** — ela mascara um lado fraco (back 95% + front 40% ≈ 78% "verde" com metade descoberta). É falso-verde estrutural.
2. **Contract test derivado de schema único** (OpenAPI de `005-api-contract.md`): os tipos e mocks do front são gerados/validados a partir do **mesmo** schema do back. Mutar um campo no back **tem** que deixar o contract test vermelho — senão é teatro. Esta é a trava anti-drift do polyglot.

**Magro de propósito** (adicionar qualquer item abaixo exige novo ADR):
- Backend: sem ORM pesado no MVP — domínio puro + adapter in-memory/SQLite **claramente marcado como didático**.
- Frontend: **sem** NgRx/state manager global, SSR/Universal, PWA, Storybook, design system. Signals + service resolvem.
- E2E (Playwright): **1–2 fluxos** críticos (ex.: criar post → aparecer na listagem), não cobertura exaustiva.

## 5. Consequências

- **Positivas:**
  - Cada princípio da constitution vira uma **peça pequena e apontável** em sala (idempotency dependency, RED middleware, porta/Protocol, service tipado, interceptor).
  - DoD (P-13) sai quase "de graça": `/docs` publica a referência de API, RED instrumentado dia-1, `TestClient`/`HttpTestingController` fazem **teste HTTP real** (cobrem o wiring de DI).
  - Ensina genuinamente a **costura de contrato cross-language** — a lição mais valiosa do arranjo.
- **Negativas / custo assumido:**
  - **Polyglot** = duas toolchains pinadas (`uv`/`ruff`/`pytest` + Node/`eslint`/`ng`), dois jobs de CI, e o risco permanente de **contract drift** entre linguagens — endereçado pela condição 2.
  - Angular é "pesado" para um blog e tem curva inicial maior (mitigado cortando o MVP até o osso); Python não é stack de alto throughput (irrelevante aqui, mas registrado).
  - Material didático tende a ser copiado: o repo in-memory/SQLite **precisa** estar marcado como didático para não virar produção.
- **Impacto em specs/código:**
  - `specs/_templates/006-architecture.md` → `specs/006-architecture.md` deve registrar: FastAPI hexagonal leve (domain/application/infrastructure/interfaces) + Angular standalone (api/ services/ components/).
  - `005-api-contract.md` é a **fonte única** do contrato (OpenAPI), consumida pelo gerador de tipos do front.
- **Impacto em testes/gates:**
  - Dois ratchets independentes (P-07); CI com **gate AND** (merge bloqueia se qualquer job reprovar); secret-scan transversal (P-10) sobre o repo inteiro.
  - Dependência de integração ausente em CI deve **falhar, não `skip`** (skip mascara "integração não rodou" → falso-verde).
  - `.pre-commit-config.yaml`: descomentar e **pinar** os blocos ruff (Python) e eslint (JS/TS) na versão do CI.

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- O objetivo do exemplo deixar de ser didático e passar a haver requisito de **produção/escala** real.
- For decidido criar um **segundo exemplo** noutra stack (Java/Go) para demonstrar SDD poliglota — não substitui este, gera ADR próprio.
- O custo de manter **duas toolchains** no CI superar o valor pedagógico (ex.: flaky crônico de ambiente apesar do pin).
- Surgir geração de tipos OpenAPI→TS instável a ponto de o contract test deixar de ser confiável.

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Tech Lead Backend | `tl-python` | 2026-06-24 | Aprovado — FastAPI + Pydantic v2 |
| Tech Lead Frontend | `tl-frontend` | 2026-06-24 | Aprovado — Angular standalone, signals, magro |
| Tech Lead QA | `tl-qa` | 2026-06-24 | Aprovado **com condições** — ratchet por-stack + contract test de schema único (ambas incorporadas à §4) |
