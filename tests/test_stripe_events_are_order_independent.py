"""A Stripe event delivered before its checkout is parked and replayed — never lost.

Type: Test
Uses: the REAL router (`src/api/routers/stripe_webhook.py`) through a FastAPI TestClient,
      unsigned (`STRIPE_ALLOW_UNSIGNED=1`, no secret), on the development base
      (localhost:5433), with REAL commits on disposable tenants deleted at teardown.
      The Stripe coupon call is stubbed: nothing leaves.
Depends on: migration 145 (stripe_unmatched_events), 143 (referral_rewards)

Error class: `a-webhook-that-assumes-the-order-of-delivery`.

2026-10-04, test-mode referral run: an `invoice.paid` arrived BEFORE its
`checkout.session.completed`. Every handler resolves the tenant through
`artist_subscriptions.stripe_customer_id`, which only the checkout writes: the invoice
matched nothing, the endpoint answered 200, and the referral month was lost with no trace.
The existing referral tests were green on that defect because their harness SEEDED
`artist_subscriptions` before the invoice — the one thing the real delivery order does
not promise. This file never seeds that table: the checkout writes it, through the router.

Mutation record (2026-10-05, each applied from a cp backup, the line verified changed,
restored from the backup):
- the replay loop removed from `_checkout_completed` → red in
  `test_any_delivery_order_gives_the_same_state[invoice-first]` ("an event is still parked");
- `stripe_unmatched.park` reduced to `return` → red in
  `test_an_event_whose_checkout_never_comes_stays_parked_and_is_reported` (no parked row);
- the subscription branch back to an unchecked UPDATE (no park) → red in
  `test_any_delivery_order_gives_the_same_state[updated-first]` (current_period_end None);
- `lock_customer` reduced to a no-op → red in
  `test_a_concurrent_invoice_and_checkout_lose_nothing` (event left parked, no reward).
"""
from __future__ import annotations

import threading
import time
import uuid

import pytest

T_START, T_END = 1_790_000_000, 1_792_592_000
_CREATED = {"customer.subscription.created": 100, "invoice.paid": 101,
            "customer.subscription.updated": 102, "checkout.session.completed": 103}


def _conn():
    from src.utils.pg_connect import connect
    c = connect()
    c.autocommit = True
    return c


@pytest.fixture()
def db():
    try:
        conn = _conn()
    except Exception:      # noqa: BLE001 — no base, skip like the other live tests
        pytest.skip("no development base (localhost:5433) — `make up`")
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM stripe_unmatched_events LIMIT 0")
        cur.execute("SELECT 1 FROM referral_rewards LIMIT 0")
    except Exception:      # noqa: BLE001
        conn.close()
        pytest.skip("migrations 143/145 not applied — `make migrate`")
    made = {"artists": [], "customers": []}
    try:
        yield cur, made
    finally:
        _cleanup(cur, made)
        conn.close()


def _cleanup(cur, made) -> None:
    ids, customers = made["artists"] or [0], made["customers"] or [""]
    cur.execute("DELETE FROM stripe_unmatched_events WHERE stripe_customer_id = ANY(%s)",
                (customers,))
    cur.execute("DELETE FROM referral_rewards WHERE referrer_artist_id = ANY(%s) "
                "OR referred_artist_id = ANY(%s)", (ids, ids))
    cur.execute("DELETE FROM referral_events WHERE referrer_artist_id = ANY(%s) "
                "OR referred_artist_id = ANY(%s)", (ids, ids))
    for table in ("artist_subscriptions", "subscription_plan_history", "saas_users"):
        cur.execute(f"DELETE FROM {table} WHERE artist_id = ANY(%s)", (ids,))  # noqa: S608
    cur.execute("DELETE FROM saas_artists WHERE id = ANY(%s)", (ids,))


