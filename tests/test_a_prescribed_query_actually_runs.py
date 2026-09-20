"""Une requête que l'admin copie-colle doit s'exécuter, et dire QUELLE question elle pose.

Type: Test
Uses: ast, la base joignable
Depends on: src/dashboard/views/useful_links.py, src/utils/freshness_monitor
Persists in: nothing

Pourquoi ce garde existe
------------------------
`useful_links` rend en `st.code` des commandes `psql` que l'admin copie-colle. Elles
étaient écrites à la main et prescrivaient `MAX(collected_at)` pour les SEPT sources,
sous le libellé « Dernière collecte », pendant qu'`admin.py:358` calculait la même chose
en lisant la date MÉTIER là où elle existe. Les colonnes divergeaient sur cinq
plateformes sur six.

⚠️ **Ce n'est pas une erreur, c'est une AMBIGUÏTÉ** : les deux colonnes répondent à deux
questions — « quand a-t-on écrit » et « de quand date la donnée ». Mesuré le 2026-09-20,
en direct : `meta_insights_performance_day` porte `collected_at = ce matin 05:00` et
`day_date = 2024-09-30`. **721 jours d'écart.** Le DAG tourne, ré-écrit les mêmes lignes
vieilles de deux ans, et toute sonde lisant l'horodatage d'écriture la déclare fraîche.
Les deux questions sont désormais posées, et étiquetées.

⚠️ **Et ce test EXÉCUTE les requêtes.** La première version dérivée du registre
produisait `SELECT MAX(date) FROM artists` — `tenant_metric_col` décrit la
`tenant_table`, pas `table`. Une relecture ne l'a pas vu ; l'exécution l'a nommé en une
seconde. Une requête qu'on prescrit à un humain doit avoir été lancée au moins une fois.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.freshness_monitor import MONITOR_TARGETS  # noqa: E402

_VUE = ROOT / "src" / "dashboard" / "views" / "useful_links.py"


def _requetes_prescrites() -> list[str]:
    """Les SELECT que la vue construit, reconstitués depuis le registre.

    La vue les dérive de `MONITOR_TARGETS` ; ce test refait la même dérivation et
    l'EXÉCUTE. Si la vue cesse de dériver, `test_the_view_derives_instead_of_listing`
    le dit.
    """
    out = []
    for cible in MONITOR_TARGETS:
        tbl, col = cible["table"], cible["col"]
        out.append(f"SELECT MAX({col}) FROM {tbl}")
        metric = cible.get("metric_col")
        if metric and metric != col:
            out.append(f"SELECT MAX({metric}) FROM {tbl}")
    return out


def _arbre() -> ast.Module:
    return ast.parse(_VUE.read_text(encoding="utf-8"))


def test_the_view_derives_instead_of_listing() -> None:
    """ANTI-VACUITÉ : si la vue réécrit une liste à la main, ce test ne garde plus rien.

    Lu à l'AST : `"MONITOR_TARGETS" in texte` serait satisfait par le commentaire qui
    explique pourquoi la vue dérive — le défaut exact que
    `test_a_guard_reads_structure_not_text` a mesuré trois fois le 2026-09-04.
    """
    importe = any(isinstance(n, ast.ImportFrom)
                  and any(a.name == "MONITOR_TARGETS" for a in n.names)
                  for n in ast.walk(_arbre()))
    assert importe, (
        "`useful_links` n'importe plus le registre — il a donc une TROISIÈME liste de "
        "colonnes à faire coïncider avec celles d'`admin.py` et de `freshness_monitor`.")


@pytest.mark.parametrize("sql", _requetes_prescrites())
def test_every_prescribed_query_runs(sql: str) -> None:
    """LE GARDE. Une requête donnée à un humain doit s'exécuter."""
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable")
    try:
        db.fetch_query(sql)
    except Exception as exc:                   # noqa: BLE001
        raise AssertionError(
            f"requête prescrite à l'admin qui échoue : {sql}\n  -> "
            f"{type(exc).__name__}. Elle est affichée en `st.code` pour être "
            "copiée-collée ; une colonne inexistante s'y lit comme une panne de la base."
        ) from exc
    finally:
        db.close()


def test_the_two_questions_are_labelled_differently() -> None:
    """Deux requêtes sous le même libellé, c'est l'ambiguïté qu'on vient de retirer.

    Les libellés sont lus dans les LITTÉRAUX du code, pas dans le texte du fichier :
    une prose qui parle de « dernière COLLECTE » ne prouve pas qu'un libellé la porte.
    """
    litteraux = {v.value for n in ast.walk(_arbre())
                 for v in ast.walk(n)
                 if isinstance(v, ast.Constant) and isinstance(v.value, str)}
    docstrings = {ast.get_docstring(n) for n in ast.walk(_arbre())
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))}
    litteraux -= {d for d in docstrings if d}
    assert any("dernière COLLECTE" in x for x in litteraux), (
        "aucun libellé ne dit « dernière COLLECTE » — la première question a disparu.")
    assert any("dernière DONNÉE" in x for x in litteraux), (
        "aucun libellé ne dit « dernière DONNÉE ». Sur Meta les deux diffèrent de "
        "721 jours ; les afficher sous le même mot fait lire l'une pour l'autre.")


def test_the_registry_column_belongs_to_the_table_it_names() -> None:
    """La confusion EXACTE que l'exécution a trouvée, figée.

    `tenant_metric_col` décrit la `tenant_table`, pas `table`. Les confondre produisait
    `SELECT MAX(date) FROM artists`, sur une table qui n'a pas cette colonne. Lu à
    l'AST : la vue ne doit lire QUE `metric_col`.
    """
    lus = {n.args[0].value for n in ast.walk(_arbre())
           if isinstance(n, ast.Call)
           and getattr(n.func, "attr", "") == "get"
           and n.args and isinstance(n.args[0], ast.Constant)
           and isinstance(n.args[0].value, str)}
    assert "tenant_metric_col" not in lus, (
        "la vue lit `tenant_metric_col`, dont la colonne appartient à une AUTRE table "
        "que celle qu'elle interroge — elle produirait `SELECT MAX(date) FROM artists`.")
    assert "metric_col" in lus, (
        "la vue ne lit plus `metric_col` : elle a cessé de poser la seconde question, "
        "celle qui vaut 721 jours sur Meta.")
