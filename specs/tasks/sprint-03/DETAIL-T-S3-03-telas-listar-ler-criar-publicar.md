# DETAIL — T-S3-03 — Telas: listar posts (cursor), ler por id, criar+publicar

**Sprint:** 3
**Tamanho:** L _(estimativa)_
**Papel:** FE (+ TL revisão `tl-frontend` + `tl-qa`)
**Depende de:** **T-S3-01** (scaffold Angular + `BlogApiService` + interceptor + tipos gerados — pré-requisito duro); `005-api-contract.md` v1.1.0 congelada (F001/F002/F003/F004).
**Bloqueia:** E2E Playwright (futuro, `007` §6) — fora desta sprint salvo fluxo trivial.

> Produzido por `tl-frontend` no `sprint-flow`; consumido pelo `review-loop`. Descreve a tarefa no **presente** — status real vive no índice/board (`docs/lessons/process.md`).

---

## 1. Objetivo

Entregar as telas que consomem F001/F002/F003/F004 via o `BlogApiService` tipado: **listar** posts publicados (paginação cursor opaco, ADR-0002), **ler** post por id, e **criar+publicar**. Componentes standalone signals-first, **sem lógica de negócio** (ADR-0001 — componente "burro"), com estados explícitos de loading/erro/vazio e acessibilidade básica (WCAG AA). Valor: o usuário-aprendiz vê o front consumindo o contrato `/v1` com erro tipado e paginação keyset funcionando ponta-a-ponta.

## 2. CAs / RNs cobertos

Os CAs são definidos no backend e o front os **consome/exibe** (não os reimplementa):

- **CA-F003-01 (RF-005):** listar publicados paginado por cursor — exibe até `limit` itens + "carregar mais" enquanto `next_cursor != null`.
- **CA-F003-02 (RF-006):** rascunhos **não** aparecem na lista — o front consome a allowlist do back; **não** filtra no cliente (isolamento é server-side, P-04).
- **CA-F003-03 (RF-007):** página seguinte via `?cursor=` sem repetir/omitir — o front trata `next_cursor` como **token cego** (ecoa, nunca constrói/interpreta — `005` §1, ADR-0002).
- **CA-F004-01/02 (RF-011):** ler por id → `200` exibe post; `404 post_not_found` (rascunho **ou** inexistente, mesma resposta) → estado de erro genérico que **não** revela existência.
- **CA-F002-01/02/03 + CA-F001-* (RF-001/008/009/010):** criar (`201`/replay) → publicar (`200`, `published_at` preenchido; republicar no-op) → erros `422 validation_error`, `400 idempotency_key_required`, `404 post_not_found` exibidos por `code`.
- **ADR-0001 §4:** componente sem negócio; service tipado é o único transporte; signals-first.
- **RNF-S-01 (`004`):** `title`/`content` são input externo — renderizar via **interpolação Angular `{{ }}`** (escapa por padrão); **proibido** `[innerHTML]` com conteúdo do usuário (XSS).

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `frontend/src/app/app.routes.ts` | alterar | Rotas lazy: `''`→lista, `posts/new`→criar, `posts/:id`→detalhe. |
| `frontend/src/app/posts/post-list/post-list.ts` | criar | Componente standalone signals: lista + paginação cursor + estados. |
| `frontend/src/app/posts/post-list/post-list.html` | criar | Template: `<ul>` semântica, botão "carregar mais", `aria-live` para resultados. |
| `frontend/src/app/posts/post-detail/post-detail.ts` | criar | Componente: lê `:id`, exibe post ou erro tipado. |
| `frontend/src/app/posts/post-detail/post-detail.html` | criar | `<article>` semântica; estado `404` acessível. |
| `frontend/src/app/posts/post-create/post-create.ts` | criar | Form (reactive) criar→publicar; mapeia `errors[]` de `422` ao campo. |
| `frontend/src/app/posts/post-create/post-create.html` | criar | Form acessível: `<label for>`, `aria-invalid`, `aria-describedby`, `role="alert"`. |
| `frontend/src/app/posts/post-store.ts` | criar | **Camada de estado fina** (signals) que orquestra chamadas ao `BlogApiService` — mantém negócio fora do componente. |
| `frontend/src/app/shared/async-state.ts` | criar | Tipo discriminado `AsyncState<T>` (`idle\|loading\|loaded\|empty\|error`) reutilizado nas 3 telas. |
| `frontend/src/app/shared/ui-status/*` | criar (opcional) | Componentes de loading/erro/vazio reusáveis (a11y centralizada). |
| `frontend/src/app/posts/post-list/post-list.spec.ts` | criar | Testing Library: loading/vazio/erro, paginação cursor, allowlist consumida. |
| `frontend/src/app/posts/post-detail/post-detail.spec.ts` | criar | `200` exibe; `404` mostra erro genérico sem vazar existência. |
| `frontend/src/app/posts/post-create/post-create.spec.ts` | criar | criar→publicar feliz; `422` mapeia campo; `400`/`409` exibidos por `code`. |
| `frontend/src/app/posts/post-store.spec.ts` | criar | Estado: transições, idempotência da intenção (mesma key no retry). |

