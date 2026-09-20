"""Le digest hebdomadaire ne somme qu'UNE génération de lignes Meta.

Type: Test
Uses: la base joignable
Depends on: src/utils/digest_queries
Persists in: nothing

Pourquoi ce garde existe
------------------------
`meta_insights_performance` porte deux générations sous le même schéma :

    231 lignes QUOTIDIENNES     3 087,82 €    date_start 2023-08-25 → 2024-09-30
     21 lignes de CUMUL À VIE   3 077,83 €    toutes datées du 2025-12-15

Les additionner donne **6 165,65 €** — presque exactement le double — et c'est ce que
l'e-mail hebdomadaire envoyait à l'artiste. La borne `date_start >= CURRENT_DATE - 7`
ne l'évitait que par **accident de calendrier** : juste tant que le 2025-12-15 est hors
de la fenêtre, faux les sept jours où il y entre.

⚠️ Le correctif n'a PAS ajouté un second discriminant dans la requête du digest.
`v_meta_campaign_daily` distingue déjà les deux générations. Réécrire le critère ici
aurait créé une seconde définition à faire coïncider avec la première.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.digest_queries import META_WEEKLY_SPEND_SQL  # noqa: E402


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                      # noqa: BLE001
        return None


def test_the_digest_reads_the_gold_view_not_the_raw_table() -> None:
    """Lu dans la REQUÊTE, pas dans un commentaire — et sans base."""
    sql = re.sub(r"--[^\n]*", "", META_WEEKLY_SPEND_SQL).lower()
    assert "v_meta_campaign_daily" in sql, (
        "la requête du digest ne lit pas la vue or. La table brute mélange les lignes "
        "quotidiennes et les cumuls à vie.")
    assert not re.search(r"from\s+meta_insights_performance\b", sql), (
        "la requête lit encore `meta_insights_performance` — la table qui porte les deux "
        "générations.")


def test_the_two_generations_are_still_distinguishable() -> None:
    """ANTI-VACUITÉ, et la mesure qui a fait écrire ce garde.

    Si la table cessait de porter les lignes de cumul, l'assertion suivante deviendrait
    vraie pour rien. Ce test rend visible le jour où ça arrive.
    """
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        r = db.fetch_query(
            "SELECT count(*) FILTER (WHERE date_start = collected_at::date), count(*) "
            "FROM meta_insights_performance")[0]
    finally:
        db.close()
    if r[1] == 0:
        pytest.skip("table vide sur cette instance")
    assert r[0] >= 1, (
        "plus aucune ligne de cumul dans `meta_insights_performance` : soit elles ont "
        "été purgées — mettre à jour ce fichier — soit le discriminant "
        "`date_start = collected_at::date` a cessé de les reconnaître.")


def test_the_gold_view_returns_strictly_less_than_the_raw_table() -> None:
    """LE CŒUR. La vue doit ÉCARTER des lignes, sinon elle ne sert à rien.

    Une vue qui rendrait le même total que la table brute passerait le test de lecture
    ci-dessus tout en ne corrigeant rien.
    """
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        brut = db.fetch_query(
            "SELECT round(coalesce(sum(spend),0)::numeric,2) "
            "FROM meta_insights_performance")[0][0]
        vue = db.fetch_query(
            "SELECT round(coalesce(sum(spend),0)::numeric,2) "
            "FROM v_meta_campaign_daily")[0][0]
    finally:
        db.close()
    if brut == 0:
        pytest.skip("aucune dépense sur cette instance")
    assert vue < brut, (
        f"la vue or rend {vue} € et la table brute {brut} € — la vue n'écarte AUCUNE "
        "ligne de cumul. Son critère (une ligne correspondante dans "
        "`meta_insights_performance_day`) ne discrimine plus, et le digest est redevenu "
        "faux sans que la requête ait changé.")
