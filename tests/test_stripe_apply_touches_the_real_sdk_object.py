"""R369 — the Stripe calls are exercised against REAL stripe-python objects, never a fake.

Type: Test
Uses: src/utils/referral_rewards.py (stripe_apply, stripe_remove),
      src/api/routers/stripe_webhook.py (the signed-event path); the installed `stripe`
      package. No network: the SDK's HTTP-issuing class methods are monkeypatched, and the
      objects they return are built by the SDK itself (`construct_from`).

Why: since stripe-python 15 a StripeObject is NOT a dict — `.get` raises
AttributeError("'get' is a dict method, but a Subscription is not a dict"). `stripe_apply`
called `sub.get("discounts")` and every referral coupon failed that way, while the referral
tests stayed green because they inject a lambda in place of `stripe_apply`. The webhook paid
the same lesson on 2026-06-12 (9493941c) and kept only a comment. Class:
`an-sdk-object-read-as-a-dict` (.claude/dev-docs/error-classes.md).

Mutation record (2026-10-04, tools/dev/mutate_guards.py-style, each applied ALONE):
 M1 `.to_dict()` dropped at the retrieve boundary → red (AttributeError on Subscription.get).
 M2 boundary read with `sub["discounts"] if "discounts" in sub` (valid) but the nested
    `d.get("id")` kept on the expanded Discount → red (AttributeError on Discount.get).
 M3 `retrieve(...).to_dict()` + `d["id"]` vs `.get("id")` on the converted dict → green
    (a correct spelling is accepted).
 W1 webhook: `event = stripe.Webhook.construct_event(...)` without json.loads → red
    (AttributeError on Event.get, re-raised by TestClient).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

stripe = pytest.importorskip("stripe")

from src.utils import referral_rewards as rr  # noqa: E402

_SUB = {"id": "sub_t", "object": "subscription",
        "discounts": ["di_1", {"id": "di_2", "object": "discount"}]}


def _real_sub(payload: dict):
    return stripe.Subscription.construct_from(payload, "sk_test")


def test_the_premise_an_sdk_object_is_not_a_dict() -> None:
    """If the SDK makes objects dicts again, say the premise changed rather than pass."""
    sub = _real_sub(_SUB)
    assert not isinstance(sub, dict)
    with pytest.raises(AttributeError):
        sub.get("discounts")
    with pytest.raises(AttributeError):
        sub.discounts[1].get("id")
    assert type(sub.discounts[1]).__name__ == "Discount", "the fixture's discount is EXPANDED"


@pytest.fixture()
def modified(monkeypatch):
    calls: list = []
    monkeypatch.setattr(stripe.Subscription, "modify",
                        lambda sid, **kw: calls.append((sid, kw)))
    return calls


def _sent_by(apply, monkeypatch, modified) -> list:
    """Run an apply implementation against a REAL Subscription; return what it sent."""
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda sid: _real_sub(_SUB))
    apply("sub_t", "cpn_x", "k")
    return modified


_EXPECTED = [("sub_t", {
    "discounts": [{"discount": "di_1"}, {"discount": "di_2"}, {"coupon": "cpn_x"}],
    "idempotency_key": "k"})]


def test_stripe_apply_keeps_every_discount_of_a_real_subscription(monkeypatch, modified) -> None:
    assert _sent_by(rr.stripe_apply, monkeypatch, modified) == _EXPECTED


def test_the_detector_sees_the_defect_it_is_written_for(monkeypatch, modified) -> None:
    """The harness above, fed the defect itself (R272's spelling), must raise."""
    def read_as_a_dict(sid, coupon, key):
        sub = stripe.Subscription.retrieve(sid)
        kept = [{"discount": d if isinstance(d, str) else d.get("id")}
                for d in (sub.get("discounts") or [])]
        stripe.Subscription.modify(sid, discounts=kept + [{"coupon": coupon}], idempotency_key=key)

    def nested_read_as_a_dict(sid, coupon, key):
        sub = stripe.Subscription.retrieve(sid)
        kept = [{"discount": d if isinstance(d, str) else d.get("id")}
                for d in (sub["discounts"] if "discounts" in sub else [])]
        stripe.Subscription.modify(sid, discounts=kept + [{"coupon": coupon}], idempotency_key=key)

    def converted_once(sid, coupon, key):
        sub = stripe.Subscription.retrieve(sid).to_dict()
        kept = [{"discount": d if isinstance(d, str) else d.get("id")}
                for d in (sub.get("discounts") or [])]
        stripe.Subscription.modify(sid, discounts=kept + [{"coupon": coupon}], idempotency_key=key)

    for defect, what in ((read_as_a_dict, "Subscription"), (nested_read_as_a_dict, "Discount")):
        with pytest.raises(AttributeError, match=f"a {what} is not a dict"):
            _sent_by(defect, monkeypatch, modified)
    assert modified == []
    assert _sent_by(converted_once, monkeypatch, modified) == _EXPECTED


def test_stripe_apply_on_a_subscription_without_discounts(monkeypatch, modified) -> None:
    monkeypatch.setattr(stripe.Subscription, "retrieve",
                        lambda sid: _real_sub({"id": "sub_t", "object": "subscription"}))
    rr.stripe_apply("sub_t", "cpn_x")
    assert modified == [("sub_t", {"discounts": [{"coupon": "cpn_x"}], "idempotency_key": None})]


def test_stripe_remove_BINDS_to_the_sdk_call_only_not_what_it_removes(monkeypatch) -> None:
    """Binding only. Whether DELETE /discount removes OUR coupon on a multi-discount
    subscription is unverified (R369) — this test does not cover it."""
    seen: list = []
    monkeypatch.setattr(stripe.Subscription, "_cls_delete_discount",
                        classmethod(lambda cls, sid, **kw: seen.append(sid)))
    rr.stripe_remove("sub_t")
    assert seen == ["sub_t"]


def test_an_applied_reward_is_not_removed_while_removal_is_unverified() -> None:
    assert rr.REMOVE_ON_A_MULTI_DISCOUNT_SUBSCRIPTION_VERIFIED is False, (
        "flipping this needs a test that pins the Stripe test-mode result of "
        "DELETE /subscriptions/{id}/discount on a multi-discount subscription")


# ── the neighbour: the webhook reads a REAL signed event ─────────────────────────────

class _Cur:
    def execute(self, sql: str, params: tuple = ()) -> None:
        pass  # the per-customer advisory lock (R369) — nothing to read back

    def close(self) -> None:
        pass


class _Conn:
    def cursor(self) -> _Cur:
        return _Cur()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def _signed(payload: bytes, secret: str) -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_the_webhook_reads_a_real_signed_event(monkeypatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routers import stripe_webhook as wh
    import src.utils.referral_rewards as rr_mod

    secret = "whsec_test_r369"  # pragma: allowlist secret
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(wh, "_get_db", lambda: _Conn())
    seen: list = []
    monkeypatch.setattr(rr_mod, "on_invoice_paid",
                        lambda cur, data, event_id: seen.append((data, event_id)))
    payload = json.dumps({"id": "evt_r369", "object": "event", "type": "invoice.paid",
                          "data": {"object": {"object": "invoice", "customer": "cus_x",
                                              "billing_reason": "subscription_create"}}}
                         ).encode()
    app = FastAPI()
    app.include_router(wh.router)
    resp = TestClient(app).post(
        "/webhooks/stripe", content=payload,
        headers={"stripe-signature": _signed(payload, secret)})
    assert resp.status_code == 200, resp.text
    assert seen == [({"object": "invoice", "customer": "cus_x",
                      "billing_reason": "subscription_create"}, "evt_r369")]
