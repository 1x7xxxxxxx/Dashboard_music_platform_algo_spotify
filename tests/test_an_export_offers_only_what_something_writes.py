"""Une case d'export ne propose pas une table que rien n'écrit.

Type: Test
Uses: ast
Depends on: src/dashboard/views/export_csv.py, src/dashboard/utils/csv_exporter.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-20 (R140 §16.10) : `export_csv.py:74,78` proposait à l'artiste de
cocher **Apple Music** et **YouTube playlists**, et `csv_exporter.py` en faisait des
onglets du ZIP. Trois tables — `apple_daily_plays`, `apple_listeners`,
`youtube_playlists` — portaient **0 ligne**, et **aucun chemin de code ne les écrit**.
Les deux parseurs Apple qui les produiraient (`apple_music_csv_parser.py:179` et `:221`)
n'ont **aucun appelant**.

**Un onglet vide dans un ZIP se lit comme une perte de données**, pas comme une absence
de source : l'artiste coche, attend, ouvre, et conclut que ses chiffres ont disparu.

⚠️ Le prédicat porte sur la PROPRIÉTÉ « quelque chose écrit-il cette table », pas sur
« la table est-elle vide ». Une table vide pour un artiste NEUF est normale ; une table
qu'aucun code n'alimente est vide pour tout le monde, et le restera.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_ARBRES = ("src", "airflow", "tools")
# Les QUATRE retirées le 2026-09-20. La dernière — `youtube_comments` — n'était PAS
# dans la liste de R140 §16.10 : elle a été trouvée par l'entonnoir de ce garde, qui a
# ramené 8 candidats, en a écarté 7 (des lignes existent, donc un écrivain sous une
# autre forme) et a confirmé celle-ci. Elle n'existe QUE comme schéma
# (`src/database/youtube_schema.py:133`) : la table est créée, jamais alimentée.
_RETIREES = {"apple_daily_plays", "apple_listeners", "youtube_playlists",
             "youtube_comments"}


def _tables_exportees() -> set[str]:
    """Les tables que le ZIP promet, lues à l'AST dans la liste des onglets."""
    arbre = ast.parse((ROOT / "src/dashboard/utils/csv_exporter.py").read_text(
        encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Tuple) and len(n.elts) == 3:
            premier = n.elts[0]
            if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
                out.add(premier.value)
    return out


def _tables_ecrites() -> set[str]:
    """Les tables qu'un chemin de code ÉCRIT réellement.

    Trois formes, et elles couvrent ce dépôt : `upsert_many('t', …)`,
    `insert_many('t', …)`, et un `INSERT INTO t` dans une chaîne SQL.
    """
    ecrites: set[str] = set()
    motif_sql = re.compile(r"INSERT\s+INTO\s+(\w+)", re.I)
    for arbre in _ARBRES:
        for f in (ROOT / arbre).rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            texte = f.read_text(encoding="utf-8", errors="replace")
            ecrites |= {m.group(1) for m in motif_sql.finditer(texte)}
            try:
                a = ast.parse(texte)
            except SyntaxError:
                continue
            for n in ast.walk(a):
                if (isinstance(n, ast.Call)
                        and getattr(n.func, "attr", "") in ("upsert_many", "insert_many")
                        and n.args and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str)):
                    ecrites.add(n.args[0].value)
    return ecrites


def test_the_export_list_is_not_empty() -> None:
    """Anti-vacuité : sans onglets lus, l'assertion suivante est vraie pour rien."""
    assert len(_tables_exportees()) >= 10, (
        f"seulement {len(_tables_exportees())} onglet(s) lus dans `csv_exporter` — le "
        "motif a raté sa cible et le garde n'affirme plus rien.")


