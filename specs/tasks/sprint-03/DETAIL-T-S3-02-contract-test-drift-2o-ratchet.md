# DETAIL — T-S3-02 — Contract test cross-stack + gate de drift de contrato (005 ↔ OpenAPI ↔ TS)

**Sprint:** 03
**Tamanho:** M _(estimativa)_
**Papel:** QA (`qa` / `spec-qa`) + TL revisão (`tl-qa` + `tl-frontend` + `tl-python`)
**Depende de:** T-S3-01 (scaffold Angular existe: `frontend/` com `package.json`, `openapi-typescript` pinado, `npm run gen:api`, e o arquivo gerado `src/app/api/generated/openapi-types.ts` — ADR-0005 §8); backend já serve `/openapi.json` (FastAPI, `backend/src/blog/main.py` → `app = create_app()`).
**Bloqueia:** fechamento da costura cross-stack da Sprint 3 (a trava anti-drift do polyglot — ADR-0001 §4.2, `007` §6).

> Produzido por `tl-qa` no `sprint-flow`; consumido pelo `review-loop`. Materializa as condições **vinculantes** do ADR-0005 §8 (gate de drift mecânico + contract test do elo `005`↔OpenAPI↔TS + red-green do gate) e a costura "Contract test cross-language" de `007-test-strategy.md` §6. **Drift de contrato ≠ ratchet de cobertura** — são gates separados (este DETAIL = drift; T-S3-07 = cobertura do front). Ver `docs/lessons/qa.md` ("gate que morde", "gate não-wired é inerte", "lint vs build").

---

## 1. Objetivo

Fechar o elo **`005-api-contract.md` ↔ OpenAPI (FastAPI) ↔ tipos TS gerados** com **dois mecanismos verificáveis e independentes**:

1. **Gate de drift de contrato** — regenera os tipos TS a partir do `/openapi.json` do **app vivo** e falha o CI (`git diff --exit-code`) se o arquivo versionado estiver desatualizado. Gerador **determinístico** (regenerar 2× = byte-a-byte idêntico), senão o diff vira flaky (P1).
2. **≥1 contract test cross-stack** que valida um **payload real** (resposta do `TestClient` / fixture de `005`) contra (a) os tipos TS gerados **e** (b) o schema de `005` — provando que o backend *emite* o que o tipo *declara* (o `tsc` prova *shape*, não *emissão*).

Sem (1), tipos desatualizados passam silenciosamente; sem (2), um Pydantic divergente do `005` passa o `tsc` e quebra em runtime. Os dois juntos = trava anti-drift honesta.

## 2. CAs / RNs cobertos

- **Não realiza CA de negócio** — protege **todos** os CAs de F001/F003/F002/F004 contra divergência back↔front (contract drift = "Alto" na matriz de risco, `007` §7).
- **ADR-0005 §8 (vinculante):** gate de drift mecânico (`git diff --exit-code` sobre arquivo gerado do app vivo, gerador determinístico); ≥1 contract test (payload real × tipos gerados × `005`); red-green do gate; separação de gates (drift ≠ cobertura).
- **ADR-0001 §4.2:** contract test cross-language — mutar um campo no back **tem** que deixar o contract test/gate vermelho.
- **`007` §6:** "Contract test derivado de schema único" + "trava anti-drift do polyglot".
- **`005` v1.1.0:** schemas `Post`, `CreatePostRequest`, `ApiError` (Problem Details), `status: "draft"|"published"`, `published_at: string|null`, `next_cursor: string|null`.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `frontend/scripts/check-contract-drift.sh` (ou alvo `npm run check:contract`) | criar | Sobe o app vivo / usa o `/openapi.json` real → `npm run gen:api` → `git diff --exit-code` no arquivo gerado. É o **juiz do CI** do gate de drift. |
| `frontend/tests/contract/post-payload.contract.spec.ts` | criar | Contract test cross-stack: carrega um payload real (fixture capturada do `TestClient`/`005`) e o valida contra os tipos gerados (compile-time via `satisfies`) **e** contra o schema `005` (runtime via validador de schema). |
| `frontend/tests/contract/fixtures/` | criar | Fixtures de payload **real** gravadas: `post.published.json`, `post.draft.json`, `list.page.json`, `error.problem.json` — capturadas da resposta do backend, **não** escritas à mão (ver §4.3). |
| `backend/scripts/dump_openapi.py` (ou alvo) | criar | Emite o `/openapi.json` determinístico do app montado (`create_app()`), com `sort_keys=True`, para o gerador consumir em CI sem subir servidor HTTP. |
| `backend/tests/contract/test_openapi_matches_005.py` | criar | Pino do lado backend: assevera que o OpenAPI emitido contém os schemas/campos que `005` exige (`status` enum `draft|published`, `published_at` nullable, `next_cursor` nullable, `ApiError` Problem Details). Fecha o elo `005`→OpenAPI. |
| `.github/workflows/ci.yml` | alterar | Adicionar **job `frontend`** (ou steps no job front de T-S3-07) com: gerar openapi → `gen:api` → `git diff --exit-code` (gate de drift) **e** rodar o contract test. Wiring real (gate não-wired é inerte). |

