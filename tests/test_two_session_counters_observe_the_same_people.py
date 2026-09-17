"""Deux instruments qui annoncent « combien de gens à la fois » comptent les mêmes gens.

Type: Test
Uses: re, live Postgres (spotify_etl)
Depends on: tools/scale_check.sh, src/utils/daily_ops_metrics.py
Persists in: nothing

Le dépôt compte le pic de sessions par minute à DEUX endroits :

  · `tools/scale_check.sh` — le déclencheur nº 1 de la mise à l'échelle, celui qui
    décide s'il faut des répliques ;
  · `daily_ops_metrics._peak_sessions` — le résumé quotidien écrit en base.

Ils excluaient tous deux les canaris et le bac à sable, et s'arrêtaient là — sauf que
l'un faisait `LEFT JOIN saas_artists` et l'autre un `JOIN` interne. La jointure interne
jette **tout événement sans artiste correspondant**, c'est-à-dire les sessions d'AVANT
connexion (`artist_id` NULL). Ce n'était pas une intention : le docstring ne parlait que
du bac à sable. C'était un effet de bord de l'exclusion.

Mesuré le 2026-09-18 sur la base de développement :

  · **3 387 des 8 331 lignes (40 %)** de `usage_events` n'ont aucun artiste
    correspondant, dont **2 427** avec `artist_id` NULL ;
  · les deux formes divergent sur **1 244 des 2 028 minutes actives (61 %)** ;
  · écart maximal sur une seule minute : **10 sessions** ;
  · pic sur 24 h : **8** (JOIN interne) contre **10** (LEFT JOIN).

Le pic sur 180 jours coïncidait à 16 des deux côtés — par chance. Un chiffre qui
s'accorde n'est pas une preuve que les deux instruments observent la même chose.

Ce que ce garde vérifie
-----------------------
Non pas un NOMBRE gelé — il bougera — mais que les deux instruments rendent la même
valeur sur la même fenêtre, exécutés contre la même base. C'est la seule formulation
qui survive à la croissance du trafic.

Ce qu'il ne couvre PAS
----------------------
Les fenêtres, qui diffèrent VOLONTAIREMENT (180 jours pour le pic historique de la
mise à l'échelle, 24 h pour le résumé du jour) — on compare donc à fenêtre égale. Et
il ne dit pas laquelle des deux définitions est la bonne : il dit qu'il n'y en a
qu'une.

Mutation record — 2026-09-18, trois passes.
  1. Remettre `JOIN` au lieu de `LEFT JOIN` dans `_peak_sessions` : **rouge** (8 ≠ 10
     sur les données du jour).
  2. Écrire `JOIN saas_artists` dans le DOCSTRING tout en gardant le défaut dans le SQL :
     **rouge aussi** — la jointure est atteinte par l'AST puis lue dans le littéral SQL,
     donc la prose ne peut pas la satisfaire. C'est la correction demandée par
     `test_a_guard_reads_structure_not_text`, qui a refusé la première version de ce
     fichier : elle cherchait le motif dans le TEXTE du module Python.
  3. Aveugler l'extracteur : **rouge** sur l'anti-vacuité.

---
rex: []
---
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.db_gate import db_ready as _db_ready

_ROOT = Path(__file__).resolve().parents[1]
_SCALE = _ROOT / "tools" / "scale_check.sh"
_OPS = _ROOT / "src" / "utils" / "daily_ops_metrics.py"

pytestmark = pytest.mark.skipif(
    not _db_ready(),
    reason="No provisioned Postgres on 127.0.0.1:5433 — comparing two counters needs rows",
)

# La fenêtre commune. Les deux instruments en utilisent une DIFFÉRENTE dans la vraie
# vie, et c'est voulu ; on compare donc leur définition, pas leur horizon.
_WINDOW = "180 days"


def _join_in_sql(sql: str) -> str | None:
    """`LEFT JOIN` ou `JOIN` dans un texte SQL.

    Le SQL n'est pas du Python : on le lit donc par motif, et c'est légitime. Ce qui ne
    l'est pas, c'est de chercher ce motif dans un FICHIER Python — un commentaire ou un
    docstring y suffirait, et ce dépôt a pris quatre gardes au vert comme ça en une
    soirée. D'où les deux extracteurs ci-dessous : l'un passe par l'AST pour ATTEINDRE
    le littéral SQL, l'autre lit un `.sh`, que rien ne sait parser.
    """
    m = re.search(r"(LEFT\s+JOIN|JOIN)\s+saas_artists", sql, re.I)
    return re.sub(r"\s+", " ", m.group(1).upper()) if m else None


def _ops_join() -> str | None:
    """La jointure de `_peak_sessions`, atteinte par l'AST puis lue dans SON SQL."""
    tree = ast.parse(_OPS.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_peak_sessions"), None)
    if fn is None:
        return None
    for node in ast.walk(fn):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and "usage_events" in node.value):
            return _join_in_sql(node.value)
    return None


