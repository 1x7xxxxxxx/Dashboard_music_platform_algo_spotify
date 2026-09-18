#!/usr/bin/env python3
"""Quels scripts d'outillage n'est invoqué par AUCUN exécutant ?

Type: Utility (audit)
Uses: pathlib
Triggers: `make config-check`, la CI, et le test qui porte le cliquet
Persists in: rien

---
rex:
  - date: 2026-09-18
    issue: "Trois versions successives de ce balayage ont sur-compte : 12 scripts morts, puis 11, puis 8. Les deux corrections venaient de surfaces d execution oubliees, pas d une relecture du predicat."
    fix: "Un script appelant est une surface ; le champ signature du catalogue en est une aussi — audit_runner LANCE ces commandes. Les deux sont declarees explicitement, avec le compte qu elles ont corrige."
    severity: warn
---

Pourquoi ce fichier existe
--------------------------
Un outil que rien n'invoque n'est pas neutre : **c'est une affirmation qu'une chose est
couverte**. Ce dépôt l'a mesuré ailleurs (33 spawns pour les agents nommés dans une
règle impérative, **0 sur 23** pour ceux nommés dans un tableau) ; la même loi vaut pour
un script.

⚠️ **Trois versions de ce balayage, trois comptes différents — et je les ai tous crus.**

| version | verdict | ce qui manquait |
|---|---|---|
| 1 | **12** scripts morts, 1 311 l. | un script peut en appeler un autre (`pytest_without_dotenv.py` ← `check_guards_are_env_independent.py`) |
| 2 | **11** scripts morts, 1 263 l. | `audit_runner --static`/`--all` **LANCENT** les commandes du champ `signature:` du catalogue — sept scripts tournaient à chaque CI |
| 3 | **8** scripts, 871 l. | — |

Sur-comptage de **32 %**, dans le même sens que les dix balayages du 2026-09-17 : le
prédicat cherchait une FORME (« le nom apparaît-il dans un Makefile ou un workflow ? »)
là où la question est une PROPRIÉTÉ (« quelque chose l'exécute-t-il ? »). C'est
`a-sweep-predicate-that-matches-a-form-not-a-property`, et la règle 20 de CLAUDE.md
existe pour ça.

Ce que ce balayage NE dit pas
-----------------------------
Qu'un script injoignable doive être supprimé. Un **instrument de mesure** est
légitimement injoignable : il ne prétend rien couvrir. Ils le déclarent par un
marqueur, et ce fichier les compte à part.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CIBLES = ("**/.claude/scripts/*.py", "**/tools/dev/*.py")

# Le marqueur qu'un instrument pose pour dire « je ne couvre rien, mon silence ne ment
# sur rien ». Il porte sa raison dans le fichier même, pas dans une liste ailleurs —
# une liste d'exemptions se périme sans bruit.
MARQUEUR = "OUTIL DE MESURE À USAGE PONCTUEL"


def est_instrument(corps: str) -> bool:
    """Le fichier DÉCLARE-T-IL être un instrument de mesure ?

    ⚠️ LE MARQUEUR EST UN EN-TÊTE, PAS UNE MENTION. Première version :
    `MARQUEUR in corps`. Ce fichier-ci porte la chaîne dans sa propre prose — il s'est
    donc déclaré instrument lui-même, à sa première exécution.
    `guard-satisfied-by-its-own-comment`, cinquième instance de la journée, et cette
    fois dans l'outil écrit pour compter les outils.

    La TÊTE est ce qui précède le premier `import` — structurel, pas un nombre de
    lignes choisi au jugé. `lazy_body_cost.py` a une docstring de 60 lignes ; un seuil
    à 40 l'aurait déclaré muet pour la longueur de sa prose, ce qui n'a rien à voir
    avec la question posée.

    Extraite pour être APPELABLE : tant qu'elle vivait dans la boucle, la seule façon
    de la tester était de passer par l'arbre réel — et câbler cet audit a rendu son
    propre cas inatteignable, donc l'assertion écrite pour lui est devenue vacante.
    """
    lignes = corps.splitlines()
    fin = next((i for i, x in enumerate(lignes)
                if x.startswith(("import ", "from "))), len(lignes))
    return MARQUEUR in "\n".join(lignes[:fin])


def _surfaces() -> list[pathlib.Path]:
    """Tout ce qui peut EXÉCUTER un script de ce dépôt."""
    out: list[pathlib.Path] = [ROOT / "Makefile", ROOT / ".pre-commit-config.yaml",
                               ROOT / "CLAUDE.md"]
    for motif in (".github/workflows/*.yml", ".claude/hooks/*.py",
                  ".claude/commands/*.md", ".claude/rules/*.md",
                  ".claude/skills/*/SKILL.md", ".claude/workflows/*",
                  ".claude/scripts/*.py", "tools/dev/*.py", "tools/*.py", "tools/*.sh",
                  "tests/*.py"):
        out += sorted(ROOT.glob(motif))
    for motif in ("src/**/*.py", "airflow/**/*.py"):
        out += sorted(ROOT.glob(motif))
    return [p for p in out if p.is_file()]


def _signatures() -> str:
    """Les COMMANDES du catalogue, pas son texte.

    `audit_runner --static` et `--all` lancent le champ `signature:`. Lire le fichier
    entier ferait passer pour vivant tout script dont le catalogue PARLE — et il parle
    de beaucoup de choses qu'il ne lance pas. C'était le faux positif de la version 2.
    """
    cat = ROOT / ".claude" / "dev-docs" / "error-classes.md"
    if not cat.exists():
        return ""
    return "\n".join(x for x in cat.read_text(encoding="utf-8").splitlines()
                     if x.lstrip().startswith("- signature:"))


def injoignables() -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """(injoignables sans marqueur, instruments déclarés)."""
    surfaces = _surfaces()
    textes = {}
    for p in surfaces:
        try:
            textes[p] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    sigs = _signatures()

    muets: list[tuple[str, int]] = []
    instruments: list[tuple[str, int]] = []
    for motif in CIBLES:
        for c in sorted(ROOT.glob(motif.lstrip("*/"))):
            rel = c.relative_to(ROOT).as_posix()
            corps = c.read_text(encoding="utf-8", errors="replace")
            lignes = len(corps.splitlines())
            if c.name in sigs:
                continue
            if any(c.name in t for p, t in textes.items() if p != c):
                continue
            (instruments if est_instrument(corps) else muets).append((rel, lignes))
    return muets, instruments


def main() -> int:
    muets, instruments = injoignables()
    print(f"▶ outils injoignables : {len(muets)} sans marqueur · "
          f"{len(instruments)} instrument(s) déclaré(s)")
    for rel, n in instruments:
        print(f"  ⚙  {rel} ({n} l.) — instrument déclaré, ne couvre rien")
    if not muets:
        print("✅ aucun script d'outillage n'est injoignable en silence")
        return 0
    for rel, n in muets:
        print(f"  ⊘  {rel} ({n} l.)")
    print(f"\n⊘ {len(muets)} script(s) qu'aucun exécutant n'atteint et qui ne le disent "
          "pas.\n  Un outil que rien n'invoque est une AFFIRMATION qu'une chose est "
          "couverte.\n  Trois issues : le câbler, le retirer vers `.claude/.retired/`, "
          f"ou poser le marqueur\n  « {MARQUEUR} » s'il s'agit d'un instrument de mesure "
          "qui ne couvre rien.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