> **Nota — nomes a confirmar no review-loop.** Os paths do front (`frontend/...`) seguem ADR-0005 §8 (`src/app/api/generated/openapi-types.ts`) e o que T-S3-01 criar. Se T-S3-01 escolher outra raiz/nome do script `gen:api`, **ajustar** — o gate só vale se aponta para o arquivo realmente gerado.

## 4. Design da solução

### 4.1 Gate de drift — fonte é o app VIVO, não um snapshot

O ADR-0005 §8 é explícito: `gen:api` lê o `/openapi.json` do **app vivo** (não um snapshot que envelhece). Para rodar em CI **sem** subir um servidor HTTP (mais determinístico e rápido), o "app vivo" é materializado emitindo o documento do app montado:

```python
# backend/scripts/dump_openapi.py
import json, sys
from blog.main import app  # app = create_app() — o MESMO app de produção
# sort_keys=True => saída determinística (mesmo input -> mesmos bytes).
json.dump(app.openapi(), sys.stdout, sort_keys=True, ensure_ascii=False, indent=2)
sys.stdout.write("\n")
```

```sh
# frontend/scripts/check-contract-drift.sh — JUIZ do gate de drift (roda no CI)
set -euo pipefail

# 1) Emite o OpenAPI do app de produção (determinístico, sort_keys).
( cd ../backend && python scripts/dump_openapi.py ) > openapi.json

# 2) Regenera os tipos a partir do contrato VIVO (openapi-typescript, pinado).
npm run gen:api   # internamente: openapi-typescript openapi.json -o src/app/api/generated/openapi-types.ts

# 3) Gate: se o gerado versionado divergir do recém-gerado, drift = VERMELHO.
git diff --exit-code -- src/app/api/generated/openapi-types.ts
# exit 0 => sincronizado; exit 1 => alguém mexeu no Pydantic e não regenerou.
```

**Determinismo (anti-diff-flaky, P1):** o gerador deve produzir bytes idênticos em execuções repetidas. Provar no spike/DoD: rodar `gen:api` **duas vezes** seguidas → `git diff --exit-code` limpo nas duas. Fontes comuns de não-determinismo a barrar: ordem de chaves do `app.openapi()` (resolvido por `sort_keys=True`), versão flutuante do `openapi-typescript` (resolvido pelo **pin** — lint/pin é bloqueante), `\r\n` vs `\n` (resolvido por `.gitattributes` normalizando o arquivo gerado em LF — atenção no Windows do dev).

### 4.2 Contract test cross-stack — `tsc` prova *shape*, não *emissão*

O `git diff` prova que o **tipo** acompanha o OpenAPI; o `tsc` prova que código TS respeita o tipo. **Nenhum dos dois** prova que o backend **emite** um payload conforme. Por isso ≥1 contract test sobre **payload real** (`007` §6; ADR-0005 §8 "elo da fonte da verdade"):

