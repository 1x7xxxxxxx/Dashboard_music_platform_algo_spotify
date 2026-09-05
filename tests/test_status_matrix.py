"""The setup matrix: five platforms, three boxes, and zero API calls to draw it.

Installed 2026-08-22. Before it, four surfaces each drew their own indicator and none
of them answered the question an artist actually asks — "is MY SoundCloud working?".
The credentials KPI strip came closest and got two things wrong: its second axis was
the FLEET's Airflow state (🟢 while this tenant had zero rows), and it iterated the
four form TABS, so Instagram — a platform everywhere else — had no column at all.

The three properties below are the ones that keep it honest:

  * drawing it costs nothing. Streamlit reruns the page on every widget interaction;
    a matrix that probed on render would be five API calls per click per tenant;
  * a platform nobody measured shows `?`, never a ✅. "Not measured" and "measured
    and fine" must not look alike — the same rule as `probe_ran` in the nightly path;
  * all five platforms appear, because the missing fifth is the defect it exists to
    surface.
"""
from __future__ import annotations

import ast
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "src" / "dashboard" / "utils" / "status_matrix.py"


# ── structural ───────────────────────────────────────────────────────────────

def test_the_renderer_opens_no_connection_of_its_own():
    """It is called from pages already capped at one connection each."""
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    opens = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "get_db_connection"]
    assert not opens, (
        f"status_matrix opens a database connection at line(s) {opens}. Every view "
        "that renders it is capped at one by tests/test_view_connection_budget.py, "
        "and they have already spent theirs — the caller hands `db` in."
    )


def test_rendering_never_calls_a_probe():
    """AST, not text.

    The first version of this searched the function body for the string `probe=`
    and matched the COMMENT that explains why it is absent. That mistake happened
    four times in one session; a guard that its own documentation can trip is not
    reading the code.
    """
    src = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    render = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "render_status_matrix")

    probed = [
        n.lineno for n in ast.walk(render)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", getattr(n.func, "attr", "")) == "artist_readiness"
        and any(kw.arg == "probe" for kw in n.keywords)
    ]
    assert not probed, (
        f"render_status_matrix passes a probe into artist_readiness (line {probed}) "
        "— that is one API call per red platform on every Streamlit rerun"
    )

    reaches = [
        n.lineno for n in ast.walk(render)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        and "platform_probes" in (getattr(n, "module", "") or
                                  " ".join(a.name for a in n.names))
    ]
    assert not reaches, (
        f"the render path imports the live probe directly (line {reaches})"
    )


# ── behavioural, against the real database ───────────────────────────────────

