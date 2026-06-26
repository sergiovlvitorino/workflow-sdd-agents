# ADR-0004 — Modelo de "publicar" sem autenticação

**Status:** Aceito _(com refinamentos do painel — ver §8)_ · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-25
**Autor:** design-flow (orquestrador-sintetizador)
**Revisores requeridos:** Product Owner + Tech Lead Backend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** F002 (editar/publicar post) · F004 (ler por id) · P-04 (isolamento de dados) · `specs/003-functional-requirements.md` (Sprint 2) · `specs/006-architecture.md` (autorização)

---

## 1. Contexto

O backlog descrevia F002 como "editar/publicar **com autorização**". A restrição vigente do projeto é **rodar localmente, sem autenticação, com fim educacional**. Isso cria uma divergência que precisa ser resolvida **antes** de implementar a Sprint 2: não há login, não há usuário, não há sessão — então o que significa "autorização" para publicar ou editar um post?

Hoje a única regra de visibilidade existente é a **allowlist de leitura** (P-04): `GET /v1/posts` só devolve `status == "published"`; rascunhos nunca vazam. O conceito que falta é a **transição `draft → published`** — é ela que "dá vida" ao blog (hoje posts publicados só existem via seed didático).

Decidir agora é necessário porque a escolha define se o domínio ganha (ou não) qualquer noção de identidade/propriedade — uma decisão estrutural difícil de reverter depois que F002 estiver escrita.

**Forças:**
- Restrição explícita: **sem autenticação**.
- Não introduzir identidade no domínio sem necessidade real (escopo pequeno).
- Manter P-04 satisfeito e provável por teste negativo.
- Coerência spec×código (P-02): a spec não pode prometer "autorização" que o código não implementa.

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. Publicação como transição de estado aberta** _(escolhida)_ | Coerente com "sem auth"; não introduz identidade no domínio; F002 vira só máquina de estados + idempotência; P-04 segue garantido pela allowlist de leitura | Qualquer cliente local pode publicar/editar qualquer post — aceitável só porque o contexto é local/monousuário/didático |
| **B. Auth leve (token estático) para escrita** | Ensina o conceito de proteção de escrita | **Contraria a restrição "sem autenticação"**; adiciona segredo/config (atrito com P-10); complexidade desproporcional ao escopo |
| **C. Pseudo-propriedade por "chave de autor" por post** | Simula ownership sem login | Introduz identidade no domínio sem usuário real; ensina um meio-termo confuso; mais superfície de erro para um exemplo |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Aderência à restrição "sem autenticação" | **Alto** | É uma restrição dada, não negociável aqui |
| Não poluir o domínio com identidade desnecessária | **Alto** | Escopo pequeno; YAGNI; mantém o exemplo limpo |
| Coerência spec×código (P-02) | **Alto** | A spec deve descrever exatamente o que o código faz |
| Clareza pedagógica | Médio | O exemplo deve ensinar máquina de estados + idempotência, não auth meia-boca |

## 4. Decisão

**Escolhida: Alternativa A — "publicar" é uma transição de estado aberta, sem autenticação.**

A operação de publicação (e edição) é exposta sem qualquer noção de identidade ou propriedade: num contexto **local e monousuário**, abre-se mão de autenticação **deliberadamente**. A "autorização" da constitution (P-04) é satisfeita **exclusivamente** pela allowlist de leitura já existente — rascunhos continuam invisíveis em `GET /v1/posts`; publicar é o que os torna visíveis.

F002 reduz-se a uma **máquina de estados** (`draft → published`) protegida por idempotência (P-03), espelhando o padrão já estabelecido em `POST /v1/posts`:
- A transição é idempotente: republicar um post já publicado retorna o estado atual sem efeito colateral (sem duplicar `published_at`).
- Transições inválidas (ex.: publicar um id inexistente) falham explicitamente com erro tipado RFC 9457 (P-11).
- `published_at` é definido no momento da publicação e não muda em replays.

Inegociável:
- **Nenhum conceito de usuário/sessão/token entra no domínio.** Se F002 exigir isso, a premissa "sem auth" mudou e este ADR deve ser reaberto.
- A spec `003-functional-requirements.md` (v1.1.0) deve ser corrigida para remover "com autorização" e descrever a transição aberta — sem isso há divergência spec×código (P-02).
- P-04 permanece coberto por **teste negativo**: rascunho nunca aparece na listagem pública.

## 5. Consequências

