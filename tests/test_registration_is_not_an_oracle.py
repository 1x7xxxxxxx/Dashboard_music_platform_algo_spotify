"""The registration page must answer nothing to a visitor who has proven nothing.

Installed 2026-08-22 (R23). Four leaks sat on one page, all reachable anonymously:

  * `:332` said "L'email 'x' est déjà enregistré." — account enumeration, one
    request per address, for anyone;
  * `:344-351` validated a promo/referral code and returned EARLY when it was bad,
    so a submit was a free probe into a 24-bit space (`secrets.token_hex(3)`), and a
    hit granted `promo_plan='premium'`;
  * `:385` sent an email from our domain to an address the visitor chose, with no
    budget of any kind;
  * `:408` handed the raw psycopg2 message — constraint and column names — straight
    to the page.

These tests are written against BEHAVIOUR, not against the source. The version that
shipped before this file would have passed any structural check ("does the code call
a throttle?"): what it got wrong was what the page *shows*, so that is what is
compared here — the rendered markdown of two submits, byte for byte.
"""
import os
import re
import uuid

import pytest

from tests.db_gate import requires_live_db

pytestmark = requires_live_db()

_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from src.dashboard.views.register import show
show()
"""


def _app():
    from streamlit.testing.v1 import AppTest

    return AppTest.from_string(_SCRIPT.format(root=os.getcwd()))


def _submit(at, *, email: str, name: str = "Oracle Probe",
            code: str = "", pw: str = "a-long-enough-password-1"):
    """Fill the register form the way a visitor does, and submit it."""
    at.run(timeout=90)
    at.text_input[0].set_value(name)
    at.text_input[1].set_value(email)
    at.text_input[2].set_value(pw)
    at.text_input[3].set_value(pw)
    at.text_input[4].set_value(code)
    at.checkbox[0].set_value(True)   # terms
    at.button[0].click().run(timeout=90)
    return at


def _visible(at, email: str = "") -> str:
    """Everything the page rendered, with the volatile bits neutralised.

    Three things are normalised and nothing else:

      * the address the visitor typed — the page echoes it back, and the visitor
        already knows it, so it carries no information about our database;
      * an incident reference (8 random hex);
      * a Retry-After count.

    Every remaining difference between two renders is a signal an anonymous visitor
    can read, which is exactly what the comparison is for.
    """
    parts = [e.value for e in at.success] + [e.value for e in at.warning] \
        + [e.value for e in at.error] + [e.value for e in at.info]
    text = "\n".join(str(p) for p in parts)
    if email:
        text = text.replace(email, "<email>")
    text = re.sub(r"\b[0-9a-f]{8}\b", "<ref>", text)
    return re.sub(r"\b\d+ seconde", "<n> seconde", text)


class _FakeSMTP:
    """Records what would have been sent. Never opens a socket.

    Not a convenience: without it this module posted real mail through the configured
    Brevo relay, once per submit, to addresses it had invented. Found by running it.
    """

    sent: list[tuple[str, str]] = []

    def __init__(self, *_a, **_kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def starttls(self):
        pass

    def login(self, *_a):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append((msg["To"], msg["Subject"]))


@pytest.fixture(autouse=True)
def _no_real_smtp(monkeypatch):
    """Both senders take the SUCCESS path, over a socket that does not exist."""
    import src.utils.verification_email as ve

    _FakeSMTP.sent = []
    monkeypatch.setattr(ve.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(ve, "_smtp_config", lambda: {
        "host": "smtp.invalid", "port": 587, "user": "u", "password": "p",
        "from_name": "streaMLytics", "from_email": "noreply@streamlytics.test",
    })
    yield _FakeSMTP


@pytest.fixture
def taken_email():
    """An address that already has an account, cleaned up afterwards."""
    from src.dashboard.utils import get_db_connection
    from src.dashboard.views.register import _create_artist_and_user

    suffix = uuid.uuid4().hex[:10]
    email = f"{suffix}@example.test"
    db = get_db_connection()
    user_id, artist_id = _create_artist_and_user(
        db, artist_name=f"Taken {suffix}", slug=f"taken-{suffix}",
        username=f"taken_{suffix}", email=email,
        pw="a-long-enough-password-1", token=f"tok-{suffix}",
    )
    db.close()
    yield email
    db = get_db_connection()
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


@pytest.fixture(autouse=True)
def _fresh_budget():
    """Each test starts with a full per-IP budget.

    The limiter is module state shared by the whole process, and AppTest has no
    request headers, so every test in this file lands in the same "unknown" bucket.
    Without this, test order would decide which assertions run.
    """
    from src.dashboard.utils import throttle

    for lim in throttle._LIMITERS.values():
        lim._hits.clear()
    yield
    for lim in throttle._LIMITERS.values():
        lim._hits.clear()


@pytest.fixture
def cleanup_emails():
    """Delete any account the test created, by email."""
    created: list[str] = []
    yield created
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    for email in created:
        rows = db.fetch_query("SELECT id, artist_id FROM saas_users WHERE email = %s",
                              (email,))
        for user_id, artist_id in rows:
            db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
            if artist_id:
                db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    db.close()


def test_a_taken_address_renders_exactly_what_a_free_one_renders(taken_email,
                                                                 cleanup_emails):
    """The whole point. Any difference here is the enumeration oracle.

    Both submits go through `_render_success`, and the fixture leaves SMTP
    unconfigured, so both land on the same "created, but no mail went out" branch.
    That equality is the property; which of the two branches it settles on is not.
    """
    fresh = f"{uuid.uuid4().hex[:10]}@example.test"
    cleanup_emails.append(fresh)

    free_render = _visible(_submit(_app(), email=fresh), fresh)
    taken_render = _visible(_submit(_app(), email=taken_email), taken_email)

    assert free_render == taken_render, (
        "the page distinguishes a registered address from a free one:\n"
        f"  free  → {free_render!r}\n"
        f"  taken → {taken_render!r}\n"
        "An anonymous visitor reads that difference one address at a time."
    )
    # Non-vacuity, and specifically NOT "is it non-empty": two identical *validation
    # errors* also compare equal. This test passed on a rejected password before the
    # assertion below existed, which is exactly the failure mode the whole file is
    # about — a check that is true of nothing.
    assert "Compte créé" in free_render or "Account created" in free_render, (
        f"the fresh submit did not reach the success path: {free_render!r}. "
        "Whatever the two renders agree on, it is not the thing under test."
    )


def test_a_taken_address_creates_no_second_account(taken_email):
    """Answering identically must not mean answering by creating a duplicate."""
    from src.dashboard.utils import get_db_connection

    db = get_db_connection()
    before = db.fetch_query("SELECT COUNT(*) FROM saas_users WHERE email = %s",
                            (taken_email,))[0][0]
    db.close()

    _submit(_app(), email=taken_email)

    db = get_db_connection()
    after = db.fetch_query("SELECT COUNT(*) FROM saas_users WHERE email = %s",
                           (taken_email,))[0][0]
    db.close()
    assert after == before == 1, f"{before} → {after} rows for one address"

    # The identical screen tells the visitor to check an inbox. For the honest case —
    # a user who forgot they had signed up — something must actually arrive there,
    # or closing the oracle has simply made the page lie to them.
    assert (taken_email, "Votre compte streaMLytics existe déjà") in _FakeSMTP.sent, (
        f"nothing was sent to the real owner: {_FakeSMTP.sent!r}"
    )


def test_an_invalid_code_still_costs_a_full_registration(cleanup_emails):
    """A bad code must not short-circuit the submit.

    While validation happened BEFORE creation with an early return, a probe cost one
    HTTP request and left no trace. The account now exists whatever the code was, so
    probing the 24-bit space means creating 16 million accounts through a per-IP
    budget — which is the difference between a weekend and never.
    """
    from src.dashboard.utils import get_db_connection

    email = f"{uuid.uuid4().hex[:10]}@example.test"
    cleanup_emails.append(email)
    _submit(_app(), email=email, code="ZZZZZZ")

    db = get_db_connection()
    rows = db.fetch_query(
        "SELECT a.referred_by_code, a.first_month_discount_pct, a.promo_plan "
        "FROM saas_users u JOIN saas_artists a ON a.id = u.artist_id "
        "WHERE u.email = %s", (email,),
    )
    db.close()
    assert rows, "an invalid code aborted the registration — the probe is free again"
    referred_by, discount, promo_plan = rows[0]
    assert not referred_by, f"a code nobody validated reached the row: {referred_by!r}"
    assert discount == 0, f"an unvalidated code granted a {discount}% discount"
    assert promo_plan == "premium", (
        "the welcome trial did not apply — an invalid code changed the plan outcome, "
        "which is itself an oracle on whether the code exists"
    )


def test_the_page_is_rationed_per_client(cleanup_emails):
    """Every submit sends mail to an address the visitor typed. That must be bounded."""
    from src.dashboard.utils.throttle import REGISTER_MAX

    last = ""
    for _ in range(REGISTER_MAX + 1):
        email = f"{uuid.uuid4().hex[:10]}@example.test"
        cleanup_emails.append(email)
        last = _visible(_submit(_app(), email=email), email)

    assert "Trop de tentatives" in last or "Too many sign-up" in last, (
        f"submit #{REGISTER_MAX + 1} from one client was accepted: {last!r}. "
        "Unbounded, the page is an open relay for one mail per request, from our "
        "domain, to any address."
    )


def test_a_database_failure_does_not_describe_the_schema(cleanup_emails, monkeypatch):
    """psycopg2 names the constraint and the columns it violated. Not to a visitor."""
    import src.dashboard.views.register as reg

    def _boom(*_a, **_kw):
        raise RuntimeError(
            'duplicate key value violates unique constraint "saas_users_email_key" '
            'DETAIL: Key (email)=(x@y.z) already exists.'
        )

    monkeypatch.setattr(reg, "_derive_identifiers", _boom)
    email = f"{uuid.uuid4().hex[:10]}@example.test"
    cleanup_emails.append(email)
    rendered = _visible(_submit(_app(), email=email), email)

    for leaked in ("saas_users_email_key", "unique constraint", "DETAIL", "RuntimeError"):
        assert leaked not in rendered, (
            f"{leaked!r} reached an anonymous page: {rendered!r}"
        )
    assert "<ref>" in rendered, (
        "the generic message carries no reference, so the operator cannot find the "
        "traceback the visitor just hit — that is swallowing, not redacting"
    )
