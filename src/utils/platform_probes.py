"""Run the SAME connection probe the credentials form runs, from anywhere.

Type: Utility
Uses: src.dashboard.views.credentials._registry.CONNECTION_TESTS, tenant_identity
Triggers: alert_monitor.check_onboarding_readiness (nightly), tools/artist_preflight.py
Persists in: nothing

Why this module exists — 2026-08-22.

Two surfaces answer "is this artist's platform working", and they answer different
questions with the same words:

  * `artist_readiness` reads the DATABASE — declared identity × row recency. It knows
    THAT nothing arrived. It then guesses at why, from a static `nodata_hint` string.
  * `CONNECTION_TESTS` calls the PLATFORM API. It knows WHY. It only ran when a human
    clicked "Tester la connexion" or typed `make artist-preflight`.

Measured divergence, GRiNCH (tenant 13), the same night:

    connection test → "User ID 72854583 joignable, mais aucun titre public n'y est
                       rattaché — il n'y aura donc rien à collecter."
    nightly alert   → "vérifie le User ID ; l'app SoundCloud partagée doit être
                       configurée (admin)."

The second is a guess, it is wrong, it blames the artist and the admin for an empty
account, and it is the one that was automatic. Two beta sessions were spent on that
gap.

The budget question answers itself, and it is worth stating because it is the reason
this is cheap: **freshness is the proof; the probe is only the explainer.** A platform
with fresh rows has already demonstrated that its credential produced data — no API
call proves it better. So the probe runs ONLY for the (tenant, platform) pairs the
database has already judged red. Today that is two probes a night, not thirty-five.

The probes still live under `src/dashboard/views/credentials/` because they call
`i18n.t()`, which imports Streamlit. Moving them is the right end state and is its own
piece of work; this module is the seam, so that move changes no caller.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from src.utils.diagnosis_text import clamp

logger = logging.getLogger(__name__)

# Les situations qu'une sonde peut nommer. Ce ne sont PAS des synonymes de `ok` :
# `nothing_to_collect` et `resolved` sortent d'une réponse HTTP 200 parfaitement
# valide, et `identity_missing` d'une app qui fonctionne. Un écran qui ne lit que
# `ok` ne peut pas les distinguer — c'est le défaut que cette liste ferme.
UNREACHABLE = "unreachable"              # rien n'a répondu : réseau, délai, 5xx
REFUSED = "refused"                      # elle répond et refuse : 401 / 403
NOT_FOUND = "not_found"                  # elle répond : cet identifiant n'existe pas
IDENTITY_MISSING = "identity_missing"    # l'app va bien, le locataire n'a rien saisi
NOTHING_TO_COLLECT = "nothing_to_collect"  # 200, joignable, mais aucun contenu
RESOLVED = "resolved"                    # une résolution RÉUSSIE qui attend un collage

PROBE_CATEGORIES = frozenset({
    UNREACHABLE, REFUSED, NOT_FOUND, IDENTITY_MISSING, NOTHING_TO_COLLECT, RESOLVED,
})


class _Tagged(str):
    """Un message de sonde qui porte la situation qu'il décrit.

    La situation voyage SUR le message, et non en troisième élément du tuple, parce
    que `(ok, message)` est un contrat public : `CONNECTION_TESTS` est dépaqueté en
    deux à dix-neuf endroits, dont la vue et quatre fichiers de tests. L'élargir
    aurait été un changement de contrat pour une information qui appartient au
    « pourquoi », pas au verdict.

    Attention : toute opération de chaîne rend un `str` nu et PERD la situation.
    On étiquette donc en dernier, après `.format()` et après `clamp()`.
    """

    __slots__ = ("category",)


def tagged(message: str, category=None) -> str:
    """`message`, portant la situation que la sonde a mesurée."""
    out = _Tagged(message)
    out.category = category if category in PROBE_CATEGORIES else None
    return out


def category_of(message) -> "str | None":
    """La situation portée par un message de sonde, ou `None`."""
    return getattr(message, "category", None)

# What a probe can answer. `None` is NOT a verdict — it means the probe did not run
# (budget exhausted, or the import failed in this container). A check that could not
# run must say so rather than look like a passing or a failing one; that contract is
# the same one `check_central_apps` states in its ImportError branch.
ProbeResult = Optional[tuple[bool, str]]


def probe(db, artist_id: int, logical_platform: str) -> ProbeResult:
    """Run the credentials-form probe for one (tenant, platform). Never raises.

    Returns (ok, message), or None when the probe itself is unavailable.
    """
    try:
        from src.dashboard.views.credentials._registry import CONNECTION_TESTS
        from src.utils.tenant_identity import storage_platform
    except Exception as e:  # noqa: BLE001 — no Streamlit in this container, say so
        logger.warning("connection probes unavailable here: %s", type(e).__name__)
        return None

    test = CONNECTION_TESTS.get(logical_platform)
    if test is None:
        return None

    try:
        fields = _identity_fields(db, artist_id, logical_platform, storage_platform)
    except Exception as e:  # noqa: BLE001 — a DB blip is not the artist's fault
        logger.warning("could not read identity for tenant %s / %s: %s",
                       artist_id, logical_platform, type(e).__name__)
        return None

    try:
        ok, message = test(fields)
    except Exception as exc:  # noqa: BLE001
        # A raising probe is a red REASON, never a crash and never a verdict about
        # the artist — `broken-probe-rendered-as-user-fault`.
        return False, tagged(f"la vérification a échoué ({type(exc).__name__})",
                             UNREACHABLE)
    # The WHOLE diagnosis, not its first line. A probe message is authored in two
    # halves — the symptom, then the gesture that fixes it — and `splitlines()[0]`
    # kept the half nobody can act on. See `src.utils.diagnosis_text`, which renders
    # it per surface instead of flattening it for the narrowest one.
    # `clamp(str(...))` rend un `str` nu : la situation est re-attachée après, sinon
    # elle disparaît sans erreur et l'écran retombe sur le libellé neutre.
    return bool(ok), tagged(clamp(str(message)), category_of(message))


def _identity_fields(db, artist_id: int, logical_platform: str, storage_platform):
    """The identity dict the probe expects, resolved the way the form resolves it.

    Two subtleties, both already learned elsewhere in this repo:
      * Instagram's `ig_user_id` lives in the **meta** storage row, so keying on the
        logical name returns an empty dict and the probe reports a missing identity
        for a tenant that declared one correctly.
      * Spotify's id is mirrored onto `saas_artists.spotify_artist_id`, and that
        mirror — not `extra_config` — is what `spotify_api_daily` actually reads.
    """
    import json

    rows = db.fetch_query(
        "SELECT platform, extra_config FROM artist_credentials WHERE artist_id = %s",
        (artist_id,))
    creds = {}
    for platform, extra in rows:
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        creds[platform] = extra or {}

    fields = dict(creds.get(storage_platform(logical_platform), {}))
    if logical_platform == "spotify" and not fields.get("spotify_artist_id"):
        row = db.fetch_query(
            "SELECT spotify_artist_id FROM saas_artists WHERE id = %s", (artist_id,))
        fields["spotify_artist_id"] = (row[0][0] if row else "") or ""
    # Who is asking. A probe may need to consult tenant-scoped state that is not an
    # identity field — SoundCloud reads the tracks this tenant declared as hosted
    # elsewhere, which is what makes an empty profile legitimately green.
    fields["_artist_id"] = artist_id
    return fields


def make_budgeted_probe(db, artist_id: int, budget: list) -> Callable[[str], ProbeResult]:
    """A `probe(platform)` callable for one tenant, sharing a mutable budget.

    `budget` is a one-element list used as a counter shared across tenants, so the cap
    is a FLEET cap and not a per-tenant one — otherwise 100 tenants × 5 platforms is
    500 calls whatever the number says.

    When the budget is exhausted the callable returns `None`, which the caller must
    render as "not measured", never as "measured and fine". Exhaustion is logged so a
    silently truncated night is visible; a cap nobody is told about reads as full
    coverage, which is the `guard-scope-is-a-hand-written-list` shape.
    """
    def _call(logical_platform: str) -> ProbeResult:
        if budget[0] <= 0:
            logger.warning("probe budget exhausted — tenant %s / %s not measured",
                           artist_id, logical_platform)
            return None
        budget[0] -= 1
        return probe(db, artist_id, logical_platform)

    return _call
