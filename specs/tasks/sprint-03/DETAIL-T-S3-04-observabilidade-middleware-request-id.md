# DETAIL — T-S3-04 — F005 observabilidade: middleware ASGI único (log estruturado RED-skeleton + `request_id` correlacionado)

**Sprint:** 3
**Tamanho:** M _(estimativa)_
**Papel:** BE (+ TL revisão `tl-python` + `tl-qa`; SRE consultivo — ADR-0006 §8 já validada)
**Depende de:** T-S2-06/07 (router + handlers de erro existentes em `interfaces/`), T-S2-09 (gate ratchet/coverage-gates.sh existente)
**Bloqueia:** — (entrega F005; é pré-requisito conceitual para correlação em qualquer feature observável futura)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Materializar P-05 (observabilidade desde o dia 1) no nível decidido pela ADR-0006 (logging estruturado local, sem infra de métricas): **um único middleware ASGI** que gera/propaga um `request_id` por requisição, emite um log JSON Lines por evento (esqueleto RED: método, rota-template, status, duração) e **correlaciona** o mesmo `request_id` no header de resposta e nos logs de erro dos Problem Details (P-11). Sem mudar o contrato `005` (request_id só em header + log).

## 2. CAs / RNs cobertos

- **CA-F005-01 (RED em forma de log):** toda requisição emite um evento estruturado com `method`, `route` (template), `status`, `duration_ms` numérico.
- **CA-F005-02 (log estruturado sem dado sensível, P-09):** o log carrega `request_id`; **nunca** body, query crua, headers arbitrários, `title`/`content`, `Authorization`/cookies.
- **ADR-0006 §8 (VINCULANTE — esta tarefa materializa, item a item):**
  - **Propagação:** middleware grava `request.state.request_id`; os handlers de `errors.py` (hoje sem o id) passam a lê-lo e logá-lo no evento de erro.
  - **id_gen injetável** no `create_app` (DI, como `_new_ulid`/`_utc_now`) — sem isso o teste de correlação não consegue afirmar o valor.
  - **Header de entrada `X-Request-ID`** sanitizado (charset `[A-Za-z0-9._-]`, ≤128) **ou** descartado e gerado ULID; **ecoado** no header de resposta.
  - **Allowlist** de campos do log (não blocklist).
  - **try/finally** — observabilidade nunca causa 500.
  - **Correlação** `log["request_id"] == resp.headers["x-request-id"]` num caso de erro.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/interfaces/observability.py` | criar | Middleware ASGI único + sanitização de `X-Request-ID` + logger JSON Lines (allowlist) + `ContextVar` do request_id. |
| `src/blog/main.py` | alterar | Registrar o middleware **único**; expor `id_gen` injetável no `create_app` (default `_new_ulid`); fiar o logger. |
| `src/blog/interfaces/errors.py` | alterar | Cada handler lê `request.state.request_id` (fallback ContextVar) e emite o log de erro correlacionado; nada muda no corpo da resposta (contrato `005` intacto). |
| `tests/integration/test_observability_http.py` | criar | TestClient HTTP real: 2 branches (com/sem header), correlação no caso de erro, negativo de PII, determinismo de `duration_ms`/`timestamp`, sanitização/log-injection. |
| `backend/coverage-gates.sh` | alterar | Nova categoria por-glob `observabilidade` (`interfaces/observability.py`) — ver §5.3 (avaliação). |
| `backend/pyproject.toml` | alterar | Eventual re-fixação do `--cov-fail-under` global ao novo patamar medido (ratchet só sobe — P-07; número decidido no review-loop, não chutado aqui). |

## 4. Design da solução

### 4.1 Um único ponto de wiring (ADR-0006 §4 "inegociável")

Middleware ASGI **único** registrado em `create_app`, **não** instrumentação espalhada por router/handler. O middleware é o produtor do evento de sucesso (status final); os handlers de `errors.py` produzem o evento de erro correlacionado pelo **mesmo** `request_id` (via `request.state` / `ContextVar`). O middleware não duplica o evento quando um handler já logou o erro — decisão de não-duplicação em §4.6.

### 4.2 Geração e sanitização do `request_id` (input externo → P-11)

```text
# observability.py
import re

