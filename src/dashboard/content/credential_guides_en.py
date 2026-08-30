"""EN translation of the API-credential guides (mirror of CREDENTIAL_GUIDES).

Type: Sub
Depends on: credential_guides (dataclasses + screenshot resolver reused as-is)

Only the prose is translated; screenshots, portal URLs and the fake example
values are shared with the FR source. Selected by the guide PDF when lang == 'en'.
"""
from src.dashboard.content.credential_guides import CredStep, CredField, PlatformCred

_SPOTIFY = PlatformCred(
    key="spotify",
    title="Spotify",
    icon="🎵",
        intro="**One single value to paste: the link to your Spotify Artist page.**",
    portal_url="https://open.spotify.com",
    steps=(
        CredStep("On Spotify, open **your artist page** → **⋯** → **Share** → "
                 "**Copy link to artist**."),
        CredStep("Paste it below → **Save**. We extract the ID automatically — "
                 "no need to cut it up."),
    ),
    fields=(
        CredField("Spotify Artist ID or URL",
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
        "A **single value** to provide: your SoundCloud **User ID** (a number). "
        "Streams and followers are then collected automatically."
    ),
    portal_url="https://soundcloud.com/discover",
    steps=(
        CredStep("Signed into SoundCloud, open "
                 "[soundcloud.com/discover](https://soundcloud.com/discover)."),
        CredStep("View the page **source** (**{{VIEW_SOURCE}}**), then search "
                 "(**{{FIND}}**) for exactly this:\n\n"
                 "```\nsoundcloud:users:\n```\n"
                 "The **number stuck right after the colon** is your **User ID** — in "
                 "`soundcloud:users:377065610` that is `377065610`. Copy neither the "
                 "prefix nor the colon.",
                 "soundcloud_user_id.png", "Source → soundcloud:users:<your ID>"),
        CredStep("Paste this **User ID** into **🔑 API Credentials → SoundCloud**, "
                 "then **Test the connection**."),
    ),
    fields=(
        CredField("User ID", "377065610",
                  note="the number found in the /discover page source"),
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
        CredStep("Open the **Ads Manager** "
                 "([adsmanager.facebook.com](https://adsmanager.facebook.com/)) and "
                 "sign in. Pick the right account if you have several."),
        CredStep("**Easiest method — via the URL.** Look at your browser's "
                 "**address bar** (at the very top). The URL contains an **`act=`** "
                 "parameter, for example:\n\n"
                 "`adsmanager.facebook.com/adsmanager/manage/campaigns?`**`act=123456789012345`**`&business_id=…`\n\n"
                 "Your **Ad Account ID** is the **number right after `act=`** and "
                 "**before the next `&`**. Tip: double-click that number to select "
                 "it, then **{{COPY}}**.",
                 "meta_url_id.png", "The number after act= in the address bar"),
        CredStep("⚠️ Don't confuse it with `business_id=…` (your Business Manager) "
                 "or an **ad set ID**: only the number after **`act=`** is correct."),
        # This step existed as an "**Admin prerequisite**" footnote. The label told
        # the artist it was not their job — while it is THEIR ad account, in THEIR
        # Business Manager, and nobody else can do it for them. So they did not, the
        # connection test failed, and nothing said why. That is the 2026-06-19
        # session.
        CredStep("⚠️ **Required, and it is yours to do.** Until this account is "
                 "shared, collection sees nothing — even with the right ID. In "
                 "**Business Manager → Settings → Apps**, find "
                 "**ETL_DASHBOARD_SPOTIFY** (ask us to add it if it is not there), "
                 "then **Business Assets → Add Assets → Ad Account**: pick yours and "
                 "grant **Analyst** (or Advertiser) permission."),
        CredStep("Paste this number into **🔑 API Credentials → Meta / Instagram**, "
                 "then **Test the connection**. (The `act_` prefix is added automatically.)"),
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
        CredField("Ad Account ID", "act_1234567890",
                  note="number or 'act_'-prefixed — for Meta Ads"),
        CredField("Instagram Business Account ID", "17841400000000000",
                  note="optional — ~17 digits, for Instagram stats"),
    ),
    admin_note=(
        "On our side: System User created, 5-scope token in place, and the Instagram "
        "attachment done at the Facebook Page level."
    ),
)

CREDENTIAL_GUIDES_EN: tuple[PlatformCred, ...] = (_SPOTIFY, _YOUTUBE, _SOUNDCLOUD, _META)
