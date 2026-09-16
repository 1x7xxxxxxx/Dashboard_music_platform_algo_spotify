#!/usr/bin/env python3
"""De combien de MAJEURES chaque action épinglée est-elle en retard ?

Type: Utility
Uses: gh (API GitHub), .github/workflows/*.yml, .github/actions/*/action.yml
Triggers: security-nightly.yml (non bloquant)
Persists in: nothing

Pourquoi cet outil existe — mesuré le 2026-09-16
------------------------------------------------
`.github/dependabot.yml` ignore les mises à jour MAJEURES pour `github-actions`, et la
raison est bonne : une majeure change le runner sous la CI, et la CI est la seule chose
qui parle avant un déploiement. Le prix de cette prudence n'avait jamais été mesuré.

`astral-sh/setup-uv` était épinglé en **v4** alors que la v10 était publiée. Six
majeures. Conséquence concrète, lue dans le log : la v4 parle à l'API de cache que
GitHub a retirée, donc `Failed to restore: Cache service responded with 400` sur CHAQUE
exécution — un taux de succès de cache de 0 %, et **20 s perdues par job**, soit le plus
gros poste fixe une fois la suite shardée.

Rien ne pouvait le signaler. Dependabot ne propose pas les majeures, et une action qui
ne publie QUE des majeures ne produit alors aucune PR : le silence est indiscernable
d'« à jour ». Une règle de prudence sans échéance ni visibilité devient un gel.

Ce que cet outil fait, et ce qu'il ne fait pas
----------------------------------------------
Il RAPPORTE, il ne bloque pas. Le choix de monter une majeure reste humain — c'est
exactement ce que la clause de `dependabot.yml` veut protéger. Ce qui change est qu'on
sait de quoi on s'abstient.

Il ne regarde que les actions TIERCES : une action locale (`./.github/actions/...`) n'a
pas de version amont.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(v?\d+)[^\s]*\s*$")


def pinned_actions() -> dict[str, set[str]]:
    """{ 'owner/repo': {'v4', 'v6'} } — lu dans les workflows ET les actions locales."""
    found: dict[str, set[str]] = {}
    roots = [_ROOT / ".github" / "workflows", _ROOT / ".github" / "actions"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.y*ml")):
            for line in path.read_text(encoding="utf-8").splitlines():
                m = _USES.match(line)
                if m:
                    found.setdefault(m.group(1), set()).add(m.group(2))
    return found


def latest_major(repo: str) -> int | None:
    """La majeure de la dernière release, ou None si l'API ne répond pas."""
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}/releases/latest", "--jq", ".tag_name"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    m = re.search(r"v?(\d+)", out.stdout.strip())
    return int(m.group(1)) if m else None


def main() -> int:
    rows = []
    unknown = []
    for repo, versions in sorted(pinned_actions().items()):
        latest = latest_major(repo)
        if latest is None:
            unknown.append(repo)
            continue
        for v in sorted(versions):
            cur = int(re.search(r"(\d+)", v).group(1))
            rows.append((latest - cur, repo, v, latest))

    rows.sort(reverse=True)
    print("| retard (majeures) | action | épinglée | dernière |")
    print("|---|---|---|---|")
    for behind, repo, v, latest in rows:
        mark = "🔴" if behind >= 2 else ("🟠" if behind == 1 else "✅")
        print(f"| {mark} {behind} | `{repo}` | `{v}` | `v{latest}` |")
    if unknown:
        print()
        print("Sans réponse de l'API (jeton ou dépôt sans release) : "
              + ", ".join(f"`{r}`" for r in unknown))

    late = [r for r in rows if r[0] >= 2]
    if late:
        print()
        print(f"**{len(late)} action(s) à 2 majeures ou plus de retard.** Dependabot ne "
              "les proposera JAMAIS : `.github/dependabot.yml` ignore les majeures pour "
              "`github-actions`. La montée est un geste humain — ce rapport dit lequel.")
    # Toujours 0 : ce contrôle RAPPORTE, il ne garde pas.
    return 0


if __name__ == "__main__":
    sys.exit(main())
