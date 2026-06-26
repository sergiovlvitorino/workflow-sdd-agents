# Playbook Python — backend, dados, integrações

> Lições generalizáveis. Confronte com o código atual antes de aplicar (ver [README](README.md)).

## RLS multi-tenant (Postgres + Row-Level Security)

Origem: 2026-06. Classe de defeito recorrente.

- **Repo que abre a própria sessão deve setar o GUC de tenant antes da query.** Se um repositório/worker cria seu próprio engine/session em vez de herdar a sessão da request, ele entra **sem** `app.tenant_id` setado → ou vaza (policy permissiva) ou retorna vazio (policy restritiva). Faça `SET LOCAL app.tenant_id = ...` no início da transação.
- **Variante worker/background:** processos sem request usam um GUC dedicado (ex.: `app.system_worker`). Coloque o privilégio de sistema **só no `USING`** da policy; a escrita continua tenant-gated (`WITH CHECK`). Worker pode ler cross-tenant para processar a fila, mas não escrever fora do tenant do registro.
- **`SET LOCAL` reseta no `commit()`.** Se o método faz INSERT → commit → SELECT na mesma sessão, o SELECT perde o tenant (volta a NULL → 0 linhas). Re-sete após o commit, ou commite só DEPOIS do read.
- **Um helper que seta GUC tem de emitir o LITERAL EXATO que a policy compara.** `set_config('app.system_worker', 'on', ...)` enquanto a policy compara `= 'true'` → a policy **não casa** e o worker processa **zero linhas, sem erro** (falso-verde perfeito: roda, não lança, não faz nada). O teste tem de provar que o worker **processa** (>0 linhas sob role app), não só que "não lança".
- **`INSERT` numa coluna `SERIAL`/Identity sob role NOBYPASSRLS exige `GRANT USAGE, SELECT ON SEQUENCE`** — o `GRANT ... ON TABLE` não basta. Fácil de esquecer porque o teste que só exercita `SELECT` sob role app (e faz `INSERT` sob superuser) mascara o gap por anos. Teste o caminho de **escrita** sob a role app.
- **Centralize a primitiva `set_config(GUC)` num único helper** (ela tende a se espalhar por dezenas de call-sites copy-paste); guarde a allowlist de exceções num scanner.
- **Teste sob a role de aplicação, nunca superuser** (ver [qa.md](qa.md) — superuser ignora RLS e dá falso-verde).

## Idempotência e exactly-once

- **Transição de estado atômica + replay pré-efeito.** Contra efeito duplicado (ex.: emissão/cobrança em dobro): mude o estado `failed → in_flight` numa transição atômica (UPDATE condicional, não read-then-write), e faça *replay* da verificação imediatamente **antes** do efeito irreversível.
- **In-doubt puro é indistinguível de falha-pré-efeito.** Se o sistema externo executou mas você não tem o recibo, nenhum estado local resolve com certeza — só **reconciliação ativa** (consultar o sistema externo) desambígua. Não finja que um retry cego resolve. Na dúvida fail-open vs fail-closed: se o estado "falhou" é indistinguível entre "antes" e "depois" do efeito, fail-closed cego prende os legítimos (a falha pré-efeito é o caso comum) — converte um bug de duplicação raro num bug de disponibilidade frequente.
- **TOCTOU: pré-check + save em transações separadas tem janela.** Efeito externo irreversível (emissão/cobrança) que vem **antes** de persistir o registro precisa de **reserva atômica do slot antes do efeito** — `INSERT ... ON CONFLICT (chave) DO NOTHING RETURNING`; só o vencedor (RETURNING não-nulo) executa o efeito. Um pré-check (`SELECT`) seguido de `save` deixa N requests paralelos furarem o gate antes de qualquer um commitar (a UNIQUE constraint só morde **depois** do efeito — tarde demais).
- **Reserva precisa ser recuperável de crash:** o slot reservado leva `reserved_at` + TTL; um slot expirado é re-adquirível (`ON CONFLICT DO UPDATE ... WHERE reserved_at < now()-:ttl`). Senão um vencedor que reserva e morre antes do efeito trava a chave para sempre.
- **Claim atômico fecha a janela cross-path ANTES do efeito; constraint pós-fato não.** Para serializar caminhos concorrentes (retomar item de fila vs retry externo), use `UPDATE ... WHERE status=:esperado RETURNING` (só um vencedor transiciona) **antes** de chamar o sistema externo — preferível a uma unique constraint, que só dispara depois que a 2ª chamada externa já saiu.
- **Perdedor de corrida NUNCA fabrica resposta.** Faz poll-até-terminal e replica o estado **real** do vencedor; se ainda não-terminal, levanta erro de in-flight (409/425 + Retry-After). Nunca devolve estado intermediário nem sucesso fabricado.
- **`IdempotencyStore` compartilhado entre rotas precisa de chave NAMESPACED por operação/recurso.** Se duas rotas (`POST /posts` e `PUT /posts/{id}/publish`) gravam no mesmo store com a `Idempotency-Key` **crua** do cliente, a mesma chave reusada entre elas colide → 409 espúrio (o replay de uma acha o slot da outra). Namespace na **store_key** (`f"publish:{idem_key}"`); o discriminador de recurso (para o 409 legítimo "mesma chave, alvo divergente") vai no **payload_hash** (`sha256(post_id)`), não na store_key (senão vira cache-miss e o 409 não dispara).

