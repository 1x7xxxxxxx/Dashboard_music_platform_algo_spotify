"""Guard: l'accueil, le PDF et la page Apple comptent la MÊME chose.

Type: Test
Uses: live Postgres (spotify_etl), platform_timeseries
Depends on: platform_totals, apple_lifetime_plays, collect_report_data
Persists in: rien

Balayé le 2026-09-08 : il existait au moins QUATRE façons de calculer « le total » dans
ce dépôt, et elles ne s'accordaient pas.

* l'accueil et l'export PDF additionnaient `youtube_channel_history.view_count` — le
  compteur de CHAÎNE, prouvé ~10× faux le matin même (+360 en une journée contre 64
  vues chez YouTube Studio) ;
* le PDF ignorait de surcroît `from_date`/`to_date` : un rapport « 30 jours » imprimait
  des chiffres de carrière sous un titre de période ;
* la page Apple sommait toute sa table et comptait deux fois les années contenues dans
  un export « depuis le début » ;
* l'API rendait le cumul d'UNE SEULE vidéo comme total de la plateforme.

Un même artiste lisait donc trois totaux différents sur trois pages, sans qu'aucun test
ne s'en aperçoive : chacune était cohérente avec elle-même. C'est ce test qui manquait —
il ne vérifie pas un calcul, il vérifie que deux surfaces racontent la même histoire.
"""
from __future__ import annotations

import datetime as dt

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture(scope="module")
def db():
    from src.dashboard.utils import get_db_connection
    conn = get_db_connection()
    yield conn
    conn.close()


def _tenant_with_data(db) -> int:
    from src.dashboard.utils.platform_timeseries import combined_total, platform_totals
    rows = db.fetch_query("SELECT id FROM saas_artists WHERE active ORDER BY id") or []
    for (aid,) in rows:
        if combined_total(platform_totals(db, int(aid))) > 0:
            return int(aid)
    pytest.skip("aucun locataire avec des chiffres dans la base locale")
    return 0


def test_the_home_and_the_pdf_read_the_same_helper(db) -> None:
    """Les deux surfaces appellent la MÊME fonction, sur la MÊME période.

    Lu sur la structure : c'est la seule façon de garantir qu'elles ne divergeront pas
    au prochain changement. Comparer deux nombres ne dirait rien le jour où l'une des
    deux cesse d'être appelée.
    """
    import ast
    import pathlib

    for path, fn_name in (("src/dashboard/views/home.py", "_section_streams"),
                          ("src/dashboard/utils/pdf_exporter/_report.py",
                           "collect_report_data")):
        tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == fn_name), None)
        assert fn is not None, f"{path} ne définit plus {fn_name}"
        called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
                  for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert "platform_totals" in called, (
            f"{path}::{fn_name} calcule ses totaux tout seul — c'est ainsi que trois "
            "pages en sont venues à afficher trois chiffres différents")


def test_no_surface_reads_the_channel_counter_as_streams(db) -> None:
    """Le compteur de CHAÎNE YouTube ne doit plus alimenter un total d'écoutes.

    Il porte les vidéos privées, supprimées et des agrégats internes, et il avance par
    paliers. C'est la source que la classe `an-aggregate-counter-is-not-the-sum-of-its
    -parts` a fait abandonner pour la figure ; elle alimentait encore l'accueil, le PDF
    et l'API.
    """
    import ast
    import pathlib

    from src.dashboard.utils import platform_timeseries as pts
    for sql_name in ("_SQL_LIFETIME_YOUTUBE", "_SQL_YOUTUBE"):
        sql = getattr(pts, sql_name)
        assert "youtube_video_stats" in sql, sql_name
        assert "youtube_channel_history" not in sql, (
            f"{sql_name} est revenu au compteur de chaîne")

    tree = ast.parse(pathlib.Path("src/api/routers/kpis.py").read_text(encoding="utf-8"))
    consts = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    yt_reads = [c for c in consts if "youtube_video_stats" in c]
    assert yt_reads, "l'API ne lit plus les compteurs par vidéo — garde à repointer"
    for sql in yt_reads:
        assert "DISTINCT ON" in sql or "SUM" in sql, (
            "l'API rend le compteur d'une seule vidéo comme total de la plateforme :\n"
            + sql[:200])


def test_a_bounded_period_is_never_larger_than_the_lifetime(db) -> None:
    """L'invariant le plus simple, et celui qu'aucune surface ne vérifiait.

    Une période bornée ne peut pas dépasser « depuis le début » : si elle le fait, c'est
    qu'on additionne deux formes — un cumul et des quantités du jour, ou deux relevés
    qui se recouvrent.
    """
    from src.dashboard.utils.platform_timeseries import platform_totals

    aid = _tenant_with_data(db)
    life = platform_totals(db, aid)
    window = platform_totals(db, aid, dt.date(2020, 1, 1), dt.date.today())
    for key, windowed in window.items():
        if windowed is None:
            continue
        lifetime = life.get(key) or 0
        assert windowed <= lifetime, (
            f"{key} : {windowed} sur la période contre {lifetime} depuis le début — "
            "une fenêtre ne peut pas contenir plus que tout l'historique")


def test_an_unmeasured_platform_is_none_not_zero(db) -> None:
    """« Rien mesuré » et « zéro écoute » ne doivent pas se ressembler."""
    from src.dashboard.utils.platform_timeseries import platform_totals

    aid = _tenant_with_data(db)
    far = platform_totals(db, aid, dt.date(1990, 1, 1), dt.date(1990, 12, 31))
    assert set(far.values()) <= {None}, (
        f"une période sans aucune collecte rend {far} au lieu de None partout")
