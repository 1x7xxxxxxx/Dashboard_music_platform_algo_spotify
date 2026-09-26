"""The age of a row must be measured by the clock that holds the row.

Installed 2026-08-22. `check_freshness` computed `datetime.now() - val` in Python.
`datetime.now()` is NAIVE — it is the CONTAINER's local time — while psycopg2 converts
an aware timestamp to the SESSION timezone when writing into a `timestamp without time
zone` column, and production Postgres runs `Europe/Paris`.

Measured from a container with no `TZ`: SoundCloud reported an age of **-1h** — a row
in the future. It agreed at all only because the scheduler happens to run in Paris.

The direction matters as much as the size: the error is OPTIMISTIC. A genuinely stale
source keeps reading fresh for one or two hours, which is the worst way for a
staleness check to be wrong.

The age is now computed by Postgres in the same statement that reads the value.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.db_gate import requires_live_db

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "src" / "utils" / "freshness_monitor.py"


# ── structural: the second clock must not come back ──────────────────────────

def second_clocks(source: str) -> list[str]:
    """Every argument-less `now()` / `utcnow()` / `today()` a module calls. Pure.

    AST, so the SQL string `now()` Postgres evaluates — the ONE clock — is not a call.
    """
    offenders = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name in ("now", "utcnow", "today") and not node.args:
            offenders.append(f"line {node.lineno}: {name}()")
    return offenders


def test_the_module_does_not_read_a_second_clock():
    """`datetime.now()` anywhere in the age path is the defect, by construction."""
    offenders = second_clocks(MODULE.read_text(encoding="utf-8"))
    assert not offenders, (
        "freshness_monitor reads a clock of its own: " + ", ".join(offenders) + ".\n"
        "The rows live in Postgres and are stored in ITS session timezone; any other "
        "clock is a second one, and the two agree only by coincidence of deployment."
    )


def test_the_age_is_asked_of_postgres():
    src = MODULE.read_text(encoding="utf-8")
    assert "EXTRACT(EPOCH FROM (now() -" in src, (
        "the age is no longer computed in SQL — whatever replaced it is a second clock"
    )


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the Python clock subtracted from a Postgres row is named, in both
    spellings; the age asked of Postgres — `now()` inside SQL — is not."""
    defect = ("from datetime import datetime, date\n"
              "def age(last):\n    return datetime.now() - last\n"
              "def day():\n    return date.today()\n")
    assert sorted(second_clocks(defect)) == ["line 3: now()", "line 5: today()"]
    fixed = ("def age(db, t):\n"
             "    return db.fetch_query('SELECT EXTRACT(EPOCH FROM (now() - MAX(c)))')\n")
    assert second_clocks(fixed) == []


# ── behavioural: against the real database ───────────────────────────────────

