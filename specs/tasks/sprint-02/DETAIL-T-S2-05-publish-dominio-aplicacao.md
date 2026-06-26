# DETAIL — T-S2-05 — F002 domínio + aplicação: `Post.publish` + caso de uso `PublishPost`

**Sprint:** 2
**Tamanho:** M _(estimativa)_
**Papel:** BE (+ TL revisão)
**Depende de:** T-S2-04 (método `get(id)` na porta `PostRepository`)
**Bloqueia:** T-S2-06 (endpoint de publicação consome este caso de uso)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Modelar a publicação como **máquina de estados no domínio** (`draft → published`) com relógio injetado e expor o caso de uso `PublishPost` idempotente por estado — o blog passa a publicar de verdade, sem qualquer noção de identidade/auth (ADR-0004).

## 2. CAs / RNs cobertos

- **CA-F002-01 (RF-008):** publicar `draft` → `200` com `status="published"` e `published_at` preenchido.
- **CA-F002-02 (RF-009):** republicar `published` é **no-op** — mantém o **mesmo `published_at`**; contagem de publicados não muda.
- **CA-F002-03 (RF-010), parte de aplicação:** publicar id inexistente → falha tipada (busca por id; `None` → erro que o router mapeia a `404 post_not_found`).
- **ADR-0004 §8 (vinculante) — esta tarefa materializa:**
  - **A máquina de estados mora no domínio:** `Post.publish(now)` retorna novo `Post` (`dataclasses.replace`, `frozen=True`) com `status=PUBLISHED` e `published_at=now`. `now` vem do **relógio injetado** — nunca `now()` interno. A regra **não vaza** para `application/`.
  - **Idempotência por estado:** publicar um `published` é no-op; `published_at` inalterado.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/domain/post.py` | alterar | Adicionar método `publish(self, now: datetime) -> Post` (frozen `replace`, no-op se já publicado). |
| `src/blog/application/publish_post.py` | criar | Caso de uso `PublishPost` + exceção `PostNotFound`. |
| `tests/unit/test_post_publish.py` | criar | Unit do domínio (transição, no-op, relógio injetado). |
| `tests/unit/test_publish_post_usecase.py` | criar | Unit do caso de uso (busca, persistência, no-op, not-found). |

## 4. Design da solução

### 4.1 Domínio — `Post.publish` (ADR-0004 §8: regra no domínio)

```text
@dataclass(frozen=True)
class Post:
    ...
    def publish(self, now: datetime) -> Post:
        """Transição draft → published. Idempotente POR ESTADO.

        - DRAFT → retorna novo Post com status=PUBLISHED, published_at=now.
        - PUBLISHED → no-op: retorna self (published_at INALTERADO).
        `now` é o relógio injetado (nunca now() interno) — coerente com create().
        """
        if self.status is PostStatus.PUBLISHED:
            return self                              # guarda de no-op — mutation-âncora
        return replace(self, status=PostStatus.PUBLISHED, published_at=now)
```

Decisão: a **guarda de no-op** vive aqui, não no caso de uso. Remover essa guarda (re-setar `published_at` incondicionalmente) é a **mutation-âncora** do ADR-0004 §8 — o teste de republicação deve matá-la. `replace` porque `Post` é `frozen=True` (imutabilidade do domínio).

### 4.2 Aplicação — `PublishPost`

```text
class PostNotFound(Exception):
    """Post inexistente para publicação → router mapeia a 404 post_not_found."""

class PublishPost:
    def __init__(self, repo: PostRepository, *, clock: Callable[[], datetime]) -> None:
        self._repo = repo
        self._clock = clock

    def execute(self, post_id: str) -> dict[str, Any]:
        post = self._repo.get(post_id)
        if post is None:
            raise PostNotFound()
        published = post.publish(self._clock())      # regra no domínio; clock injetado
        if published is not post:                    # houve transição real (não era no-op)
            self._repo.add(published)                # add = upsert idempotente (T-S2-04 INSERT OR IGNORE? ver nota)
        return _to_response_dict(published)
