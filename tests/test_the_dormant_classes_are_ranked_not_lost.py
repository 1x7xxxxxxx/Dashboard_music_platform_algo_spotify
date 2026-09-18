"""Les classes dormantes sont RANGÉES à la fin, jamais retirées.

Type: Test
Uses: json, re
Depends on: .claude/dev-docs/error-classes.md, error-class-health.json
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
Le catalogue portait 402 classes sur 8 400 lignes, dont **206 (51 %)** remplissaient
toutes les conditions du sommeil : jamais récidivé, un balayage a eu lieu et n'a trouvé
aucun autre site, statut `guarded`/`resolved`/`fixed`, et un garde automatique dont le
fichier `tests/…` existe. Un humain qui ouvrait le document rencontrait les 402 dans
l'ordre de leur écriture.

**Pourquoi un titre de section et PAS un second fichier.** C'était le plan, et la
mesure l'a écarté :

* le gain en temps d'une scission est **≈ 0 s** — les 13 s que le catalogue coûte à la
  suite sont dominées par les 8,46 s du cliquet de santé, qui viennent du rejeu de
  l'historique **git** ; scinder le fichier d'aujourd'hui ne change rien aux révisions
  d'hier ;
* le rayon de souffle est de **47 sites lecteurs** (33 en Python, 14 ailleurs), chacun
  devant décider « le fichier actif seul, ou les deux ? ».

Un second fichier qu'un lecteur oublie est la dérive que ce dépôt paie le plus souvent.
Un titre de section coûte une ligne et ne peut être oublié par personne : les trois
parseurs du dépôt l'ignorent déjà, parce qu'aucun n'accepte un titre qui ne soit pas en
kebab-case.

Ce que ce fichier tient
-----------------------
1. **Aucun identifiant n'est perdu** dans le rangement — la vraie peur d'un déplacement
   de 206 blocs.
2. La section existe et **décrit ce qu'elle contient**, en nombre.
3. Le critère reste MÉCANIQUE : une classe rangée là remplit encore les conditions.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
_CAT = ROOT / ".claude" / "dev-docs" / "error-classes.md"
_SANTE = ROOT / ".claude" / "dev-docs" / "error-class-health.json"
_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$")
_SEP = "## 💤 Classes DORMANTES"


def _blocs() -> list[tuple[str, str]]:
    out = []
    for b in re.split(r"(?m)^(?=## )", _CAT.read_text(encoding="utf-8"))[1:]:
        m = _HEAD.match(b.split("\n", 1)[0])
        if m:
            out.append((m.group(1), b))
    return out


def _dormante(c: dict) -> bool:
    if c.get("history_additions", 0) != 0:
        return False
    if c.get("siblings_sites") != 0:
        return False
    if c.get("status") not in ("guarded", "resolved", "fixed"):
        return False
    if not c.get("guard_automatic"):
        return False
    g = c.get("guard_ref") or ""
    return g.startswith("tests/") and (ROOT / g.split("::")[0]).exists()


def test_no_identifier_was_lost_in_the_move() -> None:
    """La peur d'un déplacement de 206 blocs, et la seule qui compte."""
    du_catalogue = {cid for cid, _ in _blocs()}
    de_la_sante = set(json.loads(_SANTE.read_text(encoding="utf-8"))["classes"])
    perdues = de_la_sante - du_catalogue
    assert not perdues, (
        f"{len(perdues)} classe(s) présentes dans l'instantané de santé et ABSENTES du "
        f"catalogue : {sorted(perdues)[:5]}. Un rangement qui perd un bloc améliore "
        "tous les taux sans rien livrer — c'est exactement ce que les planchers de "
        "population interdisent.")
    assert len(du_catalogue) == len(_blocs()), (
        "deux blocs portent le même identifiant : le déplacement en a dupliqué un.")


def test_the_dormant_section_exists_and_says_how_many() -> None:
    """Une section qui ne dit pas ce qu'elle contient se lit comme une décharge."""
    texte = _CAT.read_text(encoding="utf-8")
    assert _SEP in texte, (
        "la section des classes dormantes a disparu : les 402 classes sont de nouveau "
        "mêlées, et un lecteur rencontre d'abord celles qui dorment depuis des mois.")
    entete = texte[texte.index(_SEP):texte.index(_SEP) + 1400]
    assert re.search(r"Les \d+ classes qui suivent", entete), (
        "l'en-tête de la section ne dit plus COMBIEN de classes elle contient. Un "
        "nombre écrit est un nombre qu'on peut contredire ; son absence, non.")


def test_every_class_after_the_separator_still_meets_the_criterion() -> None:
    """Le critère reste MÉCANIQUE — il ne devient pas un tiroir où l'on range à la main.

    C'est le risque réel d'une section « dormantes » : qu'on y pousse une classe gênante
    plutôt qu'une classe endormie. Le verdict vient de `error-class-health.json`, que
    personne ne rédige.
    """
    texte = _CAT.read_text(encoding="utf-8")
    apres = texte[texte.index(_SEP):]
    sante = json.loads(_SANTE.read_text(encoding="utf-8"))["classes"]
    rangees = [m.group(1) for b in re.split(r"(?m)^(?=## )", apres)[1:]
               for m in [_HEAD.match(b.split("\n", 1)[0])] if m]
    assert rangees, "la section dormante est vide"
    reveillees = [c for c in rangees if c in sante and not _dormante(sante[c])]
    assert not reveillees, (
        f"{len(reveillees)} classe(s) rangée(s) parmi les dormantes ne remplissent plus "
        f"le critère : {reveillees[:5]}. Leur garde a rougi, ou un balayage a trouvé un "
        "site — elles doivent remonter. Le rangement est mécanique, pas un tiroir.")


def test_the_live_half_is_not_empty_and_is_the_smaller_one() -> None:
    """Anti-vacuité : sans elle, tout ranger en dormant passerait ce fichier au vert."""
    texte = _CAT.read_text(encoding="utf-8")
    avant = texte[:texte.index(_SEP)]
    vivantes = [m.group(1) for b in re.split(r"(?m)^(?=## )", avant)[1:]
                for m in [_HEAD.match(b.split("\n", 1)[0])] if m]
    assert len(vivantes) >= 50, (
        f"seulement {len(vivantes)} classe(s) avant le séparateur. Soit le critère "
        "s'est élargi au point de tout endormir, soit la lecture est cassée — dans les "
        "deux cas le classement ne dit plus rien.")