```ts
// frontend/tests/contract/post-payload.contract.spec.ts (Vitest)
import { describe, it, expect } from 'vitest';
import type { components } from '../../src/app/api/generated/openapi-types';
import published from './fixtures/post.published.json';
import Ajv from 'ajv';
import openapiSchema from '../../openapi.json'; // o MESMO doc do gate de drift

type Post = components['schemas']['Post'];

describe('contract: Post payload (005 ↔ OpenAPI ↔ TS)', () => {
  it('payload real do backend satisfaz o tipo gerado (compile-time)', () => {
    // `satisfies` falha a COMPILAÇÃO se a fixture real não casar o tipo gerado.
    const post = published satisfies Post;
    // Asserts de VALOR (não "is not None"): prova os campos críticos do 005.
    expect(post.status).toBe('published');          // enum, não string cega
    expect(typeof post.published_at).toBe('string'); // published => non-null (005 §2.3)
    expect(post).toHaveProperty('id');
  });

  it('payload real valida contra o schema de 005 (runtime, via OpenAPI)', () => {
    const ajv = new Ajv({ strict: false });
    const validate = ajv.compile(openapiSchema.components.schemas.Post);
    const ok = validate(published);
    expect(ok, JSON.stringify(validate.errors)).toBe(true);
  });

  it('draft tem published_at = null (005 §2.4 — fronteira nullable)', () => {
    // fixture draft real; prova o lado null do union published_at: string|null.
    // (mutar o Pydantic para published_at non-null derruba este caso.)
  });
});
```

**Por que ambos os asserts:** o `satisfies Post` é estático (morre na compilação se o *shape* do tipo mudar e a fixture não); o `ajv.compile(...Post)` é runtime e ataca **valores** (enum inválido, nullable violado) que o TS-estrutural deixa passar quando a fixture é `any`/`JSON`. Os dois fecham o elo dos dois lados.

### 4.3 As fixtures são payload REAL, não escritas à mão (anti-falso-verde)

`qa.md` "fake que espelha o contrato mas não o caminho esconde wiring": uma fixture escrita à mão pode espelhar o `005` e **mascarar** uma divergência real do backend. As fixtures de `frontend/tests/contract/fixtures/` são **capturadas** da resposta do `TestClient` (script de captura no backend, ou copiadas das fixtures de contrato já existentes em `backend/tests/`), nunca digitadas. Capturar **antes** de qualquer campo não-determinístico (timestamps/ids) ou normalizá-los na captura (ver `qa.md` "golden gravadas").

### 4.4 Pino do lado backend — `005` → OpenAPI

O contract test do front prova OpenAPI↔TS↔payload. Falta cravar `005`→OpenAPI (o OpenAPI poderia divergir do documento `005` e o front nunca notaria, pois consome o OpenAPI). `backend/tests/contract/test_openapi_matches_005.py` assevera os pontos sensíveis do `005` v1.1.0 sobre `app.openapi()`:

```python
def test_status_enum_is_draft_published():
    schema = app.openapi()["components"]["schemas"]["Post"]["properties"]["status"]
    assert set(schema["enum"]) == {"draft", "published"}  # 005: union, não string cega

def test_published_at_is_nullable():
    # 005 §2.3/2.4: published_at: string | null
    ...

def test_next_cursor_nullable_and_apierror_is_problem_details():
    # 005 §2.2 next_cursor: string|null ; §4 ApiError = RFC 9457
    ...
```

> **Atenção (drift latente já visível):** `main.py` cria `FastAPI(..., version="1.0.0")` mas `005` está em **v1.1.0**. Se o `info.version` do OpenAPI for verificado contra `005`, este teste **nasce vermelho** — é um drift real (red-green grátis). Decidir no review-loop: alinhar `version` ou não asseverá-lo (registrar a escolha). Não silenciar sem decisão.

### 4.5 Onde wira no CI

O job front (a partir da raiz do repo) roda, **em ordem**:

```yaml
# .github/workflows/ci.yml — job frontend (compartilhado com T-S3-07)
- name: Drift de contrato (005 ↔ OpenAPI ↔ TS)
  working-directory: frontend
  run: bash scripts/check-contract-drift.sh     # gen:api + git diff --exit-code

- name: Contract test cross-stack (payload real × tipos × 005)
  working-directory: frontend
  run: npm run test:contract                     # Vitest, arquivo de contrato

- name: Pino 005 → OpenAPI (backend)
  working-directory: backend
  run: pytest tests/contract/test_openapi_matches_005.py
```

> O gate de **drift** e o **2º ratchet de cobertura** (T-S3-07) são steps/jobs **distintos** — um não pode mascarar o outro (ADR-0005 §8 "separação de gates"). Cobertura verde com tipos drifted = ainda vermelho, e vice-versa.

## 5. Impacto em testes e quality gates

- **Novos gates (cross-stack):**
  - **Drift de contrato** — `git diff --exit-code` sobre o arquivo gerado, fonte = app vivo. Bloqueante.
  - **Contract test** — ≥1 spec Vitest validando payload real × tipos gerados × schema `005`. Bloqueante.
  - **Pino `005`→OpenAPI** — pytest no backend. Bloqueante.
