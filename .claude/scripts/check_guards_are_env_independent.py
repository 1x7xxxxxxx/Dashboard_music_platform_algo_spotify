#!/usr/bin/env python3
"""Un garde ne lit pas le `.env` du poste pour décider de son verdict.

Type: Utility
Uses: pytest, .claude/scripts/pytest_without_dotenv.py
Triggers: signature de la classe `guard-reads-the-box-not-its-subject`
Depends on: tests/ (fichiers chargeant un module de `tools/`), src/utils/env_files.py
Persists in: nothing

Ce qu'il fait
-------------
Rejoue, avec `ENV_FILES` vidé, les fichiers de test qui chargent un module de
`tools/` — donc ceux dont l'import déclenche `load_project_env()`. Le verdict doit
être le même que sur un poste équipé. Il ne l'était pas le 2026-09-05 :
`test_the_sandbox_default_address_is_deliverable` lisait l'adresse de l'opérateur
dans le `.env` au lieu de la poser, passait ici, et ne POUVAIT pas passer sur un
runner. Huit runs de CI l'avaient masqué en échouant plus tôt.

Pourquoi ce n'est pas une signature `pytest` directe
----------------------------------------------------
`audit_runner.pytest_targets` regroupe les signatures pytest « simples » en UNE
invocation, en ne gardant que les node-ids : le `PYTHONPATH` et le `-p` du plugin
seraient jetés, et la signature ne pourrait plus jamais tirer. Un script sans le mot
`pytest` dans son nom garde son propre sous-processus.

Mesuré le 2026-09-05 : 22 fichiers, 842 tests, ~41 s, verdict identique dans les deux
conditions une fois le défaut corrigé.

⚠️ Remesuré le 2026-09-25 : **104 fichiers, 117 s en série** — le script était à lui
seul le chemin critique de la CI (100 s des ~200 s du job « Portes statiques », quand
chaque shard de la suite en prend ~130). Il tourne désormais sous xdist, comme la suite.

---
rex: []
---
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_TESTS = _REPO / "tests"
_PLUGIN_DIR = _REPO / ".claude" / "scripts"


def _files_loading_a_tool() -> list[str]:
    """Les tests qui chargent un module de `tools/` — leur import charge l'env."""
    out = []
    for path in sorted(_TESTS.glob("test_*.py")):
        body = path.read_text(encoding="utf-8")
        if '"tools"' in body or "'tools'" in body or "tools/" in body:
            out.append(str(path.relative_to(_REPO)))
    return out


def _workers() -> str:
    """4 by default — the CI runner's vCPU count, and a ceiling this workstation's
    memory budget tolerates (`PYTEST_WORKERS` in the Makefile overrides it)."""
    return os.environ.get("PYTEST_WORKERS") or "4"


def _changed_tests() -> list[str]:
    """Test files modified or added in the working tree, relative to HEAD."""
    out = subprocess.run(["git", "status", "--porcelain", "--", "tests/"], cwd=_REPO,
                         capture_output=True, text=True, timeout=30).stdout
    names = {line[3:].strip() for line in out.splitlines() if len(line) > 3}
    return sorted(n for n in names if Path(n).name.startswith("test_") and n.endswith(".py"))


def main() -> int:
    files = _files_loading_a_tool()
    # `--changed` : only the test files this working tree touches — the replay the CI
    # static gate runs on 127 files, cut to what a loop just wrote. Added 2026-09-26:
    # a proof written that night passed `make test-changed` and went red in CI, where
    # this replay runs it under the very plugin it proves.
    if "--changed" in sys.argv:
        changed = set(_changed_tests())
        files = [f for f in files if f in changed]
        if not files:
            print("✅ aucun test modifié ne charge un module de `tools/` — rien à rejouer")
            return 0
    if not files:
        print("❌ aucun fichier de test ne charge un module de `tools/` — le "
              "détecteur ne mesure plus rien ; vérifier `_files_loading_a_tool`.")
        return 1

    env = {**os.environ,
           "PYTHONPATH": f"{_PLUGIN_DIR}:{os.environ.get('PYTHONPATH', '')}"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-q", "-p", "pytest_without_dotenv",
         "-n", _workers(), "--dist", "loadgroup"],
        cwd=_REPO, env=env, capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode == 0:
        print(f"✅ {len(files)} fichier(s) rendent le même verdict sans `.env` — "
              "aucun garde ne lit la configuration du poste")
        return 0

    print(f"❌ un garde change de verdict quand le `.env` du poste disparaît "
          f"({len(files)} fichier(s) rejoués). Il est vert là où il a été écrit et "
          "rouge là où il tourne — pose ce que tu lis (`monkeypatch.setenv`) au lieu "
          "de le lire sur la machine.")
    for line in proc.stdout.splitlines():
        if line.startswith(("FAILED", "ERROR")):
            print(f"   {line}")
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1:]
    print(f"   sans .env : {tail[0] if tail else '(pas de verdict pytest)'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
