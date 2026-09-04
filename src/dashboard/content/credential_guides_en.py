"""EN translation of the API-credential guides (mirror of CREDENTIAL_GUIDES).

Type: Sub
Depends on: credential_guides (dataclasses + screenshot resolver reused as-is)

Only the prose is translated; screenshots, portal URLs and the fake example
values are shared with the FR source. Selected by the guide PDF when lang == 'en'.
"""
from src.dashboard.content.credential_guides import (
    META_APP_DISPLAY_NAME,
    _META_BM_ADACCOUNTS_URL,
    _META_BM_APPS_URL,
    CredField,
    CredStep,
    PlatformCred,
)

_SPOTIFY = PlatformCred(
    key="spotify",
    title="Spotify",
    icon="🎵",
        intro="**One single value to paste: the link to your Spotify Artist page.**",
    portal_url="https://open.spotify.com",
    steps=(
        CredStep("On Spotify, open **your artist page**, then click the `•••` "
                 "button — the **three dots**, to the right of the "
                 "*Follow / Following* button.",
                 "spotify_share_artist_link.png",
                 "The ••• button → Share → Copy link to artist"),
        CredStep("In the menu that opens: **Share** → **Copy link to artist**."),
        CredStep("Paste the link into the **Spotify Artist ID or profile URL** "
                 "field, then **💾 Save**."),
    ),
    fields=(
        CredField("Spotify Artist ID or profile URL",
                  "https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4",
                  note="paste the full URL of your artist page — we extract the id"),
    ),
    admin_note=(
        "**Admin, once** : create an app on developer.spotify.com (`client_credentials` "
        "flow, no Redirect URI is ever used) and set `SPOTIFY_CLIENT_ID` / "
        "`SPOTIFY_CLIENT_SECRET` as environment variables. Artists then only paste "
        "their profile link."
    ),
)

_YOUTUBE = PlatformCred(
    key="youtube",
    title="YouTube",
    icon="🎬",
    intro=(
        "**2 values** to grab: the **API key** (YouTube Data API v3) and your "
        "**channel ID**."
    ),
    portal_url="https://console.cloud.google.com/apis/credentials",
    steps=(
        CredStep("At [console.cloud.google.com/apis/dashboard](https://console.cloud.google.com/apis/dashboard), "
                 "create (or select) a project, then click **+ Enable APIs and services**.",
                 "GCP_Api_services.png", "APIs & services → Enable APIs"),
        CredStep("In the [API Library](https://console.cloud.google.com/apis/library), "
                 "search for **YouTube Data API v3**.",
                 "GCP_youtube_data_api_v3.png", "Library → search the API"),
        CredStep("Click the **YouTube Data API v3** result.",
                 "GCP_youtube_click.png", "Select the API"),
        CredStep("Click **Enable**; the product page should show **API enabled**.",
                 "gcp_activated_api_GCP_menu.png", "API enabled"),
        CredStep("Go to [Credentials](https://console.cloud.google.com/apis/credentials) → "
                 "**Create credentials → API key**, then **Show key** and copy it.",
                 "gcp_create_api_key.png", "Credentials → API key → Show key"),
        CredStep("Get the **Channel ID**: at "
                 "[youtube.com/account_advanced](https://www.youtube.com/account_advanced) → "
                 "**Channel ID** → **Copy** (starts with `UC…`).",
                 "youtube_id_channel.png", "YouTube → Advanced settings → Channel ID"),
        CredStep("Paste the **API key** + the **Channel ID** into **🔑 API Credentials → YouTube**."),
    ),
    fields=(
        CredField("API Key", "AIzaSyA1B2c3D4e5F6g7H8i9J0kLmNoPqRsTuVwX", secret=True,  # pragma: allowlist secret
                  note="starts with 'AIza', ~39 characters"),
        CredField("Channel ID", "UC_x5XG1OV2P6uZZ5FSM9Ttw",
                  note="starts with 'UC', 24 characters"),
    ),
    note="Free quota ~10,000 units/day; exceeding it returns 403 (temporary).",
)

