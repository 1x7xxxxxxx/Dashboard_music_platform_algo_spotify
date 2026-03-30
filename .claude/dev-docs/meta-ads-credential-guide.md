# Meta Ads — Credential Setup Guide

Reference for artists configuring Meta credentials in the ETL dashboard.

---

## Overview

The dashboard pulls Meta Ads data (campaigns, ad sets, ads, insights) via the Facebook Marketing API using
**System User tokens** — not personal user tokens. System User tokens are long-lived (never expire by default)
and are scoped to a specific Business Manager, which avoids token revocation when a personal account changes its
password or loses access.

All artists share the same Meta app: **ETL_DASHBOARD_SPOTIFY**. Artists do NOT create their own app.

---

## Step-by-step setup

### 1. Access Business Manager

Open [business.facebook.com](https://business.facebook.com) and navigate to your Business Manager account.
You must have **Admin** access to the Business Manager.

### 2. Create a System User (if not already present)

1. In Business Manager, go to **Settings → Users → System Users**.
2. Click **Add** → give the System User a name (e.g., `etl-dashboard`) → role: **Admin**.
3. Click **Create System User**.

### 3. Generate a System User Access Token

1. Click the System User you just created → **Generate New Token**.
2. Select the app: **ETL_DASHBOARD_SPOTIFY** (if not listed, see Step 5 to link it first).
3. Select the following scopes:
   - `ads_read`
   - `ads_management`
   - `instagram_basic` *(required for Instagram stats)*
   - `instagram_manage_insights` *(required for Instagram stats)*
   - `pages_show_list` *(required to resolve Instagram Business Account ID)*
4. Click **Generate Token** — copy and save it. It will not be shown again.

> **This is the value for the "Access Token (Long-lived)" field in the dashboard.**
> System User tokens do not expire unless manually revoked.

### 4. Find your Ad Account ID

1. In Business Manager, go to **Settings → Ad Accounts**.
2. Your account ID is the numeric value shown (e.g., `123456789`).
3. **Do NOT add the `act_` prefix** — the dashboard adds it automatically when calling the API.

> **This is the value for the "Ad Account ID" field in the dashboard.**

### 5. Link your Ad Account to the ETL_DASHBOARD_SPOTIFY app

This step is required for the token to have access to your ad data.

1. In Business Manager, go to **Settings → Apps**.
2. Find **ETL_DASHBOARD_SPOTIFY** in the list (or request your admin to add it).
3. Click the app → **Business Assets → Add Assets → Ad Account**.
4. Select your ad account → assign **Analyst** or **Advertiser** permission.

### 6. Find the App ID and App Secret

These credentials belong to the shared ETL_DASHBOARD_SPOTIFY app. Contact your platform admin to obtain them —
they are pre-filled in the dashboard by default and you should not need to change them.

If filling them manually:
1. Go to [developers.facebook.com](https://developers.facebook.com) → **My Apps → ETL_DASHBOARD_SPOTIFY**.
2. Go to **Settings → Basic**.
3. **App ID** is shown at the top of the page.
4. **App Secret**: click **Show** (requires password confirmation).

### 7. Find your Instagram Business Account ID

Required only if you want Instagram Insights data (separate from Meta Ads).

```
GET https://graph.facebook.com/v18.0/me/accounts?access_token=YOUR_TOKEN
```

This returns your Facebook Pages. Find the Page linked to your Instagram account, note its `id`.

```
GET https://graph.facebook.com/v18.0/PAGE_ID?fields=instagram_business_account&access_token=YOUR_TOKEN
```

The `instagram_business_account.id` in the response is your Instagram Business Account ID.

> **This is the value for the "Instagram Business Account ID" field in the dashboard.**

---

## Field summary

| Dashboard field | Where to find it | Secret? |
|---|---|---|
| Access Token (Long-lived) | Business Manager → System Users → Generate Token | Yes (encrypted) |
| App Secret | developers.facebook.com → ETL_DASHBOARD_SPOTIFY → Settings → Basic | Yes (encrypted) |
| App ID | Same page as App Secret | No |
| Ad Account ID | Business Manager → Settings → Ad Accounts (numeric only, no `act_`) | No |
| Instagram Business Account ID | Graph API call (see Step 7) | No |

---

## Common mistakes

| Mistake | Consequence | Fix |
|---|---|---|
| Using a personal User token (from Graph API Explorer) | Token expires in 60 days; revoked when password changes | Use a System User token (never expires) |
| Adding `act_` prefix to the account_id | API returns "Invalid ad account ID" | Enter only the numeric ID; dashboard adds `act_` |
| Using `read_insights` scope only | `ads_management` scope required to list ad sets and ads | Regenerate token with both `ads_read` + `ads_management` |
| Missing `instagram_basic` / `instagram_manage_insights` scopes | Instagram DAG fails with permission error | Regenerate token with all 5 scopes listed in Step 3 |
| Not linking ad account to the app (Step 5) | API returns "Object does not exist" | Link via Business Manager → Apps → Business Assets |
| Creating a new app instead of using ETL_DASHBOARD_SPOTIFY | Token will not match the app credentials stored in the system | Always use the shared app provided by the platform admin |

---

## Token refresh behavior

The `meta_token_refresh` Airflow DAG (runs every Monday 07:00 UTC) handles two cases:

| Token type | `expires_at` in DB | DAG behavior |
|---|---|---|
| System User token | `NULL` | Skipped — System User tokens never expire |
| Personal long-lived token | Set (60 days rolling) | Refreshed automatically if < 30 days remaining |

**Conclusion**: with a System User token, no periodic action is required. The token is valid indefinitely unless revoked manually in Business Manager.