class TestAgainstPostgres:
    pytestmark = requires_live_db()

    def test_no_source_reports_a_negative_age(self):
        """A row in the future is impossible; reporting one means two clocks."""
        from src.dashboard.utils import get_db_connection
        from src.utils.freshness_monitor import check_freshness

        db = get_db_connection()
        try:
            negatives = [
                (r["source"], r["age_h"]) for r in check_freshness(db)
                if r["age_h"] is not None and r["age_h"] < 0
            ]
        finally:
            db.close()
        assert not negatives, (
            f"sources with an age in the future: {negatives}. That is the two-clock "
            "defect: the value is stored in Postgres's timezone and compared against "
            "the container's."
        )

    def test_the_age_survives_a_container_timezone_that_differs(self, monkeypatch):
        """The measurement must not move when the PROCESS timezone changes.

        This is the actual failure reproduced: the same database, read from two
        containers with different `TZ`, used to give ages two hours apart.
        """
        import os
        import time

        from src.dashboard.utils import get_db_connection
        from src.utils.freshness_monitor import check_freshness

        db = get_db_connection()
        try:
            monkeypatch.setitem(os.environ, "TZ", "UTC")
            if hasattr(time, "tzset"):
                time.tzset()
            utc_ages = {r["source"]: r["age_h"] for r in check_freshness(db)}

            monkeypatch.setitem(os.environ, "TZ", "Pacific/Kiritimati")  # UTC+14
            if hasattr(time, "tzset"):
                time.tzset()
            far_ages = {r["source"]: r["age_h"] for r in check_freshness(db)}
        finally:
            monkeypatch.delitem(os.environ, "TZ", raising=False)
            if hasattr(time, "tzset"):
                time.tzset()
            db.close()

        drifted = {
            s: (utc_ages[s], far_ages[s]) for s in utc_ages
            if utc_ages[s] is not None and far_ages[s] is not None
            and abs(utc_ages[s] - far_ages[s]) > 0.2
        }
        assert not drifted, (
            f"the reported age moved with the container's timezone: {drifted}. "
            "Two containers reading one database must agree on how old a row is."
        )

    def test_a_known_fresh_source_reads_as_fresh(self):
        """Non-vacuity: the checks above are also true of a monitor returning nothing.

        ⚠️ IL POSE LA LIGNE QU'IL LIT — 2026-09-18, et c'est une correction.

        Cette assertion lisait la base AMBIANTE et demandait qu'au moins une source y
        ait un âge mesurable. Sur un poste de développement c'est toujours vrai ; sur
        une base de CI, fraîchement créée depuis `init_db.sql` et les migrations, elle
        est VIDE — aucune source n'a d'âge, et le test rougit pour une raison qui n'est
        pas son sujet.

        Il a échoué en CI **trois exécutions de suite sans que personne le voie**,
        parce qu'une porte statique rougissait plus tôt et que la suite n'allait jamais
        jusqu'au bout — `une-CI-rouge-cache-tout-ce-qui-suit`, troisième instance dans
        ce dépôt. Il est apparu à la minute où cette porte est redevenue verte.

        Le remède est celui que `check_guards_are_env_independent.py` répète à chaque
        exécution : **poser ce qu'on lit** au lieu de le lire sur la machine. La ligne
        est écrite, mesurée, puis retirée.
        """
        import datetime as _dt

        from src.dashboard.utils import get_db_connection
        from src.utils.freshness_monitor import check_freshness

        db = get_db_connection()
        marqueur = f"ci-freshness-{_dt.datetime.now(_dt.timezone.utc):%H%M%S%f}"
        try:
            db.execute_query(
                "INSERT INTO youtube_channel_history "
                "(channel_id, artist_id, subscriber_count, view_count, collected_at) "
                "VALUES (%s, 1, 0, 0, NOW())", (marqueur,))
            results = check_freshness(db)
            assert results, (
                "check_freshness returned nothing — nothing above is being tested")
            # L'ASSERTION PORTE SUR LA SOURCE QU'ON VIENT D'ÉCRIRE, pas sur « au moins
            # une source ». C'est ce qui rend la ligne posée PORTANTE : sans elle, la
            # valeur lue serait celle de la base ambiante, et le test redeviendrait
            # vert pour une raison qui ne lui appartient pas.
            youtube = next((r for r in results if r["source"] == "YouTube"), None)
            assert youtube is not None, (
                "la source YouTube a disparu de `MONITOR_TARGETS` — ce test pose une "
                "ligne dans `youtube_channel_history` et ne la retrouverait plus.")
            assert youtube["age_h"] is not None, (
                "YouTube n'a pas d'âge mesurable alors qu'une ligne vient d'être POSÉE "
                "avec `collected_at = NOW()` : la colonne d'âge n'est pas lue.")
            assert youtube["age_h"] < 1, (
                f"YouTube est lue à {youtube['age_h']} h alors que la ligne a été "
                "écrite à l'instant — les deux horloges ont divergé.")
        finally:
            try:
                db.execute_query(
                    "DELETE FROM youtube_channel_history WHERE channel_id = %s",
                    (marqueur,))
            except Exception:          # pragma: no cover — le nettoyage ne masque rien
                pass
            db.close()
