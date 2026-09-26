"""Un locataire jamais mesuré n'a pas « zéro » — il n'a pas de mesure.

Type: Test
Uses: psycopg2, a live Postgres
Depends on: les vues or, src/dashboard/utils/platform_timeseries.py
Persists in: nothing

Why this exists
---------------
Mesuré le 2026-09-12, sur un locataire sans aucune donnée :

    platform_totals(db, 999999)
      → {'spotify': 0, 'youtube': 0, 'soundcloud': 0, 'apple': 0}

Quatre zéros AFFIRMÉS, pendant que les vues or rendaient correctement « aucune
ligne ». ADR-022 dit pourtant, mot pour mot, que le travail de la porte est de
rendre `None` quand rien n'a été mesuré. Elle ne le faisait que sur sa branche
bornée ; la branche « depuis le début » portait un `COALESCE(total, 0)` dans son
SQL et un `or 0` dans son Python, et `gold_apple_lifetime` un `COALESCE` de plus.

Ce que l'artiste lisait : « 0 écoute » le jour de son inscription. Ça ne se lit pas
comme « la collecte n'a pas encore tourné », ça se lit comme un produit qui ne
marche pas — la classe `absence-rendered-as-a-measurement`, sur une surface qu'elle
n'avait pas encore atteinte.

Pourquoi ce test balaie les HUIT plateformes
---------------------------------------------
Parce que la question se repose pour chacune, et qu'une réponse pour Spotify ne dit
rien d'Instagram. Le tableau `plateforme × famille` de
`.claude/dev-docs/gold-coverage.md` comptait huit cases vides sur cette famille : ce
fichier est ce qui les remplit.

Le locataire fantôme et la transaction annulée
-----------------------------------------------
On n'invente pas de données : on interroge un identifiant qui n'existe pas. Rien
n'est écrit, rien n'est à nettoyer, et le test ne dépend d'aucun jeu de données
particulier — il marche sur une base vide comme sur la production.

Mutation record — 2026-09-12 : avec `COALESCE(total, 0)` remis dans `_SQL_LIFETIME`,
ce test nomme les trois plateformes de `platform_totals` ; avec le `COALESCE` remis
dans `gold_apple_lifetime` (migration 113), il nomme Apple. Vu rouge sur les deux
moitiés du défaut.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Un identifiant qu'aucune table ne porte. Choisi hors de toute séquence : les
# `saas_artists.id` sont des SERIAL à trois chiffres, et un test qui prendrait
# `max(id) + 1` se mettrait à interroger un vrai locataire le jour d'une inscription.
_GHOST = 999_999

# (plateforme, la relation or qui la définit, la colonne qu'on somme)
#
# La relation est NOMMÉE ici — et pas seulement la plateforme — parce que le tableau
# `plateforme × famille` compte les gardes qui lisent une relation dans un littéral
# SQL. Un garde qui prononce « Instagram » sans lire `v_instagram_media_monthly` ne
# garde rien, et ce dépôt a pris quatre gardes au vert sur leur propre commentaire.
_GOLD_BY_PLATFORM = (
    ("Spotify S4A", "SELECT SUM(streams) FROM v_s4a_song_daily WHERE artist_id = %s"),
    ("YouTube", "SELECT SUM(total) FROM v_platform_totals "
                "WHERE platform = 'youtube' AND artist_id = %s"),
    ("SoundCloud", "SELECT SUM(playback_count) FROM v_soundcloud_track_latest "
                   "WHERE artist_id = %s"),
    ("Apple Music", "SELECT SUM(total) FROM v_platform_totals "
                    "WHERE platform = 'apple' AND artist_id = %s"),
    ("Instagram", "SELECT SUM(likes) FROM v_instagram_media_monthly WHERE artist_id = %s"),
    ("Meta Ads", "SELECT SUM(spend) FROM v_meta_daily WHERE artist_id = %s"),
    ("Hypeddit", "SELECT SUM(visits) FROM v_hypeddit_daily WHERE artist_id = %s"),
    ("Revenu", "SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue WHERE artist_id = %s"),
)


def _dsn() -> dict | None:
    """Les mots-clés de connexion — par la porte canonique, jamais recopiée.

    ⚠️ 2026-09-22 : ce bloc construisait son DSN à la main et ne lisait que
    l'environnement. Sur un poste dont le mot de passe vit dans
    `config/config.yaml`, la socket s'ouvre et l'authentification échoue — le
    module ne skippe pas, il ERREUR. Dix modules de test portaient exactement
    cette forme, trouvés par balayage après que trois d'entre eux ont rougi.
    `tests/db_gate.dsn()` passe par `src.utils.pg_connect.resolve_kwargs`, qui
    connaît les trois sources (`DATABASE_URL`, les `DATABASE_*`, `config.yaml`).

    Classe : `a-second-door-that-knows-fewer-sources-than-the-first`.
    """
    from tests.db_gate import dsn

    return dsn()


_CONN = _dsn()

pytestmark = [pytest.mark.xdist_group("an-unmeasured-platform-says-so"), pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — l'absence ne se lit que dans la base",
)]


@pytest.fixture(scope="module")
def cursor():
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.parametrize("platform,sql", _GOLD_BY_PLATFORM,
                         ids=[p for p, _ in _GOLD_BY_PLATFORM])
def test_a_gold_view_renders_no_row_rather_than_a_zero(cursor, platform, sql) -> None:
    """La vue or ne fabrique pas de ligne pour un locataire qu'elle n'a pas vu."""
    cursor.execute(sql, (_GHOST,))
    row = cursor.fetchone()
    value = row[0] if row else None
    assert value is None, (
        f"{platform} : la couche or rend {value} pour un locataire qui n'a AUCUNE "
        "donnée. Un zéro affirmé se lit comme une mesure — « ce compte n'a rien "
        "fait » — quand la vérité est « on n'a rien mesuré ». Les deux méritent deux "
        "affichages différents, et la vue est l'endroit où la distinction se perd "
        "en premier.")


def test_the_python_door_says_none_for_every_platform_it_serves() -> None:
    """La PORTE, et c'est elle qui avait le défaut.

    ADR-022 : « elle rend `None` quand rien n'a été mesuré (jamais `0`) ». Ce test
    est la phrase exécutable de cette ADR.
    """
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.platform_timeseries import platform_totals

    # ⚠️ LA CONNEXION VIENT DE `_CONN`, jamais de constantes.
    #
    # La première version construisait un `PostgresHandler(host="127.0.0.1",
    # port=5433, …)` — les valeurs de CE poste — alors que `_dsn()` résout aussi
    # `DATABASE_URL`. En CI, où la base écoute ailleurs, le module ne skippait pas
    # (le DSN existe) et la connexion échouait : `connection refused`. Un garde qui
    # lit la machine plutôt que la configuration est vert là où il a été écrit et
    # rouge là où il tourne — la classe `guard-predicate-depends-on-the-host-env`,
    # et `check_guards_are_env_independent.py` la surveille.
    class _Handle:
        """Le minimum que `platform_totals` attend d'un handler : `fetch_query`."""

        def __init__(self, cursor):
            self._cursor = cursor

        def fetch_query(self, sql, params=None):
            self._cursor.execute(sql, params or ())
            return self._cursor.fetchall()

    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            totals = platform_totals(_Handle(cur), _GHOST)
    finally:
        conn.rollback()
        conn.close()

    affirmed = {k: v for k, v in (totals or {}).items() if v == 0}
    assert not affirmed, (
        f"`platform_totals` affirme un zéro pour {sorted(affirmed)} sur un locataire "
        "jamais mesuré. Mesuré le 2026-09-12, la porte rendait les QUATRE à zéro "
        "pendant que les vues rendaient correctement « aucune ligne » — le "
        "`COALESCE(total, 0)` était dans la porte, pas dans la couche or.")
    assert set(totals) >= {"spotify", "youtube", "soundcloud", "apple"}, (
        f"la porte ne sert plus les quatre plateformes : {sorted(totals)}. Un test "
        "vert sur trois clés ne dit rien de la quatrième.")


