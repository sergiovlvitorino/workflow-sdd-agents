# DETAIL — T-S3-01 — Scaffold Angular (standalone, signals) + pipeline de codegen de tipos do OpenAPI

**Sprint:** 3
**Tamanho:** L _(estimativa)_
**Papel:** FE (+ TL revisão `tl-frontend` + `tl-qa`)
**Depende de:** `005-api-contract.md` v1.1.0 **congelada** (fonte do contrato); backend FastAPI vivo expondo `/openapi.json` (`backend/src/blog/main.py`, `create_app`); ADR-0001 (stack), ADR-0005 §8 (vinculante — tooling/localização/gate de drift).
**Bloqueia:** T-S3-02, T-S3-03 (todo componente/serviço consome os tipos gerados e o service base desta tarefa).

> Produzido por `tl-frontend` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (`docs/lessons/process.md`).

---

## 1. Objetivo

Criar o frontend Angular do blog (standalone, signals-first, **magro** por ADR-0001) e a **pipeline de codegen de tipos TypeScript a partir do `/openapi.json`** do FastAPI (ADR-0005 §8): um único arquivo `AUTO-GENERATED`, um service tipado base como único ponto que fala HTTP, interceptor que traduz erro RFC 9457 e centraliza o prefixo `/v1`, e o **gate de drift mecânico** (`git diff --exit-code` sobre o gerado). Valor: estabelecer a fonte única de verdade ponta-a-ponta — drift de contrato vira build vermelho, não bug de runtime.

## 2. CAs / RNs cobertos

Tarefa de **scaffold/infra** — não realiza CA de negócio (esses são de T-S3-03). Materializa decisões vinculantes:

- **ADR-0005 §4/§8 (vinculante):** codegen via `openapi-typescript` (só tipos, zero runtime); tipos em `src/app/api/generated/openapi-types.ts` marcado `AUTO-GENERATED`; `npm run gen:api` lê o **app vivo**; gate de drift = `git diff --exit-code`; gerador **determinístico** (regenerar 2× = byte-a-byte idêntico); pin de versão.
- **ADR-0001 §4:** Angular standalone, signals-first, **sem** NgRx/SSR/PWA/Storybook/design system; **service tipado é o único ponto que fala HTTP**; `HttpInterceptor` traduz HTTP→erro tipado (P-11) e centraliza `/v1` (P-08).
- **RNF-C-01 (`004`):** contrato `/v1` é a fonte; front é consumidor (anti-drift).
- **RNF-Q-01 / `007` §2 §6:** o **2º ratchet (front)** nasce nesta sprint, barrado **separadamente** do backend (gate AND, nunca média global) — o gate de cobertura é instituído aqui e elevado em T-S3-03.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `frontend/package.json` | criar | Deps **pinadas** (Angular ~19, `openapi-typescript` 7.x, Vitest/Testing Library); scripts `start`, `build`, `test`, `test:cov`, `gen:api`, `gen:api:check`, `lint`. |
| `frontend/angular.json` | criar | Workspace standalone (sem módulos), builder padrão, `test` via Vitest (ver §4.6). |
| `frontend/tsconfig.json` / `tsconfig.app.json` / `tsconfig.spec.json` | criar | `strict: true` (+ `noUncheckedIndexedAccess`); path alias `@api/*`, `@app/*`. |
| `frontend/.gitignore` | criar | `node_modules`, `dist`, `coverage`, `.angular`. **NÃO** ignorar o gerado (ADR-0005: versionar). |
| `frontend/src/main.ts` | criar | Bootstrap standalone via `bootstrapApplication`. |
| `frontend/src/index.html` | criar | Shell HTML semântico: `<html lang="pt-BR">`, skip-link, landmark `<main id="main">`. |
| `frontend/src/styles.css` | criar | Reset enxuto + tokens (custom properties); `@media (prefers-reduced-motion)`; `:focus-visible`. |
| `frontend/src/app/app.config.ts` | criar | `ApplicationConfig`: `provideHttpClient(withInterceptors([apiErrorInterceptor]))`, `provideRouter(routes)`, token `API_BASE_URL`. |
| `frontend/src/app/app.routes.ts` | criar | Rotas vazias/placeholder (preenchidas em T-S3-03), com `loadComponent` (lazy). |
| `frontend/src/app/app.ts` | criar | Componente raiz standalone: skip-link target + `<router-outlet>`. |
| `frontend/src/app/api/generated/openapi-types.ts` | criar (gerado) | **AUTO-GENERATED — DO NOT EDIT.** Saída do `gen:api`. Versionado. |
| `frontend/src/app/api/api.types.ts` | criar | Aliases de domínio derivados do gerado (`Post`, `Page`, `ApiError`, `CreatePostRequest`, enums). Componentes importam **daqui**, nunca do gerado. |
| `frontend/src/app/api/api-error.ts` | criar | `ApiError` tipado (discriminado por `type`/`status`) + `ApiErrorCode` (union dos sufixos do catálogo `005` §4). |
| `frontend/src/app/api/api-error.interceptor.ts` | criar | `HttpInterceptorFn`: traduz `HttpErrorResponse` (`application/problem+json`) → `ApiError` tipado; centraliza `/v1` se optar por base path relativo. |
| `frontend/src/app/api/blog-api.service.ts` | criar | **Service tipado base** — único ponto que fala HTTP. Métodos: `listPosts`, `getPost`, `createPost`, `publishPost` (assinaturas em §4.4). |
| `frontend/src/app/api/idempotency.ts` | criar | Gerador de `Idempotency-Key` (`crypto.randomUUID()`) usado nas escritas (P-03). |
| `frontend/CODEOWNERS` (ou raiz) | criar/alterar | Proteger `src/app/api/generated/**` (revisão obrigatória; não editar à mão). |
| `frontend/eslint.config.js` | criar | ESLint **pinado** (`.pre-commit-config.yaml`/CI), com regra que **proíbe import** de `api/generated/*` fora de `api/` (barreira arquitetural). |
| `frontend/vitest.config.ts` | criar | Vitest + jsdom + `@testing-library/angular`; `coverage` (v8) com `thresholds` (2º ratchet, §5). |
| `frontend/scripts/check-generated-header.mjs` | criar | Sentinela: falha se o arquivo gerado **não** começar com o cabeçalho `AUTO-GENERATED` (anti-edição-à-mão silenciosa). |
| `frontend/README.md` | criar | Como rodar, como regenerar tipos, regra "não editar o gerado", como o gate de drift funciona. |
| `frontend/src/app/api/blog-api.service.spec.ts` | criar | Testes do service base com `provideHttpClientTesting` (`HttpTestingController`) — cobre URL, headers, mapeamento de erro. |
| `frontend/src/app/api/contract.spec.ts` | criar | **Contract test:** payload real/fixture de `005` validado contra os tipos gerados **e** contra o schema de `005` (ADR-0005 §8). |
| `.pre-commit-config.yaml` | alterar | Descomentar/pinar o bloco eslint (ADR-0001 §5) restrito a `frontend/`. |
| `.github/workflows/*` (ou equivalente) | alterar | Job **front** separado: `gen:api:check` (drift) **+** `test:cov` (2º ratchet) — gate AND com o job Python; **nunca** média global. |

