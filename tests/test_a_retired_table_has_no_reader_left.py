"""Une table retirée au profit d'une vue or n'a plus AUCUN lecteur.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/**, src/api/**, src/utils/**, airflow/dags/**,
            src/dashboard/utils/period_filter.py (_REPLACED_BY_GOLD)
Persists in: nothing

Le défaut, rapporté par l'artiste le 2026-09-21
-----------------------------------------------
« J'avais pourtant download les derniers csv de apple music mais j'ai l'info
"Aucune mesure Apple Music sur cette période. La dernière remonte au
2025-12-11". »

Il avait raison, et le message aussi : ils parlaient de DEUX TABLES.

    apple_songs_history      2 relevés · 2025-11-29 → 2025-12-11
    apple_songs_performance  1 relevé  · 2026-06-08          ← ses imports

L'import CSV écrit la seconde. **Rien n'écrivait la première** — déclarée,
autorisée, lue par TROIS surfaces (la croissance de la page Apple, le graphe du
PDF client, la fraîcheur de la page admin), alimentée par personne.

Classe : `a-table-that-is-read-and-no-longer-written`. Elle ne lève jamais et
n'échoue jamais : une table sans nouvelle ligne se lit comme « pas encore de
données ». Ici elle se lisait comme « ton import n'est pas arrivé ».

Ce que ce garde tient, et ce qu'il ne tient PAS
------------------------------------------------
Il tient : une table inscrite dans `_REPLACED_BY_GOLD` — la liste des tables
retirées, chacune avec sa vue de remplacement et SA raison — n'est plus lue nulle
part dans le code de production.

Il ne tient PAS la question générale « quelles tables sont lues sans être
écrites ? ». Un balayage l'a tentée le 2026-09-21 et a rendu **13 candidates** ;
en les ouvrant, la plupart sont écrites par un chemin que le prédicat ne voit pas
(`upsert_many` avec un nom de table en VARIABLE, un `INSERT` construit sur
plusieurs lignes, un module de schéma exclu du balayage). **Ce nombre n'est donc
pas publié comme un résultat** — règle 20 : un balayage qui n'a pas été muté dans
les deux sens ne rend pas un compte, il rend une piste. La seule instance
VÉRIFIÉE, ligne par ligne, est Apple.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Le code de PRODUCTION. Les modules de schéma déclarent les tables (c'est leur
# métier) et les outils d'audit les inspectent : ni les uns ni les autres ne sont
# des lecteurs au sens du produit.
_PROD = [
    *(_ROOT / "src" / "dashboard").rglob("*.py"),
    *(_ROOT / "src" / "api").rglob("*.py"),
    *(_ROOT / "src" / "utils").rglob("*.py"),
    *(_ROOT / "src" / "collectors").rglob("*.py"),
    *(_ROOT / "src" / "transformers").rglob("*.py"),
    *(_ROOT / "airflow" / "dags").glob("*.py"),
]


# ⚠️ CE N'EST PAS `_REPLACED_BY_GOLD`, et la première version de ce fichier
# faisait l'erreur — elle a rougi en nommant treize lecteurs parfaitement
# légitimes de `s4a_song_timeline`.
#
# Les deux listes disent des choses DIFFÉRENTES :
#   · `_REPLACED_BY_GOLD` = « ne peut pas être BORNÉE par le sélecteur de
#     période », parce que son étendue inclurait la ligne « Total ». La table
#     reste parfaitement lisible ailleurs, avec son filtre.
#   · celle-ci = « plus AUCUN chemin ne l'écrit ». La lire, c'est lire un gel.
#
# Confondre les deux, c'est interdire une lecture saine et laisser passer la
# morte. Une seule table est ici, et elle a été vérifiée ligne par ligne.
_DEAD_TABLES = {
    "apple_songs_history": (
        "v_apple_song_cumulative",
        "plus RIEN ne l'écrit — l'import CSV alimente `apple_songs_performance` "
        "(`utils/csv_platforms.py`). Vérifié sur tout l'arbre le 2026-09-21 : "
        "déclarée, autorisée, lue par trois surfaces, alimentée par personne. Un "
        "artiste a lu « la dernière mesure remonte au 2025-12-11 » le jour où il "
        "déposait un export"),
}


# LA SEULE SURFACE QUI A LE DROIT DE LIRE UNE TABLE MORTE, et c'est par
# définition : un invariant confronte la vue or à SES SOURCES BRUTES. Lui
# interdire de lire la table d'héritage reviendrait à interdire la mesure qui
# prouve que la vue ne l'a pas perdue.
#
# ⚠️ L'exemption est NOMINATIVE et porte sa raison. Le dépôt a mesuré le
# 2026-09-21 ce que coûte une exemption plus large que son motif : celle de
# `test_a_song_join_normalises_both_sides` couvrait un FICHIER pour une raison
# qui ne valait que pour UNE requête, et la seconde requête du même fichier —
# défectueuse — passait sans avoir jamais été examinée.
_RECONCILIATION = {"src/utils/gold_invariants.py"}


def _retired() -> dict:
    return _DEAD_TABLES


def _sql_literals(path: pathlib.Path) -> list[str]:
    """Les chaînes du module, docstrings EXCLUES — f-strings recousues.

    ⚠️ Par l'AST et jamais par le texte. Ce dépôt a pris quatre gardes textuels
    verts sur leur propre commentaire, et DEUX rouges sur leur propre docstring
    le 2026-09-21. Le nom d'une table retirée DOIT pouvoir être écrit en prose —
    c'est même là qu'on explique pourquoi elle l'a été.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:                      # pragma: no cover
        return []
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = getattr(n, "body", None)
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                docs.add(id(corps[0].value))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            out.append("".join(v.value for v in n.values
                               if isinstance(v, ast.Constant) and isinstance(v.value, str)))
    return out