_RID_CHARSET = re.compile(r"[^A-Za-z0-9._-]")
_RID_MAXLEN = 128

def sanitize_request_id(raw: str | None) -> str | None:
    """Sanitiza o header X-Request-ID de entrada. Retorna None se inservível."""
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if len(candidate) > _RID_MAXLEN:
        return None                      # excede limite → descarta, gera novo
    if _RID_CHARSET.search(candidate):
        return None                      # charset proibido (CRLF/lixo) → descarta
    return candidate
```

- **Política:** sanitização por **rejeição total** (não "limpeza parcial"). Um header com qualquer caractere fora do allowlist (inclui CR/LF, espaços, `:`) é **descartado** e o middleware **gera** um ULID via `id_gen`. Racional: limpeza parcial (`re.sub`) pode produzir um id ambíguo/colidente e mascara tentativa de injeção; rejeitar é mais simples e auditável.
- **Risco coberto:** log injection — CRLF no header quebraria o JSON Lines (1 evento = 1 linha). Rejeitar antes de qualquer log fecha o vetor. O id que entra no JSON é **sempre** charset-safe (de entrada sanitizada **ou** ULID gerado).
- **Header alvo:** `X-Request-ID` (case-insensitive, padrão HTTP). **Ecoar** o id resolvido no header de resposta `X-Request-ID`.

### 4.3 id_gen injetável (ADR-0006 §8 — sem isso o teste de correlação não afirma valor)

```text
# main.py
def create_app(
    *,
    repo: PostRepository | None = None,
    idem: IdempotencyStore | None = None,
    id_gen: Callable[[], str] = _new_ulid,      # NOVO — injetável (mesmo padrão de clock)
) -> FastAPI:
    ...
    install_observability(app, id_gen=id_gen)   # único ponto de wiring
```

- O teste de correlação injeta um `id_gen` determinístico (ex.: `lambda: "TEST-RID-01"`) e afirma `log["request_id"] == "TEST-RID-01" == resp.headers["x-request-id"]` no branch **sem** header de entrada.
- Default de runtime = `_new_ulid` (já existe). Não acoplar ao `clock`: são duas injeções independentes.

### 4.4 Campos do log (ADR-0006 §8 — allowlist, snake_case, JSON Lines stdout)

```text
event = {
    "timestamp": clock().isoformat(),     # ISO-8601 UTC (clock injetado, tz-aware)
    "level": "info" | "error",
    "request_id": rid,                    # sanitizado-ou-gerado, charset-safe
    "method": request.method,             # GET/POST/PUT
    "route": route_template,              # "/v1/posts/{post_id}"  NUNCA a path com valores
    "status": response.status_code,       # int
    "duration_ms": round(elapsed_ms, 3),  # numérico >= 0
}
emit(json.dumps(event, separators=(",", ":")))   # 1 linha, stdout
```

- **`route` é o TEMPLATE, nunca a path com valores** (ADR-0006 §8 — cardinalidade/vazamento de id). Obter de `request.scope["route"].path` (FastAPI/Starlette popula a rota casada no scope após o roteamento). Se a rota não casou (404 de rota inexistente), `route` cai para um sentinela seguro (ex.: `"<unmatched>"`) — **nunca** a path crua.
- **Allowlist é o contrato:** o evento é montado campo-a-campo a partir desta lista fixa. **Proibido** logar `request.body`, `request.url.query`, headers arbitrários, `title`/`content`, `Authorization`/cookies (hábito ensinado mesmo sem auth hoje — P-09/P-10). Não existe "passar o request inteiro pro logger".
- **`json.dumps`** garante escape de qualquer conteúdo string que entre nos campos permitidos (defesa em profundidade adicional à sanitização do id).
- **`emit`** escreve em stdout (12-factor). Implementação: `logging` com um handler/formatter que já entrega a linha pronta, **ou** `print(..., flush=True)` encapsulado — decisão de implementação no review-loop; o que importa para o teste é 1 linha JSON parseável em stdout.

### 4.5 Propagação aos handlers de erro (ADR-0006 §8 — bloqueante)

O middleware único **não** correlaciona o request_id nos Problem Details sozinho. Mecanismo:

```text
# observability.py (dentro do middleware, ANTES de chamar call_next)
rid = sanitize_request_id(request.headers.get("x-request-id")) or id_gen()
request.state.request_id = rid          # handlers já recebem Request
_request_id_ctx.set(rid)                # ContextVar — fallback p/ logs fora do ciclo
```

```text
# errors.py — helper compartilhado, aplicado em TODOS os handlers
def _request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", None) or _request_id_ctx.get("")

