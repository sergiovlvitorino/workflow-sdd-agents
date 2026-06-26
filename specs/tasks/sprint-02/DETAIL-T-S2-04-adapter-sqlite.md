# DETAIL — T-S2-04 — Adapter SQLite (PostRepository + IdempotencyStore)

**Sprint:** 2
**Tamanho:** L _(estimativa)_
**Papel:** BE (+ TL revisão)
**Depende de:** — _(usa só as portas já existentes em `application/ports.py`; ver §4 sobre o método `get`)_
**Bloqueia:** T-S2-05 (precisa de `get(id)` na porta), T-S2-06, T-S2-07 (precisam de durabilidade real em runtime)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Entregar persistência durável local: um adapter SQLite (`SqlitePostRepository` + `SqliteIdempotencyStore`) que implementa as **mesmas portas** já definidas, provando na prática a reversibilidade da arquitetura hexagonal (P-12) — o blog passa a lembrar dos posts entre execuções **sem tocar uma linha de `domain/` ou da lógica dos casos de uso**.

## 2. CAs / RNs cobertos

- **ADR-0003 §4 (inegociável):** domínio e casos de uso intactos; schema explícito/versionável; ≥1 integração HTTP no wiring de produção (SQLite).
- **ADR-0003 §8 (vinculante) — esta tarefa materializa:**
  - Driver `sqlite3` da **stdlib** (sem ORM).
  - **Atomicidade da idempotência (P-03):** `UNIQUE` + `INSERT OR IGNORE` no store de idempotência (write-once). O `add(post)` usa **UPSERT** (`ON CONFLICT(id) DO UPDATE`), não `INSERT OR IGNORE` — ver §4.4 para o racional (necessário para a transição draft→published de T-S2-05; P-03 garantida pelo store write-once + retorno antecipado em `create_post.py`, não pelo `add`).
  - **Concorrência/thread (P-11):** conexão-por-request + `PRAGMA journal_mode=WAL`; nada de `ProgrammingError` intermitente (flaky = P1).
  - **Mapeamento:** grava `PostStatus.value`; datetimes ISO-8601 **UTC tz-aware** (ler de volta naive quebra o keyset); comparação keyset **row-value** `(published_at, id) < (?, ?)`.
  - **Durabilidade entre conexões em arquivo** (`tmp_path`, **nunca** `:memory:` no teste-âncora).
- **ADR-0002:** keyset opaco preservado, estrito `<`, ordenação `(published_at DESC, id DESC)`.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/infrastructure/sqlite_repository.py` | criar | `SqlitePostRepository` + `SqliteIdempotencyStore` + `init_schema(conn)` + fábrica de conexão. |
| `src/blog/application/ports.py` | alterar | Adicionar `get(self, id: str) -> Post \| None` à `PostRepository` (ver §4 — extensão de contrato de fronteira, não muda comportamento existente). |
| `src/blog/infrastructure/in_memory.py` | alterar | Implementar `get(id)` no `InMemoryPostRepository` para manter paridade de contrato. |
| `src/blog/main.py` | alterar | `create_app(*, repo=None, idem=None)` parametrizável: SQLite **default em runtime**, in-memory injetável nos testes. |
| `.gitignore` | alterar | Ignorar `*.db`, `*.db-wal`, `*.db-shm` (arquivo SQLite fora do VCS — ADR-0003 §4). |
| `tests/contract/test_post_repository_contract.py` | criar | Suíte de contrato de porta **parametrizada** (in-memory **e** SQLite). |
| `tests/integration/test_sqlite_durability.py` | criar | Durabilidade entre conexões (escreve numa instância, lê em **nova** instância no mesmo arquivo). |
| `tests/integration/test_sqlite_http.py` | criar | ≥1 integração HTTP montando a app com o adapter SQLite real (wiring de produção). |

> **Higiene de DETAIL:** a alteração de `application/ports.py` (adicionar `get`) é tecnicamente uma mudança de fronteira, **não** de comportamento de domínio/caso de uso. ADR-0003 §4 proíbe que a *troca de adapter* exija tocar `domain/`/lógica de aplicação; adicionar um método à porta para suportar **novas features** (F002/F004) é extensão legítima, não vazamento. Sem `get`, T-S2-05/07 não têm como buscar por id. A alternativa (porta `PostReaderById` separada) é registrada como trade-off em §4.

## 4. Design da solução

### 4.1 Decisão de fronteira: `get(id)` na porta

`PublishPost` (T-S2-05) e `GET /v1/posts/{id}` (T-S2-07) precisam buscar um post por id. Duas opções:

| Critério | A. Adicionar `get` a `PostRepository` _(escolhida)_ | B. Nova porta `PostReaderById` |
|---|---|---|
| Acoplamento | 1 porta coesa "repositório de posts" | 2 portas, mais cerimônia |
| Aderência ao código atual | `count()`/`add()`/`list_published()` já moram juntos | divide responsabilidade artificialmente |
| Risco de vazamento | nenhum — é leitura por chave primária | nenhum |

**Recomendação:** A. `get(id)` é a operação de leitura por chave primária natural de um repositório. Adicionar à porta existente. Os **dois** adapters (in-memory + SQLite) implementam, garantido pela suíte de contrato.

```text
# application/ports.py — adição
class PostRepository(Protocol):
    def add(self, post: Post) -> None: ...
    def get(self, id: str) -> Post | None: ...      # NOVO — leitura por PK (None se ausente)
    def count(self) -> int: ...
    def list_published(self, *, after, limit) -> list[Post]: ...
