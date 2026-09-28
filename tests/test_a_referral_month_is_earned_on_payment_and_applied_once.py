"""R272 — the referral month: earned on the referred artist's FIRST payment, applied as a
Stripe coupon on the referrer's subscription, once, whatever Stripe retries.

Type: Test
Uses: src/utils/referral_rewards.py on the development base (localhost:5433), inside a
      transaction that is ROLLED BACK — nothing stays, no Stripe call leaves (stubbed)

Code-critic verdict (R272 a): an idempotency table, the first-payment discriminant
(`billing_reason`), a referrer without a Stripe customer (pending), the counter reconciled,
and a guard that reads what is WRITTEN — these tests read the rows, not the calls.

Mutation record (2026-09-28) : the `ON CONFLICT DO NOTHING RETURNING` check removed (a
retry credits twice) → red ; the `billing_reason` test removed (a renewal earns) → red ;
the « one applied at a time » check removed → red.
"""
from __future__ import annotations

import pytest

from src.utils import referral_rewards as rr


@pytest.fixture()
def cur():
    try:
        from src.utils.pg_connect import connect
        conn = connect()
    except Exception:      # noqa: BLE001 — no base, skip like the other live tests
        pytest.skip("no development base (localhost:5433) — `make up`")
    conn.autocommit = False
    c = conn.cursor()
    try:
        c.execute("SELECT 1 FROM referral_rewards LIMIT 0")
    except Exception:      # noqa: BLE001
        conn.rollback()
        conn.close()
        pytest.skip("migration 143 not applied — `make migrate`")
    try:
        yield c
    finally:
        conn.rollback()
        conn.close()


def _artist(cur, name):
    cur.execute("INSERT INTO saas_artists (name, slug) VALUES (%s, %s) RETURNING id",
                (name, f"{name}-r272-test"))
    return cur.fetchone()[0]


def _subscribe(cur, artist, customer, sub):
    cur.execute("SELECT id FROM subscription_plans ORDER BY id LIMIT 1")
    plan = cur.fetchone()[0]
    cur.execute("INSERT INTO artist_subscriptions (artist_id, plan_id, stripe_customer_id, "
                "stripe_subscription_id, status) VALUES (%s, %s, %s, %s, 'active')",
                (artist, plan, customer, sub))


def _months(cur, artist):
    cur.execute("SELECT referral_free_months FROM saas_artists WHERE id = %s", (artist,))
    return cur.fetchone()[0]


def _statuses(cur, referrer):
    cur.execute("SELECT status FROM referral_rewards WHERE referrer_artist_id = %s ORDER BY id",
                (referrer,))
    return [r[0] for r in cur.fetchall()]


def test_a_first_payment_earns_once_and_the_coupon_lands(cur):
    referrer, referred = _artist(cur, "parrain"), _artist(cur, "filleul")
    _subscribe(cur, referrer, "cus_parrain", "sub_parrain")
    _subscribe(cur, referred, "cus_filleul", "sub_filleul")
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer, referred))
    applied = []
    invoice = {"customer": "cus_filleul", "billing_reason": "subscription_create", "amount_paid": 1000}
    rr.on_invoice_paid(cur, invoice, "evt_1", lambda s, c, *k: applied.append((s, c)))
    assert applied == [], "no coupon configured → pending, no Stripe call"
    assert _statuses(cur, referrer) == ["pending"] and _months(cur, referrer) == 1

    rr.on_invoice_paid(cur, invoice, "evt_1", lambda s, c, *k: applied.append((s, c)))
    rr.on_invoice_paid(cur, invoice, "evt_2", lambda s, c, *k: applied.append((s, c)))
    assert _statuses(cur, referrer) == ["pending"], "a retry or a second event earns nothing"
    assert _months(cur, referrer) == 1

    assert rr.apply_next(cur, referrer, lambda s, c, *k: applied.append((s, c)), "COUPON") is not None
    assert applied == [("sub_parrain", "COUPON")]
    assert _statuses(cur, referrer) == ["applied"] and _months(cur, referrer) == 0


def test_a_renewal_earns_nothing(cur):
    referrer, referred = _artist(cur, "parrain2"), _artist(cur, "filleul2")
    _subscribe(cur, referred, "cus_f2", "sub_f2")
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer, referred))
    rr.on_invoice_paid(cur, {"customer": "cus_f2", "billing_reason": "subscription_cycle", "amount_paid": 1000},
                       "evt_r", lambda s, c, *k: None)
    assert _statuses(cur, referrer) == [] and _months(cur, referrer) == 0