async def handle_validation_error(request, exc) -> JSONResponse:
    rid = _request_id_of(request)
    body = _error_body(...)                              # corpo INALTERADO (contrato 005)
    _log_error(rid, request, status=422)                # evento level=error correlacionado
    return JSONResponse(status_code=422, content=body, media_type=PROBLEM_JSON,
                        headers={"X-Request-ID": rid})   # ecoa o id também no erro
```

- **Corpo do erro inalterado:** `request_id` vai **só** no header + log (ADR-0006 §8 default; **não** mexe no `instance` do RFC 9457 → sem minor bump em `005`).
- **Header `X-Request-ID` no erro também:** o middleware pode não ter chance de injetar o header de resposta em todos os caminhos de exceção; cada handler ecoa explicitamente para garantir a asserção de correlação. (Defesa em profundidade: middleware ecoa no caminho feliz, handler ecoa no caminho de erro.)
- **`ContextVar`** (`contextvars.ContextVar[str]`) é o fallback para logs emitidos fora do `Request` (não usado hoje, mas previsto pela ADR; mantém o padrão sem custo).

### 4.6 try/finally — observabilidade nunca causa 500 (ADR-0006 §8)

```text
async def __call__(self, request, call_next):
    rid = ...; request.state.request_id = rid; token = _request_id_ctx.set(rid)
    start = perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        try:
            status = response.status_code if response is not None else 500
            self._emit_success(rid, request, status, _ms(start))
            if response is not None:
                response.headers["X-Request-ID"] = rid     # eco no caminho feliz
        except Exception:           # noqa: BLE001 — observabilidade não pode derrubar request
            pass                    # nunca propaga; log/duração best-effort
        finally:
            _request_id_ctx.reset(token)