## 4. Design da solução

### 4.1 Arquitetura: componente burro + store fina + service tipado

```text
Component (signals, template, a11y)   -> NUNCA fala HTTP, NUNCA contém regra
        │ chama
PostStore (signals: AsyncState<T>)    -> orquestra, mapeia ApiError->UI, mantém cursor
        │ chama
BlogApiService (T-S3-01)              -> ÚNICO transporte HTTP (tipos gerados)
```

- **Negócio fora do componente** (ADR-0001): o componente só lê signals e dispara intenções (`store.loadMore()`, `store.publish(id)`). Decisão de "quando há próxima página", acúmulo de itens, mapeamento de erro → no `PostStore`.
- **`PostStore` não é state manager global** (ADR-0001 proíbe NgRx): é um serviço com `signal()`/`computed()`, instanciado por rota/feature (escopo do componente quando fizer sentido), enxuto.
- **`AsyncState<T>` discriminado** força tratar todos os estados (loading/erro/vazio) — anti "tela branca" e anti loading infinito.

```ts
// shared/async-state.ts
export type AsyncState<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'loaded'; data: T }
  | { kind: 'empty' }                          // lista vazia (200 com items: [])
  | { kind: 'error'; error: ApiError };
```

### 4.2 Listar (F003) — paginação cursor opaco

```ts
// post-list.ts (esqueleto)
export class PostListComponent {
  private store = inject(PostListStore);
  readonly state    = this.store.state;        // signal<AsyncState<Post[]>>
  readonly hasMore  = this.store.hasMore;      // computed: next_cursor != null
  readonly loadingMore = this.store.loadingMore;
  ngOnInit() { this.store.loadFirstPage(); }
  loadMore() { this.store.loadMore(); }
}

// post-list.store.ts (regras de paginação — fora do componente)
//  - loadFirstPage: listPosts({ limit }) -> acumula items, guarda next_cursor (opaco)
//  - loadMore: listPosts({ cursor: nextCursor }) -> CONCATENA, atualiza next_cursor
//  - next_cursor === null  => hasMore = false (última página, 005 §1)
//  - cursor é TOKEN CEGO: só ecoa em ?cursor=, nunca constrói/interpreta (ADR-0002)
```

Decisões:
- **`next_cursor` opaco** (`005` §1, ADR-0002): a UI só repassa; nunca decodifica. `next_cursor: null` ⇒ esconde "carregar mais".
- **Allowlist é do back** (CA-F003-02): a lista exibe o que o `GET /v1/posts` retornou. **Proibido** filtrar `status` no cliente (isolamento é server-side, P-04; filtrar no front mascararia vazamento, não o evitaria).
- **`invalid_cursor` (400)** improvável na navegação normal (cursor sempre vem do back), mas tratado como `error` tipado se ocorrer (P-11).
- **Acúmulo "carregar mais"** (não substituição) — fluxo natural keyset. A 2ª página não repete itens (garantia do back, CA-F003-03); o front não dedup — confia no contrato (e o teste prova ids da pág.1 ∩ pág.2 = ∅ no nível do store).

### 4.3 Ler por id (F004) — 404 que não revela existência

```ts
// post-detail.ts
const id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
this.store.load(id);   // getPost(id): 200 -> loaded; 404 post_not_found -> error genérico
```

- **`404` rascunho == `404` inexistente** (`005` §2.4; ADR-0004 §8): o front exibe **uma única** mensagem genérica ("Post não encontrado"), **sem** distinguir os casos — diferenciar reintroduziria vazamento. Discrimina por `code === 'post_not_found'`, não por `detail`.
- Mensagem ao usuário é **própria do front** (i18n simples via `textContent`/interpolação), **não** o `detail` do back (texto livre, pode mudar — `005` §4).

### 4.4 Criar + publicar (F001 → F002)

