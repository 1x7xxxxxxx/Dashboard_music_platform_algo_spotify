#!/usr/bin/env python3
"""Tout `trigger_dag(...)` du dashboard porte-t-il `conf={'artist_id': …}` ?

Sortie ≠ 0 quand un appel n'est pas scopé. Lit l'ARBRE, jamais le texte.

---
rex:
  - date: 2026-09-04
    issue: "La signature de la classe `dag-trigger-without-tenant-scope` (P1,
      deterministic, bloquante en CI) était `! grep -rn 'trigger_dag(' src/dashboard/
      | grep -v 'conf='`. Un commentaire en fin de ligne mentionnant `conf=` sur un
      appel réellement non scopé — `trigger_dag(dag_id)  # TODO conf=` — supprimait
      le hit en silence. La classe la plus grave du catalogue reposait sur une
      correspondance de texte."
    fix: "Détecteur AST : chaque `Call` dont la fonction s'appelle `trigger_dag` doit
      porter un mot-clé `conf`, et ce `conf` doit mentionner `artist_id`. Les
      commentaires n'existent pas dans un arbre."
    severity: crit
---
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DASHBOARD = _ROOT / "src" / "dashboard"


def unscoped_triggers(root: Path = _DASHBOARD) -> list[str]:
    """`fichier:ligne` de chaque `trigger_dag(...)` sans `conf={'artist_id': …}`."""
    out: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name != "trigger_dag":
                continue
            conf = next((k.value for k in node.keywords if k.arg == "conf"), None)
            if conf is not None and _mentions_tenant(conf, tree):
                continue
            rel = path.relative_to(_ROOT)
            out.append(f"{rel}:{node.lineno}")
    return out


def _mentions_tenant(conf: ast.AST, tree: ast.AST) -> bool:
    """`conf` porte-t-il `artist_id` — littéralement, ou via la variable passée ?

    Suivre la VARIABLE est obligatoire, et c'est ce qui a fait échouer la première
    version : `collection_trigger.py` construit `conf = {'artist_id': artist_id} if …`
    puis appelle `trigger_dag(dag_id, conf=conf)`. Un détecteur qui n'inspecte que
    l'expression du mot-clé ne voit qu'un `Name` et crie au défaut — un faux positif
    sur du code correct, ce qui use un garde aussi sûrement qu'un faux négatif.
    """
    if "artist_id" in ast.dump(conf):
        return True
    if not isinstance(conf, ast.Name):
        return False
    return any(isinstance(n, ast.Assign)
               and any(getattr(t, "id", None) == conf.id for t in n.targets)
               and "artist_id" in ast.dump(n.value)
               for n in ast.walk(tree))


def main() -> int:
    hits = unscoped_triggers()
    for h in hits:
        print(f"{h}: trigger_dag() sans conf={{'artist_id': …}}")
    if hits:
        print(f"\n{len(hits)} déclenchement(s) non scopé(s) — les collecteurs "
              "tourneraient sur toute la flotte.", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
