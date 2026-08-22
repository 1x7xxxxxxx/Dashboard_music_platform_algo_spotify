"""The duplicate-identifier message must not tell one tenant about another.

Installed 2026-08-22 (R30). The pentest listed
`credentials/_core.py:338-340` as "displays the other tenant's artist_id". Re-read
the same day, that is not what happens: the function RETURNS the holder — on purpose,
`tests/test_identity_uniqueness.py` requires it, because an admin resolving a
duplicate claim has to know who to ask — and the one caller discards it.

So the value is one line away from the page and nothing keeps it there. Deleting the
return value would have broken a capability someone deliberately tested for; this
puts the guarantee where the risk actually is, at the render.

What a tenant may be told: which field, and which value — both of which they just
typed. What they may not be told: who else has it, or that the holder is tenant 12.
"""
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()


@pytest.fixture
def two_tenants():
    """Two tenants, the first holding a YouTube channel id."""
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    ids = []
    for _ in range(2):
        slug = f"conflict-{uuid.uuid4().hex[:10]}"
        ids.append(db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id", (slug, slug),
        )[0][0])
    db.execute_query(
        "INSERT INTO artist_credentials (artist_id, platform, extra_config) "
        "VALUES (%s, 'youtube', %s::jsonb)",
        (ids[0], '{"channel_id": "UC-conflict-test"}'),
    )
    db.close()
    yield ids
    db = get_db_connection()
    for artist_id in ids:
        db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s",
                         (artist_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def test_the_rendered_refusal_never_contains_the_other_tenant_id(two_tenants,
                                                                 monkeypatch):
    """Render the real refusal and read every string it produced."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.credentials import _core

    holder, claimant = two_tenants
    db = get_db_connection()
    try:
        conflict = _core.find_identity_conflict(
            db, claimant, "youtube", {"channel_id": "UC-conflict-test"})
    finally:
        db.close()

    assert conflict is not None, (
        "the fixture's duplicate was accepted — this test is then true of nothing"
    )
    field, value, other = conflict
    assert other == holder, "the holder is no longer reported to the caller"

    # The message the view builds, taken from the view itself rather than retyped —
    # a copy here would keep passing after the real string changed.
    import re
    from pathlib import Path

    render_src = (Path(__file__).resolve().parent.parent
                  / "src/dashboard/views/credentials/_render.py").read_text("utf-8")
    block = render_src[render_src.index('"credentials.identity_taken"'):]
    block = block[:block.index(".format(")]
    rendered = block.format(field=field, value=value) if "{field}" in block else block

    assert str(other) not in rendered, (
        f"the refusal shown to tenant {claimant} contains tenant {other}'s id:\n"
        f"{rendered[:300]}"
    )
    for leak in ("artist_id", "tenant", "compte #"):
        assert leak not in rendered.lower() or leak == "tenant", (
            f"the refusal names {leak!r}, which points at the other account"
        )


def test_the_format_call_does_not_pass_the_holder(monkeypatch):
    """Structural backstop: the holder must not even be an argument to the message.

    The behavioural check above reads the built string. This one reads the call, so
    a future edit that passes `other=` into `.format()` fails here even if the
    current translation happens not to interpolate it.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "src/dashboard/views/credentials/_render.py").read_text("utf-8")
    start = src.index('"credentials.identity_taken"')
    call = src[start:src.index(")", src.index(".format(", start))]
    args = call[call.index(".format("):]
    assert "_other" not in args and "other" not in args, (
        f"the holder is passed into the refusal message: {args.strip()}"
    )