class TestMatrix:
    pytestmark = requires_live_db()

    @pytest.fixture
    def tenant(self):
        from src.dashboard.utils import get_db_connection

        db = get_db_connection()
        slug = f"matrix-{uuid.uuid4().hex[:10]}"
        artist_id = db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug))[0][0]
        yield db, artist_id
        db.execute_query("DELETE FROM tenant_platform_probe WHERE artist_id = %s",
                         (artist_id,))
        db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s",
                         (artist_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
        db.close()

    def _render(self, db, artist_id, **kw):
        """Render through Streamlit's bare mode and return the readiness rows."""
        from src.dashboard.utils.status_matrix import render_status_matrix
        return render_status_matrix(db, artist_id, **kw)

    def test_an_empty_tenant_renders_five_platforms_to_connect(self, tenant):
        db, artist_id = tenant
        rows = self._render(db, artist_id, allow_probe=False)
        assert len(rows) == 5, f"expected 5 platforms, got {[r['key'] for r in rows]}"
        assert {r["key"] for r in rows} == {
            "soundcloud", "spotify", "youtube", "meta", "instagram"}
        assert all(r["status"] == "todo" for r in rows), (
            "a tenant with nothing declared must read 'à connecter' everywhere"
        )

    def test_instagram_is_present(self, tenant):
        """The one the KPI strip dropped, and the reason this matrix exists."""
        db, artist_id = tenant
        rows = self._render(db, artist_id, allow_probe=False)
        assert "instagram" in {r["key"] for r in rows}

    def test_rendering_makes_no_api_call(self, tenant, monkeypatch):
        """The load-bearing one. A rerun must be free."""
        import src.utils.platform_probes as pp

        calls = []
        monkeypatch.setattr(pp, "probe",
                            lambda *a, **k: calls.append(a) or (False, "x"))

        db, artist_id = tenant
        # Declare an identity that will never produce data → a RED platform, which
        # is exactly the case that tempts a probe.
        db.execute_query(
            "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
            "VALUES (%s, 'soundcloud', %s::jsonb)", (artist_id, '{"user_id": "1"}'))
        self._render(db, artist_id, allow_probe=False)

        assert calls == [], (
            f"{len(calls)} API call(s) fired just by drawing the page. Streamlit "
            "reruns on every interaction — that is five calls per click per tenant."
        )

    def test_a_remembered_verdict_is_shown_and_an_absent_one_is_not_invented(self,
                                                                             tenant):
        from src.dashboard.utils.status_matrix import _responds_cell, read_probes

        db, artist_id = tenant
        db.execute_query(
            "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
            "VALUES (%s, 'soundcloud', %s::jsonb)", (artist_id, '{"user_id": "1"}'))
        rows = self._render(db, artist_id, allow_probe=False)
        sc = next(r for r in rows if r["key"] == "soundcloud")

        # Nothing remembered yet.
        state, glyph, _tip = _responds_cell(sc, read_probes(db, artist_id))
        assert glyph == "?" and state == "grey", (
            "an unmeasured platform must show '?', never a tick — 'not measured' and "
            "'measured and fine' looking alike is the whole class of defect here"
        )

        # Now remember a failure, as the nightly run would.
        from src.dashboard.utils.status_matrix import save_probe
        save_probe(db, artist_id, "soundcloud", False, "aucun titre public")
        state, glyph, tip = _responds_cell(sc, read_probes(db, artist_id))
        assert state == "red" and glyph == "✖"
        assert "aucun titre public" in tip, (
            "the remembered reason is not shown — the artist would read a generic "
            "hint while the alert email carries the real sentence"
        )

    def test_arriving_data_counts_as_proof_without_a_probe(self, tenant):
        """Freshness is the proof; the probe is only the explainer."""
        from src.dashboard.utils.status_matrix import _responds_cell

        fresh = {"key": "youtube", "status": "ok"}
        state, glyph, _ = _responds_cell(fresh, {})
        assert state == "green" and glyph == "✅", (
            "a platform whose rows are arriving still asks to be probed — that is an "
            "API call to learn what the data already proved"
        )

    def test_a_stale_verdict_still_says_when_it_was_taken(self, tenant):
        from src.dashboard.utils.status_matrix import (
            _responds_cell, read_probes, save_probe,
        )

        db, artist_id = tenant
        save_probe(db, artist_id, "meta", False, "compte inaccessible")
        db.execute_query(
            "UPDATE tenant_platform_probe SET probed_at = %s "
            "WHERE artist_id = %s AND platform = 'meta'",
            (datetime.now(timezone.utc) - timedelta(days=9), artist_id))
        _s, _g, tip = _responds_cell({"key": "meta", "status": "no_data"},
                                     read_probes(db, artist_id))
        assert "9 j" in tip or "9 d" in tip, (
            f"the age of the measurement is missing from {tip!r} — a nine-day-old "
            "verdict read as today's is worse than no verdict"
        )

    def test_the_compact_form_renders_too(self, tenant):
        """The home banner uses it; it must survive an empty tenant."""
        db, artist_id = tenant
        rows = self._render(db, artist_id, compact=True, allow_probe=False)
        assert len(rows) == 5


# ── La précédence « la mesure bat la prédiction », mise sous tension ─────────
# Ajouté le 2026-09-05. Les tests ci-dessus passent `{}` comme mémoire de sondes ou
# n'insèrent aucune ligne de données : la précédence `status > probes` de
# `_responds_cell` n'était donc JAMAIS exercée, et le défaut est passé au travers.

def test_arriving_data_outranks_a_probe_that_says_otherwise():
    """Statut vert ET sonde rouge — la combinaison du rapport du 2026-09-05.

    358 lignes collectées pour ce locataire, et la sonde qui répond « aucun titre
    public ». La donnée doit gagner, et la raison de la sonde ne doit pas remonter
    dans l'infobulle d'une source qui livre.
    """
    from datetime import datetime, timezone

    from src.dashboard.utils.status_matrix import _responds_cell

    red = {"soundcloud": (False, "aucun titre public", datetime.now(timezone.utc), None)}
    for status in ("ok", "stale", "quiet"):
        state, _glyph, tip = _responds_cell({"key": "soundcloud", "status": status}, red)
        assert state != "red", f"{status} : la prédiction a battu la mesure"
        assert "aucun titre public" not in tip, (
            f"{status} : l'infobulle porte la raison d'une sonde que la donnée dément")
    # Sans donnée, la sonde reprend la main — sinon on masquerait un vrai échec.
    state, glyph, tip = _responds_cell({"key": "soundcloud", "status": "no_data"}, red)
    assert (state, glyph) == ("red", "✖")
    assert "aucun titre public" in tip


def test_the_next_step_column_is_silent_when_the_data_proves_it():
    """« Prochaine étape » écrasait `next_action` par la raison d'une sonde rouge.

    `next_action(…, OK)` rend `""`, donc une ligne ENTIÈREMENT verte affichait « User
    ID 377065610 joignable, mais aucun titre public » comme prochaine étape. Même
    défaut que `_responds_cell`, dans le même fichier, jamais signalé.

    Lecture STRUCTURELLE : le commentaire au-dessus du garde cite `_DATA_PROVES_IT`,
    donc une recherche de chaîne resterait verte après sa suppression.
    """
    import ast
    import inspect
    import textwrap

    from src.dashboard.utils import status_matrix

    tree = ast.parse(textwrap.dedent(inspect.getsource(status_matrix.render_status_matrix)))
    guarded = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.BoolOp)
        and any(isinstance(c, ast.Compare)
                and any(isinstance(o, ast.NotIn) for o in c.ops)
                and getattr(c.comparators[0], "id", "") == "_DATA_PROVES_IT"
                for c in n.values)
    ]
    assert guarded, (
        "la colonne « Prochaine étape » écrase de nouveau `next_action` par la "
        "raison d'une sonde, sans regarder si des données sont arrivées")
