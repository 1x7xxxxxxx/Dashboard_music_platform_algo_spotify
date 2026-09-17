"""Un champ écrit deux fois dans une entrée dit deux choses, et l'outil n'en lit qu'une.

Type: Test
Uses: re
Depends on: .claude/dev-docs/error-classes.md, tools/dev/error_class_health.py
Persists in: nothing

Trouvé le 2026-09-17 en repliant un doublon que je venais de créer moi-même — et le
balayage a montré que le mien n'était pas le premier.

**58 classes portaient `cause_evidence` DEUX fois**, et les 58 se contredisaient : la
première ligne disait `read` ou `measured`, la seconde était restée à `unknown`. Elles
viennent de la passe de back-fill du 2026-09-17, qui a inséré une évidence VÉRIFIÉE sans
retirer la ligne mécanique posée la veille.

⚠️ Le compteur, lui, était juste. `tools/dev/error_class_health.py` lit la PREMIÈRE
occurrence, donc `cause_unknown` valait 181 et non 239 — contrôle rejoué après le
nettoyage, le nombre n'a pas bougé d'une unité. Le défaut n'est donc pas dans la mesure :
il est dans ce qu'un HUMAIN lit en ouvrant l'entrée. Deux verdicts contradictoires sur la
même ligne de champ, dont un invisible à tout outil, c'est `deux-surfaces-deux-nombres`
appliqué à l'intérieur d'une seule surface.

Et c'est pour ça que ce garde ne se contente pas de `cause_evidence` : n'importe quel
champ du schéma peut être dupliqué par la même mécanique, et le suivant ne sera pas
forcément celui qu'on surveille.

Ce qu'il ne couvre PAS
----------------------
Un champ écrit une seule fois et FAUX — ce garde compte, il ne juge pas. Et les blocs
`History:`, dont les lignes sont délibérément répétées.

Mutation record — 2026-09-17, deux passes et la première a raté.
  1. Injecter `- cause_evidence: unknown` après la PREMIÈRE occurrence du fichier :
     **vert**. Cette occurrence vit dans le schéma du préambule, que `_entries()` écarte
     parce que son titre n'est pas un identifiant de classe. Le garde avait raison ; ma
     mutation visait à côté de son sujet.
  2. Injecter le même doublon dans `## streamlit-pin-drift`, une vraie entrée : **rouge**,
     et il nomme la classe et les deux valeurs.
  3. Aveugler le découpage (`re.split` sur `###### ` au lieu de `## `) : **rouge** sur
     l'anti-vacuité — un garde qui ne voit plus d'entrées ne peut pas se taire.
Vu rouge aussi sur les 58 réelles, avant leur nettoyage.

---
rex: []
---
"""
from __future__ import annotations

import re
from pathlib import Path

_CATALOGUE = (Path(__file__).resolve().parents[1]
              / ".claude" / "dev-docs" / "error-classes.md")

# Les champs à valeur UNIQUE du schéma. `History:` en est exclu : son bloc porte une
# ligne par évènement, et c'est sa raison d'être.
_SINGLE_VALUED = (
    "status", "severity", "kind", "symptom", "signature", "seen_red",
    "root_cause", "cause_evidence", "long_term_fix", "autofix", "guard",
    "guard_scope", "siblings", "rex_ref", "first_seen",
)


def _entries() -> list[tuple[str, str]]:
    text = _CATALOGUE.read_text(encoding="utf-8")
    out = []
    for block in re.split(r"\n(?=## )", text):
        if not block.startswith("## "):
            continue
        name = block.split("\n", 1)[0][3:].strip()
        # Le préambule du fichier porte des `## ` qui ne sont pas des classes.
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", name):
            continue
        out.append((name, block))
    return out


def test_the_scan_sees_the_catalogue() -> None:
    """Anti-vacuité : sans entrées, tout ce fichier est vert sur rien."""
    entries = _entries()
    assert len(entries) >= 300, (
        f"seulement {len(entries)} entrées lues dans `error-classes.md` — il y en avait "
        "396 le 2026-09-17. Le découpage est cassé, et le test d'à côté ne garde rien.")


def test_no_field_is_written_twice_in_one_entry() -> None:
    doubles = []
    for name, block in _entries():
        for field in _SINGLE_VALUED:
            found = re.findall(rf"^- {field}:\s*(.*)$", block, re.M)
            if len(found) > 1:
                valeurs = " | ".join(v.strip()[:40] for v in found)
                doubles.append(f"{name} · `{field}` ×{len(found)} → {valeurs}")
    assert not doubles, (
        f"{len(doubles)} champ(s) écrits deux fois dans une même entrée.\n"
        "`error_class_health.py` lit la PREMIÈRE occurrence : la seconde est invisible "
        "à tout outil et visible par tout lecteur. Les 58 trouvées le 2026-09-17 se "
        "contredisaient toutes — `read` puis `unknown`.\n"
        "Remède : garder la ligne VÉRIFIÉE, supprimer l'autre.\n  "
        + "\n  ".join(doubles[:15]))