def _reads(sql: str, table: str) -> bool:
    return re.search(rf"\b(?:FROM|JOIN)\s+{re.escape(table)}\b", sql, re.I) is not None


@pytest.mark.parametrize("table", sorted(_retired()))
def test_no_production_surface_reads_a_retired_table(table: str) -> None:
    remplacement, pourquoi = _retired()[table]
    coupables = []
    for p in _PROD:
        if "__pycache__" in str(p) or str(p.relative_to(_ROOT)) in _RECONCILIATION:
            continue
        for lit in _sql_literals(p):
            if _reads(lit, table):
                coupables.append(f"{p.relative_to(_ROOT)} : {' '.join(lit.split())[:80]}")
                break
    assert not coupables, (
        f"'{table}' est retirée ({pourquoi}) et reste LUE :\n  "
        + "\n  ".join(coupables)
        + f"\nUtilise '{remplacement}'. Une table qu'on lit sans l'écrire ne lève "
          "jamais : elle rend « pas encore de données » à un artiste qui vient "
          "justement d'importer.")


def test_the_detector_sees_a_read_when_there_is_one() -> None:
    """NON-VACUITÉ. Sans elle, le test passerait aussi sur un prédicat mort."""
    assert _reads("SELECT x FROM apple_songs_history WHERE y", "apple_songs_history")
    assert _reads("... JOIN s4a_song_timeline s ON ...", "s4a_song_timeline")
    assert not _reads("SELECT x FROM v_apple_song_cumulative", "apple_songs_history")


def test_the_detector_ignores_a_table_named_in_a_docstring(tmp_path) -> None:
    """Et la prose qui EXPLIQUE le retrait ne doit pas le déclencher."""
    sonde = tmp_path / "_probe_retired_table.py"  # tmp_path, never the real tree: a probe written there races the tree's scanners under xdist (2026-09-26)
    sonde.write_text(
        'def f():\n'
        '    """On ne lit plus FROM apple_songs_history ici."""\n'
        '    # ni FROM s4a_song_timeline\n'
        '    return "SELECT day FROM v_apple_song_cumulative"\n', encoding="utf-8")
    try:
        lits = _sql_literals(sonde)
        assert not any(_reads(x, "apple_songs_history") for x in lits), lits
        assert any(_reads(x, "v_apple_song_cumulative") for x in lits), lits
    finally:
        sonde.unlink()


def test_every_dead_table_names_a_replacement_and_a_reason() -> None:
    """Une interdiction sans remplacement NOMMÉ se fait contourner."""
    morts = _retired()
    assert morts, "`_DEAD_TABLES` est vide : ce garde ne mesure plus rien"
    for table, (remplacement, pourquoi) in morts.items():
        assert remplacement, f"{table} est interdite sans remplacement nommé"
        assert pourquoi and len(pourquoi) > 30, (
            f"{table} est déclarée morte sans la preuve : « {pourquoi} ». Une "
            "table est morte parce qu'on a CHERCHÉ son écrivain et n'en a trouvé "
            "aucun — la raison doit le dire, pas l'affirmer.")


def test_the_dead_table_really_has_no_writer() -> None:
    """NON-VACUITÉ DE LA PRÉMISSE. Le garde repose sur « rien ne l'écrit » ;
    si un écrivain revenait, l'interdiction de lecture deviendrait un contresens.

    Les quatre formes d'écriture de ce dépôt sont cherchées : SQL littéral,
    `upsert_many('<table>')`, et le nom porté comme valeur d'une clé `table`
    dans un dictionnaire de configuration (`utils/csv_platforms.py`).
    """
    formes = [
        # ⚠️ `{t}`, PAS `{{t}}`. Écrit `{{t}}`, `.format()` le rend
        # littéralement `{t}` et le motif ne contient jamais le nom de la
        # table : la mutation « un écrivain revient » est restée VERTE au
        # premier jet, le 2026-09-21. Un garde dont le motif ne nomme pas
        # son sujet ne garde rien.
        r"\b(?:INSERT\s+INTO|UPDATE)\s+{t}\b",
        r"upsert_many\s*\(\s*['\"]{t}['\"]",
        r"['\"]table(?:_name)?['\"]\s*:\s*['\"]{t}['\"]",
    ]
    for table in _retired():
        ecrivains = []
        for p in _PROD:
            if "__pycache__" in str(p):
                continue
            raw = p.read_text(encoding="utf-8", errors="ignore")
            blob = " ".join(_sql_literals(p))
            for motif in formes:
                m = motif.format(t=re.escape(table))
                if re.search(m, blob, re.I) or re.search(m, raw, re.I):
                    ecrivains.append(str(p.relative_to(_ROOT)))
                    break
        assert not ecrivains, (
            f"'{table}' est déclarée MORTE mais quelque chose l'écrit de nouveau : "
            f"{ecrivains}. Si un chemin l'alimente, la bonne réponse est de la "
            "retirer de `_DEAD_TABLES` — pas de continuer à en interdire la lecture.")
