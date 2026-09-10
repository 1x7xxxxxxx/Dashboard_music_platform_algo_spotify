"""Le danger de cette zone n'est pas de laisser une date tranquille, c'est de la « corriger ».

Type: Test
Uses: pytest, ast
Depends on: src/utils/clocks.py, src/dashboard/utils/, src/api/, airflow/dags/
Persists in: nothing

La septième cause, et ce que la mesure en a fait
------------------------------------------------
L'audit du 2026-09-10 a nommé sept causes. Six corrigées le jour même. La septième —
« aucune horloge n'est déclarée » — n'est pas un défaut mais une ABSENCE : quatre
horloges cohabitent sur le même axe (notre collecte en UTC, le jour de reporting de
Spotify, la période lue dans un nom de fichier Apple, les bornes choisies par le
lecteur) et rien ne disait laquelle avait produit une date donnée.

**La mesure a réduit le chantier et retourné le risque.** Comptés en production :

| Ère | Lignes qui changent de jour selon le fuseau |
|---|---|
| `collected_at` post-migration-019 (YouTube) | **0 sur 5 807** — les collectes atterrissent à 10 h UTC |
| toutes plateformes, post-019 | **29** au total, toutes déclenchées à la main tard dans la journée |
| pré-019 | 267 — mais ce sont des `DATE`, un jour calendaire, pas un instant |

J'avais écrit « 200 lignes, 7,9 % » dans le catalogue : ce chiffre mélangeait les deux
ères sur une base locale. Le chiffre juste est ci-dessus, et il change la conclusion.

Ce que ce fichier garde
-----------------------
Pas « convertis tes dates » — l'inverse. Une date qui vient d'un ÉDITEUR (colonne d'un
CSV, période lue dans un nom de fichier) est un jour calendaire : il n'y a pas d'instant
à réinterpréter. Lui appliquer une conversion de fuseau déplacerait 267 jours déjà
justes d'une journée entière, en croyant les réparer. C'est le seul chemin connu pour
casser cette zone, et c'est celui qu'une prochaine « harmonisation des fuseaux »
prendrait naturellement.

Le garde tient donc trois propriétés : les horloges sont DÉCLARÉES, l'écart
irréconciliable est NOMMÉ plutôt qu'effacé, et aucune surface ne convertit une date
qui n'est pas un instant.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import pytest

from src.utils.clocks import (COLUMN_CLOCK, UNRECONCILABLE_NOTE, Clock, clock_of,
                              is_convertible)

ROOT = Path(__file__).resolve().parents[1]

# Les colonnes de date que l'application manipule, relevées en production le
# 2026-09-10. Chacune doit avoir une horloge déclarée — c'est la cause (G) elle-même.
DATE_COLUMNS_IN_PRODUCTION = (
    "collected_at", "date", "day_date", "line_date", "period_end", "period_start",
    "prediction_date", "published_at", "release_date", "reporting_date",
    "run_date", "snapshot_date",
)


@lru_cache(maxsize=64)
def _read(rel: str) -> str:
    """Lu à l'appel, pas à l'import — un test doit rester collectable sans sa cible."""
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("column", DATE_COLUMNS_IN_PRODUCTION)
def test_every_date_column_declares_its_clock(column) -> None:
    """La cause (G) : une date qui circule sans dire d'où elle vient."""
    assert clock_of(column) is not None, (
        f"`{column}` existe en production et n'a pas d'horloge déclarée. Tant qu'une "
        "date circule sans dire laquelle des quatre horloges l'a produite, aucune "
        "comparaison de période n'est vérifiable — c'est la septième cause de l'audit "
        "du 2026-09-10, et la déclaration EST le correctif.")


def test_only_our_own_timestamps_are_convertible() -> None:
    """Un jour calendaire lu chez un éditeur n'est pas un instant."""
    assert is_convertible("collected_at"), (
        "nos propres horodatages sont des instants UTC : eux se convertissent")
    for column in ("date", "period_start", "period_end", "reporting_date",
                   "release_date", "published_at", "line_date"):
        assert not is_convertible(column), (
            f"`{column}` est déclarée convertible alors qu'elle porte un JOUR "
            "CALENDAIRE lu chez un éditeur. La convertir déplacerait des jours déjà "
            "justes — mesuré : 267 lignes pré-019 partiraient d'une journée entière.")


def test_no_surface_converts_a_publisher_date_through_a_timezone() -> None:
    """Le seul chemin connu pour casser cette zone : « harmoniser » les fuseaux."""
    publisher_cols = {c for c, k in COLUMN_CLOCK.items() if k != Clock.OURS}
    offenders = []
    for base in ("src", "airflow"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            if rel.endswith("clocks.py") or "/tests/" in rel:
                continue
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            docs = {id(p.body[0].value) for p in ast.walk(tree)
                    if isinstance(p, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))
                    and p.body and isinstance(p.body[0], ast.Expr)
                    and isinstance(p.body[0].value, ast.Constant)
                    and isinstance(p.body[0].value.value, str)}
            for node in ast.walk(tree):
                # Une chaîne SQL qui convertit le fuseau d'une colonne d'éditeur.
                if not (isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and id(node) not in docs):
                    continue
                sql = node.value
                if "AT TIME ZONE" not in sql.upper():
                    continue
                hit = sorted(c for c in publisher_cols if c in sql)
                if hit:
                    offenders.append(f"{rel}:{node.lineno} → {hit}")
    assert not offenders, (
        "une conversion de fuseau est appliquée à une date d'éditeur, qui est un jour "
        "calendaire et non un instant : elle déplacerait des jours déjà justes d'une "
        f"journée entière. {offenders}")


def test_the_gap_we_cannot_close_is_named_rather_than_erased() -> None:
    """Nommer ce qu'on ne peut pas corriger fait partie du correctif."""
    assert "Spotify" in UNRECONCILABLE_NOTE and "Apple" in UNRECONCILABLE_NOTE, (
        "la note qui nomme l'écart irréconciliable a perdu les deux sources "
        "concernées — un écart anonyme se lit comme une erreur de notre côté")
    assert "corrigeable" in UNRECONCILABLE_NOTE, (
        "la note doit dire que l'écart n'est PAS corrigeable, sinon elle se lit comme "
        "une tâche en attente au lieu d'une propriété du monde")


def test_the_measurement_clock_is_not_the_display_clock() -> None:
    """Un jour de mesure ne dépend pas du poste qui l'affiche."""
    from src.utils.clocks import DISPLAY_TZ, MEASUREMENT_TZ
    assert MEASUREMENT_TZ == "UTC", (
        "le jour de mesure a quitté UTC : les collecteurs écrivent "
        "`datetime.now(timezone.utc)`, donc tout autre choix rend les jours de "
        "mesure dépendants de la machine qui affiche")
    assert MEASUREMENT_TZ != DISPLAY_TZ, (
        "confondre l'horloge de MESURE et celle d'AFFICHAGE est exactement la faute "
        "que cette séparation existe pour empêcher")
