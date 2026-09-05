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
    intro=None,
    portal_url="https://open.spotify.com",
    # Une ligne, comme la source française. Ce bloc est resté à l'ancienne version
    # tout un lot parce qu'un `str.replace` sans assertion n'a pas mordu et n'a rien
    # dit — la traduction du catalogue masquait l'écart à l'écran, mais le PDF anglais
    # est rendu depuis CETTE source et portait encore trois étapes.
    steps=(
        CredStep("`•••` button → **Share** → **Copy link to artist** → paste it into "
                 "**Artist profile URL**, above.",
                 "spotify_share_artist_link.png",
                 "The ••• button → Share → Copy link to artist"),
    ),
    fields=(
        CredField("Artist profile URL",
                  "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV",
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
    intro=None,
    portal_url="https://soundcloud.com",
    steps=(
        CredStep("Open your **SoundCloud profile** and copy the address shown in the "
                 "browser bar — it looks like `https://soundcloud.com/your-name`."),
        CredStep("Paste it into **Enter your credentials**, the left-hand column, "
                 "then **Save**."),
    ),
    fields=(
        CredField("SoundCloud profile", "https://soundcloud.com/your-name",
                  note="your page link — nothing to cut out"),
    ),
)

_META = PlatformCred(
    key="meta",
    title="Meta / Instagram",
    icon="📱",
    # No intro, like Spotify. Kept in step with the FR guide (2026-09-05): three
    # actions, nothing that merely describes context. See `credential_guides.py`
    # for what was removed and why — `test_the_two_language_guides_stay_in_step`
    # fails if the two drift apart.
    intro=None,
    portal_url="https://adsmanager.facebook.com/",
    steps=(
        CredStep("Open the portal above, pick the account you want to track, then "
                 "**copy the address bar** and paste it into **Your ad account "
                 "link**, above.",
                 "meta_url_id.png", "The number after act= in the address bar"),
        # This step existed as an "**Admin prerequisite**" footnote. The label told
        # the artist it was not their job — while it is THEIR ad account, in THEIR
        # Business Manager, and nobody else can do it for them. So they did not, the
        # connection test failed, and nothing said why. That is the 2026-06-19
        # session, and it is why this step survived the trim.
        CredStep("⚠️ **Share this account with our application — nobody can do it "
                 "for you.** Without that sharing, collection sees nothing, even "
                 "with the right link.\n\n"
                 f"[Business Manager → Apps]({_META_BM_APPS_URL}) → look for "
                 f"**{META_APP_DISPLAY_NAME}** (not in the list? ask us to add you). "
                 f"Then [Ad accounts]({_META_BM_ADACCOUNTS_URL}) → **Add people / "
                 "apps** → grant **Analyst** permission."),
        CredStep("**Instagram, optional.** Business Suite → **Settings → Accounts → "
                 "Instagram accounts** → copy the **numeric ID** shown under the name "
                 "(not your @handle). The account must be **Business or Creator** and "
                 "linked to a **Facebook Page**."),
    ),
    fields=(
        CredField("Your ad account link",
                  "https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=123456789012345",
                  note="paste the full Ads Manager URL — we extract the account "
                       "number from it"),
        CredField("Instagram Business Account ID", "17841400000000000",
                  note="optional — ~17 digits, for Instagram stats"),
    ),
    admin_note=(
        "On our side: System User created, 5-scope token in place, and the Instagram "
        "attachment done at the Facebook Page level."
    ),
)

CREDENTIAL_GUIDES_EN: tuple[PlatformCred, ...] = (_SPOTIFY, _YOUTUBE, _SOUNDCLOUD, _META)
