"""Personne ne redéclare la colonne d'une table que le registre connaît déjà.

Type: Guard
Uses: src.utils.source_registry et les surfaces qui la lisent
Persists in: nothing

CINQ listes des mêmes tables, et j'ai arrêté le balayage à deux
---------------------------------------------------------------
Le matin du 2026-09-22 j'ai unifié deux registres de sources — la grille de l'accueil
et l'alerte nocturne — parce qu'iMusician n'était que dans l'un et pouvait se périmer
sans qu'aucune alerte ne le dise. **Je n'ai pas balayé.** La règle transverse 14 de ce
dépôt dit de chercher les frères AVANT d'écrire le correctif ; l'après-midi en a trouvé
deux de plus :

    src/dashboard/views/db_health.py     `_DATASETS`, 11 entrées écrites à la main
    src/dashboard/views/admin.py         `_supervision_freshness`, HUIT requêtes
                                         `SELECT MAX(...)` composées sur place

Les deux s'accordaient avec le registre au moment de la mesure. C'est exactement la
forme d'un défaut latent : une copie ne devient fausse qu'au premier changement, et
personne ne relit cinq listes pour vérifier qu'elles disent la même chose.

Ce que ce garde exige, et ce qu'il n'exige PAS
----------------------------------------------
Il n'exige pas une liste unique. `db_health` suit des JEUX DE DONNÉES — « cet import
grossit-il » — là où le registre suit des PLATEFORMES — « celle-ci livre-t-elle ». Les
deux questions ont des granularités différentes, et `s4a_audience`, les ventes
iMusician ou la popularité des titres n'ont rien à faire dans un registre de
plateformes.

Il exige que **là où deux surfaces parlent de la MÊME table, elles ne s'inventent pas
une troisième colonne.** Le registre en déclare deux par table, et chacune répond à une
question précise :

    `col`         la date d'ÉCRITURE — quand la ligne a été posée
    `metric_col`  la date de MESURE — de quand la donnée parle

⚠️ CE QUE CE GARDE N'ATTRAPE PAS, et je l'ai découvert en le mutant.

Il refuse une TROISIÈME colonne. Il ne refuse PAS de lire la date d'écriture là où il
faudrait celle de mesure — les deux sont permises par construction, parce que
`db_health` a besoin de la date d'écriture pour dire « cet import grossit-il ».

Remplacer la colonne de mesure par `collected_at` dans `admin._supervision_freshness`
laisse donc ce garde VERT, alors que c'est exactement le défaut des 718 jours :
`meta_insights_performance_day` rend **2024-09-30** par sa date de mesure et « à jour »
par sa date d'écriture, parce que le DAG ré-écrit chaque matin des lignes de 2024. Meta
était mort depuis six semaines derrière un feu vert.

La première version de cette docstring affirmait couvrir ce cas. Un garde dont la prose
promet plus que son prédicat est pire qu'un garde absent : on cesse de vérifier. Le
test `test_a_freshness_surface_reads_the_measurement_date` ci-dessous couvre le cas
manquant, et il est étroit à dessein — une fonction dont le métier EST la fraîcheur.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from src.utils.source_registry import PAR_CLE, SOURCES

#: ⚠️ `[a-z0-9_]+` ET NON `[a-z_]+`. Le premier jet omettait les chiffres, donc il
#: ratait `s4a_song_timeline` — la table la plus lue du dépôt — en ne capturant que
#: le « s ». C'est le test de non-vacuité ci-dessous qui l'a attrapé : le prédicat
#: aurait été vert sur tout, y compris sur le défaut qu'il existe pour voir.
_SQL_MAX = re.compile(r"(?:MAX|MIN)\(\s*([a-z0-9_]+)\s*\)[^;\"']*?FROM\s+([a-z0-9_]+)",
                      re.I)

_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Les colonnes que le registre autorise pour une table qu'il connaît : celle
#: d'écriture et celle de mesure. Une troisième est soit une faute de frappe, soit une
#: question qu'on n'a pas nommée.
_PAR_TABLE = {s.table: {s.col} | ({s.metric_col} if s.metric_col else set())
              for s in SOURCES}

#: Les surfaces qui déclarent des tables et des colonnes à la main. La liste est
#: explicite : un balayage de tout `src/` attraperait chaque requête du dépôt, et ce
#: garde parle des REGISTRES, pas des requêtes.
_SURFACES = (
    "src/dashboard/views/db_health.py",
    "src/dashboard/views/admin.py",
    "src/dashboard/utils/kpi_helpers.py",
    "src/utils/freshness_monitor.py",
)


def test_the_registry_declares_two_columns_for_at_least_one_table() -> None:
    """NON-VACUITÉ. Sans `metric_col` nulle part, ce fichier ne garde rien."""
    avec_mesure = [s.cle for s in SOURCES if s.metric_col]
    assert len(avec_mesure) >= 2, (
        f"seulement {avec_mesure} portent une colonne de mesure — la distinction que "
        "ce garde protège n'existe plus dans le registre.")


@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_invents_a_third_column_for_a_known_table(rel: str) -> None:
    """Une table du registre se lit par sa date d'écriture ou par celle de mesure.

    Le prédicat cherche les `SELECT ... FROM <table>` et les paires
    `"table": ..., "col": ...` d'un dictionnaire. Une troisième colonne signifie
    qu'une surface s'est fait sa propre idée de « quand cette donnée date ».
    """
    src = (_ROOT / rel).read_text(encoding="utf-8")
    fautes: list[str] = []

    # a) Les requêtes composées : `MAX(<col>) FROM <table>` ou `MIN(<col>)`.
    for m in _SQL_MAX.finditer(src):
        col, table = m.group(1), m.group(2)
        permises = _PAR_TABLE.get(table)
        if permises and col not in permises:
            fautes.append(f"{table}.{col} (permises : {sorted(permises)})")

    # b) Les registres en dictionnaire : une entrée qui porte `table` et `col`.
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Dict):
            continue
        d = {k.value: v.value for k, v in zip(n.keys, n.values)
             if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
        table, col = d.get("table"), d.get("col") or d.get("ts_col")
        permises = _PAR_TABLE.get(table) if table else None
        if permises and col and col not in permises:
            fautes.append(f"{table}.{col} (permises : {sorted(permises)})")

    assert not fautes, (
        f"`{rel}` lit une table du registre par une colonne qu'il ne déclare pas :\n"
        + "\n".join(f"    {f}" for f in fautes)
        + "\n\nLe registre en déclare DEUX par table — la date d'écriture et celle de "
          "mesure — et chacune répond à une question. Une troisième est soit une faute "
          "de frappe, soit une question qu'il faut nommer dans le registre. Confondre "
          "les deux premières a laissé Meta pour mort six semaines derrière un feu "
          "vert : 718 jours d'écart sur la même table.")


def test_the_predicate_would_catch_a_real_divergence() -> None:
    """NON-VACUITÉ du prédicat, sur la forme exacte qu'il doit refuser.

    Un prédicat qui ne matche rien laisse tout passer. On lui présente la requête
    fautive telle qu'elle s'écrirait, et on exige qu'il la voie.
    """
    table = next(s.table for s in SOURCES if s.metric_col)
    faux = f"SELECT MAX(inventee) FROM {table}"
    trouve = [m.groups() for m in _SQL_MAX.finditer(faux)]
    assert trouve == [("inventee", table)], (
        f"le prédicat ne voit pas « {faux} » — il ne garde donc rien.")
    assert "inventee" not in _PAR_TABLE[table], (
        "la colonne inventée est déclarée au registre : la démonstration ne prouve "
        "rien.")


def test_a_dataset_list_may_track_what_the_registry_does_not() -> None:
    """LA RÉCIPROQUE, et elle compte autant.

    Ce garde ne doit PAS pousser à tout ramener dans un registre unique.
    `db_health` suit `s4a_audience`, les ventes iMusician et la popularité des
    titres : des jeux de données, pas des plateformes. Les y faire entrer
    mélangerait « cette plateforme livre-t-elle » et « cet import grossit-il ».
    """
    from src.dashboard.views.db_health import _DATASETS

    propres = [d["table"] for d in _DATASETS if d["table"] not in _PAR_TABLE]
    assert propres, (
        "`db_health` ne suit plus aucune table hors du registre : soit tout y a été "
        "ramené — et deux questions sont désormais mélangées — soit la liste a été "
        "vidée. Les deux méritent d'être relues.")
    assert set(d["table"] for d in _DATASETS) & set(_PAR_TABLE), (
        "`db_health` ne partage plus AUCUNE table avec le registre : le test de "
        "cohérence ci-dessus ne vérifie plus rien sur ce fichier.")


def test_a_freshness_surface_reads_the_measurement_date() -> None:
    """Une fonction dont le MÉTIER est la fraîcheur lit la date de MESURE.

    Étroit à dessein : `db_health` a besoin de la date d'écriture pour « cet import
    grossit-il », et le garde général permet donc les deux colonnes. Celui-ci ne
    vise que les surfaces dont le sujet est « de quand cette donnée date ».

    Par l'AST : la fonction doit APPELER `colonne_de_mesure`, pas la mentionner.
    """
    src = (_ROOT / "src" / "dashboard" / "views" / "admin.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "_supervision_freshness"), None)
    assert fn is not None, "`_supervision_freshness` a disparu d'`admin.py`"

    appelle = any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == "colonne_de_mesure"
             or getattr(n.func, "attr", None) == "colonne_de_mesure")
        for n in ast.walk(fn))
    assert appelle, (
        "`_supervision_freshness` ne demande plus la colonne de MESURE au registre. "
        "Elle lira la date d'écriture, et `meta_insights_performance_day` passera de "
        "« 722 jours de retard » à « à jour » alors que la dernière donnée réelle "
        "datera toujours de 2024 — 718 jours d'écart sur la même table.")