@pytest.fixture()
def stripe_env(monkeypatch):
    """Unsigned delivery, a coupon configured, the coupon call recorded instead of sent."""
    from src.utils import referral_rewards as rr
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("STRIPE_ALLOW_UNSIGNED", "1")
    monkeypatch.setenv("STRIPE_REFERRAL_COUPON_ID", "COUPON_T")
    sent: list = []
    monkeypatch.setattr(rr, "stripe_apply", lambda sub, coupon, *k: sent.append((sub, coupon)))
    return sent


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routers.stripe_webhook import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _tenant(cur, made, tag: str) -> dict:
    key = f"{tag}-{uuid.uuid4().hex[:10]}"
    cur.execute("INSERT INTO saas_artists (name, slug) VALUES (%s, %s) RETURNING id",
                (f"order-test {key}", f"order-test-{key}"))
    aid = cur.fetchone()[0]
    email = f"{key}@order-test.invalid"
    cur.execute("INSERT INTO saas_users (username, email, password_hash, artist_id) "
                "VALUES (%s, %s, 'x', %s)", (key, email, aid))
    made["artists"].append(aid)
    made["customers"].append(f"cus_{key}")
    return {"id": aid, "email": email, "cus": f"cus_{key}", "sub": f"sub_{key}"}


def _event(kind: str, t: dict) -> dict:
    period = {"items": {"data": [{"current_period_start": T_START,
                                  "current_period_end": T_END}]}}
    obj = {
        "checkout.session.completed": {
            "customer": t["cus"], "subscription": t["sub"], "client_reference_id": str(t["id"]),
            "customer_details": {"email": t["email"]}, "metadata": {"plan_name": "premium"}},
        "invoice.paid": {"customer": t["cus"], "billing_reason": "subscription_create",
                         "amount_paid": 1000},
        "customer.subscription.created": {"id": t["sub"], "customer": t["cus"],
                                          "status": "incomplete", **period},
        "customer.subscription.updated": {"id": t["sub"], "customer": t["cus"],
                                          "status": "active", "cancel_at_period_end": False,
                                          **period},
    }[kind]
    return {"id": f"evt_{kind}_{t['cus']}", "type": kind, "created": _CREATED[kind],
            "data": {"object": obj}}


def _send(client, kind: str, t: dict) -> None:
    r = client.post("/webhooks/stripe", json=_event(kind, t))
    assert r.status_code == 200, f"{kind}: {r.status_code} {r.text}"


def _referral(cur, made) -> tuple[dict, dict, object]:
    """A referrer already subscribed through the router, and their referred artist."""
    client = _client()
    referrer, referred = _tenant(cur, made, "parrain"), _tenant(cur, made, "filleul")
    _send(client, "checkout.session.completed", referrer)
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer["id"], referred["id"]))
    return referrer, referred, client


def _state(cur, referrer, referred) -> dict:
    # Compared in SQL, written the same way (`to_timestamp`): the column has no time zone.
    cur.execute("SELECT status, current_period_end, current_period_end = to_timestamp(%s) "
                "FROM artist_subscriptions WHERE artist_id = %s", (T_END, referred["id"]))
    status, period_end, period_is_t_end = cur.fetchone()
    cur.execute("SELECT status FROM referral_rewards WHERE referred_artist_id = %s",
                (referred["id"],))
    rewards = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT count(*) FROM stripe_unmatched_events WHERE stripe_customer_id = %s "
                "AND replayed_at IS NULL", (referred["cus"],))
    return {"status": status, "period_end": period_end, "period_is_t_end": period_is_t_end,
            "rewards": rewards,
            "waiting": cur.fetchone()[0]}


_ORDERS = {
    "invoice-first": ["invoice.paid", "checkout.session.completed"],
    "checkout-first": ["checkout.session.completed", "invoice.paid"],
    "created-first": ["customer.subscription.created", "checkout.session.completed"],
    "updated-first": ["customer.subscription.updated", "checkout.session.completed"],
    "all-before": ["customer.subscription.updated", "invoice.paid",
                   "customer.subscription.created", "checkout.session.completed"],
    "all-after": ["checkout.session.completed", "customer.subscription.created",
                  "customer.subscription.updated", "invoice.paid"],
    "late-created": ["customer.subscription.updated", "checkout.session.completed",
                     "customer.subscription.created"],
}


