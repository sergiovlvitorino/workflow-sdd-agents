# DETAIL — T-S4-03 — SEC-03: fechar o TOCTOU de idempotência no CREATE (piso P-03)

**Sprint:** 4 (hardening)
**Tamanho:** M _(estimativa)_
**Papel:** BE (+ TL revisão `tl-python` + `tl-qa`)
**Depende de:** ADR-0003 (persistência SQLite / porta `IdempotencyStore`); T-S2-09 (gate ratchet/`coverage-gates.sh`); ADR-0007 (proposto por esta tarefa — ver §4.6)
**Bloqueia:** — (fecha a única dívida de segurança que quebra piso de constitution — baseline `docs/quality/hardening-baseline-2026-07.md`, ordem de fechamento #5)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Tornar `CreatePost.execute` **atômico sob concorrência**: dois (ou N) `POST /v1/posts` concorrentes com a **mesma** `Idempotency-Key` + mesmo payload produzem **exatamente um** post e a **mesma** resposta (mesmo `id`). Hoje a sequência `idem.get → Post.create → repo.add → idem.put` é um clássico check-then-act (TOCTOU): as leituras não são serializadas com as escritas e o `INSERT OR IGNORE` write-once só protege o registro da **chave** — que chega **depois** do `add`. Resultado atual: dois posts com `id` distintos. Isso viola **P-03** (efeito colateral duplicado), o único piso de constitution quebrado no baseline de hardening (SEC-03).

## 2. Invariantes / regras cobertos

Esta é tarefa de hardening (não entrega CA de feature). Os invariantes a **provar** por teste:

- **INV-P03-CREATE-1 (atomicidade da criação idempotente):** N `execute` concorrentes, mesma `key` + mesmo payload → `post_repo.count() == 1` **e** todas as respostas com o **mesmo** `id`. Vale para **ambos** os adapters (in-memory e SQLite — a suíte é parametrizada).
- **INV-P03-CREATE-2 (conflito preservado sob concorrência):** duas `execute` concorrentes, mesma `key` + payloads **diferentes** → a perdedora recebe `IdempotencyConflict` (→ 409), nunca um segundo post silencioso.
- **INV-P03-CREATE-3 (sem regressão sequencial):** replay sequencial (mesma key+payload → `replayed=True`, resposta original) e conflito sequencial (mesma key, payload diferente → 409) permanecem idênticos ao comportamento atual.
- **Piso governante:** P-03 (idempotência em toda rota de escrita) + P-07 (idempotência = 100% das rotas de escrita) + P-11 (falha explícita: perdedor-com-payload-divergente falha tipado, nunca "best effort").

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `backend/src/blog/application/ports.py` | alterar | `IdempotencyStore.put(...) -> bool` (True = venceu o claim write-once). Mudança de assinatura da porta → exige ADR (§4.6). |
| `backend/src/blog/application/create_post.py` | alterar | Reordenar para **claim-antes-de-criar**: `put` (claim) decide o vencedor; só o vencedor faz `repo.add`; perdedor lê o vencedor e faz replay **ou** 409. §4.3. |
| `backend/src/blog/infrastructure/sqlite_repository.py` | alterar | `SqliteIdempotencyStore.put` retorna `cursor.rowcount == 1` (INSERT OR IGNORE já é o árbitro atômico sob o `_lock` compartilhado). §4.4. |
| `backend/src/blog/infrastructure/in_memory.py` | alterar | `InMemoryIdempotencyStore.put` retorna `bool` sob um `threading.Lock` próprio (check-and-set atômico — sem lock o bool mente sob corrida). §4.5. |
| `backend/tests/integration/test_create_post_concurrency.py` | criar | **Teste de prova red-green** (§5.1): `ThreadPoolExecutor` + `Barrier`, N `execute` concorrentes sobre o use-case real, parametrizado nos 2 adapters. Nasce **vermelho** hoje. |
| `backend/tests/contract/test_post_repository_contract.py` | alterar | Reforçar o contrato write-once: `put` agora retorna `bool`; **exatamente um** True entre N puts concorrentes com a mesma key (mutation-âncora de adapter). |
| `backend/tests/unit/test_create_post_usecase.py` | alterar | Cobrir as novas ramificações do use-case (vencedor / perdedor-replay / perdedor-conflito) com fakes determinísticos. |
| `specs/adr/ADR-0007-claim-idempotente-antes-de-criar.md` | criar | ADR da mudança de contrato da porta + invariante de concorrência que o use-case passa a exigir (§4.6). |
| `backend/pyproject.toml` / `backend/coverage-gates.sh` | alterar (condicional) | Re-fixar `--cov-fail-under` ao patamar re-medido se subir (ratchet só sobe — P-07; número decidido no review-loop, nunca chutado). |

## 4. Design da solução

### 4.1 Anatomia do TOCTOU atual (o que quebra P-03)

```text
# create_post.py — HOJE (~:47-64)
existing = idem.get(key)          # (1) LEITURA — NÃO pega o _lock (só escritas pegam)
if existing is not None: ...      #     replay/409 sequencial
post = Post.create(id_gen())      # (2) ULID novo e DISTINTO por chamada
repo.add(post)                    # (3) UPSERT por post.id (ids distintos → linhas distintas)
idem.put(key, hash, resp)         # (4) INSERT OR IGNORE — write-once, mas SÓ da CHAVE, e chega DEPOIS de (3)
```

Janela de corrida: T1 e T2, mesma `key`, mesmo payload. Ambos executam (1) e veem `None` (leituras não serializadas). Ambos geram ULIDs distintos em (2), ambos persistem em (3) → **dois posts**. Em (4) o segundo `put` é no-op (write-once), então a tabela de chaves tem **uma** linha apontando para o vencedor — mas `count()==2`. O `_lock` serializa cada `add`/`put` **individual**, não o intervalo `get…put` do use-case, e `get` nem pega o lock. O UPSERT de `add` **não** deduplica: os ids são diferentes, então não há conflito de PK para colapsar.

**Conclusão de causa-raiz:** a deduplicação hoje é tentada no lugar errado (no `add`, por PK do post) e tarde demais (o claim da chave chega após o `add`). O árbitro precisa vir **antes** da criação e **decidir quem cria**.

### 4.2 Decisão: onde mora cada invariante

| Invariante | Dono | Mecanismo |
|---|---|---|
| **Claim atômico write-once** (exatamente um vencedor por key) | **Porta/adapter `IdempotencyStore.put`** | SQLite: `INSERT OR IGNORE` + `_lock` compartilhado → `rowcount==1` é o vencedor. In-memory: check-and-set sob `threading.Lock`. |
| **Claim-antes-de-criar** (só o vencedor faz `add`; perdedor faz replay/409) | **Use-case `CreatePost.execute`** | Reordena: `put` (claim) → ramifica por vencedor/perdedor. |
| **UPSERT idempotente por id** | `PostRepository.add` (inalterado) | Mantém suporte a draft→published; **deixa de ser** o ponto de dedup de criação (não conseguia deduplicar ULIDs distintos). |

A dedup migra do `add` (que não podia) para o **claim da chave** (que é o árbitro natural — a `key` é o identificador de idempotência, não o `post.id`).

### 4.3 Use-case reordenado — claim-antes-de-criar

```text
# create_post.py — DEPOIS
def execute(self, key, title, content) -> tuple[dict, bool]:
    payload_hash = _sha256_payload(title, content)

    # Fast-path sequencial (replay / conflito já materializados) — INALTERADO:
    existing = self._idem.get(key)
    if existing is not None:
        stored_hash, stored_resp = existing
        if stored_hash != payload_hash:
            raise IdempotencyConflict()          # 409 sequencial
        return dict(stored_resp), True           # replay sequencial

    # Chave ainda não vista por ESTA chamada → constrói candidato e DISPUTA o claim:
    post = Post.create(title, content, new_id=self._id_gen(), now=self._clock())
    candidate_resp = to_response_dict(post)
    won = self._idem.put(key, payload_hash, candidate_resp)   # CLAIM write-once atômico

    if won:
        self._repo.add(post)                     # só o VENCEDOR persiste o post
        return candidate_resp, False

    # PERDEDOR: outra chamada concorrente reivindicou a key primeiro.
    winner = self._idem.get(key)                 # write-once garante: já visível
    assert winner is not None                    # acabamos de perder um put → linha existe
    stored_hash, stored_resp = winner
    if stored_hash != payload_hash:
        raise IdempotencyConflict()              # 409 sob concorrência (payload divergente) — P-11
    return dict(stored_resp), True               # replay do vencedor; NÃO faz add
```

- **Por que funciona (mesma payload):** ambas as chamadas passam do `existing is None`, ambas montam posts com ULIDs distintos, ambas chamam `put`. O write-once elege **um** vencedor (`won=True`); o outro recebe `won=False`, lê a resposta do vencedor e faz replay. Só o vencedor faz `add` → `count()==1`, e o perdedor devolve o `id` do vencedor → **mesmo id em todas as respostas**.
- **Por que preserva o 409 (payload divergente):** o perdedor lê `stored_hash` do vencedor; se difere do seu, `IdempotencyConflict` → 409 (P-11, nunca um segundo post).
- **Por que não há regressão sequencial:** o `get` de fast-path continua sendo o primeiro passo; replay e 409 sequenciais seguem o caminho original, byte a byte. As ramificações novas (`won` / perdedor) **só** disparam quando duas chamadas atravessam `existing is None` na mesma janela — o cenário concorrente.

### 4.4 Adapter SQLite — `rowcount` é o árbitro (sem novo lock)

```text
# sqlite_repository.py — SqliteIdempotencyStore.put
def put(self, key, payload_hash, response_json) -> bool:
    with self._lock, self._conn:
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (key, payload_hash, response_json) "
            "VALUES (?, ?, ?)",
            (key, payload_hash, json.dumps(response_json, ensure_ascii=False)),
        )
        return cur.rowcount == 1        # 1 = inseriu (venceu); 0 = já existia (perdeu)
```

- **Atomicidade já existente:** o `_lock` compartilhado + `INSERT OR IGNORE` já serializam e resolvem write-once (ADR-0003 §4.4). A única mudança é **expor o veredito** via `rowcount`. `sqlite3` popula `rowcount` corretamente para `INSERT ... OR IGNORE` (1 quando insere, 0 quando ignora).
- **Nada muda no `_lock`** nem no schema. Sem migração.

### 4.5 Adapter in-memory — claim precisa de lock (senão o bool mente)

```text
# in_memory.py — InMemoryIdempotencyStore
def __init__(self) -> None:
    self._store: dict[str, tuple[str, dict[str, object]]] = {}
    self._lock = threading.Lock()          # NOVO — torna o check-and-set atômico

def put(self, key, payload_hash, response_json) -> bool:
    with self._lock:
        if key in self._store:
            return False                   # perdeu
        self._store[key] = (payload_hash, response_json)
        return True                        # venceu (write-once)
```

- **Por que o lock é obrigatório aqui:** sem ele, `if key not in store` → `store[key]=...` é check-then-set **não-atômico**; sob `ThreadPoolExecutor` duas threads passam o `if` e **ambas** retornam `True` → dois vencedores → dois `add` → `count()==2`. O SQLite ganha essa atomicidade de graça do `INSERT OR IGNORE`; o in-memory precisa do lock explícito. **Lição de contrato:** a garantia é do **contrato da porta**, não do adapter — cada adapter a implementa com seu mecanismo (§4.6).
- `get` e `count` permanecem sem lock (leitura de `dict` é atômica sob GIL para o uso do teste; escrita concorrente já serializada pelo lock).

### 4.6 Mudança de contrato da porta → ADR-0007 (necessário)

`IdempotencyStore.put` muda de `-> None` para `-> bool`. É **mudança de assinatura de porta** (P-12: contrato de fronteira). Exige ADR:

```text
# ports.py
class IdempotencyStore(Protocol):
    def get(self, key: str) -> tuple[str, dict[str, object]] | None: ...
    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> bool: ...
    #                                                                            ^^^^ NOVO
```

**ADR-0007 — "Claim idempotente antes de criar"** deve registrar:
- **Decisão:** `put` vira um *claim* que retorna se o chamador venceu o write-once; o use-case só cria o post se venceu.
- **Contrato de concorrência vinculante (P-06/P-12):** *qualquer* adapter futuro de `IdempotencyStore` (Redis, Postgres, DynamoDB `PutItem` com `attribute_not_exists`) **DEVE** garantir claim atômico write-once com veredito exato — senão o invariante P-03 quebra silenciosamente na troca de adapter. Isso é o que a reversibilidade de integração (P-12) exige tornar explícito.
- **Alternativa rejeitada (Approach 2 — `post_id` derivado da idem-key):** ver §4.7.
- **Status:** amenda/relaciona ADR-0003 §4.4 (write-once) sem substituí-lo.

> **Nota:** a assinatura de `PostRepository` **não** muda. `add` continua UPSERT idempotente; apenas deixa de ser (indevidamente) o ponto de dedup de criação.

### 4.7 Alternativa considerada e rejeitada — `post_id` derivado da idem-key (Approach 2 da baseline)

Derivar `post_id = f(key)` deterministicamente tornaria `add` um upsert convergente: N chamadas concorrentes com a mesma key gerariam o **mesmo** id → uma linha (o `test_concurrent_upsert_same_id_no_duplicate` já prova que o UPSERT colapsa ids iguais). In-memory ficaria trivialmente correto (`store[id]=post` é um `setitem` atômico, sem lock). **Não exigiria mudança de porta.**

**Rejeitada, apesar de mais simples, por:**
1. **Regressão de segurança (decisiva):** o `post_id` passaria a ser função de um input **controlado pelo cliente** (o header `Idempotency-Key`). O cliente escolhe a key → **prevê/enumera** o `id` do post resultante. Isso regride a propriedade "IDs são ULID (~128 bits), não enumeráveis" que o baseline lista explicitamente como piso a não regredir, e amplifica o squatting de `Idempotency-Key` (dívida já aceita no ADR-0004). Mitigar com `HMAC(key, segredo)` traria gestão de segredo (P-10) e persistência do segredo entre restarts — peso desproporcional ao escopo didático.
2. **Semântica de conflito concorrente muddy:** duas chamadas concorrentes com **mesma key + payloads diferentes** derivariam o **mesmo** id, ambas fariam UPSERT (last-write-wins no conteúdo) e poderiam devolver 201 com corpos divergentes e mesmo id — o 409 só dispararia no caminho de leitura, não na corrida. O Approach 1 mantém o 409 explícito também sob concorrência (P-11).
3. **Separação de responsabilidades:** funde **identidade** do post com **idempotência** — empurra o invariante para a geração de id (preocupação de domínio) em vez de mantê-lo na fronteira de idempotência. Perde ainda a ordenação temporal do ULID (usada como desempate no keyset `id DESC`, ADR-0002).

O Approach 1 (claim-first) preserva ULID (identidade opaca/temporal), mantém a idempotência na fronteira certa, e o custo (ADR de porta + lock in-memory) é contido e **didaticamente valioso** — ensina o padrão "claim antes de agir", a origem industrial-padrão do fix de TOCTOU em create idempotente.

## 5. Impacto em testes e quality gates

### 5.1 Teste de prova (red-green, OBRIGATÓRIO) — `tests/integration/test_create_post_concurrency.py`

Exercita o **use-case real** (`CreatePost.execute`) sobre adapters reais, **parametrizado nos 2 adapters** (espelha `test_post_repository_contract.py`). O `test_sqlite_concurrency.py` existente cobre `add`/`put` de adapter isolados, **nunca** o caminho use-case com a **mesma** key — este é o gap que fecha SEC-03.

```text
_N = 12                      # ≥ 8 p/ tornar o vermelho confiável

@pytest.fixture(params=["in_memory", "sqlite"], ids=["in_memory", "sqlite"])
def use_case(request, tmp_path):
    # monta CreatePost com repo+idem reais do adapter, clock fixo, id_gen = ULID REAL
    # (id_gen precisa gerar ids DISTINTOS por chamada — senão a corrida não se manifesta;
    #  NÃO injetar id_gen constante aqui, ao contrário dos unit tests)
    ...

def test_concurrent_same_key_same_payload_creates_single_post(use_case, post_repo):
    barrier = threading.Barrier(_N)                  # latch: libera todas juntas
    def worker():
        barrier.wait()                               # maximiza a sobreposição (sem sleep → sem flaky)
        resp, _ = use_case.execute("SAME-KEY", "Título", "Conteúdo")
        return resp["id"]
    with ThreadPoolExecutor(max_workers=_N) as pool:
        futures = [pool.submit(worker) for _ in range(_N)]
        ids = [f.result() for f in as_completed(futures)]   # propaga exceção se houver
    assert post_repo.count() == 1, f"P-03 violado: {post_repo.count()} posts para 1 key"
    assert len(set(ids)) == 1, f"ids divergentes sob concorrência: {set(ids)}"
```

- **Determinismo (flaky = P1):** `threading.Barrier(_N)` como latch — **nenhum** `sleep`. Todas as threads bloqueiam até a N-ésima chegar, então disparam quase-simultaneamente, garantindo que todas atravessem `existing is None` **antes** de qualquer `put`. Isso faz o **vermelho ser confiável** no código atual (sem barreira, o scheduler poderia serializar por sorte → falso-verde). As asserções são de **estado** (`count`, `set(ids)`), nunca de timing.
- **id_gen REAL (distinto por chamada):** ao contrário dos unit tests (que injetam `id_gen` constante), aqui o `id_gen` precisa produzir ULIDs distintos — senão o TOCTOU não se manifesta e o teste não nasceria vermelho. Ponto de atenção explícito no review-loop.
- **Nasce vermelho hoje:** código atual → cada thread gera ULID distinto e faz `add` → `count()==_N` (ou ≥2) e `len(set(ids))==_N`. **Ambas** as asserções falham. Após o fix → `count()==1`, `len(set(ids))==1`.

**Teste do conflito sob concorrência (INV-P03-CREATE-2):**

```text
def test_concurrent_same_key_divergent_payload_one_conflict(use_case, post_repo):
    # 2 threads, mesma key, payloads diferentes, barreira p/ colidir
    # → exatamente uma levanta IdempotencyConflict; exatamente 1 post; ids iguais entre não-conflitantes
    ...
    assert post_repo.count() == 1
    assert conflicts == 1
```

### 5.2 Mutation-âncoras (reverter o fix → vermelho)

- **Âncora principal (ordem):** trocar `if won: repo.add(post)` de volta para `repo.add(post)` **incondicional** (perdedor também cria) → `count()==_N` → `test_concurrent_same_key_same_payload` **vermelho**.
- **Âncora do claim (adapter):** fazer `SqliteIdempotencyStore.put` retornar `True` fixo (ignorar `rowcount`) → todos "vencem" → dois `add` → vermelho no cenário SQLite.
- **Âncora do lock in-memory:** remover o `self._lock` de `InMemoryIdempotencyStore.put` → bool mente sob corrida → vermelho no cenário in-memory (prova que o lock é load-bearing, não decorativo).
- **Âncora de contrato (adapter, em `test_post_repository_contract.py`):** N `put` concorrentes com a mesma key → **exatamente um** `True`. Se `put` sempre retornar `True`/`None` → vermelho.
- **Âncora do 409:** remover o `if stored_hash != payload_hash: raise` do ramo perdedor → conflito concorrente vira replay silencioso → `test_concurrent...divergent_payload` vermelho (P-11).

### 5.3 Gates afetados

- **Cobertura (P-07 — idempotência = 100% das rotas de escrita):** `create_post.py` é use-case de idempotência → categoria de risco máxima. As **cinco** ramificações precisam de cobertura: (a) replay sequencial, (b) 409 sequencial, (c) `won` (cria), (d) perdedor-replay, (e) perdedor-409. (a)/(b) já cobertos; (c)/(d)/(e) cobertos pelos testes de §5.1 + unit. Confirmar 100% branch em `create_post.py` no gate.
- **Contrato de adapter:** `test_post_repository_contract.py::test_put_is_write_once_idempotent` passa a assertar o `bool` (primeiro `put` → `True`; segundo → `False`). `InMemoryIdempotencyStore` e `SqliteIdempotencyStore` mantêm paridade (a suíte roda parametrizada — nenhum adapter pode divergir).
- **`mypy --strict` no `src/` inteiro:** assinatura nova `put(...) -> bool` no Protocol e nos 2 adapters; rodar no projeto todo (não só arquivos tocados — `mypy` parcial não vê os consumidores; `docs/lessons/python.md`).
- **`ruff`** nos arquivos tocados (pinado do projeto — CLAUDE.md); `pytest-randomly` verde (a barreira não introduz dependência de ordem).
- **Global ratchet:** re-medir `TOTAL` após a feature; se subir, re-fixar `--cov-fail-under` (só sobe — P-07; número medido no review-loop, nunca chutado). Sem folga → escrever teste, **não** baixar piso.

## 6. Riscos

- **Deadlock no `_lock` (analisado — NÃO ocorre):** o vencedor faz `put` (adquire `_lock`) e **depois** `add` (adquire `_lock`) — aquisições **sequenciais**, não aninhadas: `put` libera o lock ao sair do `with` **antes** de `add` entrar. `threading.Lock` é não-reentrante e travaria se aninhado, mas o design nunca aninha (`put`→release→`add`). O perdedor faz `put`→`get` (leitura sem lock). Confirmar no review que nenhuma refatoração introduza `add` **dentro** do `with self._lock` do `put`.
- **Regressão nos testes de idempotência sequencial:** mitigada por manter o `get` de fast-path como primeiro passo intacto — replay/409 sequenciais seguem o caminho original. Os testes existentes (`test_replay_returns_stored_response`, `test_conflicting_payload_raises`, `test_put_is_write_once_idempotent`) devem continuar verdes (o último ganha só a asserção do `bool`).
- **Janela de falha parcial (residual, documentar):** o vencedor faz `put` (claim) e **depois** `add`. Se `add` falhar após o claim, a key fica reivindicada apontando para um post inexistente (replays devolvem uma resposta consistente para um post que não persistiu). É a mesma classe de janela do código atual (que hoje pode deixar post órfão sem key) — não pior. Fechar de verdade exige *unit-of-work* transacional cobrindo as duas tabelas (fora do escopo; candidato a follow-up junto de SEC-06). Registrar como dívida residual conhecida no ADR-0007, não silenciar.
- **`rowcount` de `INSERT OR IGNORE`:** validar no adapter que `sqlite3` retorna `1`/`0` (comportamento padrão; um teste de contrato dedicado ancora isso).
- **Flaky por timing (P1):** eliminado por `Barrier` (latch) + asserções só de estado; **sem** `sleep`, **sem** asserção de ordem/tempo.
- **Contaminação de ambiente:** cada parametrização usa `tmp_path`/instância isolada (padrão da suíte de contrato). **Não paralelizar** este teste com outros que escrevem no mesmo DB/arquivo (CLAUDE.md — o `ThreadPoolExecutor` interno é intencional e isolado por fixture; a suíte externa não deve rodar agentes concorrentes no mesmo repo+DB).
- **`id_gen` no teste de prova:** se por engano injetarem `id_gen` constante (como nos unit tests), a corrida some e o teste não nasce vermelho — falso-verde. Chamado explicitamente em §5.1.

## 7. Definition of Done (verificável — amarrada a P-03)

- [ ] **`CreatePost.execute` reordenado** para claim-antes-de-criar: só o vencedor do claim faz `repo.add`; perdedor faz replay (mesma payload) ou `IdempotencyConflict` (payload divergente).
- [ ] **`IdempotencyStore.put -> bool`** na porta e nos 2 adapters; SQLite via `rowcount==1`, in-memory via check-and-set sob `threading.Lock`.
- [ ] **Teste de prova red-green** (`test_create_post_concurrency.py`), **parametrizado nos 2 adapters**, com `Barrier`: `post_repo.count()==1` **e** `len(set(ids))==1` sob N `execute` concorrentes mesma key+payload. Provado que **nasce vermelho** no código atual e passa após o fix (registrar o run vermelho no PR — red-green, CLAUDE.md).
- [ ] **Conflito sob concorrência** (payload divergente, mesma key) → exatamente um `IdempotencyConflict`, exatamente 1 post (P-11).
- [ ] **Mutation-âncoras** verificadas: reverter a ordem (`add` incondicional), o `rowcount`, e o lock in-memory → cada uma torna a prova vermelha (§5.2).
- [ ] **Sem regressão sequencial:** replay/409 sequenciais e write-once permanecem verdes; `test_put_is_write_once_idempotent` passa a assertar o `bool` sem quebrar paridade entre adapters.
- [ ] **Cobertura:** 5 ramificações de `create_post.py` cobertas (100% branch na categoria idempotência — P-07); global re-fixado ao patamar medido se subir (só sobe).
- [ ] **ADR-0007** criado: decisão claim-first, contrato de concorrência vinculante para adapters futuros (P-12), alternativa `post_id`-derivado rejeitada com justificativa, janela de falha parcial registrada como dívida residual.
- [ ] `ruff` (arquivos tocados) + `mypy --strict` (no `src/` inteiro) verdes; `pytest-randomly` verde; sem regressão na suíte.
- [ ] Revisão aprovada (`tl-python` + `tl-qa`) sem ressalvas.