> **Higiene (CLAUDE.md):** esta DETAIL **descreve** os arquivos; ela própria só grava sob `specs/tasks/sprint-03/`. A criação do código é do `review-loop`. `git add` por caminho; lint pinado só nos arquivos tocados.

## 4. Design da solução

### 4.1 Layout de pastas (ADR-0001 — `api/ services/ components/`)

```text
frontend/
  package.json            # deps PINADAS + scripts gen:api / gen:api:check
  angular.json
  tsconfig*.json          # strict; alias @api/* @app/*
  eslint.config.js        # pinado; barreira: proíbe import de api/generated fora de api/
  vitest.config.ts        # 2º ratchet (thresholds de cobertura do front)
  CODEOWNERS              # protege api/generated/**
  scripts/
    check-generated-header.mjs
  src/
    index.html  main.ts  styles.css
    app/
      app.config.ts  app.routes.ts  app.ts
      api/
        generated/
          openapi-types.ts          # AUTO-GENERATED — DO NOT EDIT (versionado)
        api.types.ts                 # aliases de domínio (Post, Page<T>, ...)
        api-error.ts                 # ApiError tipado + ApiErrorCode (union)
        api-error.interceptor.ts     # HttpErrorResponse -> ApiError; centraliza /v1
        idempotency.ts               # randomUUID() para Idempotency-Key
        blog-api.service.ts          # ÚNICO ponto que fala HTTP
      posts/                          # componentes entram em T-S3-03
```

### 4.2 Pipeline de codegen — decisão de tooling e trade-offs

**Ferramenta: `openapi-typescript` (7.x, pinado).** Gera **só tipos** (`type`/`interface`), zero runtime, tree-shakeable. Decisão vinculante de ADR-0005 §8 — **rejeitar** geradores de cliente.

