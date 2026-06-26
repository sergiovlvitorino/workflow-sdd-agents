# Blog Tutorial — Frontend Angular

Frontend Angular 19 (standalone, signals-first) do blog-tutorial didático.
Stack definida em ADR-0001 e ADR-0005.

## Toolchain

- Node 20+, npm 10+
- Angular 19 (standalone, sem NgRx/SSR/PWA)
- Vitest 3 (testes unitarios, sem Karma/browser)
- ESLint 9 (pinado, bloqueante no pre-commit)
- openapi-typescript 7 (codegen de tipos, sem runtime gerado)

## Como rodar

```bash
cd frontend
npm ci           # instala deps pinadas (package-lock.json)
npm start        # dev server + proxy /v1 -> http://127.0.0.1:8000/v1
npm run build    # build de producao
npm test         # testes unitarios
npm run test:cov # testes + cobertura (2o ratchet)
npm run lint     # eslint (so arquivos .ts, barreira arquitetural inclusa)
```

## Como regenerar os tipos TypeScript

Os tipos em `src/app/api/generated/openapi-types.ts` sao gerados a partir de
`openapi-augmented.json` (schema OpenAPI aumentado com os shapes completos de
`specs/005-api-contract.md` v1.1.0).

```bash
cd frontend
npm run gen:api        # gera/atualiza o arquivo de tipos
npm run gen:api:check  # regenera + verifica cabecalho + git diff --exit-code (gate de drift)
```

### Por que openapi-augmented.json e nao o /openapi.json do backend?

O backend FastAPI usa `JSONResponse` sem `response_model` Pydantic nas rotas, o
que resulta em `schema: {}` vazio para os responses no `/openapi.json` gerado.
O arquivo `openapi-augmented.json` incorpora os schemas completos (`Post`,
`Page_Post_`, `ApiError`) derivados de `005-api-contract.md` v1.1.0.

**Quando o backend adicionar `response_model` nas rotas**, o script `gen:api`
pode ser apontado diretamente para o app vivo:
```bash
# Subir backend:
cd backend && uvicorn blog.main:app --host 127.0.0.1 --port 8000
# Gerar a partir do app vivo:
openapi-typescript http://127.0.0.1:8000/openapi.json -o src/app/api/generated/openapi-types.ts
```
Ate la, `openapi-augmented.json` e a fonte deterministica.

## Regra: nao editar o arquivo gerado

`src/app/api/generated/openapi-types.ts` e AUTO-GENERATED — nao edite manualmente.
- O CODEOWNERS protege o diretorio (revisao obrigatoria de PR).
- O sentinela `scripts/check-generated-header.mjs` falha se o cabecalho sumir.
- A regra ESLint (`no-restricted-imports`) impede que componentes importem diretamente
  do arquivo gerado (importe de `@api/api.types.ts`).

## Gate de drift

No CI, `npm run gen:api:check` regenera os tipos e roda `git diff --exit-code`.
Se o schema mudar sem regenerar, o CI fica vermelho (P-11 — falha explicita).

## Cobertura (2o ratchet)

Gate separado do backend Python (nunca media global combinada — ADR-0001 §4.1).
Thresholds em `vitest.config.ts` — so sobem, nunca descem sem ADR (P-07).

## Estrutura de pastas

```
src/app/
  api/
    generated/
      openapi-types.ts      # AUTO-GENERATED — DO NOT EDIT
    api.types.ts             # aliases de dominio (Post, PagePost, ...) — importe DAQUI
    api-error.ts             # ApiError tipado + isApiError guard
    api-error.interceptor.ts # HttpErrorResponse -> ApiError (discrimina por type, nao detail)
    blog-api.service.ts      # UNICO ponto que fala HTTP
    idempotency.ts           # generateIdempotencyKey() -> crypto.randomUUID()
  app.config.ts              # ApplicationConfig + API_BASE_URL token
  app.routes.ts              # rotas (preenchidas em T-S3-03)
  app.ts                     # componente raiz
```