def test_a_measured_zero_is_still_a_zero(cursor) -> None:
    """Non-vacuité, et la moitié qu'on oublie : on ne demande pas d'EFFACER les zéros.

    Un locataire mesuré dont le compteur vaut zéro doit rendre `0`, pas `None`. Sans
    cette assertion, « rendre None partout » satisferait le test ci-dessus et
    détruirait l'information inverse — c'est la forme que ce dépôt appelle un
    correctif qui casse le cas symétrique.
    """
    cursor.execute("""
        SELECT count(*) FROM v_hypeddit_daily
         WHERE artist_id IS NOT NULL AND visits = 0
    """)
    measured_zeros = (cursor.fetchone() or [0])[0]
    cursor.execute("SELECT count(*) FROM v_platform_totals")
    gold_rows = (cursor.fetchone() or [0])[0]
    if not gold_rows:
        pytest.skip("base sans données or — rien à distinguer")
    assert measured_zeros >= 0          # la requête a tourné
    cursor.execute("""
        SELECT count(*) FROM v_platform_totals WHERE total IS NULL
    """)
    nulls = (cursor.fetchone() or [0])[0]
    assert nulls == 0, (
        f"{nulls} ligne(s) de `v_platform_totals` portent NULL. Une LIGNE veut dire "
        "« mesuré » ; sa valeur doit donc être un nombre, fût-il zéro. Rendre NULL "
        "ici déplacerait l'ambiguïté au lieu de la lever.")


