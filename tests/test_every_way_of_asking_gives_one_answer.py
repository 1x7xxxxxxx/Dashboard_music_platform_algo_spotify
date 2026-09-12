"""La même question, posée de quatre façons, rend un seul nombre.

Type: Test
Uses: platform_chart, platform_timeseries, une base vivante
Depends on: la couche or (v_platform_totals), platform_chart.render_platform_chart
Persists in: nothing

Pourquoi ce garde existe
------------------------
Trois défauts de la même famille ont traversé toute la batterie de gardes le
2026-09-11, et pour la même raison : **chaque surface était testée seule.**

  * le mode « Cumulé » traçait **21** vues YouTube quand la tuile en annonçait
    118 219 — ×5 630 ;
  * `platform_totals` borné rendait **21** quand le compteur avait gagné 18 625 —
    ×887, imprimé sur la même page du PDF que la courbe qui le contredisait ;
  * le mode « Par période » au pas hebdomadaire totalisait **124** contre 18 740 —
    ×151, et la bande passait sous le pixel.

Chacun de ces nombres était vert dans son propre test. Ce qui manquait n'est pas un
garde de JUSTESSE mais un garde de COHÉRENCE : deux façons de répondre à la même
question doivent rendre le même nombre, et aucun test ne comparait deux surfaces.

C'est l'invariant le plus simple qu'on puisse écrire sur ce produit, et il aurait
attrapé les trois. Il est volontairement formulé sur la QUESTION du lecteur — « combien
au total sur cette plateforme ? » — et non sur une implémentation.
"""
from __future__ import annotations

import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _kwargs() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        from urllib.parse import urlparse
        u = urlparse(os.environ["DATABASE_URL"])
        return {"host": u.hostname or "localhost", "port": u.port or 5432,
                "database": (u.path or "").lstrip("/"), "user": u.username or "postgres",
                "password": u.password or ""}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {"host": _DB_HOST, "port": _DB_PORT,
            "database": os.environ.get("DATABASE_NAME", "spotify_etl"),
            "user": os.environ.get("DATABASE_USER", "postgres"),
            "password": os.environ.get("DATABASE_PASSWORD")
            or os.environ.get("DB_PASSWORD", "")}


_KW = _kwargs()

pytestmark = pytest.mark.skipif(
    _KW is None,
    reason=f"Pas de Postgres sur {_DB_HOST}:{_DB_PORT} — la cohérence se mesure sur données",
)

# Les plateformes servies par la couche or en SÉRIE. Apple n'y est pas : sa règle vit
# dans `apple_lifetime_plays` et n'a pas d'équivalent en série (ses relevés sont des
# totaux de période, pas des niveaux quotidiens). Elle est donc hors de cet invariant,
# et c'est dit plutôt que sous-entendu.
_COUNTER_PLATFORMS = ("youtube", "soundcloud")


@pytest.fixture(scope="module")
def db():
    from src.database.postgres_handler import PostgresHandler
    handler = PostgresHandler(**_KW)
    try:
        yield handler
    finally:
        handler.close()


def _tenants(db) -> list[int]:
    rows = db.fetch_query(
        "SELECT artist_id FROM youtube_video_stats WHERE artist_id IS NOT NULL "
        "AND view_count IS NOT NULL GROUP BY artist_id ORDER BY count(*) DESC", ())
    return [int(r[0]) for r in (rows or [])]


def _drawn_total(series, cumulative, mode, step, since, until) -> dict:
    """{plateforme: somme de ce que la FIGURE dessine}, hors Streamlit."""
    from src.dashboard.utils import platform_chart as pc

    captured = {}
    real_chart, real_caption = pc.st.plotly_chart, pc.st.caption
    pc.st.plotly_chart = lambda fig, **k: captured.__setitem__("fig", fig)
    pc.st.caption = lambda *a, **k: None
    try:
        pc.render_platform_chart(series, since=since, until=until, step=step,
                                 mode=mode, cumulative=cumulative, key="coherence")
    finally:
        pc.st.plotly_chart, pc.st.caption = real_chart, real_caption
    fig = captured.get("fig")
    out: dict = {}
    for trace in (fig.data if fig else []):
        # La trace SANS NOM est le porteur de survol des pas non mesurés : elle
        # ne nomme aucune plateforme, et l'agréger sous la clé `None` ferait
        # apparaître une « plateforme » fantôme dans la comparaison.
        if not trace.name:
            continue
        out[trace.name] = out.get(trace.name, 0) + sum(v for v in trace.y if v)
    return out