- **Positivas:** F002 fica simples e ensinável (máquina de estados + idempotência, sem ruído de auth); o domínio permanece puro e sem identidade; o blog passa a publicar de verdade.
- **Negativas / custo assumido:** sem proteção de escrita — explicitamente aceito porque o contexto é local/monousuário/educacional; **não** é um padrão a copiar para produção (registrar isso no material didático).
- **Impacto em specs/código:** `003-functional-requirements.md` sobe para v1.1.0 (remove "autorização", descreve transição); novo caso de uso `PublishPost` em `application/`; novo endpoint de publicação no router; `006-architecture.md` registra que autorização = allowlist de leitura apenas.
- **Impacto em testes/gates:** teste da transição idempotente (republicar não muda `published_at` nem duplica); teste negativo de visibilidade (rascunho não vaza — P-04); teste de transição inválida → erro tipado (P-11).

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- O projeto passar a ser multiusuário ou exposto fora de `localhost` (aí autenticação e ownership voltam a ser necessários).
- Surgir requisito de auditoria/atribuição de autoria por post.
- O material didático precisar **ensinar autenticação** como tópico — neste caso, um novo ADR introduz auth de forma controlada.

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Product Owner | `po` | 2026-06-25 | Aprovado com ressalvas — abrir mão de auth é decisão de produto correta para o contexto local/monousuário/educacional; P-04 preservado pela allowlist + 404 no read-by-id; F002 vira máquina de estados, entregando publicação real sem inflar o domínio. Ressalvas de rastreabilidade do backlog em §8 (não bloqueiam). |
| Tech Lead Backend | `tl-python` | 2026-06-25 | Aprovado — ressalvas de implementação em §8 |
| Tech Lead QA | `tl-qa` | 2026-06-25 | Aprovado com ressalvas — asserções-âncora e visibilidade read-by-id em §8 |

## 8. Refinamentos do painel de validação (2026-06-25)

Condições **vinculantes** para a implementação da F002:

- **A máquina de estados mora no domínio (não no caso de uso):** `Post.publish(now)` retorna um novo `Post` (`dataclasses.replace`, pois é `frozen=True`) com `status=PUBLISHED` e `published_at=now`. O `now` vem do **relógio injetado** (como em `Post.create`), nunca `now()` interno. A regra de transição não pode vazar para `application/`.
- **Idempotência (decisão de PO — manter o piso P-03):** a transição é idempotente **por estado** (publicar um `published` é no-op; `published_at` não muda) **e** a rota de publicação **aceita `Idempotency-Key`** como toda escrita. O PO fechou este ponto: **não** se abre desvio de piso por simplificação didática — a coerência do contrato vale mais que economizar uma linha de exemplo.
- **Visibilidade read-by-id (F004) — decidir agora:** um rascunho **não vaza** por `GET /v1/posts/{id}` — responde `404` como se não existisse, coerente com a allowlist de leitura (P-04). Sem essa regra, F004 reintroduz vazamento de autorização.
- **Catálogo de erros:** transição inválida / id inexistente → `404 post_not_found` (novo `type` RFC 9457) adicionado a `005` §4 e ao handler centralizado em `interfaces/errors.py` (não espalhar no router).
- **Specs:** `003-functional-requirements.md` → **v1.1.0** (remove "com autorização", descreve a transição aberta); `005-api-contract.md` → **minor bump** (novo endpoint de publicação + `published_at` preenchido + `post_not_found`).
- **Testes (condição de aceite):**
  - Republicar → `published_at_2 == published_at_1` (valor exato, relógio congelado), `status` segue `published`, contagem de publicados **não muda**.
  - Transição inválida (id inexistente) → `type` e `status` **asseverados** e **nada foi publicado**.
  - Negativo de visibilidade: rascunho não aparece na listagem **nem** por id.
  - **Mutation-âncora:** remover a guarda de no-op (re-setar `published_at` incondicionalmente) → republicação muda `published_at` → teste vermelho.

### Ressalvas de produto (PO, 2026-06-25)

- **Backlog desalinhado (item de Sprint 2, não bloqueia o ADR):** o backlog tem CAs que pressupõem **ownership/autor**, que este ADR remove — ficam **órfãos**: `CA-F002-02` ("autor não edita post de outro autor") e a linguagem "a decisão de autorização ocorre no servidor" em `specs/backlog-blog-tutorial.md`. Ao escrever F002 em `003 v1.1.0`, **reescrever esses CAs** para a transição aberta e atualizar o backlog/épico E1 — senão há incoerência spec×backlog (P-02). _(Soma-se aos bumps de `003` e `005` já listados em §5.)_
- **Nota didática obrigatória (F008):** registrar como **callout** explícito no guia, não enterrado no ADR: _"A ausência de autenticação é uma escolha de contexto local; em produção, escrita exige autenticação e autorização."_ É o que protege quem copia o exemplo.