| Critério | `openapi-typescript` _(ESCOLHIDA)_ | `openapi-generator-cli typescript-angular` | `orval` / `ng-openapi-gen` |
|---|---|---|---|
| Gera só tipos (sem runtime) | **sim** | não (services/módulos NgModule) | não (hooks/services) |
| Colide com "service tipado é o único transporte" (ADR-0001) | **não** | **sim** (gera o transporte) | **sim** |
| Toolchain | **só Node** | **exige JDK** (toolchain pesada) | Node |
| Determinismo do diff | alto (ordena por schema) | baixo (timestamps/headers no output) | médio |
| Aderência ADR-0005 §8 | total | viola | viola |

**Decisão: gere os tipos, escreva o transporte à mão.** O `BlogApiService` (§4.4) é o transporte; o gerado é só shape.

**Script `gen:api` (lê o app VIVO, não snapshot que envelhece — ADR-0005 §8):**

```jsonc
// package.json (trechos)
"scripts": {
  "gen:api":       "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/api/generated/openapi-types.ts --header-comment \"AUTO-GENERATED — DO NOT EDIT. Run: npm run gen:api\"",
  "gen:api:check": "npm run gen:api && node scripts/check-generated-header.mjs && git diff --exit-code -- src/app/api/generated/openapi-types.ts"
}
```

- **Determinismo (P1 anti-flaky):** `openapi-typescript` ordena a saída pelo schema → regenerar 2× produz **byte-a-byte idêntico**. Condição de aceite do spike (§6). Fixar `--header-comment` estável (sem data/hora) — qualquer timestamp no cabeçalho tornaria o `git diff` flaky.
- **Fonte = app vivo:** o `/openapi.json` é derivado dos schemas Pydantic (P-01 API-First). O CI sobe o FastAPI (`uvicorn blog.main:app` ou `TestClient` exportando o JSON) e aponta o `gen:api` para ele. **Não** commitar um snapshot de `openapi.json` como fonte (envelhece em silêncio).
- **Versionar o gerado:** o diff de contrato fica visível no PR (desejável didaticamente). `.gitignore` **não** ignora `api/generated/`.

> ⚠️ **Pré-condição de versão do contrato:** o `app` do FastAPI declara `version="1.0.0"` em `main.py`, mas `005` está em **1.1.0**. Isso é incoerência spec×código (P-02) e o `info.version` do OpenAPI alimenta o gerado. **Sinalizar ao backend/PO** para alinhar `FastAPI(version=...)` ao `005` **antes** de congelar o baseline do gerado — senão o primeiro `gen:api` cristaliza um número errado. (Correção é no backend, fora desta DETAIL.)

### 4.3 Gate de drift (mecânico) — distinto do ratchet de cobertura

Dois gates **separados** no job front (ADR-0005 §8 "não fundir"):

```text
job: frontend  (gate AND com job python; NUNCA média global combinada)
  1. npm ci                      # deps pinadas (package-lock versionado)
  2. (subir backend) -> serve /openapi.json
  3. npm run gen:api:check       # GATE DE DRIFT: regenera + header + git diff --exit-code
                                 #   drift => build VERMELHO (P-11), não aviso
  4. npm run lint                # eslint pinado (inclui barreira de import do gerado)
  5. npm run test:cov            # 2º RATCHET (cobertura front), thresholds em vitest.config
```

- **Drift = falha**, não warning (ADR-0005 §8; P-11). Se o backend muda um campo e ninguém regenera, `git diff --exit-code` retorna ≠0 → CI vermelho.
- **Red-green do gate (condição de aceite ADR-0005 §8):** adicionar um campo no schema Pydantic **sem** regenerar → `gen:api:check` fica **vermelho**. Se ficar verde, é teatro. Provar no review-loop (reverter a sonda com **Edit**, nunca `git checkout` — CLAUDE.md).
- `tsc` prova **shape**, não que o back **emite** aquilo → por isso o **contract test** (§4.5) é obrigatório, complementar ao diff.

### 4.4 Service tipado base — único ponto que fala HTTP

