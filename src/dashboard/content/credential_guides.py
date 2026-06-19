"""Single source of truth for the API-credential setup guides (per platform).

Type: Sub
Uses: src.utils.config_loader (asset path resolution)
Depends on: nothing at import time (pure data)
Persists in: nothing

Rendered by credential_guides_st.render_credential_guides() in the
"📖 Process — Credentials" view. Screenshots are referenced by filename and
resolved anywhere under assets/credential_guide/ (flat or per-platform
subfolder); a missing file degrades gracefully. Example values are illustrative
formats only — never real secrets.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CredStep:
    text: str
    screenshot: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class CredField:
    """A value the artist pastes into 🔑 Credentials API. `example` is a fake,
    correctly-shaped sample (never a real secret)."""
    label: str
    example: str
    secret: bool = False
    note: str | None = None


@dataclass(frozen=True)
class PlatformCred:
    key: str
    title: str
    icon: str
    intro: str
    portal_url: str
    steps: tuple[CredStep, ...]
    fields: tuple[CredField, ...]
    note: str | None = None


def assets_dir() -> Path:
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "assets" / "credential_guide"


def screenshot_path(filename: str) -> Path:
    """Resolve a screenshot by filename anywhere under assets/credential_guide/
    (flat or per-platform subfolder). Falls back to the flat path if absent."""
    base = assets_dir()
    flat = base / filename
    if flat.exists():
        return flat
    return next(base.rglob(filename), flat)


# ─────────────────────────────────────────────────────────────────────────────
# Content — edit here only. Example values are FAKE, format-correct samples.
# ─────────────────────────────────────────────────────────────────────────────

_SPOTIFY = PlatformCred(
    key="spotify",
    title="Spotify",
    icon="🎵",
    intro=(
        "**Tu n'as rien à créer.** L'app Spotify est gérée par l'administrateur "
        "(partagée par tous les artistes). Tu colles **une seule valeur** : le **lien "
        "de ta page Spotify Artist**."
    ),
    portal_url="https://open.spotify.com",
    steps=(
        CredStep("Ouvre **ta page artiste** sur Spotify (appli ou open.spotify.com). "
                 "Menu **⋯ → Partager → Copier le lien vers l'artiste**. Tu obtiens "
                 "une URL du type `https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4`."),
        CredStep("Colle ce lien dans **🔑 Credentials API → Spotify** (champ *Spotify "
                 "Artist ID ou URL*), puis **Tester la connexion**. On extrait l'ID "
                 "automatiquement — pas besoin de le découper."),
    ),
    fields=(
        CredField("Spotify Artist ID ou URL",
                  "https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4",
                  note="colle l'URL complète de ta page artiste — on extrait l'ID"),
    ),
    note=(
        "**Admin (une seule fois)** : créer une app sur developer.spotify.com (flux "
        "`client_credentials`, aucune Redirect URI utilisée) et renseigner "
        "`SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` en variables d'environnement. "
        "Les artistes n'ont alors qu'à coller le lien de leur profil."
    ),
)

_YOUTUBE = PlatformCred(
    key="youtube",
    title="YouTube",
    icon="🎬",
    intro=(
        "**Côté artiste : une seule valeur — ton Channel ID** (commence par `UC…`). "
        "La clé API est **partagée (gérée par l'admin)**, tu n'as pas à en créer. "
        "Saute directement à l'étape **Channel ID** ci-dessous.\n\n"
        "*(Les étapes 1→5 ne concernent que l'admin, une seule fois, s'il met en place "
        "sa propre clé.)*"
    ),
    portal_url="https://console.cloud.google.com/apis/credentials",
    steps=(
        CredStep("**(Admin, une fois)** Sur [console.cloud.google.com/apis/dashboard](https://console.cloud.google.com/apis/dashboard), "
                 "**créez d'abord un projet** (le bouton *Activer les API* reste **grisé "
                 "tant qu'aucun projet n'existe**), puis cliquez **+ Activer les API et "
                 "les services**.",
                 "GCP_Api_services.png", "API et services → Activer les API"),
        CredStep("Dans la [Bibliothèque d'API](https://console.cloud.google.com/apis/library), "
                 "recherchez **YouTube Data API v3**.",
                 "GCP_youtube_data_api_v3.png", "Bibliothèque → rechercher l'API"),
        CredStep("Cliquez sur le résultat **YouTube Data API v3**.",
                 "GCP_youtube_click.png", "Sélection de l'API"),
        CredStep("Cliquez **Activer** ; la page produit doit afficher **API activée**.",
                 "gcp_activated_api_GCP_menu.png", "API activée"),
        CredStep("Allez dans [Identifiants](https://console.cloud.google.com/apis/credentials) → "
                 "**Créer des identifiants → Clé API**, puis **Afficher la clé** et copiez-la.",
                 "gcp_create_api_key.png", "Identifiants → Clé API → Afficher la clé"),
        CredStep("Récupérez le **Channel ID** : sur "
                 "[youtube.com/account_advanced](https://www.youtube.com/account_advanced) → "
                 "**ID de la chaîne** → **Copier** (commence par `UC…`).",
                 "youtube_id_channel.png", "YouTube → Paramètres avancés → ID de la chaîne"),
        CredStep("Collez la **clé API** + le **Channel ID** dans **🔑 Credentials API → YouTube**."),
    ),
    fields=(
        CredField("API Key", "AIzaSyA1B2c3D4e5F6g7H8i9J0kLmNoPqRsTuVwX", secret=True,  # pragma: allowlist secret
                  note="commence par 'AIza', ~39 caractères"),
        CredField("Channel ID", "UC_x5XG1OV2P6uZZ5FSM9Ttw",
                  note="commence par 'UC', 24 caractères"),
    ),
    note="Quota gratuit ~10 000 unités/jour ; un dépassement renvoie 403 (temporaire).",
)

_SOUNDCLOUD = PlatformCred(
    key="soundcloud",
    title="SoundCloud",
    icon="☁️",
    intro=(
        "Une **seule valeur** à fournir : votre **User ID** SoundCloud (un nombre). "
        "Streams et followers sont ensuite collectés automatiquement."
    ),
    portal_url="https://soundcloud.com/discover",
    steps=(
        CredStep("Connecté à SoundCloud, ouvrez "
                 "[soundcloud.com/discover](https://soundcloud.com/discover)."),
        CredStep("Affichez le **code source** de la page (**Ctrl+U**), puis cherchez "
                 "(**Ctrl+F**) `soundcloud:users:` — le **nombre** juste après est votre "
                 "**User ID** (ex. `377065610`).",
                 "soundcloud_user_id.png", "Code source → soundcloud:users:<votre ID>"),
        CredStep("Collez ce **User ID** dans **🔑 Credentials API → SoundCloud**, puis "
                 "**Tester la connexion**."),
    ),
    fields=(
        CredField("User ID", "377065610",
                  note="le nombre trouvé dans le code source de /discover"),
    ),
)

_META = PlatformCred(
    key="meta",
    title="Meta / Instagram",
    icon="📱",
    intro=(
        "Meta est **configuré au niveau de la plateforme** (app partagée). Vous "
        "fournissez **uniquement votre Ad Account ID** ; le token, l'app et "
        "Instagram sont gérés par l'administrateur."
    ),
    portal_url="https://adsmanager.facebook.com/",
    steps=(
        CredStep("Ouvrez le **Gestionnaire de publicités** "
                 "([adsmanager.facebook.com](https://adsmanager.facebook.com/)) et "
                 "connectez-vous. Sélectionnez le bon compte si vous en avez plusieurs."),
        CredStep("**Méthode la plus simple — via l'URL.** Regardez la **barre "
                 "d'adresse** de votre navigateur (tout en haut). L'URL contient un "
                 "paramètre **`act=`**, par exemple :\n\n"
                 "`adsmanager.facebook.com/adsmanager/manage/campaigns?`**`act=123456789012345`**`&business_id=…`\n\n"
                 "Votre **Ad Account ID** est le **nombre situé juste après `act=`** et "
                 "**avant le `&`** suivant. Astuce : double-cliquez sur ce nombre pour le "
                 "sélectionner, puis **Ctrl+C**.",
                 "meta_url_id.png", "Le nombre après act= dans la barre d'adresse"),
        CredStep("⚠️ Ne confondez pas avec `business_id=…` (votre Business Manager) ni "
                 "avec un **ID d'ensemble de publicités** (ad set) : seul le nombre "
                 "après **`act=`** est le bon."),
        CredStep("Collez ce nombre dans **🔑 Credentials API → Meta / Instagram**, puis "
                 "**Tester la connexion**. (Le préfixe `act_` est ajouté automatiquement.)"),
    ),
    fields=(
        CredField("Ad Account ID", "act_1234567890",
                  note="le seul champ — nombre ou préfixé 'act_'"),
    ),
    note=(
        "**Prérequis admin** : votre compte publicitaire doit être lié à l'app "
        "partagée (System User) dans Business Manager pour que la collecte "
        "fonctionne. Instagram est rattaché côté admin."
    ),
)

CREDENTIAL_GUIDES: tuple[PlatformCred, ...] = (_SOUNDCLOUD, _SPOTIFY, _YOUTUBE, _META)
