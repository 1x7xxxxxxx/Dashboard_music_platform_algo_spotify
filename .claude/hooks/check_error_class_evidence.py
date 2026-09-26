#!/usr/bin/env python3
"""Hook PostToolUse (Write|Edit) — une classe neuve porte-t-elle ses trois preuves ?

AVERTIT, ne bloque jamais. La raison n'est pas la prudence : un blocage serait rouge
pendant toute la revue humaine des 363 classes et sur chaque ajout de ligne d'historique
— c'est-à-dire pendant le travail même qu'il existe pour soutenir. Une porte rouge par
construction est une porte qu'on apprend à contourner.

Pourquoi un hook plutôt qu'une ligne de plus dans une règle
------------------------------------------------------------
Mesuré le 2026-09-16, trois rangs : un hook au moment du geste a mordu ; un test dans la
suite a mordu huit fois ; une note dans un document n'a rien retenu trois fois. L'échec
d'écriture se produit **au moment où l'on écrit**, sur un seul fichier connu — donc la
portée de ce hook est le GESTE « écrire une classe », pas un verbe.

⚠️ Il ne se déclenche que sur `.claude/dev-docs/error-classes.md`, et seulement sur les
classes qui manquent un champ. Le document de santé, lui, compte tout :
`make error-health`.

---
rex: []
---
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_CATALOGUE = "error-classes.md"
_REQUIRED = ("seen_red", "cause_evidence", "guard_scope", "siblings")  # siblings: R185
_CLASS = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$", re.M)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:          # noqa: BLE001 — un hook qui lève bloquerait chaque écriture
        sys.exit(0)

    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(_CATALOGUE):
        sys.exit(0)

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        sys.exit(0)

    missing: list[str] = []
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = (lines[0].strip().split() or [""])[0]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", cid) or cid == "class-id":
            continue
        body = "\n".join(lines[1:])
        absent = [f for f in _REQUIRED if not re.search(rf"^- {f}:", body, re.M)]
        if absent:
            missing.append(f"{cid} → manque {', '.join(absent)}")

    if not missing:
        sys.exit(0)

    print(
        f"⚠️  {len(missing)} classe(s) sans leurs trois preuves :\n   "
        + "\n   ".join(missing[:5])
        + (f"\n   (+{len(missing) - 5})" if len(missing) > 5 else "")
        + "\n"
        "   `seen_red:` la date où la signature est sortie ≠ 0 — jamais une date non\n"
        "   observée. `cause_evidence:` read/measured/inferred/retracted.\n"
        "   `guard_scope:` la famille de GESTE, et un geste voisin NON couvert.\n"
        "   Le champ qui compte le plus est `ne couvre pas:` — c'est lui qui aurait\n"
        "   écrit `pgrep` le 2026-09-12 et épargné trois récidives.\n"
        "   Compte et évolution : make error-health",
        file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
