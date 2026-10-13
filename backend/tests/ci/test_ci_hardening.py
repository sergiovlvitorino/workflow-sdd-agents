"""Guard estático de hardening do CI (SEC-02 / SEC-07 — T-S4-01 / T-S4-04).

Lê `.github/workflows/ci.yml` como TEXTO (regex; sem PyYAML — não é dep pinada
do projeto), ignorando linhas de comentário, e morde a FORMA REAL do workflow
(qa.md — "o gate morde a forma real; varredura textual é autoritativa").

Red-green (prova mental, §4.4 do DETAIL T-S4-QA):
  - reintroduzir `uses: actions/checkout@v4` (tag mutável) -> test_no_mutable_tags VERMELHO;
  - remover `permissions: contents: read` -> test_permissions_least_privilege VERMELHO;
  - remover o step pip-audit / job secret-scan -> os testes de presença VERMELHO;
  - baixar a sentinela `>= 7` para `> 0` -> mascara truncamento (revisor reprova).

Estado hardenizado -> tudo VERDE.
"""

from __future__ import annotations

import re
from pathlib import Path

# Raiz do repo a partir deste arquivo: tests/ci/ -> tests -> backend -> <repo>.
# Robusto ao cwd (o CI roda pytest com working-directory: backend).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Nº mínimo de `uses:` conhecido no workflow (3 checkout + 2 setup-python +
# 1 setup-node + 1 gitleaks-action). Sentinela anti-truncamento: se o parse
# varrer só um pedaço (ex.: "3 de 7"), o teste reprova em vez de passar vacuamente.
_N_USES_ESPERADO = 7


def _raw_lines() -> list[str]:
    assert _CI_YML.is_file(), f"ci.yml não encontrado em {_CI_YML}"
    return _CI_YML.read_text(encoding="utf-8").splitlines()


def _code_lines() -> list[str]:
    """Linhas do workflow SEM comentários (linha iniciada por `#` após indentação).

    Comentário inline (ex.: `uses: ...@<sha> # v4.2.2`) é preservado porque a
    parte de código antes do `#` é o que importa; comentário de linha inteira é
    descartado para não casar exemplos/documentação embutida no YAML.
    """
    out: list[str] = []
    for line in _raw_lines():
        if line.strip().startswith("#"):
            continue
        out.append(line)
    return out


def _uses_refs() -> list[str]:
    """Todas as referências de `uses:` (a parte após `uses:` até `#` ou fim)."""
    refs: list[str] = []
    for line in _code_lines():
        m = re.search(r"\buses:\s*(\S+)", line)
        if m:
            refs.append(m.group(1))
    return refs


def test_permissions_least_privilege() -> None:
    """(a) Existe `permissions:` com `contents: read` (nível workflow ou job)."""
    code = "\n".join(_code_lines())
    assert re.search(r"^\s*permissions:\s*$", code, re.MULTILINE), (
        "bloco `permissions:` ausente no ci.yml (least-privilege — SEC-07)"
    )
    assert re.search(r"^\s*contents:\s*read\s*$", code, re.MULTILINE), (
        "`contents: read` ausente — GITHUB_TOKEN herdaria escopo de escrita (SEC-07)"
    )


def test_uses_sentinela_anti_truncamento() -> None:
    """(e) Sentinela: pelo menos os N `uses:` conhecidos foram varridos."""
    refs = _uses_refs()
    assert len(refs) >= _N_USES_ESPERADO, (
        f"varreu apenas {len(refs)} `uses:` (esperado >= {_N_USES_ESPERADO}); "
        "possível truncamento do parse — a sentinela reprova em vez de passar vacuamente"
    )


def test_all_actions_pinned_by_sha() -> None:
    """(b) Toda ocorrência de `uses:` casa um SHA de 40 hex."""
    refs = _uses_refs()
    assert refs, "nenhum `uses:` encontrado — parse quebrado"
    for ref in refs:
        assert re.search(r"@[0-9a-fA-F]{40}\b", ref), (
            f"`uses: {ref}` não está pinado por SHA de 40 hex (supply-chain — SEC-07)"
        )


def test_no_mutable_tags() -> None:
    """(b) NENHUM `uses:` usa tag mutável (@v4, @v5, @main, @latest, @master)."""
    refs = _uses_refs()
    for ref in refs:
        assert not re.search(r"@v\d+\b", ref), f"`uses: {ref}` usa tag mutável @vN (SEC-07)"
        assert not re.search(r"@(main|master|latest)\b", ref), (
            f"`uses: {ref}` usa ref mutável @main/@master/@latest (SEC-07)"
        )


def test_gitleaks_version_fixed() -> None:
    """(c) GITLEAKS_VERSION presente e fixo (não latest/master) — paridade determinística."""
    code = "\n".join(_code_lines())
    m = re.search(r'GITLEAKS_VERSION:\s*"?([^\s"#]+)"?', code)
    assert m, "GITLEAKS_VERSION ausente — a action baixaria um CLI não-fixado (drift/flaky)"
    version = m.group(1)
    assert version.lower() not in {"latest", "master", "main"}, (
        f"GITLEAKS_VERSION='{version}' é mutável — pinar a versão exata (paridade com o pre-commit)"
    )
    assert re.match(r"^\d+\.\d+\.\d+$", version), (
        f"GITLEAKS_VERSION='{version}' não é uma versão semver fixa"
    )


def test_pip_audit_step_present() -> None:
    """(d) Existe step de `pip-audit` (supply-chain backend, SEC-07)."""
    code = "\n".join(_code_lines())
    assert "pip-audit" in code, "step `pip-audit` ausente no ci.yml (SEC-07)"


def test_secret_scan_job_present() -> None:
    """(d) Job de secret-scan (gitleaks) presente (SEC-02)."""
    code = "\n".join(_code_lines())
    assert re.search(r"^\s*secret-scan:\s*$", code, re.MULTILINE), (
        "job `secret-scan:` ausente no ci.yml (SEC-02)"
    )
    assert "gitleaks" in code, "referência a `gitleaks` ausente no ci.yml (SEC-02)"