```

### 4.2 Schema (explícito e versionável — ADR-0003 §4)

```sql
CREATE TABLE IF NOT EXISTS posts (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    status       TEXT NOT NULL,            -- PostStatus.value ('draft' | 'published')
    created_at   TEXT NOT NULL,            -- ISO-8601 UTC tz-aware, sufixo +00:00
    published_at TEXT                      -- nullable; ISO-8601 UTC tz-aware
);
-- índice que reflete a ordenação keyset (published_at DESC, id DESC)
CREATE INDEX IF NOT EXISTS ix_posts_published
    ON posts (published_at DESC, id DESC)
    WHERE status = 'published';

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key           TEXT PRIMARY KEY,        -- UNIQUE via PK
    payload_hash  TEXT NOT NULL,
    response_json TEXT NOT NULL            -- json.dumps da resposta serializada
);
```

`init_schema(conn)` roda `CREATE TABLE IF NOT EXISTS` (idempotente) no boot. Schema explícito, não "mágica" implícita (P-11).

### 4.3 Conexão e concorrência (ADR-0003 §8)

```text
def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
```

**Estratégia adotada — conexão única compartilhada por app + lock para serializar escrita** (mais simples que conexão-por-request para o escopo local/didático, e suficiente sob o threadpool do Uvicorn):

- `check_same_thread=False` permite o threadpool do Uvicorn usar a conexão.
- `threading.Lock` protege as **escritas** (`add`, `put`) contra `ProgrammingError`/corrupção concorrente. Leituras keyset são consistentes sob WAL.
- WAL: leitores não bloqueiam o escritor.

Trade-off explícito: conexão-por-request seria mais "produção-like", mas reabrir conexão/PRAGMA por request adiciona ruído pedagógico sem ganho no contexto monousuário local. A escolha (conexão compartilhada + lock + WAL) é **explícita no código**, como exige a §8 ("comportamento explícito — nada de `ProgrammingError` intermitente").

### 4.4 Atomicidade da idempotência (P-03 — bloqueante na §8)

O risco: `create_post.py` chama `repo.add(post)` e depois `idem.put(...)` em sequência. Se `put` falhar após `add` comitar, um replay recriaria o post → viola P-03.

**Decisão (explícita, reconciliada no review-loop de T-S2-04 — aprovada por tl-python + tl-qa):**

- O **store de idempotência** é write-once: `INSERT OR IGNORE` (+ `UNIQUE`), naturalmente idempotente por chave. Replay vira no-op; `get(key)` recupera o `(hash, response_dict)` original.
- O **`add(post)` usa UPSERT** (`INSERT ... ON CONFLICT(id) DO UPDATE SET ...`), **não** `INSERT OR IGNORE`. Racional: `INSERT OR IGNORE` ignoraria silenciosamente a transição `draft → published` de T-S2-05 (a linha já existe pelo id), reintroduzindo o "blog não publica de verdade". O UPSERT **não viola P-03**: no fluxo de criação, o replay é interceptado em `create_post.py` (retorno antecipado via `idem.get(key)`) **antes** de `add` ser chamado — a idempotência de criação é garantida pelo store write-once, não pelo `add`.

```text
def add(self, post: Post) -> None:
    with self._lock, self._conn:                      # transação implícita; _lock é COMPARTILHADO com o idem-store (mesma conexão)
        self._conn.execute(
            "INSERT INTO posts (id,title,content,status,created_at,published_at) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "  title=excluded.title, content=excluded.content, status=excluded.status, "
            "  published_at=excluded.published_at",
            (post.id, post.title, post.content, post.status.value,
             _iso(post.created_at), _iso(post.published_at)),
        )