@pytest.mark.parametrize("order", list(_ORDERS), ids=list(_ORDERS))
def test_any_delivery_order_gives_the_same_state(db, stripe_env, order):
    cur, made = db
    referrer, referred, client = _referral(cur, made)
    for kind in _ORDERS[order]:
        _send(client, kind, referred)
    state = _state(cur, referrer, referred)
    assert state["status"] == "active", f"{order}: {state}"
    assert state["waiting"] == 0, f"{order}: an event is still parked after its checkout"
    if "invoice.paid" in _ORDERS[order]:
        assert state["rewards"] == ["applied"], (
            f"{order}: the referral month the first payment earned is {state['rewards']} — "
            "an invoice.paid delivered before its checkout was dropped, not replayed")
        assert stripe_env == [(referrer["sub"], "COUPON_T")]
    if any(k.startswith("customer.subscription") for k in _ORDERS[order]):
        assert state["period_is_t_end"] is True, (
            f"{order}: current_period_end = {state['period_end']} — a subscription event "
            "delivered before its checkout was dropped, not replayed")


@pytest.mark.parametrize("kind", ["invoice.paid", "customer.subscription.created",
                                  "customer.subscription.updated"])
def test_an_event_whose_checkout_never_comes_stays_parked_and_is_reported(db, stripe_env, kind):
    from src.utils.stripe_unmatched import stale_issues

    cur, made = db
    orphan = _tenant(cur, made, "orphelin")
    _send(_client(), kind, orphan)
    cur.execute("SELECT event_type, payload FROM stripe_unmatched_events "
                "WHERE stripe_customer_id = %s AND replayed_at IS NULL", (orphan["cus"],))
    rows = cur.fetchall()
    assert [r[0] for r in rows] == [kind], f"{kind} for an unknown customer was not parked"
    assert "email" not in str(rows[0][1]), "the parked payload keeps more than replay reads"

    def fetch(sql, params):
        cur.execute(sql, params)
        return cur.fetchall()

    def mine():
        return [i for i in stale_issues(fetch) if orphan["cus"] in i["artist_name"]]

    assert mine() == [], "a park younger than the threshold is not an incident yet"
    cur.execute("UPDATE stripe_unmatched_events SET received_at = now() - interval '2 hours' "
                "WHERE stripe_customer_id = %s", (orphan["cus"],))
    issues = mine()
    assert len(issues) == 1 and kind in issues[0]["reason"], (
        f"a {kind} parked for 2 h is not reported by the evening check: {issues}")


def test_what_replay_gives_no_value_to_is_not_parked(db, stripe_env):
    cur, made = db
    orphan = _tenant(cur, made, "renouvellement")
    client = _client()
    for invoice in ({"billing_reason": "subscription_cycle", "amount_paid": 1000},
                    {"billing_reason": "subscription_create", "amount_paid": 0}):
        evt = {"id": f"evt_{uuid.uuid4().hex}", "type": "invoice.paid", "created": 1,
               "data": {"object": {"customer": orphan["cus"], **invoice}}}
        assert client.post("/webhooks/stripe", json=evt).status_code == 200
    for kind in ("invoice.payment_failed", "customer.subscription.deleted", "charge.refunded"):
        evt = {"id": f"evt_{uuid.uuid4().hex}", "type": kind, "created": 1,
               "data": {"object": {"customer": orphan["cus"]}}}
        assert client.post("/webhooks/stripe", json=evt).status_code == 200
    cur.execute("SELECT count(*) FROM stripe_unmatched_events WHERE stripe_customer_id = %s",
                (orphan["cus"],))
    assert cur.fetchone()[0] == 0, "a renewal, a 0 € invoice or a cancellation was parked"


