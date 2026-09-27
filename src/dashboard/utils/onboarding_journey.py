"""The journey of ONE sign-up, stage by stage — account, mail, credentials, first data.

Type: Utility
Uses: saas_users, artist_credentials, etl_run_log (one query)
Triggers: views/onboarding_health.py (one line per tenant)
Persists in: nothing

R270 (owner note L5 : « voir le parcours complet d'un nouvel inscrit »). The health page
said, per platform, whether data arrives; nothing said WHERE a new sign-up stopped — the
account created but the mail never opened, the mail verified but no credential, a
credential but no row. Each stage is read from what the stage WRITES, never from a flag
set by the page that asks for it.
"""
from __future__ import annotations

# ONE query for every tenant on the page — this page already pays an N+1 (R266).
_SQL = """
SELECT a.id, u.created, u.verified, c.first_cred, e.first_data
FROM unnest(%s::int[]) AS a(id)
LEFT JOIN (SELECT artist_id, min(created_at) AS created, bool_or(email_verified) AS verified
           FROM saas_users GROUP BY artist_id) u ON u.artist_id = a.id
LEFT JOIN (SELECT artist_id, min(created_at) AS first_cred
           FROM artist_credentials GROUP BY artist_id) c ON c.artist_id = a.id
LEFT JOIN (SELECT artist_id, min(started_at) AS first_data FROM etl_run_log
           WHERE status = 'success' AND rows_inserted > 0 GROUP BY artist_id) e
       ON e.artist_id = a.id
"""


def stages(row) -> list[tuple[str, bool, object]]:
    """[(stage, reached, when)] in journey order; a stage after a missing one is unreached.

    Pure. `row` = (account_at, email_verified, first_credential_at, first_data_at).
    """
    account_at, verified, cred_at, data_at = row if row else (None, None, None, None)
    raw = [("compte", account_at is not None, account_at),
           ("mail vérifié", bool(verified), None),
           ("identifiants", cred_at is not None, cred_at),
           ("première donnée", data_at is not None, data_at)]
    out, blocked = [], False
    for name, reached, when in raw:
        # A later stage can only count once the earlier ones are done: a credential
        # typed by the admin on an unverified account is not the artist's journey.
        reached = reached and not blocked
        blocked = blocked or not reached
        out.append((name, reached, when))
    return out


def read_journeys(db, artist_ids) -> dict[int, list[tuple[str, bool, object]]]:
    """{artist_id: stages} for every tenant given, in one query."""
    rows = db.fetch_query(_SQL, ([int(a) for a in artist_ids],)) or []
    return {int(r[0]): stages(tuple(r[1:])) for r in rows}


def journey_line(journey: list[tuple[str, bool, object]]) -> str:
    """« ✅ compte (12/09) → ✅ mail vérifié → ⬜ identifiants → ⬜ première donnée »."""
    parts = []
    for name, reached, when in journey:
        date = f" ({when:%d/%m})" if reached and hasattr(when, "strftime") else ""
        parts.append(f"{'✅' if reached else '⬜'} {name}{date}")
    return " → ".join(parts)
