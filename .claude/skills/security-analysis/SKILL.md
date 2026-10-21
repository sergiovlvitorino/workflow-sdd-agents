---
name: security-analysis
description: Auditoria de segurança executada para qualquer repositório, sem configuração prévia — descobre a(s) stack(s), roda os scanners disponíveis (segredos, SAST, dependências, IaC, CI, containers), aplica o checklist OWASP filtrado pelo que existe no repo e devolve uma tabela de achados por severidade com evidência. Se o projeto tiver um perfil de ameaça, usa-o para conferir controles e riscos aceitos; se não tiver, infere um em memória. Só audita — não corrige. Use para "auditoria de segurança", "checklist OWASP", "scan de vulnerabilidades/dependências/segredos", como etapa de auditoria de um fluxo de hardening, ou /security-analysis [escopo] [perfil=<caminho>].
---

# security-analysis

Auditoria de segurança **executada** e **agnóstica de repositório**: nada nesta skill pressupõe linguagem, build tool, cloud, layout de pastas ou arquivo de configuração. Tudo que é específico do projeto é **descoberto** no repo ou lido de um perfil de ameaça **opcional**. O que pode ser provado por ferramenta é rodado; o que só pode ser lido é lido com evidência (`arquivo:linha`); o que não foi verificado é dito.

## Quando usar

- Auditoria periódica ou pré-release de qualquer projeto.
- Depois de mudar uma fronteira de confiança: endpoint de escrita, autenticação, nova dependência, CSP/CORS/IAM, novo serviço exposto.
- Como etapa de auditoria de um fluxo de hardening (por exemplo, o `hardening-flow`, se estiver instalado). Os achados saem num formato pronto para triagem.

Para revisar **só o diff pendente**, uma revisão de diff (como o `/security-review` embutido, quando disponível) é mais barata; esta skill é para a postura do sistema.

### Argumentos (todos opcionais)
- **escopo** — diretório, arquivo, serviço ou camada (`backend`, `infra/`, `services/payments`). Sem escopo = repositório inteiro.
- **perfil=`<caminho>`** — perfil de ameaça a usar, quando não está em um dos lugares convencionais.

## Princípios

- **Descobrir, não presumir.** Stack, build, scanners, convenções e destinos de relatório vêm do repo. Nenhum caminho, comando ou ferramenta é obrigatório.
- **Executar antes de afirmar.** "Mitigado" exige evidência: teste que trava o controle, saída de scanner ou `arquivo:linha`. Leitura sem evidência = "Não verificado".
- **Ferramenta ausente nunca é verde.** Registre `não executado: <motivo>` e compense com inspeção manual marcada como tal. Antes de declarar ausente, procure nos lugares locais do projeto (ambientes virtuais, `node_modules/.bin`, `tools/`, `bin/`, wrappers como `./gradlew`/`./mvnw`) e no PATH.
- **Receita do projeto > comando cru.** Se o projeto já roda o scanner (Makefile, `package.json` scripts, `tox`/`nox`, `justfile`, `Taskfile`, workflow de CI, pre-commit), use essa invocação, com a config, allowlist e versão dela. Se o task runner não estiver instalado, execute o corpo da receita.
- **Contexto, não CVSS genérico.** Severidade = impacto × exploitabilidade **neste sistema** (§4). CVE em dependência que nunca chega ao artefato não é Crítico.
- **Riscos aceitos não são reabertos**, a menos que o gatilho registrado no perfil tenha disparado.
- **Só leitura e só defensivo.** Nada de instalar dependência no projeto, alterar arquivo versionado, deploy, `apply`, chamada mutável à cloud ou tráfego contra ambiente de terceiros. O "caminho de exploração" é uma frase que justifica a severidade, nunca um exploit. Segredo encontrado é mascarado (`AKIA****`, `sk-***`, `ghp_***`).
- **Não corrige.** A saída é o relatório. Correção é outro passo (fluxo de hardening, PR), idealmente com um teste que prove a vulnerabilidade fechada.

## Procedimento

