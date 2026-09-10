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
    # `_SQL_LIFETIME_*` lit désormais la couche or (`v_platform_totals`, ADR-019), qui
    # porte la règle « somme des compteurs PAR VIDÉO ». La série quotidienne, elle,
    # lit toujours la table directement.
    assert "youtube_video_stats" in pts._SQL_YOUTUBE
    assert "youtube_channel_history" not in pts._SQL_YOUTUBE, (
        "_SQL_YOUTUBE est revenu au compteur de chaîne")
    assert "v_platform_totals" in pts._SQL_LIFETIME, (
        "les totaux « depuis le début » ne lisent plus la couche or")

    tree = ast.parse(pathlib.Path("src/api/routers/kpis.py").read_text(encoding="utf-8"))
    consts = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    # L'API lit désormais la couche or (ADR-019) plutôt que de recopier la règle. Ce
    # garde visait `youtube_video_stats` parce que c'était là que la règle vivait ; il
    # a demandé lui-même à être repointé le 2026-09-10 (« l'API ne lit plus les
    # compteurs par vidéo »), ce qui est le comportement voulu d'un garde ancré sur un
    # emplacement plutôt que sur une propriété.
    yt_reads = [c for c in consts if "v_platform_totals" in c and "youtube" in c]
    assert yt_reads, (
        "l'API ne lit plus la couche or pour YouTube — soit elle a recopié la règle "
        "une cinquième fois, soit la vue a disparu")
    assert not [c for c in consts
                if "youtube_channel_history" in c and "view_count" in c], (
        "l'API est revenue au compteur de chaîne")

    # LA PORTÉE ÉTAIT LE DÉFAUT. Ce garde ne regardait que `platform_timeseries` et
    # l'API ; le compteur de chaîne a donc survécu comme TOTAL dans deux autres
    # surfaces jusqu'au 2026-09-10 — `kpi_helpers.get_total_views_youtube`, affiché sur
    # « Data Wrapped », et `pdf_exporter/_collectors.py`, imprimé dans le PDF client à
    # côté du total corrigé. Le même locataire lisait 120 627 ici et 118 219 là.
    #
    # On balaie donc TOUTES les surfaces qui affichent un total, et on n'accepte le
    # compteur de chaîne que là où il est légitime : les ABONNÉS, qui n'ont pas d'autre
    # source.
    for path in ("src/dashboard/utils/kpi_helpers.py",
                 "src/dashboard/utils/pdf_exporter/_collectors.py",
                 "src/dashboard/views/data_wrapped.py"):
        tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
        # Les DOCSTRINGS sont exclues : ce garde a rougi sur l'explication du correctif
        # qu'il venait de garder — deuxième fois dans la même séance. Un garde qui
        # oblige à cesser de documenter apprend que le rouge est du bruit.
        docstrings = {
            d for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            for d in [ast.get_docstring(n, clean=False)] if d is not None
        }
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            sql = node.value
            if sql in docstrings:
                continue
            if "youtube_channel_history" not in sql:
                continue
            assert "view_count" not in sql, (
                f"{path}:{node.lineno} lit `youtube_channel_history.view_count`. "
                "Ce compteur avance par paliers et porte des vidéos qui ne sont pas "
                "les siennes : il ne peut pas être un total de vues. La définition "
                "unique est la vue `v_platform_totals` (ADR-019).")


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