```ts
// post-create.ts — Reactive Forms; validação espelha o contrato (1–200 / 1–50000)
form = this.fb.group({
  title:   ['', [Validators.required, Validators.maxLength(200)]],
  content: ['', [Validators.required, Validators.maxLength(50000)]],
});
submit() {
  // 1) createPost(body) com Idempotency-Key gerada UMA vez por intenção
  // 2) on 201/replay -> publishPost(id) com NOVA Idempotency-Key (própria da publicação)
  // 3) navega para posts/:id
  // erros: 422 -> mapeia errors[].field ao controle; 400 idempotency_key_required (não deve
  //        ocorrer pois a key é sempre enviada) -> erro técnico; 409 conflict -> mensagem dedicada
}
```

Decisões:
- **Idempotency-Key por intenção** (P-03): a key é gerada **uma vez** quando o usuário clica "criar" e **reusada no retry** da mesma submissão (refresh acidental/erro de rede não duplica). Publicar usa **outra** key (operação distinta — coerente com namespace `publish:` do back, T-S2-06). A key vive no `PostStore`/estado da submissão, não regerada a cada `HttpClient.next`.
- **Validação client-side espelha o contrato** (1–200 / 1–50000) para feedback rápido, mas o **back é a autoridade**: `422 validation_error` do servidor mapeia `errors[].field` → controle (não confiar só no client).
- **Fluxo criar→publicar encadeado** (F001 então F002): falha na publicação deixa o post como rascunho (estado consistente) e mostra erro acionável — não "engole" (P-11).
- **`409 idempotency_key_conflict`**: mensagem dedicada (raro — só se reusar key em payload divergente); discriminado por `code`.

### 4.5 Acessibilidade (WCAG AA — básico)

| Elemento | Regra |
|---|---|
| Loading | `aria-busy="true"` + texto visível; nunca só spinner sem rótulo. |
| Resultados da lista | container `aria-live="polite"` anuncia "N posts carregados" / "nenhum post". |
| Erros | `role="alert"` (assertivo) com mensagem acionável; foco move para o alerta. |
| Form | todo input com `<label for>`; `aria-invalid` + `aria-describedby` apontando a msg de erro; `role="alert"` no resumo. |
| Detalhe | `<article>` com `<h1>` = título; ordem de heading correta. |
| Navegação | "carregar mais" é `<button>` real (focável, Enter/Espaço); links de post são `<a routerLink>` (não `<div onclick>`). |
| Foco | `:focus-visible` (de T-S3-01); skip-link funcional; foco gerenciado ao trocar de rota/abrir erro. |
| Movimento | respeitar `prefers-reduced-motion` (sem animação de loading agressiva). |

**Segurança no render (RNF-S-01):** `title`/`content` exibidos via interpolação `{{ }}` (Angular escapa). **Proibido** `[innerHTML]` com conteúdo do usuário; sem `bypassSecurityTrust*`. Links externos eventuais → `rel="noopener"`.

### 4.6 i18n / textos

Textos de UI vivem no front (constantes/i18n simples), renderizados por interpolação (`textContent`-equivalente). **Nunca** exibir o `detail` cru do back como fonte de verdade textual — discriminar erro por `code` e mapear a uma mensagem própria (`005` §4: front não faz string-match no `detail`).

## 5. Impacto em testes e quality gates

- **Testing Library / Vitest (unit/component)** — comportamento observável pelo usuário, não detalhe de implementação:
  - **Lista (CA-F003-01/02/03):** loading → `loaded` com N itens; `empty` (200 `items:[]`) renderiza estado vazio acessível; "carregar mais" usa `next_cursor` cego e **concatena** (ids únicos pág.1∩pág.2=∅); `next_cursor:null` esconde o botão; allowlist consumida (o teste NÃO espera filtro client-side). `HttpTestingController` valida que a 2ª chamada manda `?cursor=` exato recebido.
  - **Detalhe (CA-F004-01/02):** `200` exibe título/conteúdo; `404 post_not_found` mostra **uma** mensagem genérica — asserção **negativa**: a UI não distingue rascunho de inexistente (mesmo texto, sem vazar).
  - **Criar+publicar (CA-F001/F002):** feliz cria→publica→navega; `Idempotency-Key` presente nas duas escritas e **estável no retry** da mesma submissão (asserção do header via `HttpTestingController`); `422` mapeia `errors[].field` ao controle certo; `400`/`409` exibidos por `code` (não por `detail`).
  - **Interceptor (de T-S3-01) é exercitado de ponta** aqui: erro chega como `ApiError` tipado, componente discrimina por `code`.