def test_a_referrer_without_subscription_keeps_it_pending_then_gets_it(cur):
    referrer, referred = _artist(cur, "parrain3"), _artist(cur, "filleul3")
    _subscribe(cur, referred, "cus_f3", "sub_f3")
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer, referred))
    rr.earn(cur, {"customer": "cus_f3", "billing_reason": "subscription_create", "amount_paid": 1000}, "evt_3")
    applied = []
    assert rr.apply_next(cur, referrer, lambda s, c, *k: applied.append(s), "COUPON") is None
    assert _statuses(cur, referrer) == ["pending"], "no subscription: pending, never lost"
    _subscribe(cur, referrer, "cus_p3", "sub_p3")
    assert rr.apply_next(cur, referrer, lambda s, c, *k: applied.append(s), "COUPON") is not None
    assert applied == ["sub_p3"]


def test_one_month_at_a_time_and_the_next_after_the_discounted_invoice(cur):
    referrer = _artist(cur, "parrain4")
    _subscribe(cur, referrer, "cus_p4", "sub_p4")
    for i in (1, 2):
        referred = _artist(cur, f"filleul4{i}")
        _subscribe(cur, referred, f"cus_f4{i}", f"sub_f4{i}")
        cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, "
                    "code_used) VALUES (%s, %s, 'CODE')", (referrer, referred))
        rr.earn(cur, {"customer": f"cus_f4{i}", "billing_reason": "subscription_create", "amount_paid": 1000},
                f"evt_4{i}")
    applied = []
    rr.apply_next(cur, referrer, lambda s, c, *k: applied.append(s), "COUPON")
    rr.apply_next(cur, referrer, lambda s, c, *k: applied.append(s), "COUPON")
    assert applied == ["sub_p4"], "a second coupon before the first is billed gives nothing"
    import os
    os.environ["STRIPE_REFERRAL_COUPON_ID"] = "COUPON"
    try:
        rr.consume(cur, {"customer": "cus_p4",
                         "discounts": [{"coupon": {"id": "COUPON"}}]})
    finally:
        del os.environ["STRIPE_REFERRAL_COUPON_ID"]
    rr.apply_next(cur, referrer, lambda s, c, *k: applied.append(s), "COUPON")
    assert applied == ["sub_p4", "sub_p4"]
    assert _statuses(cur, referrer) == ["consumed", "applied"]


def test_a_stripe_refusal_leaves_it_pending_with_the_reason(cur):
    referrer, referred = _artist(cur, "parrain5"), _artist(cur, "filleul5")
    _subscribe(cur, referrer, "cus_p5", "sub_p5")
    _subscribe(cur, referred, "cus_f5", "sub_f5")
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer, referred))
    rr.earn(cur, {"customer": "cus_f5", "billing_reason": "subscription_create", "amount_paid": 1000}, "evt_5")

    def refuse(sub, coupon, *k):
        raise RuntimeError("No such coupon: 'COUPON'")
    assert rr.apply_next(cur, referrer, refuse, "COUPON") is None
    cur.execute("SELECT status, detail FROM referral_rewards WHERE referrer_artist_id = %s",
                (referrer,))
    status, detail = cur.fetchone()
    assert status == "pending" and "No such coupon" in detail and _months(cur, referrer) == 1


def _pair(cur, tag, same_email=False):
    referrer, referred = _artist(cur, f"p{tag}"), _artist(cur, f"f{tag}")
    _subscribe(cur, referred, f"cus_f{tag}", f"sub_f{tag}")
    cur.execute("INSERT INTO referral_events (referrer_artist_id, referred_artist_id, code_used) "
                "VALUES (%s, %s, 'CODE')", (referrer, referred))
    if same_email:
        for a, mail in ((referrer, f"moi.{tag}@gmail.com"), (referred, f"moi{tag}+alt@gmail.com")):
            cur.execute("INSERT INTO saas_users (username, email, password_hash, artist_id) "
                        "VALUES (%s, %s, 'x', %s)", (f"u{a}", mail, a))
    return referrer, referred


def test_a_zero_euro_first_invoice_earns_nothing(cur):
    referrer, _ = _pair(cur, "6")
    rr.earn(cur, {"customer": "cus_f6", "billing_reason": "subscription_create",
                  "amount_paid": 0}, "evt_6")
    assert _statuses(cur, referrer) == []


def test_a_self_referral_earns_nothing(cur):
    referrer, _ = _pair(cur, "7", same_email=True)
    rr.earn(cur, {"customer": "cus_f7", "billing_reason": "subscription_create",
                  "amount_paid": 1000}, "evt_7")
    assert _statuses(cur, referrer) == [], "the same mailbox (dots, +tag) is one person"


def test_a_refund_takes_the_month_back(cur):
    referrer, _ = _pair(cur, "8")
    rr.earn(cur, {"customer": "cus_f8", "billing_reason": "subscription_create",
                  "amount_paid": 1000}, "evt_8")
    assert _months(cur, referrer) == 1
    assert rr.revoke(cur, "cus_f8", lambda sub: None) == "pending"
    assert _statuses(cur, referrer) == [] and _months(cur, referrer) == 0