@pytest.mark.parametrize("step", ["week", "year"])
def test_the_period_mode_totals_what_the_lifetime_total_says(db, step) -> None:
    """« Par période » sur TOUT l'historique doit valoir le total « depuis le début ».

    C'est la formulation qui aurait attrapé le ×151 : la figure additionnait les
    écarts quotidiens mesurés, la tuile lisait le compteur, et les deux ne se sont
    jamais parlé.

    Le pas du JOUR est exclu, et la raison est écrite : un écart n'y est calculé
    qu'entre deux jours consécutifs, donc la somme est volontairement inférieure — la
    note « écoutes non traçables » l'annonce. C'est une exemption, pas un oubli.
    """
    from src.dashboard.utils.platform_timeseries import (
        PLATFORM_LABELS, cumulative_by_platform, daily_streams_by_platform,
        platform_totals,
    )

    tenants = _tenants(db)
    if not tenants:
        pytest.skip("aucun locataire mesuré")

    wrong, compared = [], 0
    for aid in tenants:
        series = daily_streams_by_platform(db, aid)
        cumulative = cumulative_by_platform(db, aid)
        drawn = _drawn_total(series, cumulative, "absolute", step, None, None)
        if not drawn:
            # AUCUNE figure n'a été rendue pour ce locataire — il n'y a alors pas deux
            # surfaces à confronter, et l'exiger transformerait ce garde de cohérence
            # en garde de présence. Mesuré le 2026-09-11 : un locataire de la base
            # locale porte des compteurs YouTube sans aucune série traçable.
            continue
        for key in _COUNTER_PLATFORMS:
            rows = cumulative.get(key)
            if not rows or len(rows) < 2:
                continue
            # Le total « depuis le début » porte aussi ce qui précède notre première
            # collecte ; la figure ne peut montrer que ce qu'on a vu croître. La
            # question commune aux deux est donc la CROISSANCE observée.
            expected = rows[-1][1] - rows[0][1]
            got = drawn.get(PLATFORM_LABELS[key])
            if got is None:
                wrong.append(f"artiste {aid} / {key} / pas={step} : la figure existe "
                             f"et cette plateforme n'y est pas, alors que son "
                             f"compteur a gagné {expected:,}")
                continue
            compared += 1
            if abs(got - expected) > max(1, expected * 0.01):
                wrong.append(
                    f"artiste {aid} / {key} / pas={step} : la figure totalise "
                    f"{got:,.0f}, la croissance du compteur vaut {expected:,} "
                    f"(×{expected / max(got, 1):.0f})")

    if not compared:
        # DISTINGUER « la base n'a pas de quoi comparer » de « le garde a sauté ».
        #
        # Ce test a rougi en CI le 2026-09-11 sur cette assertion : la base de CI est
        # neuve, aucun locataire n'y porte à la fois une série quotidienne traçable et
        # un compteur. Échouer y serait dire « le produit est incohérent » alors que
        # la mesure n'a pas pu avoir lieu — le contraire de ce que ce fichier défend.
        #
        # Mais sauter en silence rendrait le garde inutile le jour où il saute pour
        # une MAUVAISE raison. On sépare donc les deux : s'il existe un locataire avec
        # une série cumulée, il DOIT y avoir eu une comparaison.
        with_levels = [aid for aid in tenants
                       if any(len(r or []) >= 2
                              for r in cumulative_by_platform(db, aid).values())]
        assert not with_levels, (
            f"{len(with_levels)} locataire(s) portent une série cumulée et aucune "
            "comparaison n'a eu lieu : la figure ne trace aucune plateforme à "
            f"compteur (locataires : {with_levels[:5]}).")
        pytest.skip("aucun locataire de cette base ne porte de compteur traçable")
    assert not wrong, (
        "Deux surfaces du même produit répondent deux nombres à « combien sur cette "
        "plateforme ». C'est la famille de défauts du 2026-09-11, et chacun de ces "
        "nombres était vert dans son propre test.\n\n" + "\n".join(wrong))