### 0. Autorização e escopo
1. Confirme que o alvo é um repositório próprio ou autorizado. Se for de terceiros ou ambíguo, pergunte antes (em modo não interativo, devolva o bloqueio com a pergunta).
2. Fixe o escopo e registre o estado: `git rev-parse --short HEAD` e se a árvore está suja. Sem git: registre "repositório sem git — varredura de histórico de segredos não aplicável" e siga.
3. Crie um TODO: perfil → descoberta → scanners → checklist → controles do perfil → severidade → relatório.

### 1. Perfil de ameaça (opcional)
1. Use o caminho passado em `perfil=`. Senão procure, nesta ordem, e pare no primeiro que existir:
   `docs/security/threat-model.md` · `docs/threat-model.md` · `THREAT_MODEL.md` · `SECURITY.md` (seção de modelo de ameaça) · `security/threat-model.md` · `**/threat-model*.md`. Em monorepo, procure também na raiz do escopo.
2. **Encontrado:** leia inteiro. Seções que faltarem são inferidas como no passo 3 e marcadas assim.
3. **Ausente:** infira um perfil **em memória** no formato de §"Formato do perfil", a partir do que o repo mostra (IaC, entrypoints, rotas, docs de arquitetura, ADRs, README). Marque-o como **"perfil inferido — não confirmado"**. Não grave nada no repo; ao final, ofereça o perfil inferido como ponto de partida para o projeto versionar.

### 2. Descoberta
Levante, dentro do escopo:
- **Stacks e manifestos.** Liste todo manifesto/lockfile encontrado (um monorepo pode ter vários) e trate cada um como unidade de scan.
- **Artefato x toolchain.** Para cada manifesto, separe o que vai para o artefato de produção do que é só build/teste (dependências de dev, ferramentas de lint, scripts locais). Isso pesa na severidade.
- **Entrypoints.** Rotas HTTP, handlers de fila/evento, CLIs, jobs agendados, webhooks, páginas servidas.
- **Fronteiras de confiança.** Onde entra dado não confiável e onde ele é renderizado, persistido ou executado.
- **Infra e entrega.** IaC (CloudFormation/SAM, Terraform, Pulumi, CDK, Bicep, Helm/Kubernetes), Dockerfiles, workflows de CI/CD.
- **Receitas existentes.** Quais scanners o projeto já roda, e onde.

### 3. Scanners
Rode, por unidade descoberta, o que se aplica. As colunas "preferência" e "alternativa" são intercambiáveis: use o que estiver disponível, na ordem.

