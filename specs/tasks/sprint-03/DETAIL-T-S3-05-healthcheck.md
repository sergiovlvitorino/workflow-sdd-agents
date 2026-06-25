# DETAIL — T-S3-05 — F006 (gancho): `GET /v1/health` → `200 {status: "ok"}`

**Sprint:** 3
**Tamanho:** S _(estimativa)_
**Papel:** BE (+ TL revisão `tl-python` + `tl-qa`)
**Depende de:** — (independente; usa o `create_app` existente)
**Bloqueia:** — (gancho barato de F006; o resto de F006 — dashboard — fica fora do escopo)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Entregar o **gancho barato** de F006: um liveness endpoint público `GET /v1/health` que responde `200` com `{"status": "ok"}`, dando sinal de saúde do serviço como entregável de produto (P-05) sem arrastar o resto de F006 (dashboard fica explicitamente fora).

## 2. CAs / RNs cobertos

- **CA-F006-01 (RF de F006):** `GET /v1/health` → `200` com `status` `ok`.
- **Decisões de escopo (fechadas neste DETAIL):**
  - Rota **pública** — sem auth, sem ownership, sem identidade (coerente com o blog, que não tem auth hoje).
  - **Sem `Idempotency-Key`** — é leitura idempotente por natureza (GET); o piso P-03 vale para **escrita**, não para liveness.
  - **Liveness puro** — responde `ok` se o processo está de pé; **não** checa dependências (SQLite). Readiness/checagem de DB é dívida explícita do resto de F006 (fora daqui).

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/interfaces/health_router.py` | criar | Router próprio com `GET /v1/health` → `200 {"status": "ok"}`. |
| `src/blog/main.py` | alterar | `app.include_router(health_router)` no `create_app`. |
| `tests/integration/test_health_http.py` | criar | TestClient HTTP real: status 200, corpo exato, método, sem necessidade de header. |
| `backend/coverage-gates.sh` | alterar (opcional) | Ver §5.3 — avaliação de categoria; provavelmente **dobrar na categoria `api-router`** em vez de criar nova. |

## 4. Design da solução

### 4.1 Router dedicado (não pendurar no `posts_router`)

```text
# interfaces/health_router.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["health"])

@router.get("/health", status_code=200)
async def health() -> JSONResponse:
    """Liveness público (CA-F006-01). Sem auth, sem Idempotency-Key, sem checar deps."""
    return JSONResponse(status_code=200, content={"status": "ok"})