```

**Nota crítica sobre persistência do no-op vs upsert:** o adapter SQLite de T-S2-04 usa `INSERT OR IGNORE` em `add` (idempotência por PK). Mas publicar um post **muda** uma linha existente (`status`/`published_at`) — `INSERT OR IGNORE` **não atualiza** a linha existente. Há duas saídas, decidir explicitamente:

| Opção | Descrição | Trade-off |
|---|---|---|
| **A. `add` vira upsert real** _(recomendada)_ | `INSERT ... ON CONFLICT(id) DO UPDATE SET status=..., published_at=...` no SQLite | `add` passa a cobrir criação E atualização de estado; mantém a porta com 1 método de escrita; idempotência preservada (mesmo input → mesma linha) |
| B. Adicionar `update(post)` à porta | método separado de atualização | mais explícito, mas amplia a porta e duplica caminho de escrita |

**Recomendação: A.** `add` como **upsert** (`ON CONFLICT(id) DO UPDATE`) mantém a porta enxuta e idempotente — re-publicar o mesmo post grava os mesmos valores (no-op efetivo no banco). Isto **realimenta T-S2-04**: o `add` do SQLite deve ser upsert, não `INSERT OR IGNORE` puro, para suportar a transição de F002. _(O `INSERT OR IGNORE` da idempotência-store permanece — lá a semântica é write-once.)_ Registrar este ponto na revisão cruzada das duas tarefas.

> Como `publish` é no-op por estado, chamar `add(published)` mesmo no caso já-publicado é seguro com upsert (grava os mesmos valores). A guarda `published is not post` evita escrita desnecessária, mas a corretude não depende dela — depende da idempotência do upsert.

`_to_response_dict` reusa o mesmo formato dos outros casos de uso (`status` = `.value`, datetimes ISO-8601 com `+00:00`→`Z`). Considerar extrair para um módulo compartilhado (`application/serialization.py`) já que `create_post`, `list_published_posts` e agora `publish_post` duplicam essa função — **sugestão**, não bloqueante nesta tarefa (evitar refactor de arquivos de Sprint 1 fora de esconpo sem necessidade).

## 5. Impacto em testes e quality gates

- **Unit do domínio (`test_post_publish.py`):**
  - `draft.publish(FIXED_NOW)` → `status==PUBLISHED`, `published_at==FIXED_NOW`, objeto novo (frozen).
  - Republicar: `p2 = p1.publish(OTHER_NOW)` → `p2.published_at == p1.published_at` (no-op; **relógio congelado** prova que não re-setou).
  - `published_at` igual ao `now` injetado, não a `datetime.now()` (sem relógio interno).
- **Unit do caso de uso (`test_publish_post_usecase.py`):**
  - Post draft no repo → `execute` retorna `published`, repo reflete (`get(id).status == published`).
  - Republicar via caso de uso → `published_at` idêntico ao da 1ª publicação; **contagem de publicados não muda**.
  - `execute` de id inexistente → `pytest.raises(PostNotFound)` e **nada foi publicado** (asserção de estado).
- **Mutation-âncora (ADR-0004 §8):** remover a guarda `if self.status is PUBLISHED: return self` → republicação muda `published_at` → teste vermelho.
- **Gates:** unit puro (sem I/O), cobertura ≥ 95%; `mypy --strict` (atenção: `published_at` é `datetime | None` — narrowing no caso publicado).

## 6. Riscos

- **Relógio interno (armadilha python.md):** usar `datetime.now()` em `publish` mata o determinismo e o teste de no-op. **Sempre** `now` injetado.
- **`INSERT OR IGNORE` mascarando a transição:** se T-S2-04 deixar `add` como `INSERT OR IGNORE` puro, publicar **não persiste** a mudança (linha já existe, ignorada) → falso-verde nos unit com fake, vermelho no integration real. Por isso §4.2 exige `add` = upsert. Confirmar na revisão cruzada.
- **Esquecer de persistir após `publish`:** o domínio é imutável — `publish` retorna **novo** objeto; sem `repo.add(published)` a mudança se perde. Teste de estado (`get(id).status`) pega isso.

## 7. Definition of Done (verificável)

- [ ] `Post.publish(now)` no domínio: transição via `replace`, no-op por estado, relógio injetado (sem `now()` interno).
- [ ] `PublishPost.execute` busca por `get(id)`, levanta `PostNotFound` se ausente, persiste a transição via `add` (upsert).
- [ ] Unit verde: transição, no-op (relógio congelado prova `published_at` inalterado), not-found sem efeito.
- [ ] Mutation-âncora (remover guarda de no-op) mata o teste de republicação.
- [ ] Nenhuma noção de usuário/sessão/token no domínio (ADR-0004 inegociável).
- [ ] Cobertura ≥ 95% nos módulos novos; `ruff` + `mypy --strict` verdes.
- [ ] Sem regressão na suíte de Sprint 1.
- [ ] Revisão aprovada (tl-python + tl-qa) sem ressalvas.
