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
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)\s*(?:#.*)?$")


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


def _gh(*args: str) -> str | None:
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def latest(repo: str) -> tuple[int, str] | None:
    """(majeure, TAG ÉCRIVABLE) de la dernière release, ou None si l'API se tait.

    Le tag compte autant que la majeure, et pour une raison payée le 2026-09-16 :
    `astral-sh/setup-uv` publie `v10.1.0` et **PAS** de tag majeur flottant `v10`.
    Un rapport qui aurait dit « v10 » aurait suggéré un épinglage irrésolvable — les
    cinq jobs de la CI ont échoué en NEUF SECONDES sur
    `Unable to resolve action … unable to find version v10`, avant même la mise en
    route. C'est la classe `a-printed-command-is-runnable-as-printed` : ce qu'un
    rapport imprime doit pouvoir être écrit tel quel.

    On préfère donc le tag majeur flottant QUAND IL EXISTE, et on retombe sur le tag
    exact sinon — ce qui est vérifié contre la liste des tags, pas supposé.
    """
    raw = _gh("api", f"repos/{repo}/releases/latest", "--jq", ".tag_name")
    if raw is None:
        return None
    tag = raw.strip()
    m = re.search(r"v?(\d+)", tag)
    if not m:
        return None
    major = int(m.group(1))
    tags = _gh("api", f"repos/{repo}/tags", "--jq", ".[].name") or ""
    floating = f"v{major}"
    return (major, floating if floating in tags.split() else tag)


def resolves(repo: str, ref: str) -> bool | None:
    """Ce `owner/repo@ref` existe-t-il vraiment ? None si l'API se tait.

    LA question, et elle a coûté un run entier. Un épinglage irrésolvable ne fait pas
    échouer un test : il fait échouer **tous les jobs en neuf secondes**, à
    « Prepare all required actions », avant la mise en route, avec
    `Unable to resolve action … unable to find version`. Le 2026-09-16,
    `astral-sh/setup-uv@v10` a fait exactement ça — la dernière release est `v10.1.0`
    et ce dépôt ne publie PAS de tag majeur flottant, contrairement à `@v4` qui, lui,
    en avait un. Déduire le tag du numéro de version est donc faux, et rien dans le
    dépôt ne pouvait le dire avant de pousser.
    """
    out = _gh("api", f"repos/{repo}/git/ref/tags/{ref}", "--jq", ".ref")
    return None if out is None and _gh("api", f"repos/{repo}") is None else bool(out)


def main() -> int:
    rows = []
    unknown = []
    for repo, versions in sorted(pinned_actions().items()):
        got = latest(repo)
        if got is None:
            unknown.append(repo)
            continue
        major, tag = got
        for v in sorted(versions):
            m = re.search(r"(\d+)", v)
            if not m:
                continue
            rows.append((major - int(m.group(1)), repo, v, tag, resolves(repo, v)))

    rows.sort(key=lambda r: (-r[0], r[1]))
    print("| retard | action | épinglée | résout ? | à écrire pour monter |")
    print("|---|---|---|---|---|")
    broken = []
    for behind, repo, v, tag, ok in rows:
        mark = "🔴" if behind >= 2 else ("🟠" if behind == 1 else "✅")
        res = "✅" if ok else ("❓" if ok is None else "🚫 INTROUVABLE")
        if ok is False:
            broken.append(f"{repo}@{v}")
        suggestion = f"`{repo}@{tag}`" if behind else "—"
        print(f"| {mark} {behind} | `{repo}` | `{v}` | {res} | {suggestion} |")
    if unknown:
        print()
        print("Sans réponse de l'API (jeton ou dépôt sans release) : "
              + ", ".join(f"`{r}`" for r in unknown))

    if broken:
        print()
        print("🚫 **ÉPINGLAGE IRRÉSOLVABLE** — ces `uses:` n'existent pas en amont. "
              "Tous les jobs qui les portent échoueront en **neuf secondes**, avant la "
              "mise en route, sur `Unable to resolve action` : "
              + ", ".join(f"`{b}`" for b in broken))

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