def put(self, key, payload_hash, response_json) -> None:
    with self._lock, self._conn:                      # MESMO _lock do repositório (serializa add+put na conexão compartilhada)
        self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (key,payload_hash,response_json) VALUES (?,?,?)",
            (key, payload_hash, json.dumps(response_json, ensure_ascii=False)),
        )
```

> **Concorrência (ressalva bloqueante do review-loop):** como `SqlitePostRepository` e `SqliteIdempotencyStore` compartilham a **mesma** `sqlite3.Connection`, eles DEVEM compartilhar o **mesmo** `threading.Lock`. Um lock por adapter não serializa `add`+`put` na conexão (transações implícitas intercaladas entre threads → comportamento intermitente, viola §8/P-11). O lock nasce junto da conexão (em `make_connection`/holder) e é injetado nos dois adapters. Coberto por teste de concorrência (ThreadPoolExecutor disparando `add`+`put` em paralelo).

```text
def get(self, key) -> tuple[str, dict] | None:
    row = self._conn.execute(
        "SELECT payload_hash, response_json FROM idempotency_keys WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return None
    return row["payload_hash"], json.loads(row["response_json"])
```

### 4.5 Mapeamento e keyset (ADR-0003 §8, ADR-0002)

```text
def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None           # tz-aware → "...+00:00"

def _parse(s: str | None) -> datetime | None:
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)   # nunca devolve naive

