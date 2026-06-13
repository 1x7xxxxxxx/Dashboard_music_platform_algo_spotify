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
    intro=(
        "You only need **2 values**: the **Client ID** and the **Client Secret**."
    ),
    portal_url="https://developer.spotify.com/dashboard",
    steps=(
        CredStep("Go to developer.spotify.com/dashboard and sign in with your "
                 "**usual Spotify account** (no paid plan required)."),
        CredStep("Click **Create app**."),
        CredStep("Fill in: **App name** (e.g. `ETL Dashboard`), a **description**, "
                 "and **Redirect URI** = `http://127.0.0.1:8888/callback` (dummy "
                 "value, see the note below). Tick **Web API**, then **Save**."),
        CredStep("On the app page → **Settings / Basic Information**: copy the "
                 "**Client ID** and the **Client secret** (copy button ⧉).",
                 "spotify_4_developper_credential_process.png",
                 "Basic Information → Client ID + Client secret"),
        CredStep("Paste the 2 values into **🔑 API Credentials → Spotify**, then "
                 "**Test the connection**."),
    ),
    fields=(
        CredField("Client ID", "3a9f1c7e8b2d4f60a1c5e9d3b7f02a6c",  # pragma: allowlist secret
                  note="32 hexadecimal characters"),
        CredField("Client Secret", "b7e2d9f04a1c6358e0a2b4c6d8e0f1a2", secret=True,  # pragma: allowlist secret
                  note="32 characters — keep it private"),
    ),
    note=(
        "**Redirect URI**: the return URL after an OAuth login. Our "
        "`client_credentials` flow has no login → this URL is **never used**, but "
        "Spotify requires at least one. Set `http://127.0.0.1:8888/callback` and "
        "forget it. The app stays in **Development mode**, which is enough."
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
        CredStep("View the page **source** (**Ctrl+U**), then search (**Ctrl+F**) "
                 "for `soundcloud:users:` — the **number** right after is your "
                 "**User ID** (e.g. `377065610`).",
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
                 "it, then **Ctrl+C**.",
                 "meta_url_id.png", "The number after act= in the address bar"),
        CredStep("⚠️ Don't confuse it with `business_id=…` (your Business Manager) "
                 "or an **ad set ID**: only the number after **`act=`** is correct."),
        CredStep("Paste this number into **🔑 API Credentials → Meta / Instagram**, "
                 "then **Test the connection**. (The `act_` prefix is added automatically.)"),
    ),
    fields=(
        CredField("Ad Account ID", "act_1234567890",
                  note="the only field — number or 'act_'-prefixed"),
    ),
    note=(
        "**Admin prerequisite**: your ad account must be linked to the shared app "
        "(System User) in Business Manager for collection to work. Instagram is "
        "attached on the admin side."
    ),
)

CREDENTIAL_GUIDES_EN: tuple[PlatformCred, ...] = (_SPOTIFY, _YOUTUBE, _SOUNDCLOUD, _META)
