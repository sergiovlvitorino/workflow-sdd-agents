#!/usr/bin/env bash
# coverage-gates.sh — Pisos por-categoria (P-07 / T-S2-09)
#
# Roda DEPOIS de `pytest` ter gerado o arquivo .coverage.
# Cada categoria falha INDEPENDENTEMENTE (gate AND com o gate global do pytest).
#
# Uso:
#   cd backend
#   pytest                 # gera .coverage
#   bash coverage-gates.sh # valida pisos por-categoria
#
# CI: rodar ambos; merge só se os dois exitam 0.

set -euo pipefail

# ---------------------------------------------------------------------------
# Sentinela anti-glob-vazio + piso por-categoria.
#
# Implementação em dois passos separados (corrige Bloqueante 2):
#
#   Problema original: com `set -e`, a atribuição
#     `output=$(coverage report --include=... --fail-under=N)` abortava o
#     script quando o coverage retornava exit!=0 (piso não atingido OU glob
#     vazio → "No data"). A sentinela de stmts==0 nunca era alcançada.
#     Adicionalmente, `local exit_code=$?` zera $? (o builtin `local` tem
#     seu próprio exit 0), tornando o código capturado sempre 0.
#
#   Correção:
#     1. Checar statements SEM --fail-under (não gera exit!=0 por piso).
#        `|| true` neutraliza set -e para o caso de glob sem dados.
#        Se stmts==0 → glob não casou arquivo → exit 1 com mensagem nomeada.
#     2. Aplicar --fail-under SOMENTE após confirmar stmts>0, capturando o
#        exit code com `cmd || piso_exit=$?` (padrão seguro sob set -e).
# ---------------------------------------------------------------------------
check_category() {
    local name="$1"
    local include_glob="$2"
    local min_pct="$3"

    echo ""
    echo "=== Gate categoria: ${name} (>= ${min_pct}%) ==="

    # Passo 1: mede SEM --fail-under para nao abortar em caso de glob vazio.
    # `|| true` evita que o set -e mate o script; stmts=0 e detectado abaixo.
    local count_output
    count_output=$(python -m coverage report --include="${include_glob}" 2>&1) || true

    # Extrai total de Stmts da linha "TOTAL  <stmts> <miss> <branch> <bpart> <pct>"
    local stmts
    stmts=$(echo "${count_output}" | awk '/^TOTAL/{print $2}')

    # Sentinela anti-glob-vazio: 0 statements = glob nao casou nenhum arquivo.
    # Um --include que nao bate em arquivo reporta 0 Stmts e 100% vacuamente
    # (falso-verde estrutural — qa.md: "sentinela >0 mascara truncamento").
    if [[ -z "${stmts}" || "${stmts}" == "0" ]]; then
        echo ""
        echo "ERRO [${name}]: 0 statements medidos — glob '${include_glob}' nao casou nenhum arquivo."
        echo "Gate anti-glob-vazio disparado: categoria com 0 Stmts REPROVA (nao passa vacuamente)."
        exit 1
    fi

    echo "Statements encontrados: ${stmts} — aplicando piso de ${min_pct}%..."

    # Passo 2: aplica o piso. Captura exit code sem deixar set -e abortar.
    local piso_output piso_exit
    piso_exit=0
    piso_output=$(python -m coverage report --include="${include_glob}" --fail-under="${min_pct}" 2>&1) \
        || piso_exit=$?

    echo "${piso_output}"

    if [[ ${piso_exit} -ne 0 ]]; then
        echo ""
        echo "ERRO [${name}]: cobertura abaixo de ${min_pct}% (Stmts=${stmts}). Exit=${piso_exit}."
        exit "${piso_exit}"
    fi

    echo "OK [${name}]: ${stmts} statements, >= ${min_pct}%."
}

# ---------------------------------------------------------------------------
# 1) Gate global — reafirmado aqui como cinto-e-suspensório (o pytest ja barra).
#    Valor: 99 (patamar medido na Sprint 2 com folga de 1 ponto; ratchet — P-07).
# ---------------------------------------------------------------------------
echo ""
echo "=== Gate GLOBAL (>= 99%) ==="
python -m coverage report --fail-under=99

# ---------------------------------------------------------------------------
# 2) Adapter SQLite — ADR-0003 §8: piso PROPRIO, nao diluido.
#    Caminho: backend/src/blog/infrastructure/sqlite_repository.py (T-S2-04).
#    Piso: 100% (P-07 Integracoes: minimo 80; medido real 100 na Sprint 2).
# ---------------------------------------------------------------------------
check_category \
    "adapter-sqlite" \
    "src/blog/infrastructure/sqlite_*.py" \
    100

# ---------------------------------------------------------------------------
# 3) Dominio critico — maquina de estados Post.publish (domain/post.py).
#    Piso: 100% (P-07 Dominio: minimo 95; medido real 100 na Sprint 2).
# ---------------------------------------------------------------------------
check_category \
    "domain" \
    "src/blog/domain/*.py" \
    100

# ---------------------------------------------------------------------------
# 4) Idempotencia + casos de uso de ESCRITA (P-07 idempotencia = 100%).
#    Caminhos: application/create_post.py + application/publish_post.py (T-S2-05).
# ---------------------------------------------------------------------------
check_category \
    "use-cases-write" \
    "src/blog/application/create_post.py,src/blog/application/publish_post.py" \
    100

# ---------------------------------------------------------------------------
# 5) Isolamento/autorizacao — read-by-id com allowlist (P-04).
#    Caminho: application/get_post.py (T-S2-07).
#    Piso: 100% (P-07 "Isolamento" = 100% dos cenarios).
# ---------------------------------------------------------------------------
check_category \
    "isolation-get-post" \
    "src/blog/application/get_post.py" \
    100

# ---------------------------------------------------------------------------
# 6) API publica — routers (posts_router T-S2-06/07 + health_router T-S3-05).
#    Glob: todos os *_router.py em interfaces/ (sentinela anti-glob-vazio confirma
#    que casa posts_router.py E health_router.py).
#    Piso: 100% (P-07 API = 100% dos endpoints).
# ---------------------------------------------------------------------------
check_category \
    "api-router" \
    "src/blog/interfaces/*_router.py" \
    100

# ---------------------------------------------------------------------------
# 7) Handlers de erro tipado RFC 9457 (P-11).
#    Caminho: interfaces/errors.py.
#    Piso: 100%.
# ---------------------------------------------------------------------------
check_category \
    "error-handlers" \
    "src/blog/interfaces/errors.py" \
    100

# ---------------------------------------------------------------------------
# 8) Observabilidade — middleware único (sanitizacao de input externo, allowlist
#    anti-PII, correlacao request_id). P-05 + P-09; trata input externo (P-11) -> 100%.
# ---------------------------------------------------------------------------
check_category \
    "observabilidade" \
    "src/blog/interfaces/observability.py" \
    100

echo ""
echo "=== Todos os gates por-categoria APROVADOS ==="