def list_published(self, *, after, limit) -> list[Post]:
    if after is None:
        rows = self._conn.execute(
            "SELECT * FROM posts WHERE status='published' "
            "ORDER BY published_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        after_ts, after_id = after
        rows = self._conn.execute(
            "SELECT * FROM posts WHERE status='published' "
            "AND (published_at, id) < (?, ?) "            # row-value, estrito '<' (ADR-0002)
            "ORDER BY published_at DESC, id DESC LIMIT ?",
            (_iso(after_ts), after_id, limit),
        ).fetchall()
    return [_row_to_post(r) for r in rows]
```

`_row_to_post` reconstrói `Post` com `PostStatus(row["status"])` e datetimes tz-aware via `_parse`. Comparação **row-value** `(published_at, id) < (?, ?)` (SQLite suporta) — atenção: comparar como strings ISO funciona porque ISO-8601 UTC é lexicograficamente ordenável **desde que** todos os timestamps tenham o mesmo offset (`+00:00`); por isso a gravação tz-aware UTC é inegociável.

### 4.6 Factory parametrizável (`main.py`)

```text
def create_app(*, repo=None, idem=None) -> FastAPI:
    if repo is None or idem is None:                  # default de RUNTIME = SQLite
        db_path = os.environ.get("BLOG_DB_PATH", "blog.db")
        conn = _connect(db_path); init_schema(conn)
        repo = repo or SqlitePostRepository(conn)
        idem = idem or SqliteIdempotencyStore(conn)
    # ... casos de uso recebem repo/idem (wiring idêntico ao atual)
    app.state.post_repo = repo
```

Testes unit/integration injetam in-memory: `create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())`. Runtime usa SQLite por omissão. **Atenção (lição python.md):** não setar `BLOG_DB_PATH` no import de um teste — vaza para os outros. Use `tmp_path` + injeção direta nos testes SQLite.

## 5. Impacto em testes e quality gates

- **Suíte de contrato de porta parametrizada** (`@pytest.fixture(params=[in_memory, sqlite])`): mesma sequência de ids → mesmo `count()`, mesmo `get(id)`, mesma página keyset, mesmo replay de idempotência. Roda os mesmos casos contra os dois adapters (ADR-0003 §8).
- **Durabilidade entre conexões:** escreve com `SqlitePostRepository(conn_a)`, abre **nova** conexão/instância no mesmo `tmp_path` e lê de volta — feature-âncora do ADR. **Nunca `:memory:`** (cada conexão `:memory:` é um banco distinto — mascararia o teste).
- **≥1 integração HTTP com SQLite:** `create_app` montada com adapter SQLite real (`BLOG_DB_PATH=tmp_path/x.db` via injeção) — exercita o wiring de produção (anti-falso-verde).
- **Replay idempotente contra `SqliteIdempotencyStore` real:** dois POSTs mesma chave → `count()==1`, formato persistido/serialização exercitado.
- **Mutation-âncora:** `<` → `<=` no WHERE keyset SQLite duplica a fronteira → teste vermelho (paginação de página completa repete o item de fronteira).
- **Gates:** o `--cov-fail-under=95` é **global** hoje. ADR-0003 §8 exige **piso próprio do adapter, não diluído**. O adapter está factualmente a 100%; o **mecanismo** que faz o piso por-categoria "morder" (`coverage report --include=...` por categoria, gate AND) é responsabilidade de **T-S2-09** (gate ratchet backend), que sistematiza todos os pisos por-categoria de uma vez — esta tarefa não cria gate ad-hoc. _(Não relaxar o global; o piso do adapter entra no conjunto de T-S2-09.)_

## 6. Riscos

- **`sqlite3` e threads:** sem `check_same_thread=False` + lock → `ProgrammingError` intermitente sob threadpool (flaky = P1). Mitigado pela §4.3.
- **Datetime naive ao ler:** `datetime.fromisoformat` sem tz quebra o keyset e a serialização `Z`. `_parse` força tz-aware (lição python.md "ler de volta naive quebra o keyset").
- **`:memory:` em teste de durabilidade:** daria falso-verde (banco some). Teste-âncora **deve** usar arquivo em `tmp_path`.
- **Comparação keyset string vs row-value:** depende de todos os timestamps serem UTC `+00:00`; se algum entrar com outro offset, a ordenação lexicográfica fura. Mitigado: gravação sempre tz-aware UTC (clock injetado já produz UTC).
- **Contaminação de ambiente (CLAUDE.md):** não paralelizar agentes que escrevem no mesmo `.db`. Cada teste usa `tmp_path` isolado; runtime usa `blog.db` único.
- **Arquivo `.db` versionado por engano:** `.gitignore` cobre `*.db*`; revisar no `git diff --stat` antes do PR.

## 7. Definition of Done (verificável)

- [ ] `SqlitePostRepository` e `SqliteIdempotencyStore` implementam as portas; `domain/` e a lógica de `application/` **inalterados** (só a assinatura `get` adicionada à porta + impl nos dois adapters).
- [ ] Suíte de contrato parametrizada verde contra **ambos** os adapters (mesmo `count`, `get`, página keyset, replay).
- [ ] Teste de durabilidade entre conexões verde com arquivo `tmp_path` (não `:memory:`).
- [ ] ≥1 integração HTTP com a app montada sobre SQLite real, verde (wiring de produção).
- [ ] Replay idempotente contra o store SQLite real → `count()==1`.
- [ ] Mutation-âncora `<`→`<=` mata o teste de keyset.
- [ ] `add` = UPSERT (`ON CONFLICT(id) DO UPDATE`); store de idempotência write-once (`INSERT OR IGNORE` + `UNIQUE`) — P-03 explícita no código (ver §4.4).
- [ ] `PRAGMA journal_mode=WAL` + `check_same_thread=False` + **lock de escrita ÚNICO compartilhado** entre repo e idem-store (mesma conexão); teste de concorrência (`add`+`put` paralelos) verde.
- [ ] `.gitignore` ignora `*.db*`; nenhum `.db` no `git diff main HEAD --stat`.
- [ ] Cobertura global ≥ 95% **e** adapter (`sqlite_repository.py`) medido ≥ 95% (factual: 100%). O **wiring** do gate por-categoria (que faz o piso "morder") é consolidado em **T-S2-09** — não duplicar mecanismo ad-hoc aqui.
- [ ] `ruff` + `mypy --strict` no `src/` inteiro verdes.
- [ ] Revisão aprovada (tl-python + tl-qa) sem ressalvas.
