"""Une fenêtre de temps incalculable n'affiche rien — jamais le total.

Type: Test
Uses: pandas, unittest.mock
Depends on: src/dashboard/utils/airflow_monitor.py
Persists in: nothing

Trouvé le 2026-09-17 en TRIANT les candidats de la signature heuristique de
`naive-datetime-now` — c'est-à-dire en faisant le balayage de frères, pas en lisant
un rapport.

Deux défauts empilés, chacun inoffensif seul :

1. `airflow_monitor.py` posait `start = datetime.now()` — NAÏF — dans la branche d'un
   run sans `start_date` (file d'attente, run planifié), alors que la branche voisine
   pose `datetime.now(start.tzinfo)` — TZ-AWARE. La colonne `start_date` devenait donc
   MIXTE dès qu'un seul run n'avait pas démarré.
2. La comparaison `df['start_date'] >= last_24h` lève alors
   `TypeError: can't compare offset-naive and offset-aware datetimes`, et le repli
   était `except Exception: df_24h = df` — **le DataFrame ENTIER**. Tout l'historique
   se présentait comme « dernières 24 h », sur une tuile qu'un humain lit comme un
   verdict.

Reproduit avant correctif : 2 lignes rendues pour une fenêtre qui en contenait 1.

La propriété gardée ici est celle de la SORTIE, pas du mécanisme : quand la fenêtre
ne peut pas être calculée, le résultat est VIDE. Un repli qui rend le total est pire
que pas de repli — il fabrique un chiffre.

Mutation record — 2026-09-17, deux mutations, deux vues ROUGES :
  1. `df_24h = df` dans le `except`            → rouge (le repli rend le total).
  2. `start = datetime.now()` (naïf) en ligne  → rouge (la colonne redevient mixte).

---
rex: []
---
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _mixed_frame() -> pd.DataFrame:
    """Un run démarré (tz-aware) et un run en attente — la colonne exacte du défaut."""
    return pd.DataFrame({
        "start_date": [datetime.now(timezone.utc) - timedelta(hours=1),
                       datetime(2020, 1, 1)],
        "state": ["success", "queued"],
    })


def test_a_mixed_column_makes_the_comparison_raise() -> None:
    """La prémisse du défaut, exécutée — sinon le reste du fichier ne prouve rien."""
    df = _mixed_frame()
    last_24h = datetime.now(df["start_date"].iloc[0].tzinfo) - timedelta(hours=24)
    try:
        _ = df[df["start_date"] >= last_24h]
    except TypeError:
        return
    raise AssertionError(
        "pandas ne lève plus sur une colonne mixte — la prémisse de ce garde a changé, "
        "relire le repli de `airflow_monitor` avant de supprimer ce test")


def test_the_module_never_builds_a_naive_start_date() -> None:
    """La CAUSE : aucun `datetime.now()` nu ne nourrit `start_date`."""
    import ast

    source = (_ROOT / "src" / "dashboard" / "utils" / "airflow_monitor.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    nus = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if getattr(func, "attr", "") != "now":
            continue
        if getattr(getattr(func, "value", None), "id", "") != "datetime":
            continue
        if not node.args and not node.keywords:
            nus.append(node.lineno)
    assert not nus, (
        f"`datetime.now()` NAÏF aux lignes {nus} de airflow_monitor.py — il rend la "
        "colonne `start_date` mixte, et la comparaison 24 h lève. "
        "Remède : `datetime.now(timezone.utc)`")


def test_an_uncomputable_window_is_empty_not_the_whole_history() -> None:
    """La CONSÉQUENCE : le repli rend vide, jamais le total.

    Lu à l'AST plutôt qu'exécuté : la fonction fait des appels HTTP à Airflow, et la
    frontière réseau du `conftest` refuse — à raison — de les laisser partir.
    """
    import ast

    source = (_ROOT / "src" / "dashboard" / "utils" / "airflow_monitor.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    fautifs = []
    for handler in [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]:
        for node in ast.walk(handler):
            if (isinstance(node, ast.Assign)
                    and any(getattr(t, "id", "") == "df_24h" for t in node.targets)
                    and getattr(node.value, "id", "") == "df"):
                fautifs.append(node.lineno)
    assert not fautifs, (
        f"ligne {fautifs} : le repli rend `df` ENTIER, donc tout l'historique passe "
        "pour « dernières 24 h ». Un repli qui fabrique un chiffre est pire que pas "
        "de repli — rendre `df.iloc[0:0]` et le journaliser.")