def test_a_concurrent_invoice_and_checkout_lose_nothing(db, stripe_env, monkeypatch):
    """The invoice holds its transaction open between "no row" and its park; the checkout
    runs in that window. Without the per-customer lock the checkout reads an empty park
    list, both commit, and the parked invoice is never replayed."""
    from src.utils import stripe_unmatched

    cur, made = db
    referrer, referred, _ = _referral(cur, made)
    real_park, parking = stripe_unmatched.park, threading.Event()

    def slow_park(*args, **kwargs):
        parking.set()
        time.sleep(1.5)
        return real_park(*args, **kwargs)

    monkeypatch.setattr(stripe_unmatched, "park", slow_park)
    errors: list = []

    def deliver_invoice():
        try:
            _send(_client(), "invoice.paid", referred)
        except Exception as exc:      # noqa: BLE001 — reported by the main thread
            errors.append(exc)

    worker = threading.Thread(target=deliver_invoice)
    worker.start()
    assert parking.wait(10), "the invoice never reached its park"
    _send(_client(), "checkout.session.completed", referred)
    worker.join(20)
    assert not errors, errors
    state = _state(cur, referrer, referred)
    assert state["waiting"] == 0 and state["rewards"] == ["applied"], (
        f"concurrent delivery lost the invoice: {state}")


def test_a_coupon_error_during_replay_does_not_fail_the_checkout(db, stripe_env, monkeypatch):
    from src.utils import referral_rewards as rr

    def refuse(*_a):
        raise RuntimeError("No such coupon: COUPON_T")

    cur, made = db
    referrer, referred, client = _referral(cur, made)
    monkeypatch.setattr(rr, "stripe_apply", refuse)
    _send(client, "invoice.paid", referred)
    _send(client, "checkout.session.completed", referred)     # asserts 200, not 5xx
    cur.execute("SELECT status, detail FROM referral_rewards WHERE referred_artist_id = %s",
                (referred["id"],))
    status, detail = cur.fetchone()
    assert status == "pending" and "stripe" in (detail or ""), (status, detail)
    assert _state(cur, referrer, referred)["waiting"] == 0


def test_the_detector_sees_the_defect_it_is_written_for(db, stripe_env, monkeypatch):
    """The 2026-10-04 defect, fabricated on every run: an event for an unknown customer
    dropped instead of parked. The harness above must see the lost month."""
    from src.utils import stripe_unmatched
    monkeypatch.setattr(stripe_unmatched, "park", lambda *a, **k: None)
    cur, made = db
    referrer, referred, client = _referral(cur, made)
    for kind in _ORDERS["invoice-first"]:
        _send(client, kind, referred)
    assert _state(cur, referrer, referred)["rewards"] == [], (
        "with `park` disabled, an invoice.paid before its checkout must be lost — "
        "otherwise the order test above proves nothing")


@pytest.mark.parametrize("kind", ["customer.subscription.deleted", "invoice.payment_failed",
                                  "customer.subscription.updated"])
def test_an_event_for_a_previous_subscription_leaves_the_current_one_alone(db, stripe_env,
                                                                            kind):
    """R370 d — a customer resubscribed (new subscription id); a late cancellation or
    payment failure of the OLD subscription must not touch the current row."""
    cur, made = db
    t = _tenant(cur, made, "reabonne")
    client = _client()
    _send(client, "checkout.session.completed", t)
    old = f"{t['sub']}_old"
    obj = ({"id": old, "customer": t["cus"], "status": "canceled"}
           if kind.startswith("customer.")
           else {"customer": t["cus"],
                 "parent": {"subscription_details": {"subscription": old}}})
    evt = {"id": f"evt_{uuid.uuid4().hex}", "type": kind, "created": 1,
           "data": {"object": obj}}
    assert client.post("/webhooks/stripe", json=evt).status_code == 200
    cur.execute("SELECT status FROM artist_subscriptions WHERE artist_id = %s", (t["id"],))
    assert cur.fetchone()[0] == "active", (
        f"a {kind} for the customer's PREVIOUS subscription changed the current one")
    evt["id"] = f"evt_{uuid.uuid4().hex}"
    evt["data"]["object"] = {**obj, "id": t["sub"]} if kind.startswith("customer.") else {
        "customer": t["cus"], "subscription": t["sub"]}
    assert client.post("/webhooks/stripe", json=evt).status_code == 200
    cur.execute("SELECT status FROM artist_subscriptions WHERE artist_id = %s", (t["id"],))
    assert cur.fetchone()[0] != "active", f"a {kind} for the CURRENT subscription was ignored"
