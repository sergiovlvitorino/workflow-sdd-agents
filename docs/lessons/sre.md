# Playbook SRE — infra, IaC, observabilidade, runtime

> Lições generalizáveis. Confronte com o código atual antes de aplicar (ver [README](README.md)).

## Teste vs SLO/alarme (escolha o instrumento certo)

- **Nem toda invariante vira teste.** Condições que dependem do *tempo de calendário* ou do estado de produção — expiração de certificado, rotação de credencial, drift de saldo — não são testáveis de forma determinística na suíte. Viram **alarme/SLO**, não teste unitário. Monitorar expiração de cert é custo de operação ($$), não um assert.
- **Gate de IaC sobre o plano resolvido.** Valide infra sobre `terraform show -json` (o estado/plano resolvido), não sobre o `.tf` textual — o texto não pega valores computados, defaults de provider nem interpolações.
- **Inclua todos os ambientes na matrix do gate.** Um gate que roda só em `dev`/`stg` e pula `prd` deixa produção sem rede de proteção. `prd` entra na matrix.

## Scheduler / jobs / runtime

- **Scheduler sem leader election → singleton.** Um agendador periódico (ex.: Periodiq/cron-in-process) sem eleição de líder dispara o job N vezes se rodar com N réplicas. Force `desired_count=1` **e** proteja com advisory lock no banco (defesa em profundidade contra dupla-execução em rollout).
- **Avalie serverless vs long-running pela natureza do worker.** Filas com visibility timeout, schedulers stateful e conexões persistentes nem sempre cabem em Lambda/Functions efêmeras — registre o porquê da escolha (descartar EventBridge/Lambda é uma decisão, não um esquecimento).
- **A camada de runtime é parte do IaC.** Ter rede/storage no Terraform mas o compute (ECS/RDS/Redis) "na mão" é dívida de reprodutibilidade — rastreie os gargalos abertos.

## IaC / validação

- **Um erro de `terraform validate` mascara o próximo.** O validate aborta no 1º erro do grafo — corrigir um (ex.: output duplicado) revela um ciclo de SG que estava escondido atrás dele, que revela um erro de cloudtrail… **Reexecute o validate após CADA correção**; nunca declare "destravado" sem rodar de novo e ver o resultado real. (Mesma família do "erro mascara erro" em runtime.)
- **Config/IaC sem assert regride em silêncio** (não há "vermelho" para um `desired_count` que voltou a 2, um Multi-AZ que sumiu, um alarme que perdeu a dimensão). Asserte sobre `terraform show -json` com sentinela `exit 2` falha-segura, e inclua **todos os ambientes** que exigem a invariante na matrix (HA é exigido em `prd` — não basta validar `dev`/`stg`).

## Wiring de CI (gate que roda de verdade)

Origem: 2026-06 (Sprint 2 blog-tutorial). Um gate só conta quando o CI realmente o executa (ver [qa.md](qa.md) — "gate não-wired é inerte").

- **GitHub Actions só descobre workflows em `<raiz-do-repo>/.github/workflows/`.** Um `ci.yml` numa subpasta (ex.: `backend/.github/workflows/`) é **silenciosamente ignorado** — nenhum job roda no push/PR e todo o gate fica inerte. Coloque o workflow na raiz e use `defaults.run.working-directory: <subdir>` (ou `cd`) para rodar a partir do subprojeto. Prove que aparece rodando (`gh run list`/aba Actions), não só que o arquivo existe.
- **bash `set -e` aborta na PRÓPRIA atribuição `out=$(cmd)` quando `cmd` sai ≠0** — qualquer sentinela/captura de exit **depois** da atribuição vira código morto (e `local rc=$?` logo após zera `$?`, pois `local` tem exit próprio 0). Para um script de gate robusto: declare `rc=0` **antes**, capture com `out=$(cmd) || rc=$?`, e faça a checagem de sentinela (ex.: "0 statements → glob não casou nada → reprova") **independente** do `--fail-under` (rode a medição sem o threshold primeiro, cheque o vazio, só então aplique o piso). Prove a sentinela red-green com um glob deliberadamente inexistente — senão ela só "funciona por acidente" (porque a ferramenta atual retorna exit 1 em vazio).

## Otimização de CI

- **Meça antes de otimizar; não assuma o gargalo.** Tirar o "óbvio" candidato do caminho crítico pode deixar **mais lento** — cronometre as fases e ataque a que domina. O que não dá para paralelizar (um gate de ordem, uma rodada serial irredutível) é o **teto** — mova-o para outro momento (gate de fechamento) em vez de tentar acelerá-lo.

