"""Une fenêtre appliquée ne suffit pas — elle doit porter sur la bonne date.

Type: Test
Uses: pytest, ast
Depends on: src/utils/clocks.py, src/dashboard/views/
Persists in: nothing

Le trou que ce fichier ferme (2026-09-10)
-----------------------------------------
Un garde posé le matin vérifie que toute requête sous un sélecteur reprend sa fenêtre.
Il ne dit rien de **sur quoi** elle porte, et j'avais écrit que ce jugement n'était pas
mécanisable. C'était faux, et l'inventaire l'a montré : **13 sites de bornage, six
colonnes distinctes, dont UNE SEULE est une date de publication.**

Le cas qui a fait naître ce garde : Instagram bornait « Engagement par mois » sur
`timestamp`, la date de PUBLICATION du post, alors que `like_count` est un compteur
cumulé lu aujourd'hui. La barre de janvier portait les likes donnés en juin à un post
de janvier. La fenêtre était appliquée — sur la mauvaise chose — et tous les gardes
existants passaient au vert, parce qu'ils demandaient *que* la fenêtre soit appliquée,
jamais *sur quoi*.

Ce que ce garde exige
---------------------
Il n'interdit pas de borner sur une date de sortie : c'est un regroupement légitime, et
souvent le seul possible — Instagram ne nous donne qu'un compteur courant par post, il
n'existe aucun flux mensuel à calculer. Ce qu'il exige, c'est que la figure le DISE.
« Likes acquis à ce jour, par mois de publication » et « Engagement par mois » ne
décrivent pas la même chose, et seul le second se lit comme un flux.

Le sujet de chaque colonne est déclaré une fois, dans `src/utils/clocks.py`, à côté de
l'horloge qui l'a produite — deux questions différentes sur la même colonne, et il
fallait les deux.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from src.utils.clocks import COLUMN_SUBJECT, Dates, is_cohort_column, subject_of

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

_MAKERS = {"smart_period_filter", "period_filter", "entity_period_filter"}

# Les mots qui annoncent une lecture par cohorte au lecteur. Il en faut UN dans les
# textes de la vue qui borne sur une date de sortie.
_COHORT_WORDS = ("publication", "publié", "publiés", "sortie", "cohorte",
                 "acquis à ce jour", "published", "cohort")


@lru_cache(maxsize=32)
def _user_facing_strings(rel: str) -> tuple[str, ...]:
    """Les chaînes que l'artiste LIT : défauts de `t()`, titres, légendes.

    Un commentaire ou un docstring n'annonce rien à personne. Seul ce qui atteint
    l'écran peut dire au lecteur que la figure regroupe par date de sortie.
    """
    tree = ast.parse((VIEWS / rel).read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "t":
            # `t("clé", "défaut")` — le défaut est le texte français affiché.
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.append(arg.value)
        elif name in ("caption", "header", "subheader", "markdown", "info",
                      "warning", "write", "title"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.append(arg.value)
        for kw in node.keywords:
            if kw.arg in ("title", "labels", "yaxis_title", "xaxis_title"):
                for c in ast.walk(kw.value):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        out.append(c.value)
    return tuple(out)


@lru_cache(maxsize=1)
def _bindings() -> list[tuple[str, str, int]]:
    """(fichier, colonne bornée, ligne) pour chaque sélecteur de période."""
    out = []
    for path in sorted(VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            cols: list[str] = []
            if name in _MAKERS:
                for kw in node.keywords:
                    if kw.arg == "date_column" and isinstance(kw.value, ast.Constant):
                        cols.append(kw.value.value)
                # `EntitySpec(table, entity, date_column, …)` — 3ᵉ position.
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    if (isinstance(arg, ast.Call)
                            and getattr(arg.func, "id", None) == "EntitySpec"
                            and len(arg.args) >= 3
                            and isinstance(arg.args[2], ast.Constant)):
                        cols.append(arg.args[2].value)
            elif name == "sql_between" and node.args:
                if isinstance(node.args[0], ast.Constant):
                    cols.append(node.args[0].value)
            for c in cols:
                out.append((str(path.relative_to(VIEWS)), c, node.lineno))
    return out


def test_every_bound_column_declares_what_it_dates() -> None:
    """Une colonne dont on ignore le sujet ne peut pas être jugée."""
    undeclared = sorted({c for _f, c, _ln in _bindings() if subject_of(c) is None})
    assert not undeclared, (
        f"ces colonnes bornent une figure sans que `COLUMN_SUBJECT` dise de quoi elles "
        f"sont la date : {undeclared}. Tant qu'on l'ignore, on ne peut pas dire si la "
        "figure répond à ce qu'elle annonce — c'est le trou par lequel « Engagement "
        "par mois » est passé.")


def test_a_cohort_bound_figure_says_so() -> None:
    """Borner sur une date de SORTIE est légitime — le taire ne l'est pas."""
    offenders = []
    for f, col, lineno in _bindings():
        if not is_cohort_column(col):
            continue
        # Dans un texte VU PAR L'ARTISTE, pas n'importe où dans le fichier.
        #
        # La première version cherchait le mot dans tout le source : un commentaire
        # expliquant le correctif suffisait alors à satisfaire le garde, et une
        # mutation qui retirait l'annonce de l'ÉCRAN restait verte. C'est la même
        # faiblesse que « une mention vaut un bornage », trouvée le même jour — et
        # c'est la sixième fois que ce dépôt mesure qu'un garde textuel se satisfait
        # de sa propre documentation.
        if not any(w in txt.lower() for txt in _user_facing_strings(f)
                   for w in _COHORT_WORDS):
            offenders.append(f"{f}:{lineno} borne sur `{col}`")
    assert not offenders, (
        f"{offenders} : la fenêtre porte sur une date de PUBLICATION, donc la figure "
        "regroupe par cohorte de sortie et non par période d'activité. C'est une "
        "lecture valable — souvent la seule possible — mais elle doit être annoncée. "
        "« Engagement par mois » se lit comme un flux ; « likes acquis à ce jour, par "
        "mois de publication » dit ce qui est réellement montré.")


def test_the_inventory_is_not_empty() -> None:
    """Non-vacuité : sans sites, les deux contrôles ci-dessus sont vrais de rien."""
    b = _bindings()
    assert len(b) >= 10, (
        f"seulement {len(b)} bornage(s) trouvé(s) — il y en avait 13 le 2026-09-10. "
        "L'extraction vise à côté, et les deux contrôles passent sur du vide.")
    assert {c for _f, c, _ln in b} >= {"date", "collected_at", "timestamp"}, (
        "les trois familles de colonne — événement, mesure, publication — ne sont plus "
        "toutes représentées ; le garde ne prouve plus qu'il sait les distinguer.")


def test_the_three_subjects_are_actually_distinguished() -> None:
    """Un prédicat qui rendrait tout `event` satisferait le contrôle sans rien voir."""
    kinds = set(COLUMN_SUBJECT.values())
    assert kinds == {Dates.EVENT, Dates.MEASUREMENT, Dates.PUBLICATION}, (
        f"les trois sujets ne sont plus tous déclarés : {sorted(kinds)}")
    assert is_cohort_column("timestamp") and not is_cohort_column("date"), (
        "la distinction publication / événement s'est effondrée — c'est elle, et elle "
        "seule, qui distingue une cohorte d'un flux")