```

- **`call_next` em try/finally;** a captura de log/duração em **try/except interno** que **nunca** re-levanta (ADR-0006 §8 — "observabilidade não pode virar causa de 500"). É o único `except Exception: pass` justificado no projeto, **comentado na linha** (anti-pattern do playbook é silenciar erro de negócio; aqui é blindar o request contra falha do logger).
- **Não-duplicação de evento de erro:** quando um handler de `errors.py` já emitiu `level=error`, o middleware ainda emite **um** evento de sucesso com o status final (ex.: 422). São papéis distintos: o handler loga o erro tipado (P-11) com correlação; o middleware fecha o RED-skeleton com status/duração. O teste de correlação ancora no evento **de erro** do handler (que tem o `request_id`), evitando ambiguidade. Alternativa rejeitada: o middleware ser o único logger e os handlers só anotarem `state` — perderia a correlação explícita no evento de erro que a ADR §8 pede como teste central.

> **Decisão registrada (trade-off):** dois eventos por requisição-com-erro (um `error` do handler + um `info`/RED do middleware) em vez de um. Aceito porque cada um responde a uma exigência distinta da ADR §8 (correlação do Problem Details vs RED-skeleton) e o volume é irrelevante no escopo local. Se virar ruído, unificar é mudança aditiva.

## 5. Impacto em testes e quality gates

### 5.1 Testes (ADR-0006 §8 — condição de aceite), via **TestClient HTTP real**

`tests/integration/test_observability_http.py`, capturando stdout (`capsys`) e parseando JSON Lines:

- **Branch COM header:** request com `X-Request-ID: TEST-FROM-CLIENT` (charset válido) → `log["request_id"] == "TEST-FROM-CLIENT"` **e** `resp.headers["x-request-id"] == "TEST-FROM-CLIENT"`.
- **Branch SEM header:** request sem `X-Request-ID`, `id_gen` injetado determinístico (`lambda: "GEN-RID"`) → `log["request_id"] == "GEN-RID"`, não-vazio; ecoado no header.
- **Correlação (teste central):** num caso de **erro já existente** (ex.: `POST /v1/posts` sem `Idempotency-Key` → 400, ou body inválido → 422) → o evento `level="error"` tem `request_id` **igual** a `resp.headers["x-request-id"]`. **Mutation-âncora:** se o handler gerar um id novo em vez de propagar o da request → teste vermelho.
- **Negativo de PII:** `POST` com `content="SENTINELA-PII-XYZ"` (e `title="SENTINELA-TITLE"`) → assertar que **nenhuma** linha de log contém `"SENTINELA-PII-XYZ"` nem `"SENTINELA-TITLE"`; assertar que as chaves do evento são **exatamente** a allowlist (set igual), barrando vazamento por campo novo.
- **Sanitização / log-injection:** `X-Request-ID: "abc\r\ninjected: true"` (ou caractere fora do charset) → o id é **descartado** e gerado; o JSON Lines continua **1 linha por evento** (parse de cada linha não falha); o header de resposta ecoa o id **gerado** (charset-safe), não o malicioso. Caso `> 128` chars → descartado e gerado.
- **`route` é template:** `GET /v1/posts/{algum-ulid}` → `log["route"] == "/v1/posts/{post_id}"` (template), **nunca** contendo o ulid. Mutation-âncora: usar `request.url.path` em vez do template → teste vermelho (vazaria o id).
- **Determinismo (flaky = P1):** assertar **presença e tipo** de `duration_ms` (numérico, `>= 0`) e `timestamp` (string ISO parseável) — **nunca** o valor. Nenhuma asserção depende de relógio de parede para conteúdo.
- **try/finally não-500:** simular logger que levanta (monkeypatch do `emit`) e afirmar que a resposta de negócio sai **200/normal** mesmo assim (observabilidade não derruba o request).

### 5.2 Gates afetados

- **Cobertura:** o módulo novo `observability.py` precisa entrar com piso próprio (ver §5.3). Os handlers de `errors.py` ganham linhas novas (log + header) — a categoria `error-handlers` (hoje 100%) deve permanecer 100%.
- **Global ratchet:** re-medir o `TOTAL` após a feature; se subir, re-fixar `--cov-fail-under` (P-07 — só sobe; número decidido no review-loop após medir, nunca chutado). Se não houver folga, escrever teste, **não** baixar piso.
- **`mypy --strict` no `src/` inteiro:** `id_gen: Callable[[], str]`, `ContextVar[str]`, assinaturas dos handlers. Rodar no projeto todo (python.md — `mypy` só nos arquivos editados não vê consumidores).
- **`ruff`:** o `except Exception: pass` do middleware exige `# noqa: BLE001` com comentário justificando (único caso autorizado).

### 5.3 Nova categoria de cobertura em `coverage-gates.sh` — **SIM, proponho adicionar**

`observability.py` é caminho de **segurança/privacidade** (sanitização de input externo + allowlist anti-PII + correlação): cai em "API pública / falha explícita" do P-07, que exige 100%. Sem categoria própria, a média global (99) **dilui** um middleware fraco — exatamente o anti-diluição que T-S2-09 institui. Adicionar:

```sh
# coverage-gates.sh — nova categoria (após "error-handlers")
# 8) Observabilidade — middleware único (sanitização de input externo, allowlist
#    anti-PII, correlação request_id). P-05 + P-09; trata input externo (P-11) → 100%.
check_category \
    "observabilidade" \
    "src/blog/interfaces/observability.py" \
    100
```

