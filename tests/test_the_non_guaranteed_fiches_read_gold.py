"""The four « non garanti » fiches of the owner's review read gold, or say why not (R289).

- Apple Music top (fiche 6): the raw query put `LIMIT 10` after `ORDER BY song_name` and showed
  the ten ALPHABETICALLY first titles. Now the top 10 by plays, from v_apple_song_cumulative.
- SoundCloud first_seen (fiche 8) and YouTube videos (fiche 13): gold views (migration 144).
- LTV admin (fiche 62): computed from the app's own billing state — marked « état de
  l'application », never green (code-critic): no nightly check covers billing tables.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev" / "charts_dossier"))

import numbers_check  # noqa: E402
from tests.db_gate import db_ready  # noqa: E402


def test_an_admin_figure_on_app_state_is_marked_and_not_green():
    key, why = numbers_check.verdict([{"name": "LTV", "type": "bar"}], "—", [], [], "business")
    assert key == "etat-app" and "contrôles du soir" in why
    assert numbers_check.verdict([{"name": "x", "type": "bar"}], "—", [], [], "plateforme")[0] \
        == "non-garanti"


@pytest.mark.skipif(not db_ready(), reason="the gold views live in the database")
def test_the_youtube_gold_view_is_one_row_per_video_and_tenant():
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    try:
        dup = db.fetch_query("SELECT COUNT(*) FROM (SELECT artist_id, video_id FROM "
                             "v_youtube_video_latest GROUP BY 1, 2 HAVING COUNT(*) > 1) d")[0][0]
        assert dup == 0
        cols = {r[0] for r in db.fetch_query(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'v_soundcloud_track_latest'")}
        assert "first_seen" in cols
    finally:
        db.close()


@pytest.mark.skipif(not db_ready(), reason="the Apple top reads the database")
def test_the_apple_top_is_the_most_played_not_the_first_alphabetically():
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    artist = None
    try:
        slug = f"apple-{uuid.uuid4().hex[:8]}"
        artist = db.fetch_query("INSERT INTO saas_artists (name, slug, tier, active) VALUES "
                                "(%s, %s, 'free', TRUE) RETURNING id", (slug, slug))[0][0]
        for i in range(12):                    # « A00 » plays least, « A11 » most
            db.execute_query(
                "INSERT INTO apple_songs_performance (artist_id, song_name, plays, "
                "shazam_count, snapshot_date) VALUES (%s, %s, %s, 0, CURRENT_DATE)",
                (artist, f"A{i:02d}", 100 + i))
        from src.dashboard.views.apple_music import TOP_QUERY
        top = [r[0] for r in db.fetch_query(TOP_QUERY, (artist,))]
        assert top[0] == "A11" and "A00" not in top, top
    finally:
        if artist:
            db.execute_query("DELETE FROM apple_songs_performance WHERE artist_id = %s", (artist,))
            db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist,))
        db.close()