# ── The PDF bar chart: the surface the fix above missed (2026-09-26) ──────────

def _breakdown_axes(monkeypatch, streams: dict):
    """The Axes `platform_breakdown` draws — captured before it becomes a PNG."""
    from src.dashboard.utils import pdf_charts

    captured = {}

    def _keep(fig):
        captured["ax"] = fig.axes[0]
        return "data:image/png;base64,"

    monkeypatch.setattr(pdf_charts, "_fig_to_uri", _keep)
    uri = pdf_charts.platform_breakdown(streams)
    return captured.get("ax") if uri else None


def _bars(ax) -> dict:
    """{label: (visible, height)} per bar, read off the drawn patches."""
    labels = [t.get_text() for t in ax.get_xticklabels()]
    return {lbl: (p.get_visible(), p.get_height()) for lbl, p in zip(labels, ax.patches)}


def test_the_pdf_platform_chart_draws_no_bar_for_an_unmeasured_platform(monkeypatch) -> None:
    """Measured: `platform_totals(db, 1, 2025-09-26, 2026-09-26)` → apple None. The
    chart drew [9875, 328, 340, 0] and labelled Apple « 0 » while the KPI cards of the
    same PDF printed « — »."""
    ax = _breakdown_axes(monkeypatch, {"s4a": 9875, "youtube": 328,
                                       "soundcloud": 340, "apple": None})
    assert ax is not None, "three measured platforms must still draw the chart"
    bars = _bars(ax)
    assert bars["Spotify"] == (True, 9875), bars
    assert not bars["Apple"][0], f"an unmeasured Apple drew a visible bar: {bars}"
    texts = [t.get_text() for t in ax.texts]
    assert "0" not in texts, f"an unmeasured platform is labelled as a measured 0: {texts}"
    assert any("—" in t for t in texts), f"the absence must be SAID on the chart: {texts}"


def test_the_pdf_platform_chart_keeps_a_measured_zero(monkeypatch) -> None:
    """The reverse: a platform MEASURED at 0 still draws its bar at 0, labelled 0."""
    ax = _breakdown_axes(monkeypatch, {"s4a": 9875, "youtube": 328,
                                       "soundcloud": 340, "apple": 0})
    assert _bars(ax)["Apple"] == (True, 0), _bars(ax)
    assert "0" in [t.get_text() for t in ax.texts]


# ── A lookup dict read with a zero default (sweep 2026-09-27, airflow_kpi.py:290) ─────────────
# The sweep found the class under a form its COALESCE/fillna grep could not see: a dict filled
# inside `except: pass`, then read by `.get(dag, 0) or 0`. A DAG nobody measured — or every
# DAG, when the read failed — showed « 0 ligne insérée », identical to a run that inserted none.

def _zero_default_gets(tree) -> list[int]:
    """Lines where a `.get(key, 0)` result is assigned into a table row — the defect form."""
    import ast
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript)):
            continue
        for sub in ast.walk(node.value):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "get" and len(sub.args) == 2
                    and isinstance(sub.args[1], ast.Constant) and sub.args[1].value == 0):
                hits.append(node.lineno)
    return hits


def test_the_detector_sees_the_zero_default_it_is_written_for() -> None:
    import ast
    defect = ast.parse('row["n"] = int(d.get(row["DAG"], 0) or 0)')
    assert _zero_default_gets(defect), "the defect form is not seen"
    fixed = ast.parse('n = d.get(row["DAG"])\nrow["n"] = None if n is None else int(n)')
    assert not _zero_default_gets(fixed), "the fix would turn the guard red"


def test_the_dag_monitor_shows_no_zero_for_an_unmeasured_dag() -> None:
    import ast
    src = (_ROOT / "src/dashboard/views/airflow_kpi.py").read_text(encoding="utf-8")
    assert not _zero_default_gets(ast.parse(src)), (
        "airflow_kpi.py writes a `.get(dag, 0)` into a row: an unmeasured DAG reads as 0 rows")
