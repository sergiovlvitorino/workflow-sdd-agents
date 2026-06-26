# DETAIL — T-F001-01 — Criar post com idempotência (`POST /v1/posts`)

**Sprint:** 01
**Tamanho:** M _(estimativa)_
**Papel:** BE (`dev-python`) + TL revisão (`tl-python` + `tl-qa`)
**Depende de:** — (primeira tarefa; estabelece a entidade `Post` e o esqueleto FastAPI)
**Bloqueia:** T-F003-01 (lista paginada reusa a entidade `Post` e o app)

> Produzido por `tl-python` no sprint-flow; consumido pelo review-loop (implementação + revisão). Descrito no presente — o status real vive no board, não aqui. Realiza RF-001..004 e os shapes de `005-api-contract.md`.

---

## 1. Objetivo

Entregar `POST /v1/posts` criando um post idempotente: payload válido + chave nova → `201` com `id` e `status="draft"`; replay com a mesma chave não duplica e devolve o mesmo `id`; payload inválido e ausência de chave falham com erro tipado. É o **P-03 em ação** que o dev-aprendiz vê nascer (valor pedagógico central da Sprint 1).

## 2. CAs / RNs cobertos

- **CA-F001-01 (RF-001):** criação bem-sucedida → `201`, corpo com `id` e `status="draft"`.
- **CA-F001-02 (RF-002, P-03):** retry com a mesma `Idempotency-Key` e mesmo payload não cria post novo; retorna o **mesmo `id`** (este contrato fixa `200` + `Idempotent-Replayed: true`).
- **CA-F001-03 (RF-003, P-11):** payload sem `title` → `422` com `validation_error` apontando `title`.
- **CA-F001-04 (RF-004, P-03):** sem header `Idempotency-Key` → `400` `idempotency_key_required`.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `backend/src/blog/domain/post.py` | criar | Entidade `Post` (dataclass), enum `PostStatus`, fábrica `Post.create(...)` com relógio e id-gen injetados. |
| `backend/src/blog/application/ports.py` | criar | `Protocol`s `PostRepository` e `IdempotencyStore`. |
| `backend/src/blog/application/create_post.py` | criar | Caso de uso `CreatePost` (idempotência + criação). |
| `backend/src/blog/infrastructure/in_memory.py` | criar | Adapters in-memory das duas portas — **marcado como DIDÁTICO** (ADR-0001). |
| `backend/src/blog/interfaces/schemas.py` | criar | `CreatePostRequest`, `PostResponse` (Pydantic v2) conforme `005` §3. |
| `backend/src/blog/interfaces/errors.py` | criar | `ApiError` (Problem Details RFC 9457) + exception handlers (`422`/`400`/`409`). |
| `backend/src/blog/interfaces/posts_router.py` | criar | Router `POST /v1/posts`; dependency `require_idempotency_key`. |
| `backend/src/blog/main.py` | criar | Composição: instancia adapters, injeta no caso de uso, monta `FastAPI(app)`, registra handlers. |
| `backend/tests/integration/test_create_post_http.py` | criar | Teste HTTP real via `TestClient` (cobre os 4 CAs + replay/estado). |
| `backend/tests/unit/test_create_post_usecase.py` | criar | Unit do caso de uso (idempotência, conflito de payload) com fakes. |

## 4. Design da solução

**Domínio puro (relógio e id injetados — `docs/lessons/python.md`: não usar `now()`/`hash()` no construtor):**

```python
class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

@dataclass(frozen=True)
class Post:
    id: str
    title: str
    content: str
    status: PostStatus
    created_at: datetime
    published_at: datetime | None

    @staticmethod
    def create(title: str, content: str, *, new_id: str, now: datetime) -> "Post":
        return Post(id=new_id, title=title, content=content,
                    status=PostStatus.DRAFT, created_at=now, published_at=None)
```

**Portas (P-12):**

```python
class PostRepository(Protocol):
    def add(self, post: Post) -> None: ...

class IdempotencyStore(Protocol):
    # devolve (payload_hash, response_json) ou None
    def get(self, key: str) -> tuple[str, dict] | None: ...
    def put(self, key: str, payload_hash: str, response_json: dict) -> None: ...
```

**Caso de uso — idempotência por chave + resposta persistida (ADR-0001), hash determinístico `sha256`:**

```python
class CreatePost:
    def __init__(self, repo, idem, *, clock, id_gen): ...
    def execute(self, key: str, title: str, content: str) -> tuple[dict, bool]:
        payload_hash = sha256(canonical_json({"title": title, "content": content}))
        existing = self.idem.get(key)
        if existing is not None:
            stored_hash, stored_resp = existing
            if stored_hash != payload_hash:
                raise IdempotencyConflict()          # → 409
            return stored_resp, True                 # replay → (resp, replayed=True)
        post = Post.create(title, content, new_id=self.id_gen(), now=self.clock())
        self.repo.add(post)
        resp = to_response_dict(post)
        self.idem.put(key, payload_hash, resp)
        return resp, False                            # criado → (resp, replayed=False)
```