def test_something_writes_every_table_the_export_offers() -> None:
    """LE GARDE. Une table proposée que rien n'alimente sera vide pour TOUT LE MONDE.

    ⚠️ **Le prédicat est un ENTONNOIR à deux étages, et le premier seul était faux.**
    Ma première version ne cherchait qu'un écrivain LITTÉRAL (`upsert_many('t', …)`,
    `INSERT INTO t`). Elle a signalé **8 tables**, dont `youtube_videos` (278 lignes),
    `meta_insights_performance_day` (231) et `hypeddit_daily_stats` (22) — toutes
    manifestement écrites, par un nom de table passé en VARIABLE. C'est la douzième fois
    cette semaine qu'un prédicat de ce dépôt attrape une FORME D'ÉCRITURE là où la classe
    parle d'une PROPRIÉTÉ.

    La propriété est « rien n'alimente cette table ». Les deux étages :

      1. **candidat** — aucun écrivain littéral trouvé dans `src/`, `airflow/`, `tools/` ;
      2. **confirmé** — et la table est VIDE dans la base joignable.

    Une table écrite par variable a des lignes : elle sort au second étage. Une table
    vide chez un artiste neuf mais alimentée ailleurs sort au premier. Les deux étages
    sont nécessaires, et aucun ne suffit.

    Entonnoir du 2026-09-20 : **8 candidats → 7 écartés** (lignes présentes, donc un
    écrivain existe sous une autre forme) → **1 site vivant** (`youtube_comments`), qui s'ajoute aux 3 déjà connus.
    """
    from src.database.postgres_handler import PostgresHandler
    candidats = sorted(_tables_exportees() - _tables_ecrites())
    if not candidats:
        return
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable — le second étage de l'entonnoir est impossible")
    try:
        vivants, ecartes = [], []
        for t in candidats:
            try:
                n = db.fetch_query(f"SELECT count(*) FROM {t}")[0][0]      # noqa: S608
            except Exception:                  # noqa: BLE001
                ecartes.append(f"{t} (illisible)")
                continue
            (vivants if n == 0 else ecartes).append(t if n == 0 else f"{t} ({n} lignes)")
    finally:
        db.close()
    assert not vivants, (
        "table(s) proposée(s) à l'export, sans écrivain littéral ET VIDES : "
        f"{vivants}\n"
        "  écartées au second étage (des lignes existent, donc un écrivain aussi) : "
        f"{ecartes}\n\n"
        "L'artiste coche, attend, ouvre un onglet vide, et conclut que ses données ont "
        "disparu. Soit rebrancher l'écrivain, soit retirer l'onglet — mais pas laisser "
        "une case qui promet ce que rien ne produit.")


def test_the_funnel_needs_both_stages() -> None:
    """AUTO-PREUVE : chaque étage doit écarter quelque chose que l'autre laisse passer.

    Sans cette vérification, un entonnoir dont un étage est devenu inerte passerait
    inaperçu — et ce serait soit 8 faux positifs, soit un garde qui n'attrape plus rien.
    """
    candidats = _tables_exportees() - _tables_ecrites()
    assert candidats, (
        "le PREMIER étage n'écarte plus rien : toutes les tables exportées ont un "
        "écrivain littéral. Si c'est vrai, tant mieux — mais vérifier que le scan "
        "fonctionne encore, car un motif cassé donne le même résultat.")


@pytest.mark.parametrize("table", sorted(_RETIREES))
def test_the_three_removed_tables_stay_out(table: str) -> None:
    """Les trois retirées le 2026-09-20 ne reviennent pas sans leur écrivain.

    Si un parseur est rebranché, ce test le dit : il passe de « reste dehors » à
    « quelqu'un l'écrit », et l'onglet peut revenir.
    """
    if table in _tables_ecrites():
        pytest.skip(f"`{table}` a un écrivain — l'onglet peut revenir dans l'export")
    assert table not in _tables_exportees(), (
        f"`{table}` est de retour dans l'export et rien ne l'écrit toujours. Elle "
        "portait 0 ligne le 2026-09-20, et ses parseurs n'avaient aucun appelant.")
