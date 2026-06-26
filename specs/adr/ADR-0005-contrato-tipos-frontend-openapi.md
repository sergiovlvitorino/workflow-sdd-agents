# ADR-0005 — Contrato de tipos Frontend↔Backend: codegen a partir do OpenAPI

**Status:** Aceito _(com refinamentos do painel — ver §8)_ · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-25
**Autor:** design-flow (orquestrador-sintetizador)
**Revisores requeridos:** Tech Lead Frontend + Tech Lead Backend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** ADR-0001 (polyglot intencional, contract test cross-language) · `specs/005-api-contract.md` (fonte do contrato) · P-01 (API-First) · P-06 (compatibilidade)

---

## 1. Contexto

ADR-0001 escolheu um stack polyglot (FastAPI + Angular) **de propósito**, para ensinar contract test cross-language: um contrato único consumido por duas linguagens. Quando o frontend Angular entrar (Sprint 2+), surge a pergunta operacional: **como manter os tipos TypeScript em sincronia com o contrato `/v1`** definido em `005-api-contract.md`?

O FastAPI já publica um documento **OpenAPI** derivado dos schemas Pydantic (em `/openapi.json` e `/docs`). A decisão é se aproveitamos essa fonte única ou se duplicamos a verdade do lado do front.

Decidir antes de escrever o front evita o cenário clássico de drift: tipos TS escritos à mão que silenciosamente divergem do backend e só quebram em runtime.

**Forças:**
- Fonte única da verdade (P-01 API-First; P-02 spec é a verdade).
- Detecção de drift em build, não em runtime.
- Objetivo didático declarado no ADR-0001 (contract test cross-language).
- Simplicidade local (sem pipeline pesado).

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. Codegen a partir do OpenAPI** _(escolhida)_ | Fonte única (o OpenAPI que o FastAPI já gera); drift vira erro de compilação TS, não bug de runtime; materializa o "contract test cross-language" do ADR-0001; regenerar é um comando | + uma ferramenta no fluxo de build do front (ex.: `openapi-typescript`); tipos gerados não devem ser editados à mão |
| **B. Tipos TS escritos à mão** | Zero ferramenta; controle total | Duplica a verdade — duas fontes que divergem em silêncio; contradiz P-01/P-02; perde o objetivo didático |
| **C. Schema compartilhado custom (IDL próprio)** | Neutro de linguagem | Overkill para um exemplo; reinventa o que o OpenAPI já entrega de graça |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Fonte única da verdade (P-01/P-02) | **Alto** | O contrato `005` deve mandar; front não pode ter verdade paralela |
| Detecção de drift em build | **Alto** | Quebra cedo, não em runtime na frente do aluno |
| Aderência ao objetivo didático (ADR-0001) | **Alto** | O projeto existe para ensinar este padrão |
| Simplicidade local de tooling | Médio | Não pode virar pipeline pesado |

## 4. Decisão

**Escolhida: Alternativa A — geração de tipos TypeScript a partir do OpenAPI do FastAPI.**

O front gera seus tipos a partir do `/openapi.json` (via `openapi-typescript` ou equivalente leve). Os tipos gerados são **artefato derivado**: versionados ou não, mas **nunca editados à mão**. Um script de geração documentado (`npm run gen:api` ou similar) reproduz os tipos a partir do contrato vigente.

Inegociável:
- O OpenAPI é **derivado dos schemas Pydantic** — ou seja, o backend (P-01 API-First) continua sendo a origem; o front é consumidor.
- Drift detectado em build (tipos gerados desatualizados) é **falha**, não aviso — coerente com P-11.

> **Nota — possível spike:** se na primeira integração a geração se mostrar instável ou ruidosa (problema já antecipado nos gatilhos do ADR-0001), faz-se um **spike time-boxed** comparando ferramentas antes de cravar a escolha de tooling. A *decisão de princípio* (codegen, não tipos à mão) permanece; o que o spike resolve é **qual** gerador.

## 5. Consequências

