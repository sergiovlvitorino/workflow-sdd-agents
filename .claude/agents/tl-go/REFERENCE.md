# Referência — tl-go

Catálogo de consulta do agente `tl-go`, extraído do `AGENT.md` para manter o prompt enxuto. Sem frontmatter de propósito: o Claude Code trata este arquivo como documentação, não como agente.

## Stack & Expertise

### Core
- **Go 1.23+/1.24+**: generics, iteradores (range-over-func), `slices`/`maps`/`cmp`, `log/slog`, `errors.Is/As/Join` e wrapping com `%w`, `math/rand/v2`; 1.24+ `t.Context()`, `b.Loop()`, diretiva `tool` no `go.mod`; 1.25+ `sync.WaitGroup.Go`, `testing/synctest`.
- **Concorrência**: goroutines, channels, `sync` (`Mutex`, `Once`, `OnceValue`, `Pool`), `errgroup`, `context` propagado.
- **Módulos**: `go.mod`/`go.sum`, diretivas `go` × `toolchain`, workspaces, `replace` só local.
- **Interfaces & composição**: interfaces pequenas definidas pelo consumidor, embedding, DI manual por construtor.

### Web & APIs
- **`net/http`** com `ServeMux` 1.22+ (método e curinga, `r.PathValue`); `http.Server` com timeouts; middleware `func(http.Handler) http.Handler`.
- chi quando o roteamento precisa de grupos/middlewares por sub-árvore; Gin/Echo/Fiber só se o projeto já usa.
- **gRPC + Protobuf** (`protoc-gen-go`, `protoc-gen-go-grpc`, interceptors, `buf`); GraphQL (`gqlgen`); OpenAPI (`oapi-codegen`).

### Dados & Storage
- **DynamoDB** via AWS SDK v2 (`attributevalue`, `expression`, paginators, `ConditionExpression`, transações), single-table quando o ADR pede.
- `database/sql` / `pgx` v5, `sqlc`, `sqlx`; SQLite (`modernc.org/sqlite` sem cgo); `bbolt`; `redis/go-redis/v9`; migrations com `goose`, `golang-migrate`, `atlas`.

### Infra & Cloud
- **AWS SDK for Go v2** (S3, SQS, DynamoDB, Lambda, SSM); Lambda em `provided.al2023` com binário `bootstrap` (o runtime `go1.x` foi descontinuado), `arm64`, `CGO_ENABLED=0`.
- Docker multi-stage (`scratch`/distroless), Kubernetes (`controller-runtime`), Terraform/SAM, GitHub Actions, `goreleaser`, `ko`.

### CLI
- `cobra` (+ `viper` só se precisar de config em camadas), `urfave/cli`, Charm (`bubbletea`, `lipgloss`), `//go:embed`.

### Observabilidade
- `log/slog`, OpenTelemetry Go, `prometheus/client_golang`, `pprof` (CPU, heap, goroutine, `net/http/pprof` nunca exposto publicamente), race detector.

### Qualidade
- `testing` (table-driven, `t.Parallel`, subtests, fuzzing, benchmarks + `benchstat`), `httptest`, `testcontainers-go`, `go-cmp`; testify/gomock só se o projeto já usa.
- `go vet`, `staticcheck`, `golangci-lint` (o `golint` está deprecado — não recomende), `gosec`, `govulncheck`, `trivy`.

## Anti-patterns que você SEMPRE flagra

### Concorrência
- Goroutine sem cancelamento (`ctx`) nem espera; goroutine bloqueada em channel que ninguém fecha/lê.
- Map acessado concorrentemente sem `sync.Mutex` (ou `sync.Map` só para os casos que a doc recomenda).
- `wg.Add()` dentro da goroutine (deve ser antes do `go`; em 1.25+ prefira `wg.Go`).
- `select` bloqueante sem `case <-ctx.Done()`; `ctx` guardado em struct.
- Fechar channel do lado do receptor, ou fechar duas vezes.

### Error handling
- Erro ignorado (`_ = f()`, retorno descartado) sem justificativa.
- Erro propagado sem contexto quando a fronteira perde informação — `fmt.Errorf("salvando card %s: %w", id, err)`.
- Comparação de erro com `==` em erro embrulhado ou por `err.Error()`/`strings.Contains` — use `errors.Is`/`errors.As`.
- `%v` onde a cadeia precisa ser preservada (`%w`); vazamento do erro interno ao cliente HTTP.
- `log.Fatal`/`os.Exit` fora de `main` (impede cleanup, `defer` e teste); `panic` para erro de runtime.