- **Determinismo:** gerador idempotente (gen:api 2× = idêntico) é DoD; quebra = flaky P1.
- **Separação explícita:** este DETAIL **não** mexe no piso de cobertura do front (isso é T-S3-07). Drift ≠ cobertura.
- **Pin bloqueante:** `openapi-typescript` e `ajv` (ou validador escolhido) **pinados** no `package.json` (lint/pin é bloqueante — `004`/`qa.md`).

## 6. Riscos

- **Gerador não-determinístico → diff flaky (P1).** Ordem de chaves, versão flutuante, EOL CRLF/LF. Mitigação: `sort_keys=True` no dump, **pin** do gerador, `.gitattributes` LF no arquivo gerado, prova `gen:api` 2× idêntico no DoD.
- **Snapshot que envelhece.** Gerar a partir de um `openapi.json` versionado e estático mascara drift (o snapshot fica velho junto com o tipo). Mitigação: a fonte é o **app vivo** (`dump_openapi.py` do `create_app()`), regenerado a cada CI — ADR-0005 §8.
- **Gate não-wired é inerte** (`qa.md`). Definir o script e não rodá-lo no CI = gate que não existe. Mitigação: aparece **rodando** no job front (DoD).
- **Contract test que mocka o backend** = falso-verde (testa o mock, não o contrato). Mitigação: fixtures de **payload real capturado** (§4.3), nunca à mão; validação por schema `005` real, não placeholder.
- **`satisfies` com fixture tipada `any`** desliga a checagem estática. Mitigação: importar o JSON como dado e provar com `satisfies` + Ajv sobre valor; revisar que o tipo não foi alargado para `any`.
- **Confundir lint com build (`qa.md` "ruff check≠format análogo no JS").** No front, `tsc --noEmit` (typecheck) e `eslint` (lint) são gates **distintos** do build/gen; nenhum substitui o `git diff` de drift. Mitigação: gate de drift é passo próprio.
- **Drift `info.version` latente** (1.0.0 no app × 1.1.0 no `005`) pode reprovar o pino §4.4 já na primeira execução — é correto (drift real); decidir alinhamento sem silenciar.

## 7. Definition of Done (verificável)

- [ ] `frontend/scripts/check-contract-drift.sh` (ou `npm run check:contract`) **wired no CI**, visto rodando: emite OpenAPI do app vivo → `gen:api` → `git diff --exit-code`.
- [ ] Gerador **determinístico provado**: `npm run gen:api` rodado 2× consecutivas → `git diff --exit-code` limpo nas duas.
- [ ] ≥1 contract test (`*.contract.spec.ts`) valida **payload real** (fixture capturada, não escrita à mão) contra (a) tipos gerados (`satisfies`, compile-time) **e** (b) schema `005`/OpenAPI (Ajv, runtime), com asserts de **valor** (`status === 'published'`, `published_at` non-null no published e null no draft).
- [ ] Pino `005`→OpenAPI (`backend/tests/contract/test_openapi_matches_005.py`) verde: `status` enum `{draft,published}`, `published_at` nullable, `next_cursor` nullable, `ApiError` = Problem Details.
- [ ] **Red-green do gate de drift provado** (ADR-0005 §8): adicionar um campo no schema Pydantic (via **Edit**, ex.: novo campo em `interfaces/schemas.py`) **sem** regenerar → `check-contract-drift.sh` fica **vermelho**; reverter por Edit → verde. **Nunca `git checkout`** (CLAUDE.md).
- [ ] **Red-green do contract test provado**: mutar um valor/enum no Pydantic emitido (ex.: `status` aceitar `"PUBLISHED"` maiúsculo) → contract test fica **vermelho**; reverter.
- [ ] **Drift ≠ cobertura** registrado: gate de drift é step/job distinto do 2º ratchet (T-S3-07); um não mascara o outro.
- [ ] `openapi-typescript` + validador de schema **pinados** no `package.json` (pin bloqueante).
- [ ] `.gitattributes` força LF no arquivo gerado (anti-diff-flaky no Windows).
- [ ] Sem regressão na suíte backend existente.
- [ ] Revisão aprovada (`tl-qa` + `tl-frontend` + `tl-python`) sem ressalvas.
