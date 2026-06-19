# ADR-006 — Central credential model — admin-app-per-platform + artist-identifier

- **Status:** Accepted
- **Date:** 2026-06-19
- **Deciders:** @1x7xxxxxxx
- **Supersedes:** —
- **Related:** `.claude/dev-docs/meta-instagram-asset-sharing-runbook.md` (per-tenant Meta/IG asset-sharing runbook), `.claude/dev-docs/token-management-bilan.md` (cross-platform token/refresh matrix), `tools/prod_introspect.sh` + `tools/check_central_apps.py` (operational guards added in the same hardening pass), table `artist_credentials` (per-artist override), table `saas_artists` (per-artist identifiers)

## Context

streaMLytics is a multi-tenant SaaS: one platform serves many artists. Every
external source (Spotify API, YouTube Data API, SoundCloud API, Meta Ads,
Instagram Graph) requires *developer credentials* (a registered app / API key /
access token) to call. The naïve model — each artist registers their own
developer app on each platform — is a non-starter for a non-technical music
audience: creating a Spotify dev app, a Google Cloud project with a YouTube
key, a SoundCloud OAuth client, and a Meta Business app is days of friction that
kills onboarding.

The constraint is therefore: **maximize artist simplicity** — the artist should
hand over the minimum possible (ideally a single copy-pasted identifier) and
never touch a developer console — while keeping per-tenant data isolation.

The **Benken incident** (2026-06-15, `artist_id=12`) exposed the failure mode of
an under-specified version of this model: the central apps existed, but their
env vars were wired into *some* containers and not others. The dashboard — which
runs the per-artist "connection test" buttons — was missing the central-app env
(and SoundCloud was absent from the prod compose entirely), so a tenant could be
correctly configured yet show "not connected" because the container doing the
check had no credentials. The model was sound; its *deployment invariant* was
not codified.

## Decision

**One admin-owned app per platform, provisioned once at the environment level;
each artist supplies only an identifier. Per-artist override credentials, when
present, still win in the collectors.**

Concretely:

1. **One central app per platform**, owned by the admin, exposed to all code as
   env vars: `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`, `YOUTUBE_API_KEY`,
   `SOUNDCLOUD_CLIENT_ID` / `SOUNDCLOUD_CLIENT_SECRET`,
   `META_ACCESS_TOKEN` / `META_APP_ID` / `META_APP_SECRET`.
2. **The artist provides only an identifier**, stored on `saas_artists`:
   Spotify artist URL → `spotify_artist_id`, YouTube `channel_id`, SoundCloud
   `user_id`, Meta ad `account_id`, Instagram `ig_user_id`.
3. **Spotify / YouTube / SoundCloud are zero-extra-permission**: a public
   artist/channel/user ID is readable by the central app with no action on the
   artist's account. Onboarding for these is literally one pasted field.
4. **Meta / Instagram require per-account asset-sharing**: the artist must share
   their ad account / IG-linked Page to the admin Business Manager and the admin
   must assign it to the central System User. This is the *only* step the artist
   cannot complete inside the dashboard — see the runbook
   `.claude/dev-docs/meta-instagram-asset-sharing-runbook.md`. Without it the
   central token is necessary but not sufficient and the tenant gets 0 rows.
5. **Per-artist override still wins**: if `artist_credentials` holds a
   `token_encrypted` (Fernet) / `extra_config` (JSONB) for a tenant, the
   collector uses *that* in preference to the central env app. The central app is
   the default, not a hard requirement — power tenants can BYO-credentials.

## Consequences

### Positive
- **Maximum artist simplicity**: artists never create a developer app. For
  Spotify/YouTube/SoundCloud, onboarding is a single pasted identifier with zero
  permission grants on their side.
- **One rotation point**: a token/app expiry is fixed once (the central env), not
  N times across tenants.
- **Per-tenant isolation preserved**: identifiers and per-artist overrides are
  row-scoped; one tenant's broken asset-sharing fails only that tenant.
- **Override escape hatch**: `artist_credentials` lets an advanced tenant or a
  migration supply its own credentials without code changes.

### Negative / Trade-offs
- **The admin must provision + rotate the central apps** for every platform —
  this is now an operational responsibility, not the artist's.
- **The env vars must be wired into EVERY container that reads them.** This is the
  Benken gap: the dashboard runs the connection tests, so it needs the
  central-app env too — not only the collectors / Airflow workers. Any container
  that authenticates to a platform (dashboard, api, airflow-scheduler,
  airflow-webserver) must carry the full set. A drifted, untracked prod
  `docker-compose.yml` re-introduces the gap silently.
- **Meta/Instagram retain an out-of-band onboarding step** (asset-sharing) that
  cannot be self-served in the dashboard and must be verified *before* the
  onboarding session, never discovered live.

### Neutral / Operational
- The deployment invariant ("the env var set is identical across all
  credential-reading containers") is now guarded operationally by
  `tools/prod_introspect.sh` (per-container SET/MISSING audit) and
  `tools/check_central_apps.py` (authenticates each central app before a tenant
  hits it). These are the codified form of the manual probes run during the
  Benken incident.
- Token expiry/refresh semantics per platform live in
  `.claude/dev-docs/token-management-bilan.md`; this ADR fixes *who owns* the
  app, not the refresh mechanics.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| **Artist registers their own developer app per platform** | Days of console friction (Spotify dev app + Google Cloud + SoundCloud OAuth + Meta Business app) for a non-technical music audience — kills onboarding. The whole point is that the artist touches no developer console. |
| **Central app only, no per-artist override** | Removes the escape hatch for advanced tenants / migrations that already hold their own credentials; collectors would have to special-case them in code instead of reading `artist_credentials`. |
| **Per-artist OAuth user-token for every platform** (artist logs in, we store their token) | Multiplies the rotation/refresh surface by N tenants, requires an OAuth callback per platform, and still needs the artist to navigate a consent screen — more friction than a pasted identifier for the read-only public data we need. |
| **Wire central env into collectors only (not the dashboard)** | Exactly the Benken gap: the dashboard runs the connection-test buttons, so a correctly-configured tenant shows "not connected" because the testing container lacks credentials. Rejected — every credential-reading container must carry the full set. |
| **Skip Meta/IG asset-sharing, rely on the central token alone** | A System User token can only read accounts shared to the admin Business Manager and assigned to it; without sharing the collector returns error #200/#803 and the tenant gets 0 rows. Asset-sharing is mandatory, not optional. |