```ts
// api/api.types.ts — aliases de domínio (componentes importam DAQUI)
import type { components, paths } from './generated/openapi-types';
export type Post           = components['schemas']['Post'];
export type CreatePostRequest = components['schemas']['CreatePostRequest'];
export type PagePost        = components['schemas']['Page_Post_']; // nome real conferido no gerado
export type PostStatus      = Post['status'];   // "draft" | "published" (union, NÃO string)
// published_at: string | null  (preservar nullabilidade do contrato)

// api/api-error.ts
export type ApiErrorCode =
  | 'validation_error' | 'idempotency_key_required' | 'idempotency_key_conflict'
  | 'invalid_cursor'   | 'post_not_found';
export interface ApiError {
  type: string; title: string; status: number; detail?: string;
  code: ApiErrorCode | 'unknown';            // derivado do sufixo de `type`
  errors?: { field: string; code: string; message: string }[];
}

// api/blog-api.service.ts — ÚNICO transporte HTTP
@Injectable({ providedIn: 'root' })
export class BlogApiService {
  private http = inject(HttpClient);
  private base = inject(API_BASE_URL);        // ex.: '/v1' (centralizado, P-08)

  listPosts(opts?: { limit?: number; cursor?: string }): Observable<PagePost> { /* GET base/posts */ }
  getPost(id: string): Observable<Post> { /* GET base/posts/{id} */ }
  createPost(body: CreatePostRequest): Observable<Post> {
    // header Idempotency-Key obrigatório (P-03) — gerado por idempotency.ts
  }
  publishPost(id: string): Observable<Post> {
    // PUT base/posts/{id}/publish, corpo vazio, Idempotency-Key obrigatório (P-03)
  }
}
```

Decisões:
- **`API_BASE_URL` = `/v1`** via `InjectionToken` (centralização P-08). Em dev, `proxy.conf.json` encaminha `/v1` → `http://127.0.0.1:8000/v1` (sem CORS, sem hardcode de host).
- **Idempotency-Key nas escritas** (`createPost`/`publishPost`): cada chamada gera `crypto.randomUUID()`; o retry da **mesma** intenção reusa a chave (a UI passa a key, não o service inventa em cada retry — decisão fechada em T-S3-03 onde há contexto de intenção). O service **exige** a key (parâmetro/aplicada no interceptor de escrita) — sem ela, escrita não sai (espelha o piso P-03 do back).
- Tipos de retorno são **aliases do gerado** — nunca interfaces escritas à mão (anti-drift; ADR-0005 §4 alt. B rejeitada).

### 4.5 Interceptor de erro RFC 9457 (P-11)

```ts
// api/api-error.interceptor.ts
export const apiErrorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      const body = err.error;            // application/problem+json
      const code = typeof body?.type === 'string'
        ? (body.type.split('/').pop() as ApiErrorCode) : 'unknown';
      const apiError: ApiError = {
        type: body?.type ?? 'about:blank', title: body?.title ?? 'Erro',
        status: err.status, detail: body?.detail, code, errors: body?.errors,
      };
      return throwError(() => apiError);   // componentes recebem ApiError tipado, nunca HttpErrorResponse cru
    }),
  );
```

- **Discrimina por `type`/`status`, nunca por `string-match` no `detail`** (`005` §4: `detail` é texto livre). O `code` (sufixo do `type`) é a chave que a UI usa.
- Centraliza o tratamento: nenhum componente toca `HttpErrorResponse` (ADR-0001 — interceptor traduz HTTP→erro tipado).
- Erro de rede/sem corpo Problem → `code: 'unknown'`, `status: 0` — tratado como falha explícita, nunca silenciada (P-11).

### 4.6 Tooling de teste

- **Vitest + `@testing-library/angular`** (rápido, sem Karma/browser). `provideHttpClientTesting`/`HttpTestingController` para o service (teste do transporte real, equivalente ao `TestClient` do back — `007` §1).
- **Cobertura v8** com `thresholds` no `vitest.config.ts` (2º ratchet, §5).
- Sem E2E Playwright nesta tarefa (ADR-0001 §4 "magro"; `007` §6 — futuro).

## 5. Impacto em testes e quality gates

- **Testes novos (scaffold):**
  - `blog-api.service.spec.ts` — URL correta (`/v1/posts...`), `Idempotency-Key` presente nas escritas, mapeamento `HttpErrorResponse`→`ApiError` (cada `code` do catálogo), `published_at: null` preservado.
  - `contract.spec.ts` — fixture/payload de `005` (ex.: o exemplo `201` de §2.1) tipa-checa contra `Post` gerado **e** valida contra o schema de `005`; mutar um campo no contrato deixa este teste vermelho (ADR-0001 §4.2 anti-drift).
