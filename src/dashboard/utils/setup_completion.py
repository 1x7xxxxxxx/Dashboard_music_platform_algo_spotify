"""Is this tenant's setup finished? One definition, read by everything that asks.

Type: Utility
Uses: PostgresHandler (one query), PLATFORM_IDENTITIES
Triggers: home._section_onboarding, app._first_run_landing, views/onboarding
Depends on: artist_credentials, etl_run_log, s4a_song_timeline, apple_songs_performance,
    saas_users.show_setup_on_login (migration 082)
Persists in: saas_users.show_setup_on_login (the opt-out only)

Why this module exists
----------------------
The four steps were written inside `home._section_onboarding`, and the landing router
(`app._first_run_landing`) asked a DIFFERENT question — "has this artist declared
nothing at all?" (`all(status == 'todo')`). So a tenant who connected one platform and
came back the next day was declared "past onboarding" by the router while the home page
still showed 1/4. Reported from a real second login on 2026-09-04: « je ne suis plus sur
étapes 1 2 3 » and « impossible de revenir aux différentes étapes de config ».

Two surfaces answering the same question differently is the class this repo keeps
paying for. The rule lives here, once; both surfaces read it.

Everything below the query is pure, so the completion logic is testable without a
database and without Streamlit.
"""
from __future__ import annotations

from typing import NamedTuple, Optional


class Step(NamedTuple):
    """One setup step: is it done, what to call it, and where the button goes."""
    key: str
    done: bool
    page: str


class SetupState(NamedTuple):
    steps: list[Step]
    show_on_login: bool

    @property
    def done_count(self) -> int:
        return sum(1 for s in self.steps if s.done)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def complete(self) -> bool:
        """100 % — every step done. An empty step list is NOT complete.

        `all([])` is True, and an empty list is what a failed read produces. Reading
        "I could not tell" as "finished" would send a tenant who configured nothing
        straight past the setup page, which is the exact bug this module closes.
        """
        return bool(self.steps) and all(s.done for s in self.steps)


# key → the page its button must open. Order is the order the artist sees.
#
# `run` pointed at `trigger_algo` — the Road to Algo ML page — which is Premium-gated:
# a Free artist clicking « Lancer votre première collecte » landed on the paywall.
# The collection is launched from the sidebar button, and the assistant's last step is
# what explains it, so that is where the step goes.
_STEP_PAGES: tuple[tuple[str, str], ...] = (
    ("creds", "credentials"),
    ("s4a", "upload_csv"),
    ("apple", "upload_csv"),
    ("run", "onboarding"),
)

# Labels are callables: `t()` must run at RENDER time, not at import time, or the
# whole app would freeze on whichever language was active when the module loaded.
STEP_LABELS = {
    "creds": lambda: _t("home.onboarding_creds", "🔑 Configurer les credentials API"),
    "s4a":   lambda: _t("home.onboarding_s4a", "📂 Importer un CSV Spotify for Artists"),
    "apple": lambda: _t("home.onboarding_apple", "🍎 Importer un CSV Apple Music"),
    "run":   lambda: _t("home.onboarding_run",
                        "🚀 Lancer votre première collecte de données"),
}


def _t(key: str, default: str) -> str:
    from src.dashboard.utils.i18n import t
    return t(key, default)


def steps_from_counts(has_creds: int, has_csv: int, has_apple: int,
                      has_runs: int, show_on_login: bool = True) -> SetupState:
    """Pure: the four raw counts → the state every surface renders."""
    done = {"creds": bool(has_creds), "s4a": bool(has_csv),
            "apple": bool(has_apple), "run": bool(has_runs)}
    return SetupState(
        steps=[Step(key, done[key], page) for key, page in _STEP_PAGES],
        show_on_login=bool(show_on_login),
    )


def read_setup_state(db, artist_id: int, user_id: Optional[int] = None) -> SetupState:
    """The four counts + the login preference, in ONE round-trip.

    One query on purpose: this runs in the sidebar path, and views here are capped at a
    single connection (`tests/test_view_connection_budget.py`). The caller owns the
    connection and hands it in.

    `has_creds` counts rows carrying a NON-EMPTY identity, never rows: `COUNT(*)` ticked
    the credentials step for a tab the artist opened and saved blank. The field names
    come from the identity registry and are bound as a parameter array — never
    interpolated (cross-cutting rule #8).

    On any read failure it returns NO steps, which `complete` reads as "not finished".
    A tenant is never pushed past their setup because we could not read it.
    """
    from src.utils.tenant_identity import PLATFORM_IDENTITIES

    if db is None or artist_id is None:
        return SetupState(steps=[], show_on_login=True)

    identity_fields = sorted({spec.field for spec in PLATFORM_IDENTITIES.values()})
    rows = db.fetch_query(
        """
        SELECT
            (SELECT COUNT(*) FROM artist_credentials  WHERE artist_id = %s
               AND EXISTS (
                 SELECT 1 FROM jsonb_each_text(COALESCE(extra_config, '{}'::jsonb)) AS kv(k, v)
                 WHERE kv.k = ANY(%s) AND btrim(kv.v) <> ''
               )) AS has_creds,
            (SELECT COUNT(*) FROM s4a_song_timeline   WHERE artist_id = %s LIMIT 1) AS has_csv,
            (SELECT COUNT(*) FROM apple_songs_performance WHERE artist_id = %s LIMIT 1) AS has_apple,
            (SELECT COUNT(*) FROM etl_run_log         WHERE artist_id = %s AND status = 'success') AS has_runs,
            COALESCE((SELECT show_setup_on_login FROM saas_users WHERE id = %s), TRUE)
        """,
        (artist_id, identity_fields, artist_id, artist_id, artist_id, user_id),
    )
    if not rows:
        return SetupState(steps=[], show_on_login=True)
    has_creds, has_csv, has_apple, has_runs, show = rows[0]
    return steps_from_counts(has_creds, has_csv, has_apple, has_runs, show)


def set_show_on_login(db, user_id: int, value: bool) -> bool:
    """Persist the artist's answer. Returns whether it was written."""
    if db is None or user_id is None:
        return False
    db.fetch_query(
        "UPDATE saas_users SET show_setup_on_login = %s WHERE id = %s RETURNING id",
        (bool(value), user_id),
    )
    return True
