# ADR-010 — Meta and Instagram are proven per invited artist, not by the canary

- **Status**: Accepted
- **Date**: 2026-08-22
- **Unblocks**: roadmap R1 (private beta)

## Context

The canary tenant (`artist_id=14` in production) exists so that a break in the
*per-tenant* path is visible before an artist meets it. Every other freshness check
looks at a SOURCE across the fleet, and a source stays fresh as long as one tenant
collects — usually the admin. The canary is the tenant that is not the admin.

For it to prove anything, its identity on each platform must be **different from the
admin's**; `tools/create_canary.py` refuses an identical one, because a canary that
borrows the admin's channel goes green precisely when the isolation it tests is
broken. Three platforms satisfy that cheaply, by pointing at a well-known public
profile nobody in this system owns:

| platform | canary identity | why it works |
|---|---|---|
| Spotify | `4tZwfgrHOc3mvqYlEYSvVi` (Daft Punk) | any public artist is readable by the central app |
| YouTube | `UC_x5XG1OV2P6uZZ5FSM9Ttw` (Google Developers) | any public channel is readable with an API key |
| SoundCloud | `112904040` (NASA) | any public user is readable via client-credentials |

**Meta Ads and Instagram have no public equivalent, and this is not an oversight of
ours.** Reading an ad account requires that ad account to be *shared with the app* in
Business Manager. Reading an Instagram Business Account requires a linked Page with
granted permissions. There is no ad account and no IG Business Account that a third
party can read the way a public SoundCloud profile can be read. The admin's own are
excluded by the rule above. So covering these two would require a **second real
business asset** that the operator controls and is willing to devote to a test
tenant — and obtaining exactly that has been open since Benken's onboarding in June
(ad account `65390907`, access never confirmed).

R1 — open the private beta — was therefore blocked on something that may never
arrive, by an argument that sounds like caution and functions as a permanent stop.

## Decision

The canary covers Spotify, YouTube and SoundCloud. **Meta and Instagram are proven
per invited artist instead**, by running the preflight on their own tenant once they
have connected:

```bash
make artist-preflight ARTIST=<their id>
```

That command already exists, already covers all five platforms, and is already the
documented step 4 of the beta runbook. What changes is that it stops being a
belt-and-braces nicety for Meta/Instagram and becomes the *only* proof for them —
so skipping it is skipping the check, not skipping a duplicate.

## Consequences

**What this buys.** R1 becomes doable. The two platforms that actually broke —
Meta for Benken, Instagram for GRiNCH — are checked against the artist's real
account, which is a *stronger* signal than a canary would have given: it exercises
the very asset that failed, not a stand-in.

**What it costs, precisely.** The canary detects a per-tenant regression on three
platforms the night it happens; for Meta and Instagram, the first person to notice is
the invited artist, and only if someone runs their preflight. There is no automated
before-the-fact signal for those two, and pretending otherwise was the previous state.

**How the gap stays visible.** `check_canary_health` now pushes a `canary_coverage`
xcom naming what the canary can and cannot prove, and logs a warning listing the
uncovered platforms. It deliberately does NOT raise a daily alert on them: no action
would change the fact, and a watchdog that reports an unfixable fact every night is
the `watchdog-becomes-the-noise` class. `tools/artist_preflight.py` already prints
`green FOR <platforms> ONLY` on a restricted run, which is the line to quote rather
than "the preflight is green".

**When to revisit.** The day a second Meta ad account or IG Business Account can be
devoted to the canary, add it with `make canary` and delete this ADR's exception —
the per-artist check remains useful either way.

## Alternatives considered

**Keep blocking R1 until Meta/Instagram can be canaried.** Rejected: the input has
been unavailable for two months with no owner and no date, and the roadmap already
files that shape under ADR-008. A blocker with no path to resolution is a decision to
never ship, taken without saying so.

**Give the canary the admin's Meta and Instagram identities** (they are sitting in
`.env` as `META_AD_ACCOUNT_ID` and `INSTAGRAM_USER_ID`). Rejected, and this is the
important one: it would make the canary indistinguishable from the admin on those
platforms, so it would report green *because* of the leak it exists to detect. That
is the `tenant-identity-falls-back-to-admin` class exactly — the one that filed every
tenant's `track_popularity_history` under artist 1 for months. `create_canary.py`
refuses it in code; this ADR records why the refusal must not be worked around.

**Use another real artist's account** (e.g. Benken's, `194410214` on SoundCloud).
Rejected on a second ground beyond consent: an identity may be claimed by exactly one
tenant (`find_identity_conflict`), so pointing the canary at a tenant's account is
refused by the uniqueness guard — correctly, since the two would then be
indistinguishable in every contamination report.
