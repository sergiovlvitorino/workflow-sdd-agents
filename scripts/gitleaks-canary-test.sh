#!/usr/bin/env bash
# gitleaks-canary-test.sh — prova que o SCANNER MORDE (SEC-02 / T-S4-01).
#
# Red-green determinístico do DETECTOR, SEM commitar segredo real:
#   1. escreve um segredo-CANÁRIO SINTÉTICO (AWS key de exemplo da doc,
#      AKIAIOSFODNN7EXAMPLE — inválida, não é credencial) num tmpdir;
#   2. roda `gitleaks detect` -> EXIGE exit != 0 (o scanner detecta);
#   3. remove o canário -> roda de novo -> EXIGE exit 0 (repo limpo).
#
# O canário vive em tmpdir (mktemp), NUNCA no repo versionado nem em
# .gitleaksignore (docs/lessons/security.md — "scanner lê o histórico
# cumulativo; segredo commitado é vazamento permanente"). Este harness prova a
# CAPACIDADE DE DETECÇÃO; a prova de WIRING do job (branch efêmera reprovando o
# merge) é complementar e pendente-de-push.
#
# Requer o CLI `gitleaks` no PATH (o CI instala pinado em v8.18.4 antes de rodar).

set -uo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "ERRO: CLI 'gitleaks' não encontrado no PATH. Instale-o (pinado 8.18.4) antes do harness." >&2
  exit 127
fi

echo "gitleaks: $(gitleaks version 2>&1)"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

CANARY_FILE="$TMP/leak.txt"

# --- Passo 1: canário sintético presente -> deve DETECTAR (exit != 0) ---------
# Formato que casa a regra AWS Access Key do gitleaks; valor de exemplo da AWS
# (documentação oficial), reconhecidamente INVÁLIDO.
cat > "$CANARY_FILE" <<'EOF'
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
EOF

set +e
gitleaks detect --source "$TMP" --no-git --no-banner --redact -v
rc_dirty=$?
set -e

if [[ "$rc_dirty" -eq 0 ]]; then
  echo "FALHA: gitleaks NÃO detectou o canário sintético (exit 0). O gate estaria cego." >&2
  echo "       (canário neutralizado? regra AWS desativada? allowlist indevida?)" >&2
  exit 1
fi
echo "OK: gitleaks detectou o canário (exit=$rc_dirty != 0) — o scanner morde."

# --- Passo 2: canário removido -> repo limpo -> exit 0 ------------------------
rm -f "$CANARY_FILE"

set +e
gitleaks detect --source "$TMP" --no-git --no-banner --redact -v
rc_clean=$?
set -e

if [[ "$rc_clean" -ne 0 ]]; then
  echo "FALHA: gitleaks reportou vazamento num diretório limpo (exit=$rc_clean != 0) — falso-positivo." >&2
  exit 1
fi
echo "OK: diretório limpo passou (exit 0)."

echo ""
echo "=== gitleaks-canary-test: RED-GREEN do detector comprovado ==="