**Interface HTTP:**

- `Idempotency-Key` como **dependency** que devolve a chave ou levanta `400 idempotency_key_required` quando ausente/vazia (P-03). É a peça nomeável que o dev vê (ADR-0001).

```python
def require_idempotency_key(idempotency_key: str | None = Header(default=None)) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise IdempotencyKeyRequired()               # → 400 (handler → ApiError)
    return idempotency_key
```

- Validação de `title`/`content` via Pydantic v2 (`min_length=1`, `max_length`) → `422` automático, convertido pelo handler para `ApiError` com `errors[]` apontando o campo (`005` §4).
- Router: `replayed=False` → `201`; `replayed=True` → `200` + header `Idempotent-Replayed: true`.
- Exception handlers (centralizados em `errors.py`): `RequestValidationError`→`422`, `IdempotencyKeyRequired`→`400`, `IdempotencyConflict`→`409`. `Content-Type: application/problem+json`.

**Decisões registradas:** idempotência simples (sem outbox) e adapter in-memory são de ADR-0001 — não reabrir aqui.

## 5. Impacto em testes e quality gates

- **Testes novos:**
  - **Integração HTTP real (`TestClient`)** — obrigatório por rota nova (`docs/lessons/qa.md`: handler por baixo não cobre middleware/serialização/DI):
    - CA-F001-01: `201`, body com `id` e `status=="draft"`.
    - CA-F001-02: 2º POST mesma chave+payload → `200`, `Idempotent-Replayed: true`, **mesmo `id`**, e **asserir o estado**: o repositório tem **1** post, não 2 (não basta o status — `docs/lessons/qa.md`: status HTTP não pega bug de estado).
    - CA-F001-03: sem `title` → `422`, `type` sufixo `validation_error`, `errors[0].field == "title"`.
    - CA-F001-04: sem header → `400`, `type` sufixo `idempotency_key_required`.
    - Extra (branch de erro): mesma chave + payload divergente → `409`.
  - **Unit do caso de uso:** idempotência, replay devolve resposta gravada, conflito de payload. O fake do store deve **retornar o objeto visível no estado** (não `None` quando há registro) para a mutation-âncora ser alcançável (`docs/lessons/qa.md`).
- **Mutation-âncora (o teste morde pelo motivo certo):**
  - Inverter o guard de idempotência (sempre criar) → CA-F001-02 vermelho (vira 2 posts / `id` diferente).
  - Remover a dependency `require_idempotency_key` → CA-F001-04 vermelho.
  - Trocar `sha256(payload)` por valor fixo → o teste de `409` vermelho.
- **Cobertura esperada:** API pública = **100% dos endpoints com teste de contrato**; idempotência = **100% das rotas de escrita** (P-07). Domínio (`Post.create`) ≥ 90% linha.
- **Gates afetados:** ratchet de cobertura backend (`pytest --cov`, por-stack — ADR-0001); sem `skip` (in-memory não exige infra externa → não há justificativa para skip).

## 6. Riscos

- **Falso-verde de idempotência:** assertar só `status==200` no replay sem checar a contagem de posts mascara duplicação. Mitigação: asserir o estado do repositório (1 post) e o `id` igual.
- **Fake que espelha contrato mas não o caminho:** se o store fake guardar a resposta numa chave conveniente e a produção depender do formato persistido, o caminho de replay nunca roda de verdade. Mitigação: o teste de replay exercita o **store real** (in-memory de produção), não um dublê ad-hoc (`docs/lessons/qa.md`).
- **`now()`/`hash()` no domínio:** timestamp falso e chave não-determinística (`PYTHONHASHSEED`). Mitigação: relógio e id-gen injetados; `sha256` para o payload-hash.
- **Guard adjacente matando mutação:** no teste negativo de `422`, garantir que o input está válido o suficiente para alcançar o mecanismo testado quando o gate alvo for removido.

## 7. Definition of Done (verificável)

- [ ] CA-F001-01..04 automatizados e **verdes com execução real** (`TestClient`), não só "compila".
- [ ] Replay testado por **estado** (contagem de posts) além do status HTTP.
- [ ] Branch `409` (conflito de payload) coberto.
- [ ] Cobertura ≥ piso P-07 (API 100% endpoints; idempotência 100% rota de escrita; domínio ≥ 90%).
- [ ] Mutation-âncoras da §5 verificadas (reverter o fix → vermelho).
- [ ] Sem regressão na suíte completa (não só `-k create_post`).
- [ ] `mypy --strict` no `src/` inteiro limpo (`docs/lessons/python.md`).
- [ ] Revisão aprovada (`tl-python` + `tl-qa`) sem ressalvas.
