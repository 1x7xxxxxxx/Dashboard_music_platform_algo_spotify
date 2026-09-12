"""Le dernier point d'une courbe cumulée égale le total que la couche or annonce.

Type: Test
Uses: psycopg2, une base vivante
Depends on: src/dashboard/utils/platform_timeseries.py, la vue v_platform_totals
Persists in: rien

Pourquoi ce garde existe
------------------------
ADR-019 a posé la couche or comme une FRONTIÈRE : une métrique, une définition. La
migration 097 l'a appliquée aux TOTAUX (`v_platform_totals`) après avoir trouvé trois
définitions incompatibles du total de vues YouTube dans le même produit.

Elle n'a rien dit des SÉRIES. Une courbe est pourtant la même métrique, déclinée dans
le temps : si son dernier point ne vaut pas le total affiché à côté, le locataire lit
deux nombres pour une seule chose — exactement ce qu'ADR-019 existe pour empêcher,
mais sur l'axe que personne n'avait fermé.

Mesuré le 2026-09-11 sur l'artiste 1 : la page YouTube traçait le compteur de CHAÎNE
(`youtube_channel_history.view_count`, **120 627**) sous le titre « Vues Cumulées »,
à côté d'un produit qui compte **118 219** partout ailleurs.

L'égalité n'est pas une coïncidence à surveiller : elle est VRAIE PAR CONSTRUCTION
depuis que `youtube_cumulative_views` reporte en avant la dernière valeur connue de
chaque vidéo — le même « dernier relevé par vidéo » que la vue additionne. Ce test
est ce qui empêche une « simplification » de la reprendre : retirer le report rend la
courbe plus simple, la laisse verte sur les jours de collecte complète, et la fait
mentir les autres. YouTube n'est mesurée que 39 % des jours.
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
    reason=f"Pas de Postgres sur {_DB_HOST}:{_DB_PORT} — l'égalité se vérifie sur données",
)


@pytest.fixture(scope="module")
def db():
    from src.database.postgres_handler import PostgresHandler
    handler = PostgresHandler(**_KW)
    try:
        yield handler
    finally:
        handler.close()


def _tenants_with_youtube(db) -> list[int]:
    rows = db.fetch_query(
        "SELECT artist_id, count(DISTINCT video_id) FROM youtube_video_stats "
        "WHERE artist_id IS NOT NULL AND view_count IS NOT NULL "
        "GROUP BY artist_id ORDER BY 2 DESC", ()
    )
    return [int(r[0]) for r in (rows or [])]


def test_the_youtube_curve_ends_on_the_gold_total(db) -> None:
    """Pour CHAQUE locataire qui a des vues, pas seulement pour celui qui en a le plus.

    Le locataire 1 porte 60 % des données : un garde qui ne regarde que lui passerait
    sur une régression qui ne touche que les petits catalogues — et c'est le cas d'un
    report en avant, qui ne se voit que lorsque la collecte est trouée.
    """
    from src.dashboard.utils.platform_timeseries import youtube_cumulative_views

    tenants = _tenants_with_youtube(db)
    if not tenants:
        pytest.skip("aucun locataire n'a de vue YouTube dans cette base")

    wrong = []
    for aid in tenants:
        series = youtube_cumulative_views(db, aid)
        gold = db.fetch_query(
            "SELECT total FROM v_platform_totals "
            "WHERE artist_id = %s AND platform = 'youtube'", (aid,))
        expected = int(gold[0][0]) if gold else 0
        if not series:
            wrong.append(f"artiste {aid} : la couche or annonce {expected:,}, "
                         "la courbe est vide")
            continue
        last = series[-1][1]
        if last != expected:
            wrong.append(
                f"artiste {aid} : la courbe finit à {last:,}, la tuile annonce "
                f"{expected:,} (écart {last - expected:+,})")

    assert not wrong, (
        "Une courbe cumulée ne finit pas sur le total que le produit affiche à côté. "
        "Le locataire lit deux nombres pour une seule chose.\n\n" + "\n".join(wrong))


def test_the_curve_never_goes_down(db) -> None:
    """Un cumul qui recule est un report en avant qui a sauté un jour.

    C'est le symptôme exact d'une somme qui n'additionne que les vidéos relevées ce
    jour-là : les jours de collecte partielle creusent des trous, et la courbe montre
    une chute de vues que personne n'a subie.
    """
    from src.dashboard.utils.platform_timeseries import youtube_cumulative_views

    tenants = _tenants_with_youtube(db)
    if not tenants:
        pytest.skip("aucun locataire n'a de vue YouTube dans cette base")

    drops = []
    for aid in tenants:
        series = youtube_cumulative_views(db, aid)
        for (d0, v0), (d1, v1) in zip(series, series[1:]):
            if v1 < v0:
                drops.append(f"artiste {aid} : {d0} {v0:,} → {d1} {v1:,}")
    assert not drops, (
        "Le cumul recule — la courbe annonce une perte de vues qui n'a pas eu lieu.\n"
        + "\n".join(drops[:10]))


def test_the_series_does_not_read_the_channel_counter(db) -> None:
    """La propriété a DÉMÉNAGÉ dans la vue, elle n'a pas disparu.

    Elle tenait dans `_SQL_YT_CUMULATIVE`, une constante du module. Depuis la
    migration 104, le report en avant vit dans `v_platform_levels` pour les trois
    plateformes — le garder aussi en Python serait une seconde définition du même
    niveau. Le test suit la règle là où elle est, plutôt que de disparaître avec la
    constante qu'il nommait.
    """
    definition = db.fetch_query(
        "SELECT pg_get_viewdef('v_platform_levels'::regclass, true)", ())[0][0].lower()
    assert "youtube_video_stats" in definition
    assert "youtube_channel_history" not in definition, (
        "la série cumulée est revenue au compteur de chaîne")
    assert "count(" in definition and "over (partition by" in definition, (
        "le report en avant a disparu : sans lui, un jour de collecte partielle fait "
        "plonger la courbe et son dernier point ne vaut le total que par chance")
    assert "playback_count > 0" in definition and "view_count > 0" in definition, (
        "le filtre des ZÉROS a sauté : une collecte ratée écrit 0, pas NULL, et le "
        "niveau s'effondre. Mesuré le 2026-06-01 — 19 titres SoundCloud à 0, le "
        "niveau tombait de 23 475 à 0 avant de remonter.")


# ── LE MÊME INVARIANT, MAIS SUR LA FIGURE ──────────────────────────────────
#
# Ci-dessus, la SÉRIE finit sur le total. Ici, ce que `platform_chart` en dessine.
# Les deux sont nécessaires : la série peut être juste et le mode « Cumulé » la
# reconstruire quand même à partir des différences quotidiennes — c'est exactement ce
# qui se passait, et aucun test de la série ne pouvait le voir.
#
# Pas de base et pas de Streamlit : `_as_mode` est une fonction pure.

def test_the_cumulative_mode_reads_the_gold_series_instead_of_rebuilding_it() -> None:
    """Un trou dans le quotidien ne doit pas faire disparaître des écoutes du cumul.

    Le scénario est celui de la production : YouTube n'est collectée que 39 % des
    jours, donc sa série quotidienne — une DIFFÉRENCE entre deux relevés consécutifs —
    ne porte qu'une fraction de ce que le compteur a réellement gagné.
    """
    import datetime as _d

    from src.dashboard.utils.platform_chart import _as_mode

    span = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(5)]
    # Mesurée J1 et J2 (donc un delta de 10), puis plus rien : les 90 gagnés entre J2
    # et J5 ne sont dans AUCUN delta quotidien.
    daily = {"youtube": [None, 10, None, None, None]}
    gold = {"youtube": [(span[0], 100), (span[1], 110), (span[4], 200)]}

    rebuilt = _as_mode(daily, ["youtube"], "cumulative")["youtube"]
    # `None` reste `None` : la reconstruction n'atteint même pas le dernier point.
    # Le niveau le plus haut qu'elle sache montrer est 10, pour 100 gagnés.
    assert rebuilt == [None, 10, None, None, None], (
        f"prémisse fausse : la reconstruction rend {rebuilt}")

    read = _as_mode(daily, ["youtube"], "cumulative", gold, span, "day")["youtube"]
    assert read == [100, 110, 110, 110, 200], (
        f"le mode cumulé ne lit pas la couche or : {read}. Il reconstruit à partir des "
        "différences quotidiennes, qui jettent les journées non consécutives — 21 "
        "affichés pour YouTube au lieu de 118 219 le 2026-09-11."
    )


def test_a_gap_holds_its_level_instead_of_breaking_the_curve() -> None:
    """Entre deux relevés, un compteur n'est pas inconnu : il n'a pas été relu.

    C'est la différence entre une série de QUANTITÉS, où un jour non mesuré est une
    ignorance, et une série de NIVEAUX, où il ne l'est pas. Rendre `None` au milieu
    couperait la bande empilée et la ferait retomber.
    """
    import datetime as _d

    from src.dashboard.utils.platform_chart import _as_mode

    span = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(4)]
    out = _as_mode({"youtube": [None] * 4}, ["youtube"], "cumulative",
                   {"youtube": [(span[1], 50)]}, span, "day")["youtube"]
    assert out == [None, 50, 50, 50], (
        f"{out} — avant la première mesure on ne sait rien (None, tracé 0), après on "
        "sait : le dernier compteur lu.")


def test_a_platform_without_a_gold_series_still_accumulates_its_days() -> None:
    """Spotify livre de vraies quantités quotidiennes : leur somme courante EST le cumul.

    Si ce test tombe, le correctif aura remplacé une règle juste par une autre au lieu
    de distinguer les deux régimes.
    """
    from src.dashboard.utils.platform_chart import _as_mode

    out = _as_mode({"spotify": [3, 4, None, 5]}, ["spotify"], "cumulative",
                   {"youtube": [(1, 1)]}, [0, 1, 2, 3], "day")["spotify"]
    assert out == [3, 7, None, 12]


def test_a_coarse_bucket_takes_the_last_level_not_the_sum() -> None:
    """Agréger un NIVEAU par semaine, c'est prendre le dernier, jamais additionner.

    Sommer les relevés d'une semaine multiplierait le compteur par le nombre de
    collectes — la forme de défaut que ce module nomme « on n'additionne pas deux
    formes ».
    """
    import datetime as _d

    from src.dashboard.utils.platform_chart import _as_mode

    weeks = [_d.date(2026, 1, 5), _d.date(2026, 1, 12)]     # deux lundis
    gold = {"youtube": [(_d.date(2026, 1, 6), 100), (_d.date(2026, 1, 8), 130),
                        (_d.date(2026, 1, 14), 160)]}
    out = _as_mode({"youtube": [None, None]}, ["youtube"], "cumulative",
                   gold, weeks, "week")["youtube"]
    assert out == [130, 160], f"{out} — attendu le dernier niveau de chaque semaine"


def test_a_measurement_before_the_window_sets_the_starting_level() -> None:
    """Une fenêtre bornée ne fait pas repartir un compteur de zéro."""
    import datetime as _d

    from src.dashboard.utils.platform_chart import _as_mode

    span = [_d.date(2026, 6, 1), _d.date(2026, 6, 2)]
    gold = {"youtube": [(_d.date(2026, 1, 1), 900), (_d.date(2026, 6, 2), 950)]}
    out = _as_mode({"youtube": [None, None]}, ["youtube"], "cumulative",
                   gold, span, "day")["youtube"]
    assert out == [900, 950], (
        f"{out} — « Cette année » repartirait de zéro alors que le compteur portait "
        "déjà 900 la veille")


# ── L'ADMISSION : LA FIGURE, PAS SEULEMENT LA SÉRIE ────────────────────────

def _render(series, gold, mode="cumulative", step="day", **kw):
    """Rend la figure hors Streamlit et renvoie {nom de bande: derniers y}.

    `plotly_chart` et `_render_notes` sont neutralisés : ce qui est vérifié ici est la
    FIGURE construite, pas ce que Streamlit en fait.
    """
    from src.dashboard.utils import platform_chart as pc

    captured = {}
    real_chart, real_notes = pc.st.plotly_chart, pc._render_notes
    pc.st.plotly_chart = lambda fig, **k: captured.setdefault("fig", fig)
    pc._render_notes = lambda *a, **k: None
    try:
        drawn = pc.render_platform_chart(series, mode=mode, step=step,
                                         cumulative=gold, key="guard", **kw)
    finally:
        pc.st.plotly_chart, pc._render_notes = real_chart, real_notes
    fig = captured.get("fig")
    if fig is None:
        return drawn, {}, []
    # Les ÉTIQUETTES sont des annotations dans la marge, pas une boîte de légende :
    # une plateforme peut donc être nommée sans porter la moindre trace, et c'est
    # précisément ce qu'on veut interdire. Les vérifier sur `fig.data` ne le voit pas.
    labels = [a.text for a in (fig.layout.annotations or []) if getattr(a, "text", None)]
    # `if t.name` : la figure porte depuis le 2026-09-12 une trace SANS NOM — le
    # porteur de survol des pas non mesurés, qui ne nomme aucune plateforme et ne
    # fait que couvrir l'axe. Trois gardes de ce dépôt ont levé un `TypeError` sur
    # son `name` valant `None` avant que la règle ne soit écrite ici.
    return drawn, {t.name: list(t.y)[-1] for t in fig.data if t.name}, labels


def test_a_platform_served_by_the_gold_layer_is_not_dropped_for_being_sparse() -> None:
    """Les deux verdicts de couverture portent sur le QUOTIDIEN, et ils ont raison là.

    `stackable` écarte ce qui est trop clairsemé pour faire une aire, et le plancher de
    seau vide un seau mesuré à moins de la moitié. Pour des quantités, c'est juste : un
    jour non collecté est une ignorance. Pour un NIVEAU, non — entre deux relevés le
    compteur est connu.

    Sans cette admission, le correctif du cumul serait invisible là où il compte :
    YouTube n'est relevée que 39 % des jours, donc elle est écartée avant d'être
    tracée. C'est le symptôme signalé le 2026-09-11 — « j'ai bien Spotify mais aucune
    data pour les autres plateformes » — sur « Par période », « par année » et « par
    semaine » à la fois.
    """
    import datetime as _d

    span = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(60)]
    series = {"spotify": [(d, 10) for d in span],
              "youtube": [(span[3], 5)]}          # UN seul point : trop clairsemée
    gold = {"youtube": [(span[0], 1000), (span[-1], 1600)]}

    drawn, ends, _lbl = _render(series, gold, since=span[0], until=span[-1])
    assert drawn, "la figure n'a rien rendu"
    yt = next((v for k, v in ends.items() if "YouTube" in k), None)
    assert yt == 1600, (
        f"YouTube vaut {yt} au lieu de 1600 — servie par la couche or, elle est encore "
        f"jugée sur sa série quotidienne. Bandes tracées : {sorted(ends)}")
    assert next(v for k, v in ends.items() if "Spotify" in k) == 600, (
        "Spotify a changé : l'admission doit ajouter une plateforme, jamais en "
        "modifier une autre")


def test_an_admitted_platform_with_nothing_in_the_window_takes_no_label() -> None:
    """Admise, mais sa première mesure est POSTÉRIEURE à la fenêtre : rien à tracer.

    Lui laisser une étiquette dans la marge la ferait nommer sans bande — ce qui se lit
    comme une bande disparue, la forme de défaut que ce module paie depuis le début.
    """
    import datetime as _d

    span = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(30)]
    series = {"spotify": [(d, 10) for d in span]}
    gold = {"youtube": [(_d.date(2027, 6, 1), 5000)]}     # bien après la fenêtre

    drawn, ends, labels = _render(series, gold, since=span[0], until=span[-1])
    assert drawn
    assert not any("YouTube" in k for k in ends), (
        f"YouTube porte une trace alors qu'elle n'a rien dans la fenêtre : {sorted(ends)}")
    assert not any("YouTube" in lab for lab in labels), (
        f"YouTube est ÉTIQUETÉE dans la marge sans porter aucune bande : {labels}")


# ── LE TOTAL BORNÉ : LA MÊME RÈGLE, SUR UN SCALAIRE ───────────────────────

def test_a_bounded_total_on_a_counter_is_a_difference_of_levels(db) -> None:
    """Trouvé en REGARDANT le PDF, pas en lisant le code.

    Sur la page « Vue d'ensemble », la courbe montrait YouTube à 118 219 et le bâton
    juste en dessous annonçait **21**. Deux figures, une page, un facteur 887.

    La cause est la même que celle de la courbe, appliquée à un scalaire : la somme
    des écarts quotidiens n'additionne que les journées CONSÉCUTIVES, et YouTube n'est
    relevée que 39 % des jours. Mais la croissance d'un compteur sur une fenêtre n'a
    besoin d'aucune attribution — c'est son niveau à la fin moins son niveau au début.
    Savoir QUEL JOUR elle a eu lieu est ce qu'on ignore, et ce n'est pas la question.

    Ce test compare les deux lectures pour chaque locataire : le total borné doit
    valoir la différence des niveaux de la courbe, pas la somme des écarts.
    """
    from src.dashboard.utils.platform_timeseries import (
        cumulative_by_platform, daily_streams_by_platform, platform_totals,
    )

    tenants = _tenants_with_youtube(db)
    if not tenants:
        pytest.skip("aucun locataire n'a de vue YouTube dans cette base")

    wrong = []
    for aid in tenants:
        levels = cumulative_by_platform(db, aid)
        daily = daily_streams_by_platform(db, aid)
        for key, rows in levels.items():
            if len(rows or []) < 2:
                continue
            since, until = rows[0][0], rows[-1][0]
            if not [d for d, _ in daily.get(key, []) if since <= d <= until]:
                continue           # rien de mesuré au pas quotidien : hors sujet
            expected = rows[-1][1] - rows[0][1]
            got = platform_totals(db, aid, since, until).get(key)
            if got != expected:
                wrong.append(
                    f"artiste {aid} / {key} : le total borné rend {got}, la courbe "
                    f"monte de {expected} sur la même fenêtre")
    assert not wrong, (
        "Un total borné et la courbe qui le couvre donnent deux nombres. C'est ce "
        "que le PDF imprimait sur une seule page.\n" + "\n".join(wrong))


def test_a_bounded_total_still_says_None_when_nothing_was_measured(db) -> None:
    """La correction ne doit pas transformer « rien mesuré » en un zéro affirmatif.

    Une différence de niveaux vaut 0 quand les deux bornes tombent sur le même relevé,
    et 0 se lit « aucune écoute » alors qu'on veut dire « aucune mesure ». La garde
    reste `measured_days`, et ce test la tient.
    """
    import datetime as _dt

    from src.dashboard.utils.platform_timeseries import platform_totals

    aid = _tenants_with_youtube(db)[0] if _tenants_with_youtube(db) else None
    if aid is None:
        pytest.skip("aucun locataire")
    far = platform_totals(db, aid, _dt.date(1990, 1, 1), _dt.date(1990, 12, 31))
    assert set(far.values()) <= {None}, (
        f"une fenêtre sans aucune collecte rend {far} au lieu de None partout — un "
        "zéro y affirmerait qu'il ne s'est rien passé")


def test_the_merged_query_says_exactly_what_the_single_ones_say(db) -> None:
    """Les deux plateformes tiennent en UNE requête, et elle dit la même chose.

    Fusionnées pour le cliquet d'allers-retours de l'accueil — 14 contre un plafond
    de 13 — sur la forme de `v_platform_totals` : un `UNION ALL` avec une colonne
    `platform`.

    Ce test existe parce que la première fusion était FAUSSE et muette. Elle était
    fabriquée par `.replace()` sur les deux requêtes simples ; les CTE se sont
    mélangées, la requête a rendu zéro ligne, et `_rows3` avale les exceptions — donc
    les deux courbes ont disparu de la figure sans un mot dans les logs. C'est la
    forme de défaut la plus chère de ce dépôt : une lecture qui échoue déguisée en
    « rien à lire ». Une comparaison suffit à la voir ; rien d'autre ne la voyait.
    """
    from src.dashboard.utils.platform_timeseries import (
        cumulative_by_platform, soundcloud_cumulative_plays, youtube_cumulative_views,
    )

    tenants = _tenants_with_youtube(db)
    if not tenants:
        pytest.skip("aucun locataire n'a de vue YouTube dans cette base")

    wrong = []
    for aid in tenants:
        merged = cumulative_by_platform(db, aid)
        for key, single in (("youtube", youtube_cumulative_views),
                            ("soundcloud", soundcloud_cumulative_plays)):
            expected = single(db, aid)
            if merged.get(key) != expected:
                wrong.append(
                    f"artiste {aid} / {key} : la requête fusionnée rend "
                    f"{len(merged.get(key) or [])} points, la simple {len(expected)}")
    assert not wrong, (
        "La requête fusionnée ne dit pas ce que disent les deux simples. Une requête "
        "qui échoue rend une liste vide ici — la courbe disparaît sans erreur.\n"
        + "\n".join(wrong))
    assert any(merged.get(k) for k in ("youtube", "soundcloud")), (
        "aucune des deux plateformes ne rend de point : ce test passerait sur deux "
        "listes vides égales, ce qui est exactement le défaut qu'il vise")


# ── « PAR PÉRIODE » : UN SEAU PORTE LA CROISSANCE DU COMPTEUR ──────────────

def test_a_coarse_bucket_carries_the_counter_growth_not_the_measured_deltas() -> None:
    """Le mode « Par période » sous-déclarait un compteur d'un facteur 151.

    Mesuré en production le 2026-09-11, artiste 1, « Depuis le début » (pas
    hebdomadaire) : la somme des seaux YouTube valait **124** quand le compteur avait
    gagné **18 740**. La bande tombait alors à 0,14 % de Spotify, c'est-à-dire sous le
    pixel — « je n'ai aucune data sur YouTube ».

    La raison est celle du cumulé : un écart quotidien n'existe qu'entre deux jours
    CONSÉCUTIFS, et YouTube n'est relevée que 39 % des jours. Mais la croissance d'un
    compteur sur un SEAU se dérive de ses niveaux, exactement comme sur une fenêtre —
    c'est déjà ce que fait `platform_totals` borné, et les deux devaient s'accorder.
    """
    import datetime as _d

    from src.dashboard.utils import platform_chart as pc

    captured = {}
    real_chart, real_caption = pc.st.plotly_chart, pc.st.caption
    pc.st.plotly_chart = lambda fig, **k: captured.__setitem__("fig", fig)
    pc.st.caption = lambda *a, **k: None

    days = [_d.date(2026, 1, 5) + _d.timedelta(days=i) for i in range(70)]
    # Un jour sur sept mesuré : la série quotidienne ne porte AUCUN couple
    # consécutif, donc la somme des écarts vaut 0.
    series = {"spotify": [(d, 10) for d in days],
              "youtube": [(d, 1) for i, d in enumerate(days) if i % 7 == 0]}
    gold = {"youtube": [(days[0], 1_000), (days[-1], 21_000)]}
    try:
        assert pc.render_platform_chart(series, since=days[0], until=days[-1],
                                        step="week", mode="absolute",
                                        cumulative=gold, key="g")
        fig = captured["fig"]
    finally:
        pc.st.plotly_chart, pc.st.caption = real_chart, real_caption

    total = sum(v for t in fig.data if t.name and "YouTube" in t.name
                for v in t.y if v is not None)
    assert total == 20_000, (
        f"les seaux YouTube totalisent {total:,} au lieu des 20 000 que le compteur a "
        "gagnés. Ils additionnent les écarts quotidiens, qui n'existent qu'entre deux "
        "jours consécutifs — en production, 124 au lieu de 18 740.")


def test_the_daily_step_keeps_the_honest_deltas() -> None:
    """La limite du raisonnement, et elle est délibérée.

    Attribuer à UNE journée l'écart observé entre deux relevés distants de neuf jours
    inventerait un pic. À la semaine, l'écart est attribué à la semaine où il a été
    OBSERVÉ — une approximation assumée, dont l'alternative mesurée est de
    sous-déclarer d'un facteur 151. Au jour, on garde les écarts honnêtes, et la note
    « écoutes non traçables » dit ce qui manque.

    Sans ce test, dériver les niveaux à TOUS les pas serait vert.
    """
    import datetime as _d

    from src.dashboard.utils import platform_chart as pc

    captured = {}
    real_chart, real_caption = pc.st.plotly_chart, pc.st.caption
    pc.st.plotly_chart = lambda fig, **k: captured.__setitem__("fig", fig)
    pc.st.caption = lambda *a, **k: None

    days = [_d.date(2026, 1, 5) + _d.timedelta(days=i) for i in range(20)]
    series = {"spotify": [(d, 10) for d in days],
              "youtube": [(d, 1) for i, d in enumerate(days) if i % 7 == 0]}
    gold = {"youtube": [(days[0], 1_000), (days[-1], 21_000)]}
    try:
        pc.render_platform_chart(series, since=days[0], until=days[-1], step="day",
                                 mode="absolute", cumulative=gold, key="g")
        fig = captured.get("fig")
    finally:
        pc.st.plotly_chart, pc.st.caption = real_chart, real_caption

    total = sum(v for t in (fig.data if fig else [])
                if t.name and "YouTube" in t.name
                for v in t.y if v is not None)
    assert total < 1_000, (
        f"au pas du JOUR, YouTube totalise {total:,} : les 20 000 du compteur ont été "
        "attribués à des journées précises, ce qui invente un pic là où on sait "
        "seulement COMBIEN, jamais QUEL JOUR.")