```

- **Router próprio** (`health_router`), não acoplado ao `posts_router` (prefix `/v1/posts`): health não é recurso de post; misturar inflaria o piso 100% do router de posts com um endpoint sem relação. Prefix `/v1` para casar a rota `/v1/health` (coerente com o versionamento das demais rotas — `005`).
- **Corpo literal `{"status": "ok"}`** — contrato mínimo e estável; o teste afirma o corpo **exato**.
- **Sem dependências de `app.state`** — não usa caso de uso, não toca repo/idem. Mantém o liveness barato e sem falso-negativo por dependência lenta.

### 4.2 Wiring (`main.py`)

```text
from blog.interfaces.health_router import router as health_router
...
app.include_router(posts_router)
app.include_router(health_router)        # NOVO
```

### 4.3 Interação com o middleware de observabilidade (T-S3-04)

- Se T-S3-04 já estiver mesclado, a rota `/v1/health` passa pelo middleware único como qualquer outra: emite o evento RED-skeleton com `route == "/v1/health"` (template == path, pois não há path param) e ganha o header `X-Request-ID`. **Nada a fazer aqui** — é o comportamento esperado e desejável (prova que o middleware cobre rotas novas sem instrumentação extra).
- **Sem dependência de ordem entre T-S3-04 e T-S3-05:** os dois são independentes; se T-S3-05 entrar primeiro, o teste de health não assume header de request_id (a asserção desse header pertence a T-S3-04). Manter o teste de health focado em status/corpo evita acoplar as duas tarefas.

### 4.4 Liveness vs readiness — trade-off registrado

| Critério | A. Liveness puro `{status: ok}` _(DECIDIDA)_ | B. Readiness (checa SQLite) |
|---|---|---|
| Escopo F006 "gancho barato" | sim — mínimo viável | extrapola (vira o resto de F006) |
| Custo/latência | ~zero | abre conexão/`SELECT 1` por chamada |
| Falso-negativo por dep lenta | não | sim (DB lento derruba o health) |
| Ensina o conceito de healthcheck | sim | sim, com mais ruído |

**Decisão: A — liveness puro.** O CA-F006-01 pede apenas `200 {status: ok}`. Readiness com checagem de dependência é valor real, mas é o **resto de F006**, fora deste gancho. Registrado como dívida honesta (não esquecimento): quando F006 completo entrar, readiness `GET /v1/ready` (ou `?check=deps`) é mudança aditiva.

## 5. Impacto em testes e quality gates

### 5.1 Testes — `tests/integration/test_health_http.py` (TestClient HTTP real)

- **CA-F006-01:** `GET /v1/health` → `status_code == 200`; `resp.json() == {"status": "ok"}` (corpo **exato**, não só presença de chave).
- **Sem header obrigatório:** a chamada **não** envia `Idempotency-Key` nem `Authorization` e mesmo assim retorna `200` (prova rota pública sem piso de escrita).
- **Método:** `POST /v1/health` → `405` (FastAPI default para método não permitido na rota) — opcional, mas ancora que só `GET` está exposto.
- App isolada por teste via `create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())`, padrão da suíte (in-memory; health nem usa, mas mantém o fixture coerente).

### 5.2 Gates afetados

- **Cobertura:** `health_router.py` é trivial (1 rota, 1 retorno) — coberto 100% pelo teste de CA. Sem branches.
- **Global ratchet:** o módulo novo entra na média; o teste cobre 100% dele, então não derruba o global. Re-confirmar `--cov-fail-under` no review-loop (não baixar — P-07).
- `mypy --strict` + `ruff` no arquivo novo.

### 5.3 Nova categoria em `coverage-gates.sh` — **NÃO recomendo categoria própria**

Diferente de T-S3-04 (que trata input externo/PII e merece categoria de risco própria), o health é um endpoint **trivial sem lógica de segurança ou domínio**. Opções:

- **Recomendado:** incluir `health_router.py` na categoria existente **`api-router`** ampliando o glob para `src/blog/interfaces/*_router.py` (ou adicionando o path explícito) — mantém o piso 100% da API pública cobrindo todos os routers, sem inflar o `coverage-gates.sh` com uma categoria de 2 linhas.
- **Alternativa rejeitada:** criar categoria `health` própria — desproporcional (P-07 mede categorias de **risco**; health não é risco). Adicionaria ruído ao script sem ganho.

> **Atenção (sentinela anti-glob-vazio):** se ampliar o glob da `api-router` para `*_router.py`, confirmar que casa `posts_router.py` **e** `health_router.py` (a sentinela reprova se o glob não casar arquivo). Decisão final do glob no review-loop.

## 6. Riscos

- **Escopo creep para readiness:** resistir a "só checar o DB rapidinho" — isso é o resto de F006 e introduz falso-negativo por dependência. Liveness puro é a decisão (§4.4).
- **Acoplar ao middleware de T-S3-04:** o teste de health **não** deve assertar `X-Request-ID` (pertence a T-S3-04) — manter as tarefas desacopladas para poderem entrar em qualquer ordem.
- **Vazamento de info no corpo:** o corpo é literal `{"status": "ok"}` — **nunca** expor versão, host, paths internos ou estado de dependências (P-09/P-10). Endpoint público = superfície de informação mínima.
- **Pendurar no `posts_router`:** inflaria o piso 100% do router de posts com rota não-relacionada e quebraria a coesão; usar router dedicado (§4.1).
- **Contaminação:** `create_app` isolada por teste (padrão da suíte); não paralelizar agentes que escrevem no mesmo repo+DB (CLAUDE.md).

## 7. Definition of Done (verificável)

- [ ] `GET /v1/health` → `200` com corpo **exato** `{"status": "ok"}` (teste HTTP real via TestClient).
- [ ] Rota **pública**: responde `200` **sem** `Idempotency-Key` e **sem** `Authorization`.
- [ ] Router **dedicado** (`health_router.py`), registrado em `create_app`; **não** acoplado ao `posts_router`.
- [ ] Liveness puro — **não** checa SQLite/dependências (readiness fica como dívida explícita do resto de F006).
- [ ] Corpo não vaza versão/host/paths/estado de dependências (P-09/P-10).
- [ ] Cobertura 100% do `health_router.py`; gate `api-router` (ampliado ou explícito) cobre o novo router; sentinela anti-glob-vazio confirmada; global não rebaixado (P-07).
- [ ] `ruff` + `mypy --strict` verdes; sem regressão na suíte; `pytest-randomly` verde.
- [ ] Revisão aprovada (`tl-python` + `tl-qa`) sem ressalvas.
