"""Per-IP throttling for the dashboard's unauthenticated and pre-authenticated forms.

Type: Utility
Uses: src.utils.request_throttle (shared with the FastAPI middleware) → Postgres
Triggers: registration submit (R23), TOTP challenge submit (R26), login submit
Persists in: rate_limit_hits (via src.utils.request_throttle.PostgresHitStore)

Why not `st.session_state` — measured 2026-08-22.

`src/dashboard/auth.py` already had `_check_session_rate_limit()`, and it counts in
`st.session_state`. A Streamlit session is one browser tab: opening a second tab, or
clearing the cookie, produces a fresh counter. That made it a UX guard against
fat-fingering, never a security control — which is precisely how the TOTP challenge
stayed brute-forceable (R26) even though it *looked* rate-limited.

These buckets are keyed by client IP instead, so they survive a new tab and a new
session. Depuis le 2026-09-16 ils ne vivent plus dans le processus : leur compteur est
dans Postgres (`rate_limit_hits`), donc le budget reste le même quel que soit le nombre
d'instances du dashboard. La contrainte que ce choix lève est écrite dans
`tests/test_in_memory_limits_forbid_replicas.py`.

An IP is not an identity. A NAT'd office shares one bucket and a botnet defeats it.
The budgets below are therefore sized to stop *scripted enumeration from one host*,
not to be a CAPTCHA — they leave room for a household to register several accounts.
"""
from __future__ import annotations

import os
from typing import Optional

from src.utils.request_throttle import (
    SlidingWindowLimiter,
    client_ip_from_headers,
    shared_hit_store,
)

# Registration submits per IP. Sized for "a family signs up on the same wifi", not for
# "a script probes 24 bits of promo code": at 8 per 10 min, exhausting `token_hex(3)`
# takes ~40 years from one host.
REGISTER_MAX = int(os.getenv("DASHBOARD_REGISTER_MAX", "8"))
REGISTER_WINDOW_SECS = int(os.getenv("DASHBOARD_REGISTER_WINDOW_SECS", "600"))

# TOTP code submits per IP. A 6-digit code with valid_window=1 spans 3 codes out of
# 10^6; at 10 tries per 15 min the expected time to hit one is measured in centuries.
TOTP_MAX = int(os.getenv("DASHBOARD_TOTP_MAX", "10"))
TOTP_WINDOW_SECS = int(os.getenv("DASHBOARD_TOTP_WINDOW_SECS", "900"))

# Password submits per IP — a backstop *in front of* the per-account DB lockout, which
# an attacker spraying one password across many accounts never triggers.
LOGIN_MAX = int(os.getenv("DASHBOARD_LOGIN_MAX", "30"))
LOGIN_WINDOW_SECS = int(os.getenv("DASHBOARD_LOGIN_WINDOW_SECS", "900"))

# Les trois seaux PARTAGENT leur compteur entre instances (Postgres, table
# `rate_limit_hits`). Ce ne sont pas des seaux de confort : chacun est la seule
# borne devant une énumération ou une force brute, et un budget qui se multiplie
# par le nombre de conteneurs n'est plus une borne. Le magasin est construit une
# fois par processus et n'ouvre aucune connexion avant le premier coup.
_STORE = shared_hit_store()

_LIMITERS: dict[str, SlidingWindowLimiter] = {
    "register": SlidingWindowLimiter(REGISTER_MAX, REGISTER_WINDOW_SECS, store=_STORE),
    "totp": SlidingWindowLimiter(TOTP_MAX, TOTP_WINDOW_SECS, store=_STORE),
    "login": SlidingWindowLimiter(LOGIN_MAX, LOGIN_WINDOW_SECS, store=_STORE),
}


def dashboard_client_ip() -> str:
    """Client IP of the current Streamlit request, or "unknown" outside a request.

    `st.context.headers` is unavailable in bare-script and test contexts (the same
    caveat `src/dashboard/utils/os_hints.py` documents), so this never raises. Falling
    back to a single "unknown" bucket is the safe direction: every headerless caller
    shares one budget rather than each getting a private one.
    """
    try:
        import streamlit as st

        headers = st.context.headers
        if headers is None:
            return "unknown"
        return client_ip_from_headers(headers.get)
    except Exception:  # no request context, or a Streamlit version without st.context
        return "unknown"


def throttle_consume(bucket: str, key: Optional[str] = None) -> Optional[int]:
    """Consomme une unité du budget et rend le délai d'attente s'il est épuisé.

    **C'est la forme à utiliser sur un chemin d'authentification**, et la raison est
    une course mesurable, pas une préférence.

    `throttle_check()` ne consomme pas ; `throttle_record()` consomme. Entre les deux,
    le site d'appel fait son travail — vérifier un code TOTP, un mot de passe. N
    requêtes simultanées lisent donc toutes « il reste du budget » avant qu'aucune
    n'ait enregistré, et toutes passent. Streamlit sert des sessions distinctes en
    parallèle : ouvrir N onglets suffit. C'est exactement le « compter puis agir » que
    le verrou consultatif supprime CÔTÉ BASE, laissé vivant côté appelant — un limiteur
    atomique appelé en deux temps n'est pas un limiteur atomique.

    `hit()` décide et consomme en une opération indivisible. La contrepartie est
    qu'une tentative refusée pour une autre raison est facturée ; sur un formulaire
    d'authentification c'est le bon sens du compromis, et `throttle_reset()` rend le
    budget dès que l'authentification RÉUSSIT.
    """
    return _LIMITERS[bucket].hit(_key(bucket, key))


def throttle_check(bucket: str, key: Optional[str] = None) -> Optional[int]:
    """Seconds to wait if `bucket` is over budget for this client, else None.

    Does NOT consume budget. ⚠️ Ne l'utilise PAS pour décider d'autoriser une
    tentative d'authentification : lire puis enregistrer en deux temps rouvre la
    course que `throttle_consume()` ferme. Réservé à l'AFFICHAGE — dire à un visiteur
    qu'il est déjà bloqué, sans lui facturer la lecture de cette phrase.
    """
    return _LIMITERS[bucket].peek(_key(bucket, key))


def throttle_record(bucket: str, key: Optional[str] = None) -> None:
    """Consume one unit of `bucket`'s budget for this client."""
    _LIMITERS[bucket].hit(_key(bucket, key))


def throttle_reset(bucket: str, key: Optional[str] = None) -> None:
    """Forget this client's history in `bucket` — successful authentication only."""
    _LIMITERS[bucket].reset(_key(bucket, key))


def _key(bucket: str, key: Optional[str]) -> str:
    return f"{bucket}:{key or ''}:{dashboard_client_ip()}"
