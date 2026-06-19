# Runbook — onboard a new tenant's Meta Ads + Instagram (asset sharing)

**Why this exists.** streaMLytics uses ONE admin-owned Meta System User token
(`META_ACCESS_TOKEN`, app `ETL_DASHBOARD_SPOTIFY`) for every artist. A central token
is necessary but **not sufficient**: a System User can only read an ad account / IG
account that has been **shared to the admin Business Manager and assigned to the System
User**. Without that, the collector returns *"Object does not exist / cannot be accessed
(#200 / #803)"* and the tenant gets 0 rows — exactly what happened to Benken
(`artist_id=12`, ad account `65390907`) on 2026-06-15.

This is the only onboarding step that the artist cannot do entirely inside the dashboard.
Do it **before** the onboarding session and **verify access ahead of time** — never
discover the gap live.

## A. Meta Ads — one-time per tenant

Artist side (the new tenant):
1. Business Manager → **Paramètres → Comptes publicitaires** → note the **numeric ad
   account ID** (no `act_` prefix — the dashboard adds it).
2. **Paramètres → Partenaires → Ajouter un partenaire** → enter the **admin Business
   Manager ID** → grant **Compte publicitaire → permission Annonceur (read)** on their
   ad account. *(Alternatively the admin sends a partner request the artist accepts.)*

Admin side:
3. Business Manager → **Paramètres → Utilisateurs → Utilisateurs système** → select the
   System User → **Ajouter des actifs → Comptes publicitaires** → select the newly shared
   account → enable **Afficher les performances (read)**.
4. Artist enters their **Ad Account ID** in Dashboard → Credentials → Meta (only field).

## B. Instagram — one-time per tenant

1. The artist's **Instagram must be a Business/Creator account linked to a Facebook Page**.
2. Artist shares that **Page** (and thus its linked IG account) to the admin Business
   Manager (Paramètres → Pages → Partenaires), or assigns the admin's System User to the
   Page with read access.
3. Resolve the **Instagram Business Account ID** (the dashboard guide shows the Graph
   calls) and enter it as **ig_user_id** in Dashboard → Credentials → Meta/Instagram.

## C. Admin pre-session verification (do this BEFORE the session)

Read-only checks with the System User token — confirm access exists, don't wait for the
daily DAG to reveal a gap:

```bash
# Ad account reachable? (replace <id>; act_ prefix required)
curl -s "https://graph.facebook.com/v21.0/act_<numeric_id>?fields=name,account_status&access_token=$META_ACCESS_TOKEN"
# Instagram business account reachable?
curl -s "https://graph.facebook.com/v21.0/<ig_user_id>?fields=username,followers_count&access_token=$META_ACCESS_TOKEN"
```

A JSON object (not an `error`) on both → access is in place. Then trigger the DAGs for
the tenant and confirm rows land:

```bash
# On the prod server, in /opt/streamlytics:
docker exec airflow_scheduler airflow dags trigger meta_ads_api_daily   --conf '{"artist_id": <id>}'
docker exec airflow_scheduler airflow dags trigger instagram_daily      --conf '{"artist_id": <id>}'
```

## What the code now does (so a gap is loud, not silent)

- `meta_ads_api_daily` / `instagram_daily` resolve the token from `META_ACCESS_TOKEN`
  (env) when the tenant has no per-artist token — an artist with only an `account_id` /
  `ig_user_id` is collected, not skipped.
- A not-shared account fails **only that tenant** (per-artist isolation) and is logged
  with the Meta error; the task fails only if EVERY configured tenant failed. One broken
  tenant can no longer blank the whole fleet's data.