## Observabilidade

- **Alerta por degrau, não por valor absoluto isolado** — dispare na *transição* de limiar (via outbox/savepoint para não perder nem duplicar o alerta).
- **O que dá flaky em teste vira métrica:** pico de concorrência, heartbeat de worker, profundidade de fila — instrumente em vez de assertar com timing.

## Custo / dimensionamento de runtime

Origem: 2026-06. Reduzir custo de runtime cloud preservando durabilidade/compliance.

- **Separe DURABILIDADE de DISPONIBILIDADE antes de cortar.** Multi-AZ, réplicas e N-NAT compram *disponibilidade* (uptime/RTO), não *durabilidade* (o dado committed sobrevive via backups/PITR + um object store imutável, independentemente da AZ). Para um produto pré-receita sem SLA, rodar **single-AZ + 1 instância** é defensável: perde-se uptime numa falha de AZ (RTO de restore), **não se perde dado**. Diga isso explicitamente no ADR — a pergunta do dono é "eu perco dado?", e a resposta honesta destrava nascer barato.
- **Em volume baixo, VPC interface endpoints custam MAIS que o NAT que evitam.** 6+ interface endpoints × N AZ podem custar ~10-30× um NAT instance pequeno que cobre todo o egress. Mantenha os **gateway endpoints (S3/DynamoDB) que são grátis** e, em baixo volume, prefira 1 NAT instance barato a um leque de interface endpoints + NAT GW. (Reavalie quando o volume/tráfego AWS crescer.)
- **IaC mais cara que o próprio ADR é dinheiro na mesa.** A implementação envelhece em relação à decisão (endpoints em 3 AZ quando o ADR pediu 2; default de N-NAT acima do decidido; observabilidade gerenciada em todo env quando só prod precisa). Antes de aprovar gasto, audite IaC × ADR — as divergências já custam, e corrigi-las é $0.
- **Perfil de custo por flag única, com inegociáveis SEMPRE-on.** Modele "lean (barato) vs HA (caro)" como UMA flag booleana que liga as camadas de HA juntas (Multi-AZ + N-NAT + LB + endpoints); mantenha dev/stg fora da flag (não regredir). No gate de IaC, os **inegociáveis de durabilidade/segurança** (backups/PITR, encryption, object-lock, deny-non-TLS, no-public) mordem em QUALQUER perfil (lidos do plan, não da flag); só o eixo de HA é condicional — e lido do PLAN (tag), nunca do input, **fail-closed** (ausência de tag → regime estrito). Migração lean→HA é toggle aditivo sem perda de dado; gatilho = receita/SLA.
- **Single-box (1 EC2 + containers) é a postura de menor custo; durabilidade fica em serviços gerenciados.** O banco relacional de estado vai para RDS gerenciado (NÃO self-host Postgres — economia falsa contra risco de perda do estado relacional); o broker/cache (Redis) pode ser container local efêmero se a fonte de verdade for um outbox transacional no banco. A migração para orquestração (ECS/Fargate) é limpa porque o estado (RDS + object store) não se move — só o compute/broker são reprovisionados.
- **Valide o artefato de PRODUÇÃO explicitamente quando há override auto-carregado.** `docker compose config` sem `-f` carrega o `docker-compose.override.yml` (dev) → um gate ingênuo valida a stack errada. Gateie `-f docker-compose.yml`. E **publique portas em `127.0.0.1`** atrás de um reverse-proxy (não `0.0.0.0`) — defesa em profundidade que não depende só do Security Group.
- **`.terraform.lock.hcl` versionado tem de ser MULTI-PLATAFORMA.** O `terraform init` na máquina local grava hashes só da plataforma corrente; um `apply`/`init` em outra plataforma (CI Linux, runtime ARM64/Graviton) falha por hash faltante. Antes de versionar, regenere com `terraform providers lock -platform=linux_amd64 -platform=linux_arm64 -platform=windows_amd64 -platform=darwin_arm64` (inclua as plataformas que o time/CI/runtime realmente usam; ARM64 é fácil de esquecer e é justamente o alvo Graviton). Versione o lock do **root/env** (onde o Terraform o resolve), não os de módulos-filho (criam drift sem ganho). E **resíduo que reaparece no `git status` de todo PR** (lock files untracked, artefatos de init) é decisão de governança adiada — resolva a causa (versionar OU ignorar explicitamente no `.gitignore`), não exclua manualmente a cada commit.