- A **sentinela anti-glob-vazio** já existente reprova se o path do módulo divergir (path errado falha o gate, não passa vacuamente) — confirmar o nome real do arquivo no review-loop.
- **Piso 100%** alinhado às categorias de risco de interface (router/erros já em 100%). Os branches de sanitização (charset inválido / `>128` / vazio / None) e o `except` do try/finally são justamente os que os testes de §5.1 cobrem; 100% morde se algum branch ficar sem teste.

## 6. Riscos

- **Log injection (CRLF):** mitigado por sanitização-por-rejeição **antes** de qualquer log + `json.dumps` (escape). Teste dedicado (§5.1 sanitização).
- **Vazamento de PII por campo novo:** mitigado por allowlist explícita (montagem campo-a-campo) + asserção de "chaves == allowlist exata" (§5.1 PII). Blocklist seria frágil; ADR §8 exige allowlist.
- **Vazamento de id na `route`:** usar template do scope, nunca `url.path`; mutation-âncora no teste.
- **Flaky por timing (P1):** **nunca** assertar valor de `duration_ms`/`timestamp` — só presença/tipo/`>=0`. Relógio injetado para o `timestamp`; nada de `now()` livre nas asserções de conteúdo (python.md).
- **Observabilidade derrubando request:** try/finally + except interno que não re-levanta; teste do logger-que-explode garante 200.
- **Duplicação de evento confundindo asserções:** o teste de correlação ancora explicitamente no evento `level=="error"` (filtra por `level`), não no primeiro log da lista — evita acoplar à ordem dos dois eventos.
- **Contaminação de ambiente:** captura de stdout por `capsys` é por-teste; `create_app` isolada por teste (in-memory injetado), padrão da suíte. Não paralelizar com escrita no mesmo stdout/DB (CLAUDE.md).
- **`ContextVar` não resetado vaza entre requests no mesmo worker:** `reset(token)` no `finally` mais interno (§4.6) — sob TestClient (sync) e ASGI, sempre resetar.

## 7. Definition of Done (verificável — amarrada à ADR-0006 §8)

- [ ] **Middleware ASGI único** registrado em `create_app` (um ponto de wiring; nada espalhado).
- [ ] **`id_gen` injetável** em `create_app` (default `_new_ulid`); teste de correlação injeta id determinístico e afirma o valor.
- [ ] **`X-Request-ID` de entrada sanitizado** (charset `[A-Za-z0-9._-]`, ≤128) **ou** descartado e ULID gerado; teste de log-injection (CRLF/`>128`) prova 1-linha-por-evento e header ecoado charset-safe.
- [ ] **Eco do `request_id`** no header `X-Request-ID` da resposta — no caminho feliz **e** no de erro.
- [ ] **Propagação:** `request.state.request_id` setado pelo middleware; todos os handlers de `errors.py` leem e logam o id; **corpo da resposta inalterado** (contrato `005` intacto, sem minor bump).
- [ ] **Log JSON Lines stdout** com **exatamente** a allowlist: `timestamp` (ISO-8601 UTC), `level`, `request_id`, `method`, `route` (**template**, nunca path com valores), `status`, `duration_ms` (numérico). Snake_case.
- [ ] **Privacidade:** teste negativo de PII com sentinela em `content`/`title` prova ausência no log; chaves do evento == allowlist exata; nunca `Authorization`/cookies/body/query.
- [ ] **try/finally:** logger que levanta **não** vira 500 (teste prova resposta de negócio normal).
- [ ] **Correlação (teste central, HTTP real):** num caso de erro, `log["request_id"] == resp.headers["x-request-id"]`; mutation-âncora (gerar id novo no log) → vermelho.
- [ ] **Determinismo:** asserções de `duration_ms`/`timestamp` por presença/tipo (`>= 0` / ISO parseável), nunca valor.
- [ ] **Gate:** nova categoria `observabilidade` (100%) em `coverage-gates.sh`; sentinela anti-glob-vazio confirmada; `error-handlers` mantém 100%; global re-fixado ao patamar medido (só sobe — P-07).
- [ ] `ruff` + `mypy --strict` (no `src/` inteiro) verdes; sem regressão na suíte; `pytest-randomly` verde.
- [ ] Revisão aprovada (`tl-python` + `tl-qa`) sem ressalvas.
