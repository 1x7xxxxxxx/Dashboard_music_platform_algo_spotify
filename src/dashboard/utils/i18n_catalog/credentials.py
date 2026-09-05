"""EN catalog for the credentials (API Credentials) view package."""

EN = {
    # ── router.py ──────────────────────────────────────────────────────
    "credentials.title": "🔑 API Credentials + CSV imports",
    "credentials.tab_bar": "Platform",
    "credentials.csv_tab": "📂 My files (Spotify for Artists, Apple)",
    "credentials.csv_tab_help": (
        "These two sources are not connected with an identifier: they let you "
        "download a spreadsheet file. Drop it here — the type is recognised on its "
        "own, you never have to open it."
    ),
    "credentials.no_active_artist": "No active artist. Create one in the Admin tab.",
    "credentials.target_artist": "Target artist",
    "credentials.no_artist_id": "Unable to determine your artist identifier.",
    "credentials.fernet_missing": (
        "⚠️ `fernet_key` missing from `config/config.yaml`. "
        "Saving is disabled. Generate a key by pasting these lines into a "
        "terminal opened at the project root:"
    ),
    "credentials.fetching_dag_status": "Fetching DAG status…",
    "credentials.soundcloud.inconclusive_page": (
        "Profile reachable. The first page of tracks came back empty while the "
        "platform announces more — tonight's collection will settle it."
    ),
    # Un titre par situation (2026-09-05) — `ok is False` en recouvrait huit, et
    # « the platform is not responding yet » était faux pour les huit.
    "credentials.verdict_unreachable": (
        "❌ {platform}: saved, but the platform did not answer."
    ),
    "credentials.verdict_refused": "❌ {platform}: the platform refused our access.",
    "credentials.verdict_not_found": "❌ {platform}: this identifier does not exist.",
    "credentials.verdict_identity_missing": "⚠️ {platform}: your identifier is missing.",
    "credentials.verdict_nothing_to_collect": (
        "⚠️ {platform}: reachable, but there is nothing to collect."
    ),
    "credentials.verdict_resolved": (
        "👉 {platform}: almost — one value to copy across."
    ),
    "credentials.verdict_sharing_missing": (
        "⚠️ {platform}: this account is not shared with us yet."
    ),
    "credentials.identity_taken_admin": "🛠️ Held by artist #{other}.",
    "credentials.identity_taken": (
        "❌ **{field} = {value}** already belongs to another account. A platform "
        "identifier can belong to one artist only — check that this one is yours. "
        "If you believe this is a mistake, contact the administrator."
    ),
    "credentials.field.client_id": "Client ID",
    "credentials.field.client_secret": "Client Secret",  # pragma: allowlist secret
    "credentials.field.api_key": "API Key (YouTube Data API v3)",  # pragma: allowlist secret
    "credentials.field.channel_id": "Channel ID (UC…)",
    "credentials.field.user_id": "Link to your SoundCloud profile",
    "credentials.field.account_id": "Ad Account ID (act_… or numeric)",
    "credentials.field.extra_account_ids": (
        "Extra ad accounts - for agencies (optional)"
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
    "credentials.creds_saved": (
        "Value saved on {updated} — saved does not mean verified: the test "
        "below is what says so."
    ),
    "credentials.form.enter": "Enter your credentials",
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
    "credentials.test_data_wins": (
        "✅ Data has actually arrived for this platform — the connection works."
    ),
    "credentials.test_failed_but_data": (
        "The test says otherwise, and it is wrong about the consequence: « {msg} »"
    ),
    "credentials.test_failed": "Connection failed: {msg}",
    # ── _render.py — save handler ──────────────────────────────────────
    "credentials.collect_started": (
        "🚀 {platform} collection started — data available in ~2 min"
    ),
    "credentials.dag_trigger_failed": (
        "⚠️ Credentials saved, but the first collection could not start ({err}). "
        "It will run again tonight."
    ),
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
        "Nothing to test: paste the **link to your SoundCloud profile** "
        "(https://soundcloud.com/your-name) in the field below — we derive your "
        "User ID from it."
    ),
    "credentials.resolve.empty": "Paste the link to your SoundCloud profile first.",
    "credentials.resolve.app_not_configured": (
        "The platform's SoundCloud app is not configured — this is on us, not you. "
        "Please report it to the administrator."
    ),
    "credentials.resolve.token_refused": (
        "SoundCloud did not issue a token to the platform — this is not on you. "
        "Try again in a few minutes."
    ),
    "credentials.resolve.not_found": (
        "SoundCloud does not know this link. Check it is your PROFILE address, "
        "for example https://soundcloud.com/your-name"
    ),
    "credentials.resolve.upstream_error": (
        "SoundCloud did not answer. Try again in a few minutes."
    ),
    "credentials.resolve.is_a_track": (
        "That link points to a track, not a profile. Click your artist name at the "
        "top of the page, then copy the address."
    ),
    "credentials.soundcloud.resolved": (
        "Link recognised: soundcloud.com/{p} → User ID **{i}**"
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
    # Cette traduction a perdu LA MOITIÉ du message français : elle ne disait que
    # « vérifie que c'est ton profil », et taisait le recours pour un artiste signé
    # sur un label — c'est-à-dire le cas qui a motivé toute la fonctionnalité (GRiNCH,
    # 2026-08-23, `track_count=0` par construction). Un anglophone dans ce cas lisait
    # « ton ID est peut-être faux » alors que son ID était juste.
    "credentials.soundcloud.no_public_tracks": (
        "User ID {user_id} is reachable, but **no public track** is attached to it — "
        "there will be nothing to collect. Two cases:\n\n"
        "• **Your releases come out under a label or another account** → declare them "
        "on the **☁️ SoundCloud — Performance** page, section « Mes titres hébergés "
        "sur d'autres comptes ». Paste each track URL, one per line.\n"
        "• **Otherwise** → check that this is YOUR profile ID and that your tracks are "
        "**public** (not private or unlisted)."
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
    # Le geste courant, le même que le guide. Il nommait « Apps →
    # ETL_DASHBOARD_SPOTIFY → Business Assets » : un chemin infaisable, une app
    # n'apparaissant que dans le Business Manager qui la possède.
    "credentials.meta.account_unreachable": (
        "Ad account **{act}**: it is not shared with us yet. {detail}\n\n"
        "→ Business Manager → **Ad accounts** → your account → **Partners** → "
        "**Assign partner** → {where} → **Analyst** role."
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
    "credentials.guide.portal_search": "🔗 Open **{name}** on {title}: [{url}]({url})",
    "credentials.guide.portal": "🔗 Portal: [{url}]({url})",
    "credentials.guide.col_field": "Field",
    "credentials.guide.col_example": "Example (fake)",
    "credentials.guide.col_note": "Note",
    "credentials.guide.paste_caption": "Values to paste into 🔑 API Credentials:",
    # ── credential_guides.py — Spotify guide ───────────────────────────
    "credentials.guide.spotify.expander": "{icon} {title} — obtain the credentials",
    # Pas d'`intro` : la source française n'en a plus. Et les étapes ci-dessous
    # étaient périmées d'une autre façon — DEUX étapes là où le français en a trois,
    # avec « Test connection » alors que le bouton dit « Enregistrer » depuis
    # longtemps. Le rendu préférant la traduction à la source, un lecteur anglophone
    # recevait un guide qu'aucun francophone ne lisait plus (même défaut que
    # SoundCloud, corrigé la veille — voir `test_the_soundcloud_ask_is_one_thing`).
    "credentials.guide.spotify.step_1": (
        "`•••` button → **Share** → **Copy link to artist** → paste it into "
        "**Artist profile URL**, above."
    ),
    "credentials.guide.spotify.field_1": "Artist profile URL",
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
    # Pas d'`intro` : le guide FR n'en a plus, et une clé de catalogue qui survit à
    # sa source réapparaît telle quelle à l'écran. C'est ce qui s'était produit ici —
    # ces clés décrivaient encore la procédure « cherche `soundcloud:users:` dans le
    # code source de la page », abandonnée le 2026-09-03 côté français. Un lecteur
    # anglophone lisait donc un guide qu'aucun français ne lisait plus, et le rendu
    # préfère la traduction à la source (2026-09-04).
    "credentials.guide.soundcloud.step_1": (
        "Open your **SoundCloud profile** and copy the address shown in the browser "
        "bar — it looks like `https://soundcloud.com/your-name`."
    ),
    "credentials.guide.soundcloud.step_2": (
        "Paste it into **Enter your credentials**, the left-hand column, then **Save**."
    ),
    "credentials.guide.soundcloud.field_1": "SoundCloud profile",
    "credentials.guide.soundcloud.note_1": "your page link — nothing to cut out",
    # ── credential_guides.py — Meta guide ──────────────────────────────
    "credentials.guide.meta.expander": "{icon} {title} — obtain the credentials",
    # Trois chaînes de clics, en step avec les deux guides (2026-09-05).
    # L'étape de partage nomme NOTRE Business ID, pas notre app : une app
    # n'apparaît que dans le Business Manager qui la possède.
    "credentials.guide.meta.step_1": (
        "🔗 [Ads Manager](https://adsmanager.facebook.com/) → pick your account → "
        "**copy the URL** and paste it above."
    ),
    "credentials.guide.meta.step_1_caption": (
        "The number after act= in the address bar"
    ),
    "credentials.guide.meta.step_2": (
        "🤝 **Share this account with us** — without it, collection sees nothing, "
        "even with the right link.\n\n"
        "⚙️ [Ad accounts](https://business.facebook.com/settings/ad-accounts) → your "
        "account → **Partners** → **Assign partner** → paste our Business ID → "
        "**Analyst** role."
    ),
    "credentials.guide.meta.step_3": (
        "📸 [Instagram accounts](https://business.facebook.com/settings/instagram-accounts) "
        "→ your account → copy the **numeric ID** under the name (not your @handle)."
        "\n\nIt must be a **Business** or **Creator** account, linked to a "
        "**Facebook Page**."
    ),
    "credentials.guide.meta.field_0": "Your ad account link",
    "credentials.guide.meta.note_0": (
        "paste the full Ads Manager URL — we extract the account number from it"
    ),
    # Trois étapes depuis le 2026-09-05, en step avec `credential_guides.py` et
    # `credential_guides_en.py`. Les anciennes `step_4` / `note` / `intro` ont été
    # retirées avec les étapes qu'elles traduisaient — une traduction qui survit à
    # son étape décrit un écran qui n'existe plus.
    "credentials.youtube.admin_key_invalid": "The platform's YouTube API key is being refused by Google. It is not your key and there is nothing for you to fix: please tell the administrator. Your Channel ID can stay as it is.",
    "credentials.youtube.quota_exceeded": "The platform's YouTube quota is exhausted for today. Nothing to fix on your side — try again tomorrow; the nightly collection will resume on its own.",
    "credentials.youtube.unexpected": "YouTube refused the request ({code}). {msg} If it persists, tell the administrator.",

    # ── La sélection, énumérée + le verdict de sauvegarde (2026-09-04) ──
    "credentials.next_in_tab": "{name} — in the **{tab}** tab",
    "credentials.focus_elsewhere": (
        "📂 **{names}** is not connected with an identifier: it is a file to drop. "
        "Its page is **📂 Add my Spotify for Artists & Apple figures**."
    ),
    "credentials.focus_elsewhere_go": "📂 Go and drop my files →",
    "credentials.guide.paste_header": "**The values to paste:**",
    "credentials.guide.example_inline": (
        "*e.g. {example}* — sample format, do not copy it"
    ),
    "credentials.probing_now": (
        "⏳ Setting up **{platform}** — asking the platform whether it answers…"
    ),
    "credentials.verdict_ok": "✅ {platform} is connected.",
    "credentials.verdict_next": "👉 Next: **{label}**",
    "credentials.verdict_all_done": (
        "🎉 Every platform you picked is connected. The first data arrives in ~2 min."
    ),
    "credentials.verdict_go_home": "🏠 Go to the dashboard →",
    "credentials.verdict_ko": (
        "❌ {platform}: saved, but the connection is not proven."
    ),
    "credentials.verdict_ko_what_now": (
        "Fix it below then **💾 Save** again — we will re-test straight away."
    ),
    "credentials.verdict_saved": "💾 {platform} saved.",
    "credentials.verdict_unknown": (
        "The check could not conclude for now. Use **🔌 Test the connection** below, "
        "or come back in a few minutes — tonight's collection will settle it anyway."
    ),

    # ── L'assistant « trouve mon numéro de compte » (2026-09-04) ──
    "credentials.form.example_inline": "e.g. {ex}",
}
