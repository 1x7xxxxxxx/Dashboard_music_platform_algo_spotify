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
    "credentials.field.extra_account_ids": (
        "Additional ad accounts (one per line — agencies)"
    ),
    "credentials.meta.accounts_malformed": (
        "❌ Ad account(s) in the wrong format: {bad}. Digits only, optionally "
        "prefixed with `act_`, **one per line**."
    ),
    # ── _render.py — global KPI ────────────────────────────────────────
    # The eight `credentials.kpi.*` keys were removed on 2026-08-22 with the strip
    # they belonged to. Left behind they would have been orphans — EN text nothing
    # renders — which `tests/test_i18n_orphans.py` catches, and did.
    # --- Setup matrix header (replaced the fleet-level KPI strip, 2026-08-22) ---
    "credentials.matrix_header": "#### 📋 Your platforms at a glance",
    "credentials.matrix_legend":
        "**Set up**: you entered the identifier. **Responds**: the platform answered "
        "us correctly. **Data**: figures actually arrived. No check is run until you "
        "click.",
    # --- Encryption key: absent and malformed need opposite gestures ---
    "credentials.fernet_malformed":
        "⚠️ The encryption key (`FERNET_KEY`) is **present but invalid** — most "
        "likely truncated when copied. Do NOT generate a new one: already-saved "
        "credentials would stop decrypting. Repair this one.",
    # --- A first collection that could not be started ---
    "credentials.dag_trigger_refused":
        "⚠️ Credentials saved, but the first **{dag}** collection could not start. "
        "Your data will arrive with tonight's automatic run. If nothing has arrived "
        "tomorrow, let us know.",
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
    "credentials.form.enter": "Enter your credentials",
    "credentials.form.caption_first": "🔒 Encrypted on save. This is the only action to take on this page.",
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
    "credentials.probing_now": "Checking the {platform} connection…",
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
    # --- Tracks hosted on someone else's account (the GRiNCH case) ---
    # An artist signed to a label has an empty profile and always will; the
    # collectable unit for them is the track, not the profile.
    "credentials.soundcloud.claimed_header":
        "🎵 My tracks hosted on other accounts (label, collective…)",
    "credentials.soundcloud.claimed_help":
        "If your releases come out under a label's or a collective's account, your own "
        "profile is empty and will stay that way. Paste the URL of EACH track that is "
        "yours — one per line. We will collect their plays even though they live "
        "elsewhere. A track can only be claimed by one account.",
    "credentials.soundcloud.claimed_current": "**{n} track(s) declared**:",
    "credentials.soundcloud.claimed_input": "SoundCloud URLs (one per line)",
    "credentials.soundcloud.claimed_add": "➕ Declare these tracks",
    "credentials.soundcloud.claimed_empty": "Paste at least one track URL.",
    "credentials.soundcloud.claimed_not_a_track":
        "this is not a TRACK URL (it must be …/account/track-name)",
    "credentials.soundcloud.claimed_unresolved": "not found, or private",
    "credentials.soundcloud.claimed_taken":
        "this track is already claimed by another account. A track belongs to one "
        "artist only — contact us if this is wrong.",
    "credentials.soundcloud.claimed_ok":
        "✅ {n} track(s) declared. They will be collected on the next run.",
    "credentials.soundcloud.claimed_only":
        "Profile has no public track, but **{n} declared track(s)** hosted on other "
        "accounts — those are what will be collected ✅",
    "credentials.soundcloud.no_public_tracks": (
        "User ID {user_id} is reachable, but **no public track** is attached to "
        "it — there will be nothing to collect. Check that it is YOUR profile ID "
        "(not a label or secondary account) and that your tracks are **public**, "
        "not private/unlisted."
    ),
    "credentials.soundcloud.not_found": (
        "404 — User ID '{user_id}' not found. Check that it is the numeric ID."
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
    "credentials.meta.ig_id_missing": (
        "Instagram Business Account ID missing — enter it in the Meta tab "
        "(\"Instagram Business Account ID\" field). Without it, no Instagram "
        "statistics can be collected."
    ),
    "credentials.meta.network_error_probe": (
        "Network error during the Instagram test: {err}"
    ),
    "credentials.probe_network_error": (
        "Network error ({err}) — try again in a moment. If it persists, contact "
        "the administrator."
    ),
    "credentials.identity_malformed": (
        "❌ **{field}** does not have the expected format. Expected: `{shape}`. "
        "Copy the identifier alone, with no URL or surrounding characters."
    ),
    "credentials.meta.ig_id_malformed": (
        "Invalid Instagram Business Account ID: it must be digits only "
        "(e.g. 17841400000000000)."
    ),
    "credentials.meta.account_malformed": (
        "Invalid Ad Account ID: digits only, optionally prefixed with `act_` "
        "(e.g. 567214713853881)."
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
    "credentials.youtube.admin_key_invalid": "The platform's YouTube API key is being refused by Google. It is not your key and there is nothing for you to fix: please tell the administrator. Your Channel ID can stay as it is.",
    "credentials.youtube.quota_exceeded": "The platform's YouTube quota is exhausted for today. Nothing to fix on your side — try again tomorrow; the nightly collection will resume on its own.",
    "credentials.youtube.unexpected": "YouTube refused the request ({code}). {msg} If it persists, tell the administrator.",
}