def _scale_join() -> str | None:
    """Celle de `scale_check.sh` — un script shell, qu'aucun analyseur ne parse."""
    return _join_in_sql(_SCALE.read_text(encoding="utf-8"))


def test_both_instruments_are_readable() -> None:
    """Anti-vacuité : sans les deux sources, la comparaison ne prouve rien."""
    assert _SCALE.is_file(), "`tools/scale_check.sh` a disparu — le déclencheur nº 1 de la mise à l'échelle."
    assert _OPS.is_file(), "`src/utils/daily_ops_metrics.py` a disparu."
    for nom, lu in (("scale_check.sh", _scale_join()), ("daily_ops_metrics.py", _ops_join())):
        assert lu is not None, (
            f"{nom} ne joint plus `saas_artists` : soit il a cessé d'exclure les "
            "canaris, soit ce garde lit la mauvaise requête.")


def test_the_two_counters_use_the_same_join() -> None:
    """La forme de jointure DÉCIDE qui est compté. Elle ne peut pas différer."""
    scale, ops = _scale_join(), _ops_join()
    assert scale == ops, (
        f"`scale_check.sh` fait `{scale}` et `daily_ops_metrics` fait `{ops}`.\n"
        "Un `JOIN` interne jette les sessions d'AVANT connexion (`artist_id` NULL) — "
        "40 % des lignes de `usage_events` le 2026-09-18 — alors qu'elles sont des "
        "humains et de la charge. Deux instruments qui annoncent la même grandeur ne "
        "peuvent pas observer deux populations.")


def test_the_two_counters_agree_on_the_same_window() -> None:
    """Et la forme se vérifie par EXÉCUTION, pas seulement par lecture."""
    import sys

    sys.path.insert(0, str(_ROOT))
    from src.database.postgres_handler import PostgresHandler

    def _peak(join: str) -> int:
        return db.fetch_query(f"""
            SELECT COALESCE(max(n), 0) FROM (
                SELECT count(DISTINCT u.session_id) AS n
                  FROM usage_events u
                  {join} saas_artists a ON a.id = u.artist_id
                 WHERE u.ts > now() - interval '{_WINDOW}'
                   AND COALESCE(a.is_canary, FALSE) = FALSE
                   AND COALESCE(a.is_sandbox, FALSE) = FALSE
                 GROUP BY date_trunc('minute', u.ts)
            ) x""")[0][0]

    db = PostgresHandler.from_env_or_config()
    try:
        shared = _ops_join()
        assert shared is not None
        mine, theirs = _peak(shared), _peak(_scale_join() or "JOIN")
    finally:
        db.close()
    assert mine == theirs, (
        f"sur {_WINDOW}, les deux jointures rendent {mine} et {theirs}. Le chiffre qui "
        "décide s'il faut des répliques et celui qu'on archive chaque nuit ne "
        "décrivent pas la même journée.")
