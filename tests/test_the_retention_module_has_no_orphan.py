"""Chaque fonction publique de la rétention a un appelant en production.

Type: Test
Uses: ast
Depends on: src/utils/telemetry_retention.py, src/utils/nightly_maintenance.py
Persists in: nothing

Trouvé le 2026-09-17 en balayant les frères de `un-travail-qui-n-arrive-nulle-part`,
et le site était **mon propre travail de la même séance**.

`telemetry_retention.py` a été écrit pour fermer
`a-retention-declared-in-a-comment-and-applied-by-nobody` — une rétention déclarée dans
un `COMMENT ON TABLE` et appliquée par personne. `purge_telemetry` a bien été câblée
dans `nightly_maintenance`. Mais **deux des trois fonctions publiques du module
n'avaient AUCUN appelant** :

  · `purge_summary`     — sa docstring dit « une ligne lisible pour le mail du soir »,
                          et le résumé partait en BRUT ;
  · `undeclared_tables` — sa docstring dit « doit se voir AVANT la nuit où la purge
                          échoue », et le contrôle ne tournait jamais.

⚠️ C'est la même classe déplacée d'un cran : on ne corrige pas « déclaré en commentaire,
appliqué par personne » en écrivant « un module que personne n'appelle ». La question
« qui l'appelle ? » doit être posée sur CHAQUE fonction, pas sur le module.

⚠️ Le balayage qui l'a trouvé s'est d'abord trompé : mon premier prédicat rendait **45**
fonctions orphelines dans `src/` ; quatre des cinq premières vérifiées avaient entre 1 et
8 mentions. Un `git grep -nw` honnête en rend **16**, et parmi elles des faux positifs
légitimes (une route FastAPI est appelée par son décorateur). Le chiffre brut d'un
balayage n'est pas une mesure — il faut ouvrir.

Mutation record — 2026-09-17, deux mutations, deux vues ROUGES :
  1. retirer l'appel à `purge_summary` de `nightly_maintenance`   → rouge, nom donné.
  2. `_PUBLIC` vidé                                                → rouge (anti-vacuité).

---
rex: []
---
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MODULE = _ROOT / "src" / "utils" / "telemetry_retention.py"


def _public_functions() -> list[str]:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    return sorted(
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    )


def test_the_module_still_exposes_public_functions() -> None:
    """Anti-vacuité : un module sans fonction publique rendrait ce garde muet."""
    noms = _public_functions()
    assert len(noms) >= 3, (
        f"seulement {len(noms)} fonction(s) publique(s) dans telemetry_retention.py : "
        f"{noms}. Si le module a été découpé, suivre les noms ; s'il a été supprimé, "
        "retirer ce fichier DANS LE MÊME COMMIT.")


def _used_inside_the_module() -> set[str]:
    """Les fonctions que le module s'appelle à lui-même.

    ⚠️ Ajouté après un premier jet TROP STRICT : `declared_retentions` est appelée deux
    fois dans son propre module (lignes 142 et 187) et n'a simplement pas d'underscore.
    Un garde qui exige un appelant EXTERNE pour une fonction interne demande de renommer
    du code correct — c'est un faux positif, et on corrige le prédicat, pas le code.
    """
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    return {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            for n in ast.walk(tree) if isinstance(n, ast.Call)}


def _referenced_in_production() -> set[str]:
    """Les noms RÉELLEMENT référencés par du code, hors du module de rétention.

    ⚠️ À l'AST, et ce n'est pas un détail : la version `grep` de ce garde a été mutée
    et est restée VERTE **parce que mon propre commentaire nommait la fonction**.
    « Écrire sur le geste déclenche le garde du geste » — troisième fois dans cette
    séance, et la classe est déjà au catalogue sous
    `a-bash-hook-that-blocks-the-prose-about-the-gesture`. Un commentaire n'appelle
    rien : seuls un `Call`, un `Name` et un `ImportFrom` comptent.

    ⚠️ Deux versions fausses ont précédé : `git grep` lit l'INDEX et ne voyait pas une
    modification non indexée ; `git grep --no-index` voyait le disque mais aussi la
    prose. Les deux ont été mesurées en mutant, pas devinées.
    """
    vus: set[str] = set()
    for dossier in ("src", "airflow", "tools"):
        for chemin in (_ROOT / dossier).rglob("*.py"):
            if chemin == _MODULE:
                continue
            try:
                arbre = ast.parse(chemin.read_text(encoding="utf-8"))
            except SyntaxError:                      # pragma: no cover
                continue
            for n in ast.walk(arbre):
                if isinstance(n, ast.Name):
                    vus.add(n.id)
                elif isinstance(n, ast.Attribute):
                    vus.add(n.attr)
                elif isinstance(n, ast.ImportFrom):
                    vus.update(a.name for a in n.names)
    return vus


def test_every_public_function_has_a_caller_in_production() -> None:
    """La question « qui l'appelle ? » posée à CHAQUE fonction, pas au module."""
    internes = _used_inside_the_module()
    orphelines = []
    for nom in _public_functions():
        if nom in internes:
            continue
        if nom not in _referenced_in_production():
            orphelines.append(nom)
    assert not orphelines, (
        f"fonction(s) publique(s) de la rétention sans aucun appelant hors de leur "
        f"propre module : {orphelines}.\n\n"
        "Une fonction écrite et jamais appelée ne ferme pas la classe qu'elle vise : "
        "elle la déplace d'un cran. `telemetry_retention.py` existe pour fermer "
        "« déclaré en commentaire, appliqué par personne » — l'y remplacer par "
        "« écrit dans un module que personne n'appelle » ne change rien pour la "
        "production.\n"
        "Soit la brancher, soit la retirer ; les deux sont des réponses, l'écrire "
        "n'en est pas une.")
