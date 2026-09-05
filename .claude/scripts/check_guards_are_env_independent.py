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

---
rex: []
---
"""
from __future__ import annotations

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


def main() -> int:
    files = _files_loading_a_tool()
    if not files:
        print("❌ aucun fichier de test ne charge un module de `tools/` — le "
              "détecteur ne mesure plus rien ; vérifier `_files_loading_a_tool`.")
        return 1

    env = {**dict(__import__("os").environ),
           "PYTHONPATH": f"{_PLUGIN_DIR}:{__import__('os').environ.get('PYTHONPATH', '')}"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *files, "-q", "-p", "pytest_without_dotenv"],
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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