- **Positivas:** contrato único de ponta a ponta; mudança no backend que quebra o front aparece como erro de compilação TS; o exemplo ensina o padrão correto de contract-first cross-language.
- **Negativas / custo assumido:** dependência de uma ferramenta de codegen no front; disciplina de "não editar o arquivo gerado"; necessidade de rodar a geração quando o contrato muda.
- **Impacto em specs/código:** quando o front entrar, adiciona-se o passo de geração ao seu `package.json`; `007-test-strategy.md` ativa o contract test cross-language já previsto; `005` permanece a fonte.
- **Impacto em testes/gates:** ativa o segundo ratchet (front) em gate AND com o backend (já previsto em `004`/`007`); teste/checagem de que os tipos gerados estão atualizados com o `005` vigente.

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- A geração de tipos OpenAPI→TS se mostrar comprovadamente instável mesmo após o spike (gatilho herdado do ADR-0001).
- O projeto adotar GraphQL ou outro paradigma de contrato que torne o OpenAPI inadequado.

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Tech Lead Frontend | `tl-frontend` | 2026-06-25 | Aprovado com ressalvas — tooling e localização dos tipos em §8 |
| Tech Lead QA | `tl-qa` | 2026-06-25 | Reprovado **como gate** → resolvido: §8 adiciona o mecanismo verificável de drift (de princípio sempre foi aprovado) |
| Tech Lead Backend | `tl-python` | 2026-06-25 | Aprovado (coerente com P-01 API-First; OpenAPI derivado do Pydantic) |

> A reprovação do QA era sobre o gate **não-verificável** ("drift = falha" sem mecanismo). §8 crava o mecanismo (`git diff --exit-code` + contract test), atendendo à condição.

## 8. Refinamentos do painel de validação (2026-06-25)

Condições **vinculantes** (ativadas quando o frontend Angular entrar):

- **Ferramenta:** `openapi-typescript` — gera **só tipos** (`type`/`interface`, zero runtime, tree-shakeable). **Evitar** geradores de cliente (`openapi-generator-cli typescript-angular`, `orval`, `ng-openapi-gen`): geram services/módulos/runtime que colidem com "service tipado é o único ponto que fala HTTP" (ADR-0001) e arrastam toolchain pesada (JDK). **Gere tipos, escreva o transporte à mão.** Pin de versão (lint pinado é bloqueante).
- **Localização:** arquivo único `src/app/api/generated/openapi-types.ts` marcado `// AUTO-GENERATED — DO NOT EDIT`, protegido por `CODEOWNERS`/lint. O **service** expõe aliases de domínio (`export type Post = components['schemas']['Post']`); componentes **nunca** importam do arquivo gerado. **Versionar o gerado** (o diff de contrato fica visível no PR — desejável num projeto didático).
- **Gate de drift (mecânico) — o que faltava:** `npm run gen:api` lê o `/openapi.json` do **app vivo** (não um snapshot que envelhece); no CI, `git diff --exit-code` no arquivo gerado → drift = **build vermelho**. O gerador **deve ser determinístico** (mesmo input → mesmo output byte-a-byte), senão o diff vira flaky (P1).
- **Elo `005` ↔ OpenAPI ↔ TS (fonte da verdade):** `tsc` prova *shape*, não que o back *emite* aquilo. Exigir **≥1 contract test** validando um payload real (resposta do `TestClient` / fixture do `005`) contra os tipos gerados **e** contra o schema de `005` — senão um Pydantic divergente do `005` passa silenciosamente.
- **Red-green do gate (condição de aceite):** adicionar um campo no schema Pydantic **sem** regenerar → o gate de drift fica **vermelho**. Se ficar verde, é teatro.
- **Separação de gates:** o gate de **drift de contrato** é distinto do **2º ratchet de cobertura** do front (Vitest/ng test). Não fundir — um não pode mascarar o outro.
- **Spike (meio dia) mede, contra o `/openapi.json` real:** `published_at: string | null`; `status: "draft" | "published"` (union, não `string`); `next_cursor`/`cursor` como `string` cego; determinismo do diff (regenerar 2× = idêntico); toolchain só Node (sem JDK). Se passar, crava `openapi-typescript`.
