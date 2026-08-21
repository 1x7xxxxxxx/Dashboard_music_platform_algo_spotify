"""EN catalog for the credentials (API Credentials) view package."""

EN = {
    # ── router.py ──────────────────────────────────────────────────────
    "credentials.title": "🔑 API Credentials",
    "credentials.caption": (
        "Manage your API access credentials per platform. "
        "Secrets are encrypted (Fernet) before being stored in the database."
    ),
    "credentials.no_active_artist": "No active artist. Create one in the Admin tab.",
    "credentials.target_artist": "Target artist",
    "credentials.no_artist_id": "Unable to determine your artist identifier.",
    "credentials.fernet_missing": (
        "⚠️ `fernet_key` missing from `config/config.yaml`. "
        "Saving is disabled. "
        "Generate a key: "
        "`python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"`"
    ),
    "credentials.fetching_dag_status": "Fetching DAG status…",
    "credentials.identity_taken": (
        "❌ **{field} = {value}** already belongs to another account. A platform "
        "identifier can belong to one artist only — check that this one is yours. "
        "If you believe this is a mistake, contact the administrator."
    ),
    "credentials.focus_banner": (
        "🎯 **Your selection: {done}/{total} connected.** "
        "Next: **{icon} {label}** — you will need: {need}."
    ),
    "credentials.focus_done": (
        "🎯 **Selection complete ({total}/{total}).** Data lands within ~2 min; the "
        "**🚦 Onboarding health** page will say whether each source really brings "
        "something back."
    ),
    "credentials.no_creds_banner": (
        "💡 **No credentials configured.** "
        "Select a platform below and follow the guide "
        "to connect your data sources. "
        "Start with **SoundCloud** (the quickest: a single identifier)."
    ),
    # ── _registry.py — field labels ────────────────────────────────────
    "credentials.field.client_id": "Client ID",
    "credentials.field.client_secret": "Client Secret",  # pragma: allowlist secret
    "credentials.field.api_key": "API Key (YouTube Data API v3)",  # pragma: allowlist secret
    "credentials.field.channel_id": "Channel ID (UC…)",
    "credentials.field.user_id": "Numeric User ID (e.g. 377065610)",
    "credentials.field.account_id": "Ad Account ID (act_… or numeric)",
    # ── _render.py — global KPI ────────────────────────────────────────
    "credentials.kpi.run_failed": "Last run: FAILED",
    "credentials.kpi.run_running": "Running",
    "credentials.kpi.run_ok": "Last run: OK",
    "credentials.kpi.run_unreachable": "Airflow unreachable",
    "credentials.kpi.run_never": "Never run",
    "credentials.kpi.connected": "Connected — your account",
    "credentials.kpi.app_ready": "Shared app — to connect",
    "credentials.kpi.not_configured": "To connect",
    # ── _render.py — DAG status badge ──────────────────────────────────
    "credentials.dag_badge": (
        "DAG `{dag_id}` — {icon} **{state}** — last run: {date}"
    ),
    "credentials.dag_state_never": "never run",
    # ── _render.py — current status ────────────────────────────────────
    "credentials.token_expired": (
        "Token **expired** since {date}. Renewal required."
    ),
    "credentials.token_expiring": (
        "Token expires in **{days} day(s)** ({date}) — renewal recommended."
    ),
    "credentials.creds_saved_valid": (
        "Credentials saved — updated: {updated} · "
        "Token valid until {date} ({days}d)"
    ),
    "credentials.creds_saved": "Credentials saved — updated: {updated}",
    "credentials.no_creds_platform": "No credentials saved for this platform.",
    # ── _render.py — form ──────────────────────────────────────────────
    "credentials.form.update": "Update",
    "credentials.form.caption": (
        "🔒 Secret fields encrypted • Leave empty to keep the current value"
    ),
    "credentials.form.undefined": "Not set",
    "credentials.form.secret_help": (
        "🔒 Encrypted in database — leave empty to keep current value"
    ),
    "credentials.form.save": "💾 Save",
    # ── _render.py — connection test ───────────────────────────────────
    "credentials.test_button": "🔌 Test connection",
    "credentials.testing": "Testing…",
    "credentials.test_failed": "Connection failed: {msg}",
    # ── _render.py — save handler ──────────────────────────────────────
    "credentials.collect_started": (
        "🚀 {platform} collection started — data available in ~2 min"
    ),
    "credentials.dag_trigger_failed": (
        "⚠️ Credentials saved but DAG trigger failed: {err}"
    ),
    "credentials.save_ok": "✅ {platform} credentials saved.",
    "credentials.save_error": "❌ Error while saving: {err}",
    # ── _platform_spotify.py ───────────────────────────────────────────
    "credentials.spotify.artist_missing": (
        "Spotify app OK, but your **Spotify Artist ID** is not set — without it "
        "no data can be collected. Paste your artist page URL "
        "(open.spotify.com/artist/…)."
    ),
    "credentials.spotify.test_ok_artist": "Connected — artist “{name}” ✅",
    "credentials.spotify.artist_not_found": (
        "Spotify artist not found: “{aid}”. Paste your Spotify Artist page URL "
        "(open.spotify.com/artist/…)."
    ),
    "credentials.spotify.app_not_configured": (
        "Spotify app not configured on the platform side "
        "(SPOTIFY_CLIENT_ID/SECRET) — contact the administrator."
    ),
    "credentials.spotify.guide_title": "🎵 How to obtain Spotify credentials?",
    "credentials.spotify.guide_steps": (
        "1. Go to **[developers.spotify.com](https://developer.spotify.com/dashboard)** → Log in → **Create App**\n"
        "2. Enter a name (the Redirect URI does not matter here)\n"
        "3. Copy the **Client ID** and **Client Secret** → paste them below\n"
    ),
    "credentials.spotify.guide_info": (
        "The collector uses the **client_credentials** flow: no "
        "Redirect URI or Refresh Token to manage, the token "
        "renews itself on every run."
    ),
    # ── _platform_youtube.py ───────────────────────────────────────────
    "credentials.youtube.app_not_configured": (
        "YouTube app not configured on the platform side "
        "(YOUTUBE_API_KEY) — contact the administrator."
    ),
    "credentials.youtube.test_ok_channel": (
        "API key valid — channel found, {n} video(s) ✅"
    ),
    "credentials.youtube.channel_missing": (
        "API key valid, but your **Channel ID** is not set — without it no video "
        "can be collected. Find it in YouTube Studio → Settings → Channel → "
        "Advanced settings (starts with `UC…`)."
    ),
    "credentials.youtube.channel_malformed": (
        "“{cid}” starts with `UC` but is the wrong length — a channel id is exactly "
        "24 characters. This is almost always a truncated copy/paste: copy it in full "
        "from YouTube Studio → Settings → Channel → Advanced settings."
    ),
    "credentials.youtube.channel_vanity_url": (
        "“{cid}” is a custom address (`/c/…`), and YouTube offers no way to look up "
        "the id from one. Read it directly in YouTube Studio → Settings → Channel → "
        "Advanced settings (it starts with `UC…`)."
    ),
    "credentials.youtube.handle_not_found": (
        "No channel matches “{cid}”. Check the spelling, or read the id in YouTube "
        "Studio → Settings → Channel → Advanced settings (it starts with `UC…`)."
    ),
    "credentials.youtube.handle_resolved": (
        "“{given}” is the channel **`{cid}`**. Paste that value into the Channel ID "
        "field, then run the test again."
    ),
    "credentials.youtube.channel_unrecognised": (
        "“{cid}” is neither a `UC…` id, nor an `@…` handle, nor a YouTube channel "
        "address. Paste the id from YouTube Studio → Settings → Channel → Advanced "
        "settings, or your `@…` handle — we will convert it for you."
    ),
    "credentials.youtube.channel_empty": (
        "Channel “{cid}” found, but it holds **no video** — there will be nothing "
        "to collect. If your music is distributed, the channel to use is usually "
        "the auto-generated **“… - Topic”** one, not your personal channel."
    ),
    "credentials.youtube.channel_not_found": (
        "Channel ID not found: “{cid}”. Make sure it starts with UC… "
        "(channel Advanced settings)."
    ),
    "credentials.youtube.guide_title": "🎬 How to obtain YouTube credentials?",
    "credentials.youtube.guide_steps": (
        "1. **[console.cloud.google.com](https://console.cloud.google.com)** → create/select a project\n"
        "2. **APIs & Services → Library** → enable **YouTube Data API v3**\n"
        "3. **APIs & Services → Credentials → Create credentials → API key**\n"
        "4. (recommended) Restrict the key to **YouTube Data API v3**\n"
        "5. Paste the key into **API Key** below\n"
        "6. **Channel ID**: on the YouTube channel → *Advanced settings* "
        "→ channel ID (starts with `UC…`)\n"
    ),
    "credentials.youtube.guide_info": (
        "The collector uses a **static API key** (no OAuth): "
        "the key does not expire, no refresh to manage."
    ),
    # ── _platform_soundcloud.py ────────────────────────────────────────
    "credentials.soundcloud.user_id_empty": (
        "User ID empty — see the guide above to find it (/discover)."
    ),
    "credentials.soundcloud.app_not_configured": (
        "SoundCloud app not configured on the platform side "
        "(SOUNDCLOUD_CLIENT_ID/SECRET) — contact the administrator."
    ),
    "credentials.soundcloud.token_missing": "Token missing in the OAuth response.",
    "credentials.soundcloud.test_ok": (
        "SoundCloud OAuth API OK — {count} track(s) fetched for user {user_id} ✅"
    ),
    "credentials.soundcloud.no_public_tracks": (
        "User ID {user_id} is reachable, but **no public track** is attached to "
        "it — there will be nothing to collect. Check that it is YOUR profile ID "
        "(not a label or secondary account) and that your tracks are **public**, "
        "not private/unlisted."
    ),
    "credentials.soundcloud.not_found": (
        "404 — User ID '{user_id}' not found. Check that it is the numeric ID."
    ),
    "credentials.soundcloud.guide_title": "☁️ How to obtain SoundCloud credentials?",
    "credentials.soundcloud.guide_info": (
        "**Admin (you)**: create an app once at soundcloud.com/you/apps — "
        "the `Client ID` and `Client Secret` are shared by all artists.\n\n"
        "**Each artist**: provides only their numeric `User ID`."
    ),
    "credentials.soundcloud.admin_header": "### Admin — Create the app (once)",
    "credentials.soundcloud.admin_prereq_title": "Prerequisite",
    "credentials.soundcloud.admin_prereq_desc": (
        "Have an active **Artist Pro** subscription on SoundCloud."
    ),
    "credentials.soundcloud.admin_create_title": "Create the app",
    "credentials.soundcloud.admin_create_desc": (
        "Go to **soundcloud.com/you/apps** → **Register a new application**. "
        "Name: do not use the word “SoundCloud” (e.g. `ETL Airflow Dashboard`). "
        "Redirect URI: `http://localhost` (unused)."
    ),
    "credentials.soundcloud.admin_copy_title": "Copy the credentials",
    "credentials.soundcloud.admin_copy_desc": (
        "On the app page, copy the credentials into the server environment variables "
        "(`SOUNDCLOUD_CLIENT_ID` / `SOUNDCLOUD_CLIENT_SECRET`). This form does not "
        "accept them: the app is shared by every artist (ADR-006)."
    ),
    "credentials.soundcloud.artist_header": "### Artist — Find your User ID",
    "credentials.soundcloud.two_methods": "Two methods:",
    "credentials.soundcloud.method1_title": "**Method 1 — Direct URL (simplest)**",
    "credentials.soundcloud.method1_desc": (
        "Open this URL in the browser (replace `monpseudo` with the profile slug). "
        "The JSON response contains `\"id\": 123456789` — that is the User ID to copy."
    ),
    "credentials.soundcloud.method2_title": "**Method 2 — DevTools**",
    "credentials.soundcloud.devtools_1": "Go to **soundcloud.com** logged into your account.",
    "credentials.soundcloud.devtools_2": "Press **{{DEVTOOLS}}** → **Network** tab.",
    "credentials.soundcloud.devtools_3": "Play any track.",
    "credentials.soundcloud.devtools_4": (
        "Filter requests by `/users/` — the URL contains `/users/123456789`."
    ),
    "credentials.soundcloud.devtools_5": "Copy the number — that is the User ID.",
    "credentials.soundcloud.note_header": "### Note",
    "credentials.soundcloud.note_body": (
        "- `Client ID` and `Client Secret` are **permanent** — no automatic rotation.\n"
        "- OAuth access tokens are renewed **automatically** by the DAG on every run (TTL 3600s).\n"
        "- App creation reserved for **Artist Pro** accounts. "
        "If sign-ups are closed, contact `soundcloud-api@soundcloud.com`."
    ),
    # ── _platform_meta.py ──────────────────────────────────────────────
    "credentials.meta.test_not_configured": (
        "Meta app not configured on the platform side (META_ACCESS_TOKEN) — "
        "contact the administrator."
    ),
    "credentials.meta.test_ok_account": (
        "Connected: {name} — ad account “{acc}” reachable ✅"
    ),
    "credentials.meta.ig_unreachable": (
        "Ad account OK, but the **Instagram account {ig}** is unreachable: "
        "{detail}\n\n→ Check that it is a **Business/Creator** account linked to a "
        "Page, and that the Page was shared with the platform's Business Manager."
    ),
    "credentials.meta.ig_ok_suffix": " · Instagram @{user} ✅",
    "credentials.meta.account_missing": (
        "Meta app OK, but your **Ad Account ID** is not set — without it no data "
        "can be collected. Read it from the Ads Manager URL, after `act=`."
    ),
    "credentials.meta.account_unreachable": (
        "Ad account **{act}** is not reachable with the shared app: {detail}\n\n"
        "→ Most common cause: the account was never **shared** with the app "
        "(Business Manager → Settings → Apps → ETL_DASHBOARD_SPOTIFY → Business "
        "Assets → Add assets → Ad account, Advertiser permission)."
    ),
    "credentials.meta.guide_title": "📱 Where to find each Meta / Instagram field?",
    "credentials.meta.guide_info": (
        "This dashboard uses a **System User token** — never a personal token. "
        "System User tokens do not expire (unless manually revoked). "
        "All artists use the same Meta app: **ETL_DASHBOARD_SPOTIFY** — "
        "do not create your own app."
    ),
    "credentials.meta.steps_header": "### Steps — Meta Ads",
    "credentials.meta.steps_body": (
        "Only one identifier is yours: the Ad Account ID. Everything else — the access "
        "token and the application credentials — belongs to the platform and appears "
        "nowhere in this form.\n\n"
        "1. **Business Manager → Settings → Ad accounts** → note the numeric ID "
        "(e.g. `123456789`). **Do not add the `act_` prefix** — the dashboard adds it "
        "automatically. *(This is the **Ad Account ID** field above.)*\n"
        "2. **Settings → Apps → ETL_DASHBOARD_SPOTIFY → Business Assets → "
        "Add assets → Ad account** → select your account → "
        "Advertiser permission. *(Required — without it the API returns \"Object does not "
        "exist\", and the connection test will say so.)*\n"
        "3. Click **Test connection**. If it is green, there is nothing else to do."
    ),
    "credentials.meta.ig_header": "### Additional steps — Instagram",
    "credentials.meta.ig_body": (
        "If you want Instagram stats, enter your Instagram Business Account ID below. The "
        "shared platform token already carries the required scopes (`instagram_basic`, "
        "`instagram_manage_insights`, `pages_show_list`) — ask the administrator if the "
        "connection test says otherwise.\n\n"
        "The `meta_token_refresh` DAG (weekly) does **not** attempt to renew System User tokens "
        "(they do not expire) — no periodic action required."
    ),
    "credentials.meta.ig_id_header": "### Instagram Business Account ID (optional)",
    "credentials.meta.table": (
        "| To enter here | Where to find it |\n"
        "|---|---|\n"
        "| **Ad Account ID** | Business Manager → Ad accounts (numeric only, no `act_`) |\n"
        "| **Instagram Business Account ID** *(optional)* | Graph API call above |\n"
        "\nThis table used to list five rows, three of which this form never accepted. "
        "They belong to the platform.\n"
    ),
    "credentials.meta.warning": (
        "⚠️ **Common errors**: "
        "(1) Personal token from Graph API Explorer → expires in 60 days, use System User. "
        "(2) `act_` prefix in Ad Account ID → remove it, the dashboard adds it. "
        "(3) Scope `read_insights` only → re-run with `ads_read` + `ads_management`."
    ),
    # ── credential_guides_st.py — renderer chrome ──────────────────────
    "credentials.guide.list_header": (
        "**How to obtain the credentials for each platform?**"
    ),
    "credentials.guide.portal": "🔗 Portal: [{url}]({url})",
    "credentials.guide.col_field": "Field",
    "credentials.guide.col_example": "Example (fake)",
    "credentials.guide.col_note": "Note",
    "credentials.guide.paste_caption": "Values to paste into 🔑 API Credentials:",
    # ── credential_guides.py — Spotify guide ───────────────────────────
    "credentials.guide.spotify.expander": "{icon} {title} — obtain the credentials",
    "credentials.guide.spotify.intro": (
        "**You don't have to create anything.** The Spotify app is managed by the "
        "administrator (shared across all artists). You paste **one value**: the "
        "**link to your Spotify Artist page**."
    ),
    "credentials.guide.spotify.step_1": (
        "Open **your artist page** on Spotify (app or open.spotify.com). Menu "
        "**⋯ → Share → Copy link to artist**. You get a URL like "
        "`https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4`."
    ),
    "credentials.guide.spotify.step_2": (
        "Paste that link into **🔑 API Credentials → Spotify** (field *Spotify "
        "Artist ID or URL*), then **Test connection**. We extract the ID "
        "automatically — no need to split it."
    ),
    "credentials.guide.spotify.note_1": (
        "paste the full URL of your artist page — we extract the ID"
    ),
    "credentials.guide.spotify.note": (
        "**Admin (one-time)**: create an app on developer.spotify.com "
        "(`client_credentials` flow, no Redirect URI used) and set "
        "`SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` as environment variables. "
        "Artists then only paste their profile link."
    ),
    # ── credential_guides.py — YouTube guide ───────────────────────────
    "credentials.guide.youtube.expander": "{icon} {title} — obtain the credentials",
    "credentials.guide.youtube.intro": (
        "**Artist side: a single value — your Channel ID** (starts with `UC…`). "
        "The API key is **shared (managed by the admin)**, you don't create one. "
        "Jump straight to the **Channel ID** step below.\n\n"
        "*(Steps 1→5 are admin-only, one-time, if they set up their own key.)*"
    ),
    "credentials.guide.youtube.step_1": (
        "**(Admin, once)** On [console.cloud.google.com/apis/dashboard](https://console.cloud.google.com/apis/dashboard), "
        "**create a project first** (the *Enable APIs* button stays **greyed out "
        "until a project exists**), then click **+ Enable APIs and services**."
    ),
    "credentials.guide.youtube.step_1_caption": "APIs and services → Enable APIs",
    "credentials.guide.youtube.step_2": (
        "In the [API Library](https://console.cloud.google.com/apis/library), "
        "search for **YouTube Data API v3**."
    ),
    "credentials.guide.youtube.step_2_caption": "Library → search for the API",
    "credentials.guide.youtube.step_3": "Click the **YouTube Data API v3** result.",
    "credentials.guide.youtube.step_3_caption": "API selection",
    "credentials.guide.youtube.step_4": (
        "Click **Enable**; the product page must display **API enabled**."
    ),
    "credentials.guide.youtube.step_4_caption": "API enabled",
    "credentials.guide.youtube.step_5": (
        "Go to [Credentials](https://console.cloud.google.com/apis/credentials) → "
        "**Create credentials → API key**, then **Show key** and copy it."
    ),
    "credentials.guide.youtube.step_5_caption": (
        "Credentials → API key → Show key"
    ),
    "credentials.guide.youtube.step_6": (
        "Retrieve the **Channel ID**: on "
        "[youtube.com/account_advanced](https://www.youtube.com/account_advanced) → "
        "**Channel ID** → **Copy** (starts with `UC…`)."
    ),
    "credentials.guide.youtube.step_6_caption": (
        "YouTube → Advanced settings → Channel ID"
    ),
    "credentials.guide.youtube.step_7": (
        "Paste the **API key** + the **Channel ID** into **🔑 API Credentials → YouTube**."
    ),
    "credentials.guide.youtube.note_1": "starts with 'AIza', ~39 characters",
    "credentials.guide.youtube.note_2": "starts with 'UC', 24 characters",
    "credentials.guide.youtube.note": (
        "Free quota ~10,000 units/day; exceeding it returns 403 (temporary)."
    ),
    # ── credential_guides.py — SoundCloud guide ────────────────────────
    "credentials.guide.soundcloud.expander": "{icon} {title} — obtain the credentials",
    "credentials.guide.soundcloud.intro": (
        "A **single value** to provide: your SoundCloud **User ID** (a number). "
        "Streams and followers are then collected automatically."
    ),
    "credentials.guide.soundcloud.step_1": (
        "Logged into SoundCloud, open "
        "[soundcloud.com/discover](https://soundcloud.com/discover)."
    ),
    "credentials.guide.soundcloud.step_2": (
        "Show the page **source code** (**{{VIEW_SOURCE}}**), then search "
        "(**{{FIND}}**) for `soundcloud:users:` — the **number** right after is your "
        "**User ID** (e.g. `377065610`)."
    ),
    "credentials.guide.soundcloud.step_2_caption": (
        "Source code → soundcloud:users:<your ID>"
    ),
    "credentials.guide.soundcloud.step_3": (
        "Paste this **User ID** into **🔑 API Credentials → SoundCloud**, then "
        "**Test connection**."
    ),
    "credentials.guide.soundcloud.note_1": (
        "the number found in the source code of /discover"
    ),
    # ── credential_guides.py — Meta guide ──────────────────────────────
    "credentials.guide.meta.expander": "{icon} {title} — obtain the credentials",
    "credentials.guide.meta.intro": (
        "Meta is **configured at the platform level** (shared app). You "
        "provide **only your Ad Account ID**; the token, the app and "
        "Instagram are managed by the administrator."
    ),
    "credentials.guide.meta.step_1": (
        "Open the **Ads Manager** "
        "([adsmanager.facebook.com](https://adsmanager.facebook.com/)) and "
        "log in. Select the right account if you have several."
    ),
    "credentials.guide.meta.step_2": (
        "**Easiest method — via the URL.** Look at the **address "
        "bar** of your browser (at the very top). The URL contains a "
        "**`act=`** parameter, for example:\n\n"
        "`adsmanager.facebook.com/adsmanager/manage/campaigns?`**`act=123456789012345`**`&business_id=…`\n\n"
        "Your **Ad Account ID** is the **number right after `act=`** and "
        "**before the next `&`**. Tip: double-click that number to "
        "select it, then **{{COPY}}**."
    ),
    "credentials.guide.meta.step_2_caption": (
        "The number after act= in the address bar"
    ),
    "credentials.guide.meta.step_3": (
        "⚠️ Do not confuse it with `business_id=…` (your Business Manager) or "
        "with an **ad set ID**: only the number "
        "after **`act=`** is the correct one."
    ),
    "credentials.guide.meta.step_4": (
        "Paste this number into **🔑 API Credentials → Meta / Instagram**, then "
        "**Test connection**. (The `act_` prefix is added automatically.)"
    ),
    "credentials.guide.meta.note_1": (
        "the only field — number or prefixed with 'act_'"
    ),
    "credentials.guide.meta.note": (
        "**Admin prerequisite**: your ad account must be linked to the "
        "shared app (System User) in Business Manager for collection to "
        "work. Instagram is attached on the admin side."
    ),
}