- **Estados obrigatórios:** cada tela testa **loading + erro + vazio** (anti tela-branca/loading-infinito).
- **2º ratchet (front) — ELEVA aqui** (`007` §2/§6; ADR-0001 §4.1): T-S3-01 instituiu o piso no scaffold; T-S3-03 **sobe** ao patamar com as telas cobertas. Pisos por categoria (alinhado a P-07): transporte/service 100%, máquina de estados de UI (paginação, criar→publicar) alto, branches de erro 100% (loading/erro/vazio cobertos). **Barrado separadamente** do Python (gate AND); **nunca** média global combinada.
- **Gate de drift (de T-S3-01) permanece** distinto e ativo (ADR-0005 §8 "não fundir"): tipos consumidos pelas telas vêm do gerado; mutar campo do contrato sem regenerar ⇒ build vermelho.
- **E2E Playwright:** **fora** desta sprint (`007` §6, ADR-0001 §4 "magro") — registrado para a costura futura (criar→aparecer na lista). Incluir só se trivial e sem inflar o gate.

## 6. Riscos

- **Lógica de negócio vazando para o componente** (anti-pattern ADR-0001): paginação/mapeamento de erro/idempotência da intenção devem morar no `PostStore`, não no `.ts` do componente. **Mitigação:** componente só lê signals e dispara intenções; revisão checa.
- **Filtrar `status` no cliente** (CA-F003-02): mascara vazamento em vez de evitá-lo; isolamento é server-side (P-04). **Mitigação:** teste afirma que o front **não** filtra — exibe o que o back allowlist retornou.
- **Construir/decodificar o cursor** (ADR-0002): trata-lo como não-opaco quebra a estabilidade keyset. **Mitigação:** cursor é `string` cega; teste valida eco exato.
- **`404` que revela existência:** texto diferente para rascunho vs inexistente reintroduz vazamento (ADR-0004 §8). **Mitigação:** uma única mensagem genérica; asserção negativa.
- **XSS via `content`/`title`** (RNF-S-01): `[innerHTML]` com input do usuário. **Mitigação:** só interpolação `{{ }}`; proibir `innerHTML`/`bypassSecurityTrust*` (regra de revisão/lint).
- **Idempotency-Key regenerada a cada tentativa** → retry duplica intenção (fura P-03 do lado do cliente). **Mitigação:** key gerada uma vez por intenção, estável no retry; teste do header.
- **Estados ausentes** (loading/erro/vazio): tela branca/loading infinito. **Mitigação:** `AsyncState` discriminado obriga tratar todos; teste por estado.
- **Acoplar mensagem ao `detail` do back:** texto livre que pode mudar (`005` §4). **Mitigação:** discriminar por `code`; mensagem própria do front.
- **Média global combinada:** falso-verde estrutural (ADR-0001 §4.1). **Mitigação:** ratchet front separado, gate AND.

## 7. Definition of Done (verificável)

- [ ] Três telas standalone signals-first (lista / detalhe / criar+publicar), roteadas lazy; **nenhuma** fala HTTP direto — só via `BlogApiService` através do `PostStore` (negócio fora do componente, ADR-0001).
- [ ] **Lista (CA-F003-01/02/03):** exibe publicados; "carregar mais" usa `next_cursor` **opaco** e concatena; `next_cursor:null` esconde o botão; **não** filtra `status` no cliente (allowlist do back); estado **vazio** acessível.
- [ ] **Detalhe (CA-F004-01/02):** `200` exibe; `404 post_not_found` → **uma** mensagem genérica que **não** distingue rascunho de inexistente (asserção negativa).
- [ ] **Criar→publicar (CA-F001/F002):** fluxo encadeado; `Idempotency-Key` presente nas duas escritas e **estável no retry** da intenção; `422` mapeia `errors[].field` ao controle; `400`/`409`/`404` exibidos por **`code`** (nunca por `detail`).
- [ ] Cada tela trata **loading + erro + vazio** explicitamente (sem tela branca/loading infinito) — testado por estado.
- [ ] **A11y (WCAG AA básico):** labels associados, `aria-live` nos resultados, `role="alert"` + foco nos erros, headings em ordem, `<button>`/`<a>` reais focáveis, `:focus-visible`, `prefers-reduced-motion`.
- [ ] **Segurança (RNF-S-01):** `title`/`content` via interpolação `{{ }}`; **zero** `[innerHTML]`/`bypassSecurityTrust*` com input do usuário.
- [ ] Erros recebidos como `ApiError` tipado (interceptor de T-S3-01); discriminados por `type`/`status`/`code`.
- [ ] Testes Testing Library/Vitest cobrindo os CAs e os 3 estados; `HttpTestingController` valida URL/headers/cursor.
- [ ] **2º ratchet front elevado** ao patamar das telas, **barrado separadamente** do Python (gate AND); **gate de drift** de contrato permanece verde e distinto. Nenhuma média global combinada.
- [ ] Revisão aprovada (`tl-frontend` + `tl-qa`) sem ressalvas.
