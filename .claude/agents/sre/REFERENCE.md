# Referência — sre

Catálogo de consulta do agente `sre`, extraído do `AGENT.md` para manter o prompt enxuto. Sem frontmatter de propósito: o Claude Code trata este arquivo como documentação, não como agente.

## Baseline técnico (2026-10)

### IaC
- **SAM / CloudFormation**: `sam validate --lint` (inclui cfn-lint) e `cfn-lint` antes de afirmar que o template está válido; `sam build` para pegar erro de empacotamento. Lembre: linter valida schema, **não semântica** (aceita `Resource: "*"`, aceita API implícita) — o teste estrutural do template é o que afirma invariantes.
- **CDK v2**: `cdk synth` e `cdk diff` são o "plan"; revise o template sintetizado, não só o código TS/Python.
- **Terraform ≥ 1.10 / OpenTofu**: backend S3 com **locking nativo** (`use_lockfile = true`) — a tabela DynamoDB de lock está depreciada; não a recomende em projeto novo. `terraform plan` (e assert sobre `terraform show -json`) antes de qualquer `apply`.
- Ferramenta de política quando o projeto já usa ou o risco justifica: checkov, tflint, trivy config. Não introduza dependência nova "por boa prática" num projeto que tem teto de custo/complexidade.

### CI/CD (GitHub Actions)
- **OIDC para AWS** (`aws-actions/configure-aws-credentials` com `role-to-assume`): nenhuma access key de longa duração em secret. Trust policy da role restrita por `sub` (repo + branch/environment), não `repo:org/*`.
- `permissions:` mínimo explícito no workflow/job (`contents: read`, `id-token: write` só onde assume role).
- Actions de terceiros **pinadas por SHA**; `actionlint` no CI; environment `production` com aprovação obrigatória.
- Pipeline falha ruidosamente — sem `continue-on-error`/`|| true` em gate.

### AWS
- **Least privilege**: policies por recurso (ARN), sem `Action: "*"`/`Resource: "*"` exceto managed policies conhecidas que exigem (ex.: `AWSXRayDaemonWriteAccess` anexada por `Tracing: Active`) — escopo a revisão à policy inline. `aws iam simulate-principal-policy` prova permissão melhor que leitura.
- **Lambda**: arm64 quando as dependências permitem; runtime suportado mais recente da linguagem (confira a data de depreciação na doc da AWS antes de afirmar); timeout e memória medidos, não chutados; concorrência reservada para limitar blast radius/custo quando fizer sentido.
- **S3 + CloudFront**: Block Public Access ligado, **OAC** (OAI é legado), response headers policy com HSTS, CSP, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors` via CSP (o `X-Frame-Options` é complementar). SSE-S3 já é o default; KMS só se houver requisito.
- **API Gateway**: HTTP API é mais barata e simples; REST API quando precisa de API keys/usage plans, WAF direto ou validação de request. Throttling explícito; CORS restrito à origem do front.
- **DynamoDB**: on-demand em volume baixo/irregular; PITR para dado que não pode ser perdido; TTL para lixo.
- **Logs**: `RetentionInDays` explícito (o default é nunca expirar — custo cresce em silêncio); logs estruturados sem PII/segredos.
- **Custo**: AWS Budgets com alerta (forecast e real) e Cost Anomaly Detection; cite impacto mensal estimado em toda mudança que adiciona recurso.

### Observabilidade
- Alarmes por **sintoma do usuário** (taxa de erro 5xx, latência p95/p99, throttles) antes de alarmes de causa; cada alarme com ação/runbook. Alerta na transição de limiar, não em valor isolado ruidoso.
- SLO onde houver usuário; o que dá flaky em teste (concorrência, timing) vira métrica.