- **Gates instituídos (não-negociáveis):**
  - **2º ratchet front** (`007` §2/§6): `vitest --coverage` com piso próprio, **barrado separadamente** do Python (gate AND). **Proibida média global combinada** (ADR-0001 §4.1). Nesta tarefa o piso nasce no patamar do scaffold (service + interceptor cobertos); T-S3-03 eleva.
  - **Gate de drift de contrato** (`gen:api:check`): distinto do ratchet (ADR-0005 §8 "não fundir"). Drift = vermelho.
  - **Lint pinado** (ESLint) bloqueante (CLAUDE.md); inclui a barreira de import do gerado.
  - **Secret-scan** transversal já cobre `frontend/` (P-10, repo inteiro).
- **Determinismo:** `gen:api` regenerado 2× = idêntico (anti-flaky P1).

## 6. Riscos

- **Determinismo do gerador (P1):** se o output variar entre execuções (timestamps no cabeçalho, ordenação instável), o `git diff` vira flaky e o gate perde credibilidade. **Mitigação:** `--header-comment` sem data; spike de meio-dia (ADR-0005 §8) provando regeneração idêntica 2× **antes** de cravar o tooling.
- **Snapshot de `openapi.json` que envelhece:** apontar o `gen:api` para um arquivo commitado em vez do app vivo mascara drift. **Mitigação:** CI sobe o backend e gera do endpoint vivo.
- **`info.version` desalinhado (`main.py` 1.0.0 × `005` 1.1.0):** o número entra no gerado. **Mitigação:** sinalizar ao backend/PO para alinhar antes do baseline (fora desta DETAIL).
- **Edição à mão do gerado:** quebra a fonte única. **Mitigação tripla:** cabeçalho `AUTO-GENERATED` + sentinela `check-generated-header.mjs` + CODEOWNERS + regra ESLint de barreira de import.
- **Média global combinada back+front:** falso-verde estrutural (ADR-0001 §4.1). **Mitigação:** jobs separados, gate AND; nunca somar cobertura.
- **Nomes de schema gerados** (ex.: `Page_Post_` para genéricos do Pydantic): podem não casar o alias esperado. **Mitigação:** conferir o nome real no gerado e ajustar `api.types.ts` (não editar o gerado).
- **Geradores de cliente arrastando JDK:** custo de toolchain e runtime acoplado. **Mitigação:** `openapi-typescript` (só Node, só tipos) — decisão fechada.

## 7. Definition of Done (verificável)

- [ ] `frontend/` cria app Angular **standalone, signals-first**, sem NgRx/SSR/PWA/Storybook (ADR-0001 §4); `start`/`build`/`test` verdes.
- [ ] Deps **pinadas** (`package.json` + lockfile versionado); `openapi-typescript` 7.x pinado; ESLint pinado no `.pre-commit-config.yaml`.
- [ ] `npm run gen:api` gera `src/app/api/generated/openapi-types.ts` a partir do **`/openapi.json` do app vivo**, com cabeçalho `AUTO-GENERATED — DO NOT EDIT`; arquivo **versionado**.
- [ ] **Determinismo provado:** `gen:api` rodado 2× ⇒ `git diff` vazio (byte-a-byte idêntico).
- [ ] **Gate de drift wired e mordendo:** `gen:api:check` (`git diff --exit-code`) no CI; adicionar campo Pydantic sem regenerar ⇒ build **vermelho** (red-green provado via Edit, revertido por Edit — não `git checkout`).
- [ ] `BlogApiService` é o **único** ponto que fala HTTP; expõe `listPosts/getPost/createPost/publishPost` tipados via **aliases do gerado** (sem tipos à mão); `API_BASE_URL=/v1` centralizado (P-08); escritas exigem `Idempotency-Key` (P-03).
- [ ] `apiErrorInterceptor` traduz `application/problem+json` → `ApiError` tipado discriminado por `type`/`status` (nunca por `detail`); cobre os 5 `code`s do catálogo `005` §4 + `unknown`.
- [ ] Barreira arquitetural ativa: componentes **não** importam de `api/generated/*` (regra ESLint) — só via `api.types.ts`.
- [ ] **2º ratchet (front)** instituído no `vitest.config.ts` e wired no CI, **barrado separadamente** do Python (gate AND); **nenhuma** média global combinada.
- [ ] `contract.spec.ts` valida payload real de `005` contra tipo gerado **e** schema `005`; mutar campo do contrato ⇒ teste vermelho.
- [ ] `index.html` semântico (`lang="pt-BR"`, skip-link, `<main>`); `styles.css` com `prefers-reduced-motion` e `:focus-visible`.
- [ ] Revisão aprovada (`tl-frontend` + `tl-qa`) sem ressalvas.