## Durabilidade de side-effects

- **Side-effect durável vai por consumer de outbox, não inline pós-commit.** Disparar o efeito (webhook, e-mail, evento) logo depois do `commit()` no mesmo processo **perde** o efeito se o processo morre na janela. Grave a intenção na mesma transação (tabela outbox) e tenha um consumer que entrega com retry.
- **Side-effect ACESSÓRIO dentro de TX crítica → SAVEPOINT (`begin_nested`), nunca `try/except` nu.** Um efeito secundário (alerta, métrica) emitido na mesma sessão de uma TX crítica não pode derrubá-la. `except Exception: log` é o pior dos mundos: quando o INSERT acessório falha, a TX inteira entra em `InFailedSqlTransaction`, o swallow segue, e o `commit()` principal **quebra**. Envolva só o efeito acessório em `begin_nested()` (SAVEPOINT); o efeito **principal tem de ser materializado FORA/ANTES do savepoint**, senão um rollback do acessório desfaz o principal. Re-levante erro de INFRA por **tipo** (`isinstance(exc, (OperationalError, ...))`, não string-match), contendo só o erro lógico.
- **Outbox em savepoint** para efeitos condicionais dentro de uma transação maior (ex.: alerta por degrau só se cruzou o limiar).
- **Status agregado = `UPDATE` com `CASE` sobre `COUNT` real dos filhos, não snapshot em memória** (snapshot = lost-update sob concorrência). Guarda de monotonicidade `WHERE status NOT IN (terminais)` para um agregado terminal não regredir sob recompute concorrente. Ler `status` + `summary` no mesmo GET tem de ser na **mesma sessão/TX** (senão par incoerente).

## Webhooks / entrega assinada

- **Assine e envie os bytes EXATOS.** O HMAC tem que ser sobre o `raw_body` literal que vai no fio — re-serializar o JSON depois de assinar quebra a verificação do receptor. Guarde e envie `content=raw_body`.
- **Verificação timing-safe:** compare assinaturas com `hmac.compare_digest`, nunca `==`.
- **Entrega única:** `UNIQUE` na chave de entrega + `INSERT ... ON CONFLICT DO NOTHING` para não entregar duas vezes sob concorrência.
- **Visibility timeout:** `reserved_at` + reclaim de mensagens órfãs, para um worker que morreu não travar a fila.
- **Retry com backoff** dimensionado à janela de negócio (não exponencial infinito).

## Adapters de persistência (port/adapter)

Origem: 2026-06 (Sprint 2 blog-tutorial). Trocar/implementar um adapter atrás de uma porta.

- **`add`/`save` de adapter SQL deve ser UPSERT quando a entidade tem transição de estado** (`INSERT ... ON CONFLICT(id) DO UPDATE`), não `INSERT OR IGNORE`. `INSERT OR IGNORE` ignora silenciosamente o update de um registro existente — a transição (ex.: `draft → published`) nunca persiste. O fake in-memory write-once **passa**, o SQL real **falha** → falso-verde de wiring. A idempotência de *criação* vem do IdempotencyStore write-once + retorno antecipado no caso de uso, **não** do `add`.
- **Adapters que compartilham uma conexão devem compartilhar UM lock.** Dois adapters (repo + idempotency-store) sobre a mesma `sqlite3.Connection` com `threading.Lock()` próprio cada não se serializam: sob threadpool, `with conn:` de um intercala com o do outro → transações implícitas cruzadas → `OperationalError: cannot commit` **intermitente** (flaky=P1). Crie o lock junto da conexão e injete o **mesmo** objeto nos dois (ex.: um `Handle(conn, lock)`).
- **datetime em SQLite (sem tipo nativo):** grave ISO-8601 **UTC tz-aware** e force `tzinfo=UTC` na leitura. Ler de volta um datetime **naive** quebra a comparação keyset `(published_at, id) < (?, ?)` em silêncio.
- **Teste de durabilidade entre conexões usa ARQUIVO (`tmp_path`), nunca `:memory:`** — `:memory:` é por-conexão, então prova o oposto do que afirma (cada conexão vê um banco vazio).