| Lente | Quando | Preferência | Alternativa genérica |
|---|---|---|---|
| Segredos | Sempre | `gitleaks git` (histórico) + `gitleaks dir` (árvore), com `--redact` | `trufflehog git file://. --only-verified`; sem ferramenta, `grep` de padrões conhecidos (chaves de cloud, tokens, `BEGIN … PRIVATE KEY`, `.env` versionado) |
| Dependências (multi-ecossistema) | Qualquer lockfile | `osv-scanner scan -r .` | o scanner nativo da linguagem (abaixo) |
| Python | `pyproject.toml`, `requirements*.txt`, `Pipfile`, `poetry.lock`, `uv.lock` | SAST `bandit -r <src> -ll`; deps `pip-audit` sobre o manifesto do artefato | `semgrep` |
| JavaScript/TypeScript | `package.json` | deps `npm audit --omit=dev` e, separado, o audit completo (`pnpm audit`/`yarn npm audit` conforme o lockfile); SAST: lint de segurança do projeto | `semgrep`; `grep` de sinks (`innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`, `dangerouslySetInnerHTML`, `v-html`, `bypassSecurityTrust*`) |
| Go | `go.mod` | `govulncheck ./...` (só o alcançável), `gosec ./...` | `semgrep` |
| Java/Kotlin | `pom.xml`, `build.gradle*` | OWASP Dependency-Check (plugin do build) | `osv-scanner`; `semgrep` |
| .NET | `*.csproj`, `packages.lock.json` | `dotnet list package --vulnerable --include-transitive` | `osv-scanner` |
| Ruby | `Gemfile.lock` | `bundle audit`, `brakeman` (Rails) | `osv-scanner` |
| PHP | `composer.lock` | `composer audit` | `osv-scanner` |
| Rust | `Cargo.lock` | `cargo audit` | `osv-scanner` |
| Outra linguagem | qualquer código | `semgrep --config auto` | inspeção manual dirigida pelo §4, marcada como manual |
| IaC | CloudFormation/SAM, Terraform, Kubernetes, Helm, Bicep | linter nativo (`cfn-lint`, `tflint`, `kubeconform`) + `checkov -d <dir>` | `trivy config <dir>` |
| Containers | `Dockerfile`, imagens no deploy | `trivy config` (Dockerfile); `trivy image` só para imagem local já construída | `hadolint` |
| CI/CD | `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, etc. | `zizmor` (GitHub Actions) | Inspeção: actions sem pin por SHA, `pull_request_target` com checkout do PR, permissões amplas do token, segredos em logs, scripts com input não sanitizado (`${{ github.event.* }}` em `run:`) |

Regras:
- Registre para cada execução: comando exato, versão da ferramenta, resultado resumido, ou `não executado: <motivo>`.
- Scanner que precisa de rede (bases de CVE): se a rede faltar, diga — não marque como limpo.
- Use os comandos do shell disponível (POSIX ou PowerShell); não presuma `make`.
- Não instale ferramentas no projeto. Pode sugerir a instalação **oficial** no relatório (desconfie de pacotes homônimos em registros de outra linguagem).

### 4. Checklist OWASP (Top 10 2021), filtrado pelo que existe
Para cada item **aplicável**, marque **Presente** (vulnerabilidade existe) / **Mitigado** (com evidência) / **Não aplicável** (motivo em uma linha) / **Não verificado**. Se o projeto adotar outra edição ou um padrão próprio (ASVS, edição mais recente do Top 10), mapeie para ele.

- **A01 Broken Access Control** — rotas sem autenticação onde deveria haver; autorização por recurso (IDOR); isolamento entre usuários/tenants; CORS (origem exata, sem curinga com credenciais, sem refletir `Origin`); métodos expostos além do necessário; CSRF em sessão por cookie.
- **A02 Cryptographic Failures** — TLS forçado (redirect + HSTS); criptografia em repouso; segredos/tokens em URL, log ou storage do browser; algoritmos, modos e aleatoriedade fracos; senhas sem hash adequado.
- **A03 Injection** — SQL/NoSQL parametrizado; comando/shell; template; LDAP/XPath; path traversal; **XSS**: sinks com dado dinâmico, CSP (`script-src` sem `'unsafe-inline'`/`'unsafe-eval'`, `object-src`, `base-uri`); header injection; prompt injection quando houver LLM no fluxo.
- **A04 Insecure Design** — limites de tamanho/quantidade; rate limiting; operações de custo ilimitado (varredura completa, fan-out, upload sem teto); confiança em validação só no cliente; fluxos de negócio abusáveis (replay, corrida).
- **A05 Security Misconfiguration** — headers (CSP, `X-Content-Type-Options`, `frame-ancestors`/`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`); storage privado; permissões mínimas (sem `*` em ação/recurso); debug/stack trace em produção; defaults inseguros de framework; portas/serviços expostos.
- **A06 Vulnerable and Outdated Components** — resultado do §3; runtime/framework fora de suporte; dependências sem pin/lock.
- **A07 Identification and Authentication Failures** — só se houver autenticação: armazenamento e expiração de token/sessão, rotação, chave estática no cliente (pública por definição), MFA, força-bruta, recuperação de conta.
- **A08 Software and Data Integrity Failures** — deserialização insegura (`pickle`, `yaml.load` sem safe loader, `ObjectInputStream`, `BinaryFormatter`); scripts de terceiros sem SRI; integridade da cadeia de build (pin de actions, checksum de binários baixados, assinatura de artefato).
- **A09 Logging and Monitoring Failures** — logs existem e têm retenção; sem PII/segredo em log; alertas para abuso, erro e custo.
- **A10 SSRF** — o servidor busca URL ou host vindo do usuário? Se sim, allowlist e bloqueio de endereços internos/metadados; se não, Não aplicável com a evidência.

### 5. Controles e riscos do perfil
1. **Controles declarados:** confirme cada um pela evidência indicada (rodar o teste, abrir `arquivo:linha`). Controle que sumiu ou mudou = achado (**drift**), com a severidade do risco que cobria.
2. **Riscos aceitos:** confira o gatilho. Não disparou → "Riscos aceitos (inalterados)". Disparou → achado, citando o gatilho.
3. **Lacunas conhecidas:** reconfirme; se alguma foi fechada, aponte a atualização do perfil.
4. **Superfície não modelada:** entrypoint, permissão ou dependência que existe no repo e não está no perfil = achado de drift (no mínimo Info).

Com perfil inferido, este passo se reduz a listar os controles **encontrados** com evidência; não há riscos aceitos.

### 6. Severidade
| | Exploitabilidade alta (sem auth, remota, trivial) | Média (requer auth, interação do usuário ou posição) | Baixa (teórica, sem caminho neste sistema) |
|---|---|---|---|
| **Impacto alto** (dado sensível exposto/alterado, execução remota, tomada de conta ou de infraestrutura, custo sem teto) | **CRÍTICA** | **ALTA** | MÉDIA |
| **Impacto médio** (integridade ou disponibilidade parcial, defacement, abuso limitado) | **ALTA** | MÉDIA | BAIXA |
| **Impacto baixo** (defesa em profundidade ausente, informação mínima) | MÉDIA | BAIXA | BAIXA/INFO |

Meça o impacto pelos ativos do perfil (declarado ou inferido): o mesmo achado pesa diferente num app pessoal sem dado sensível e num sistema multi-tenant com dado financeiro. Justifique cada classificação com uma frase de caminho de exploração.

### 7. Relatório
1. **Cabeçalho:** repositório, escopo, commit e estado da árvore, perfil usado (caminho + confirmado/inferido), data, stacks descobertas.
2. **Scanners:** tabela lente × unidade × comando × versão × resultado / `não executado: motivo`.
3. **Achados**, mais grave primeiro:

   | ID | Severidade | OWASP | Achado | Localização | Caminho de exploração | Evidência | Correção sugerida |
   |---|---|---|---|---|---|---|---|

   IDs `SEC-NN`, estáveis dentro do relatório. É o formato que uma etapa de triagem consome.
4. **Drift do perfil** (se houver perfil): controles que sumiram, superfície não modelada, lacunas fechadas.
5. **Riscos aceitos (inalterados)** — uma linha cada, com o gatilho.
6. **Resumo executivo** (3–5 linhas), **Top 3 ações**, **Pontos fortes** (controles verificados com evidência).
7. **Não verificado** — sempre presente, mesmo que seja "nada".
8. **Perfil inferido** (só se não havia perfil) — o rascunho, pronto para o projeto versionar.

O relatório fica na conversa. Se o perfil indicar um destino para relatórios, ofereça salvá-lo lá; não grave sem o usuário pedir.

## Formato do perfil

Arquivo Markdown versionado **no projeto** (local sugerido: `docs/security/threat-model.md`; qualquer local serve com `perfil=`). Seções, todas opcionais:

1. **Contexto** — o que o sistema é, quem usa, o que mudaria o modelo (ex.: virar multi-tenant).
2. **Ativos** — o que proteger, com peso (alto/médio/baixo) e por quê.
3. **Superfície e fronteiras de confiança** — entrypoints, componentes, onde entra dado não confiável.
4. **Controles declarados** — tabela: controle × onde está × evidência que o prova (teste, receita, `arquivo:linha`).
5. **Riscos aceitos** — tabela: risco × decisão (ADR/issue) × por que é aceitável hoje × **gatilho de reavaliação**.
6. **Lacunas conhecidas** — o que falta e não é aceito, com data da verificação.
7. **Comandos de scan do projeto** — como cada lente do §3 roda neste repo (receitas, caminhos de binários, configs, allowlists).
8. **Gatilhos de reauditoria** — mudanças que exigem rodar esta auditoria de novo.

## Observações
- Em modo subagente/não interativo, não pare para perguntar: perfil ausente → siga com o inferido; escopo ou autorização ambíguos → devolva o bloqueio com a pergunta e a alternativa, sem prosseguir.
- Repositório grande: comece pelos entrypoints e fronteiras do §2 e declare em "Não verificado" o que ficou fora, em vez de amostrar em silêncio.
- Achado em código gerado, vendorizado ou de teste: reporte com essa marcação; a severidade considera se ele chega ao artefato.