@pytest.mark.parametrize("step", ["day", "week", "year"])
def test_the_cumulative_curve_never_exceeds_the_lifetime_total(db, step) -> None:
    """Une courbe cumulée ne peut pas dépasser ce que la plateforme annonce.

    L'invariant dans l'autre sens : le ×5 630 était une sous-déclaration, mais la même
    absence de garde laisserait passer une sur-déclaration — par exemple un report en
    avant qui additionnerait au lieu de reporter.
    """
    from src.dashboard.utils.platform_timeseries import (
        PLATFORM_LABELS, cumulative_by_platform, daily_streams_by_platform,
        platform_totals,
    )

    tenants = _tenants(db)
    if not tenants:
        pytest.skip("aucun locataire mesuré")

    wrong = []
    for aid in tenants:
        series = daily_streams_by_platform(db, aid)
        cumulative = cumulative_by_platform(db, aid)
        life = platform_totals(db, aid)
        drawn = _drawn_total(series, cumulative, "cumulative", step, None, None)
        for key in _COUNTER_PLATFORMS:
            total = life.get(key)
            rows = cumulative.get(key)
            if not total or not rows:
                continue
            # En cumulé chaque point porte un NIVEAU : on compare le plus haut, pas
            # la somme — additionner des cumuls avait déjà produit 16 568 594.
            peak = max((v for _d, v in rows), default=0)
            if peak > total:
                wrong.append(f"artiste {aid} / {key} / pas={step} : la courbe monte à "
                             f"{peak:,}, la plateforme en annonce {total:,}")
            if drawn and PLATFORM_LABELS[key] not in drawn:
                wrong.append(f"artiste {aid} / {key} / pas={step} : absente de la figure "
                             f"alors que son compteur vaut {total:,}")
    assert not wrong, "\n".join(wrong)


def test_the_matrix_is_written_down_where_someone_will_read_it() -> None:
    """R95 : douze cellules, et aucune n'était écrite nulle part.

    Les trois défauts du 2026-09-11 étaient trois cellules de la matrice mode × pas.
    Un tableau dans un document ne garde rien à lui seul — mais son ABSENCE explique
    pourquoi personne n'a vu que fermer une cellule laissait les autres ouvertes.

    Ce test tient la seule chose mécanisable : le document existe, il nomme les
    quatre modes et les trois pas, et il nomme les classes d'erreur déjà payées.
    """
    import pathlib

    doc = (pathlib.Path(__file__).resolve().parent.parent
           / ".claude" / "dev-docs" / "chart-derivation-matrix.md")
    assert doc.exists(), "la matrice mode × pas n'est écrite nulle part"
    text = doc.read_text(encoding="utf-8")

    from src.dashboard.utils.platform_chart import MODES

    for mode in MODES.values():
        assert mode in text, f"le mode « {mode} » n'est pas dans la matrice"
    for step in ("jour", "semaine", "année"):
        assert step in text, f"le pas « {step} » n'est pas dans la matrice"
    for klass in ("cumulative-counter-drawn-as-its-own-history",
                  "a-bucket-sums-deltas-instead-of-deriving-the-counter",
                  "a-note-outlives-the-figure-it-explains"):
        assert klass in text, (
            f"la classe `{klass}` n'est pas rattachée à sa cellule : la matrice "
            "n'apprend rien de ce qu'on a déjà payé")