## Persistência e consultas

- **Paginação por cursor keyset, não offset.** `OFFSET` degrada e pula/duplica linhas sob escrita concorrente. Use keyset (`WHERE (col, id) > (:last_col, :last_id)`).
- **JSONB, não `sa.JSON`,** quando precisar de operadores de contenção (`@>`) e índice GIN.
- **Índice de unicidade reflete a regra de negócio:** se "by-rps" não é único, o índice não pode ser único — o handler resolve o empate de forma determinística.

## Armadilhas

- **`now()`/`new Date()` dentro de parser/serializador = timestamp falso** e teste não-determinístico. Injete o relógio.
- **Env var setada no import de um teste vaza** para os outros testes do processo. Use fixture com escopo e teardown.
- **XPath 1.0 não casa default namespace.** `//Elem` não acha um elemento em namespace default — registre um prefixo e use `//ns:Elem`.
- **Fail-closed no boot:** dependência crítica (gateway de pagamento, KMS) ausente/má-configurada deve **derrubar o boot**, não degradar silenciosamente para um caminho inseguro.

## API-First / contrato OpenAPI (FastAPI)

Origem: 2026-06 (Sprint 3 blog-tutorial). O OpenAPI é a fonte que o front consome — tem de ser completo e fiel.

- **Rota sem `response_model` → `/openapi.json` com schema de resposta VAZIO (`{}`).** Retornar `JSONResponse(content=dict)` cru gera contrato sem shape; qualquer tooling (codegen de tipos, client gen, contract test) recebe nada e o time é empurrado a manter um schema à mão (2º source-of-truth proibido). Declare `response_model=` reusando os modelos Pydantic — é o que materializa o API-First (P-01). Pode manter o corpo retornando o dict: o FastAPI valida o dict contra o `response_model` sem exigir refactor para objeto.
- **Pydantic v2 re-serializa `datetime` como `+00:00`** — se o contrato fixa o formato com sufixo `Z` (RFC 3339) e a sua fonte já emite a string canônica, declare o campo de data como **`str`** no response model (não `datetime`), com `Field(examples=["...Z"])`. Caso contrário o `response_model` reescreve o valor e muda o formato observável, quebrando o contrato e os testes. Os testes de integração que asseveram `Z` são a rede de segurança — rode-os após introduzir `response_model`.
- **Aperte enums no response model** (`status: Literal["draft","published"]`, não `str`) — o OpenAPI sai como `enum` e o codegen do front gera uma union de string, não `string` solta.

## Cache, tipos e refactor

- **Cache pertence à camada com longevidade real (singleton/processo), não à efêmera.** Antes de adicionar cache, cheque a memoização/lifecycle do objeto: se a fábrica não é memoizada (instância nova por request), cachear na instância dedupa só dentro de 1 request (teatro). Para secret: TTL curto limita staleness na rotação + invalidação explícita no sinal de credencial morta (401) com retry único. Atenção ao **blast radius** de cache compartilhado — só é seguro se os valores forem write-once-por-nome; rotação in-place exige invalidar o nome no cache.
- **Mudar nullabilidade/tipo de um campo compartilhado tem blast radius.** `mypy` rodado só nos arquivos editados **não vê** os consumidores em outros arquivos (response schema, mapper) — que viram erro no `mypy --strict` do projeto inteiro e às vezes 500 de runtime (serializar `None` num campo `int`). Rode `mypy --strict` no `src/` **inteiro** e trate cada consumidor (narrowing por `assert`, `|None` no response, guard no endpoint).
- **`hash()` do Python é aleatorizado por `PYTHONHASHSEED`** — nunca use para chave determinística (advisory lock, idempotência). Use `sha256(...)`.
- **`${VAR:-default}` no shell trata string VAZIA como ausente** (colapsa para default) — um `CI_SEEDS=""` vira o default silenciosamente. Para flags de controle de fluxo, use uma flag explícita (`SKIP_SEEDS=1`), não a presença/ausência de um valor.