_SOUNDCLOUD = PlatformCred(
    key="soundcloud",
    title="SoundCloud",
    icon="☁️",
    intro=(
        "A **single thing** to provide: the **link to your SoundCloud profile**. "
        "We derive your identifier from it; streams and followers are then collected "
        "automatically."
    ),
    portal_url="https://soundcloud.com",
    steps=(
        CredStep("Open your **SoundCloud profile** and copy the address shown in the "
                 "browser bar — it looks like `https://soundcloud.com/your-name`."),
        CredStep("Paste that link into **🔑 API Credentials → SoundCloud**, then "
                 "**Save**. Your User ID is looked up automatically and shown back "
                 "to you as confirmation."),
    ),
    fields=(
        CredField("SoundCloud profile", "https://soundcloud.com/your-name",
                  note="your page link; the numeric User ID is derived from it"),
    ),
)

_META = PlatformCred(
    key="meta",
    title="Meta / Instagram",
    icon="📱",
    intro=(
        "Meta is **configured at the platform level** (shared app). You provide "
        "**only your Ad Account ID**; the token, the app and Instagram are managed "
        "by the administrator."
    ),
    portal_url="https://adsmanager.facebook.com/",
    steps=(
        CredStep("Open the portal above and sign in. If you manage **several ad "
                 "accounts**, pick the one you want to track first: that is the one "
                 "the address will name."),
        CredStep("**Simplest: copy the whole address.** Click your browser's "
                 "**address bar** (at the very top), copy all of it, and paste it "
                 "as-is — we extract the account number from it.\n\n"
                 "`adsmanager.facebook.com/adsmanager/manage/campaigns?`**`act=123456789012345`**`&business_id=…`\n\n"
                 "If you would rather paste the number only, take the one right "
                 "after **`act=`**, stopping at the `&`. **With or without the "
                 "`act_` prefix, both work**: `act_123456789012345` and "
                 "`123456789012345` are accepted identically.",
                 "meta_url_id.png", "The number after act= in the address bar"),
        CredStep("⚠️ Don't confuse it with `business_id=…` (your Business Manager) "
                 "or an **ad set ID**: only the number after **`act=`** is correct."),
        # This step existed as an "**Admin prerequisite**" footnote. The label told
        # the artist it was not their job — while it is THEIR ad account, in THEIR
        # Business Manager, and nobody else can do it for them. So they did not, the
        # connection test failed, and nothing said why. That is the 2026-06-19
        # session.
        CredStep("⚠️ **Required, and it is yours to do.** Until this account is "
                 "shared, collection sees nothing — even with the right ID.\n\n"
                 f"Open [Business Manager → Apps]({_META_BM_APPS_URL}) and look for "
                 f"**{META_APP_DISPLAY_NAME}** — that is the name **our application "
                 "goes by on Meta**; if it is not in the list, ask us to add it. "
                 f"Then, in [Ad accounts]({_META_BM_ADACCOUNTS_URL}) → **Add people "
                 "/ apps**, pick yours and grant **Analyst** (or Advertiser) "
                 "permission."),
        CredStep("Paste the value into the **Ad Account ID** field, then "
                 "**💾 Save** — the connection is tested right after. A ❌ here "
                 "almost always points back to the sharing step above."),
        CredStep("**Instagram (optional but recommended).** To track followers and "
                 "posts we need the **Instagram Business Account ID** — not your "
                 "@handle. Open **Meta Business Suite → Settings → Accounts → "
                 "Instagram accounts**, select your account: the **numeric ID** is "
                 "shown under the name. Paste it into *Instagram Business Account ID*."),
        CredStep("⚠️ Instagram prerequisite: the account must be a **Business** or "
                 "**Creator** account (not personal) linked to a **Facebook Page**. "
                 "A personal account returns no statistics through the API."),
    ),
    fields=(
        CredField("Ad Account ID (act_… or numeric)", "act_1234567890",
                  note="the full Ads Manager URL works too — `act_1234567890` and "
                       "`1234567890` are accepted identically"),
        CredField("Instagram Business Account ID", "17841400000000000",
                  note="optional — ~17 digits, for Instagram stats"),
    ),
    admin_note=(
        "On our side: System User created, 5-scope token in place, and the Instagram "
        "attachment done at the Facebook Page level."
    ),
)

CREDENTIAL_GUIDES_EN: tuple[PlatformCred, ...] = (_SPOTIFY, _YOUTUBE, _SOUNDCLOUD, _META)