### Performance (prove com benchmark/pprof antes de bloquear)
- Alocação em hot loop; concatenação de string em loop (use `strings.Builder`); `append` sem pré-alocar quando o tamanho é conhecido.
- `defer` dentro de loop longo (executa no fim da função).
- `regexp.MustCompile` dentro de função chamada repetidamente — compile uma vez em `var` de pacote.
- **Dogma corrigido:** `time.After` em loop não vaza mais a partir do Go 1.23 (timers não referenciados são coletados) quando o `go.mod` declara `go 1.23`+; com versão anterior, ainda flagre.

### Estrutura de projeto
- Pacote `utils`/`helpers`/`common`; pacote `models` monolítico (organize por domínio).
- Import circular; `internal/` ausente quando deveria proteger API interna.
- Interface declarada no pacote produtor "para mock" em vez de no consumidor.

### API & HTTP
- `http.ListenAndServe` sem `http.Server` com `ReadHeaderTimeout`/`ReadTimeout`/`WriteTimeout`/`IdleTimeout`.
- Falta de graceful shutdown (`signal.NotifyContext` + `server.Shutdown`).
- `http.DefaultClient`/`http.Client{}` sem `Timeout` em chamada de saída.
- Corpo de request sem limite (`http.MaxBytesReader`); `json.Decoder` aceitando lixo sem validação.
- Handler que não propaga `r.Context()`; `resp.Body` não fechado (ou fechado antes do check de erro).
- Middleware que não chama `next.ServeHTTP` ou chama duas vezes; escrever header depois do corpo.
- Padrões `"GET /x/{id}"` com `go` < 1.22 no `go.mod` (o comportamento antigo do mux, ativado por `GODEBUG=httpmuxgo121=1`, não entende método nem curinga — a rota não casa como o teste supõe).

### Lambda / AWS SDK v2
- Client do SDK ou `LoadDefaultConfig` criado dentro do handler (custo por invocação).
- `Scan` onde cabe `Query`; paginação ignorada (só a 1ª página); `UnprocessedItems` de `BatchWriteItem` descartado.
- Expressão DynamoDB montada por concatenação de input; ausência de `ConditionExpression` onde há invariante (idempotência, não sobrescrever).
- `ConditionalCheckFailedException` tratado por texto em vez de `errors.As(err, &ccf)`.
- Runtime `go1.x`, binário não chamado `bootstrap`, SDK v1 em código novo.

### Database (SQL)
- `rows.Close()`/`rows.Err()` esquecidos; `Query` onde cabe `QueryRow`/`Exec`.
- Pool sem `SetMaxOpenConns`/`SetConnMaxLifetime` dimensionado ao limite do banco (em Lambda isso estoura rápido).
- SQL concatenado; transação sem `defer tx.Rollback()` como rede de segurança.

### Testes
- Teste sem asserção significativa; assert que passa por ausência do dado.
- Dependência de ordem; `time.Sleep` para sincronizar (use channels, `testing/synctest` em 1.25+ ou relógio injetado).
- `t.Parallel()` com estado compartilhado, ou junto com `t.Setenv` (panic).
- Helper sem `t.Helper()`; `t.Fatal` chamado fora da goroutine do teste.
- Mock gerado para uma interface de 1–2 métodos onde um fake escrito à mão é mais claro.
- Falta de `t.Parallel()` em testes independentes é `(opcional)`, não bloqueante.

### Segurança
- Segredo hardcoded; credencial AWS em código ou env commitado (use SSM/Secrets Manager e role).
- SQL/expressão concatenada; `os/exec` com input do usuário via shell.
- Hash de senha com `md5`/`sha1`/`sha256` puro (use `bcrypt`/`argon2id` de `golang.org/x/crypto`); `math/rand` para token (use `crypto/rand`, `rand.Text` em 1.24+).
- `text/template` gerando HTML (use `html/template`); CORS `*` em produção; `pprof` exposto.
- Log com token, segredo ou PII; erro interno no corpo da resposta.

### Código
- Funções acima de ~50 linhas sem justificativa (o `dev-go` mira em ~30; sequência linear de `if err != nil` conta menos que ramificação).
- `//nolint` sem justificativa e sem o nome do linter.
