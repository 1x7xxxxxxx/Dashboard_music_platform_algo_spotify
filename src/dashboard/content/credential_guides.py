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
import os
from dataclasses import dataclass
from pathlib import Path


# Le nom sous lequel NOTRE application Meta apparaît dans le Business Manager de
# l'artiste. Demandé le 2026-09-04 : « l'user ne doit pas voir le nom de l'app admin
# ou je comprends mal quelque chose ? »
#
# Il doit le voir, et c'est la seule réponse honnête : pour partager SON compte
# publicitaire, il doit retrouver cette app dans SON Business Manager, où Meta
# l'affiche déjà. Le masquer rendrait l'étape infaisable. Ce qui était réellement
# faux, c'est que ce nom — un identifiant interne — était écrit en dur dans le
# guide sans dire à quoi il correspond : le jour où l'app est renommée côté Meta,
# le guide envoie l'artiste chercher quelque chose qui n'existe plus, et rien ne le
# signale. Il vient donc de la configuration, comme le reste de l'identité Meta.
META_APP_DISPLAY_NAME = os.getenv("META_APP_DISPLAY_NAME", "ETL_DASHBOARD_SPOTIFY")

# Le réglage exact, chez Meta, où se fait le partage. Un lien vaut mieux qu'un
# chemin de menu recopié : les libellés de Business Manager changent, les URL non.
_META_BM_APPS_URL = "https://business.facebook.com/settings/apps"
_META_BM_ADACCOUNTS_URL = "https://business.facebook.com/settings/ad-accounts"


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
    # Un portail qu'on peut ouvrir DÉJÀ POSÉ sur l'artiste, quand la plateforme
    # expose une recherche par URL. `{q}` reçoit son nom d'artiste, échappé.
    # Demandé en test le 2026-08-30 : « vu qu'on a le nom d'artiste, on pourrait
    # même proposer le lien avec son nom directement dans l'URL ? ». Oui — et
    # c'est la seule façon de raccourcir une étape sans retirer d'information :
    # le lien fait le travail au lieu de le décrire.
    #
    # Ce n'est PAS `https://open.spotify.com/artist/` : sans identifiant derrière,
    # cette URL est un 404. Le testeur l'avait proposée puis retirée lui-même.
    portal_search_url: str | None = None
    # Ce que l'ARTISTE doit lire. Rendu sur sa page et dans son PDF.
    note: str | None = None
    # Ce que l'ADMIN doit lire, et lui seul. Ni sur l'écran de l'artiste, ni dans
    # son PDF.
    #
    # Le champ existe parce que la distinction manquait : la note Spotify disait
    # « **Admin (une seule fois)** : créer une app sur developer.spotify.com…
    # renseigner SPOTIFY_CLIENT_ID en variables d'environnement. Les artistes n'ont
    # alors qu'à coller le lien de leur profil. » Sa dernière phrase prouve qu'elle
    # est écrite POUR l'admin — et elle s'affichait à l'artiste, sur la page où il
    # doit justement se contenter de coller un lien.
    admin_note: str | None = None


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
    # Au plus court. L'intro expliquait d'abord que l'app est « gérée par
    # l'administrateur et partagée par tous les artistes » — une information
    # d'architecture, vraie, et sans usage pour quelqu'un qui a une valeur à coller.
    # Signalé en test le 2026-08-30 : « ça ajoute de la complexité pour rien, il faut
    # être au plus simple possible ». Une seule phrase, à l'impératif.
    intro="**Une seule valeur à coller : le lien de ta page Spotify Artist.**",
    portal_url="https://open.spotify.com",
    portal_search_url="https://open.spotify.com/search/{q}/artists",
    steps=(
        # `⋯` seul se lisait comme une coupure de texte, pas comme un bouton :
        # signalé le 2026-09-04 — « on peut confondre avec du texte ». Le glyphe
        # porte donc un fond de code (une forme, pas une ponctuation), il est NOMMÉ
        # en toutes lettres, et il est situé par rapport à un repère que l'artiste
        # a sous les yeux. La capture d'écran fait le reste : c'est l'étape où deux
        # testeurs se sont arrêtés.
        CredStep("Sur Spotify, ouvre **ta page artiste**, puis clique le bouton "
                 "`•••` — les **trois petits points**, à droite du bouton "
                 "*Suivre / Abonné*.",
                 "spotify_share_artist_link.png",
                 "Le bouton ••• → Partager → Copier le lien vers l'artiste"),
        CredStep("Dans le menu qui s'ouvre : **Partager** → **Copier le lien vers "
                 "l'artiste**."),
        # Trois formulations en trois jours pour cette étape, et à chaque fois pour
        # la même raison : elle décrivait OÙ coller, donc elle devenait fausse dès
        # que le formulaire bougeait.
        #
        #   « Colle-le ci-dessous »  → faux quand le guide est passé SOUS le
        #                              formulaire (ce qui est dessous, c'est le DAG) ;
        #   « page Credentials API → Spotify, encadré Saisir tes identifiants »
        #                            → exact, et redondant depuis que le guide est la
        #                              colonne de droite DE cet encadré : on décrit à
        #                              quelqu'un l'endroit où il se trouve déjà.
        #
        # Elle ne dit donc plus que le CHAMP, qui est la seule chose à savoir et la
        # seule qui ne bouge pas — vrai à l'écran comme dans le PDF, qui n'a ni
        # « dessus », ni « à côté ».
        CredStep("Colle le lien dans le champ **Spotify Artist ID ou URL profil**, "
                 "puis **💾 Enregistrer**."),
    ),
    fields=(
        CredField("Spotify Artist ID ou URL profil",
                  "https://open.spotify.com/artist/3TVXtAsR1Inumwj472S9r4",
                  note="colle l'URL complète de ta page artiste — on extrait l'ID"),
    ),
    admin_note=(
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
        "Une **seule chose** à fournir : le **lien de votre profil** SoundCloud. "
        "On en déduit votre identifiant ; streams et followers sont ensuite collectés "
        "automatiquement."
    ),
    portal_url="https://soundcloud.com",
    steps=(
        CredStep("Ouvrez votre **profil SoundCloud** et copiez l'adresse affichée "
                 "dans la barre du navigateur — elle ressemble à "
                 "`https://soundcloud.com/votre-nom`."),
        CredStep("Collez ce lien dans **🔑 Credentials API → SoundCloud**, puis "
                 "**Enregistrer**. Votre User ID est retrouvé automatiquement et "
                 "affiché en confirmation."),
    ),
    fields=(
        CredField("Profil SoundCloud", "https://soundcloud.com/votre-nom",
                  note="le lien de votre page ; le User ID numérique en est déduit"),
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
        # L'étape « Ouvrez le Gestionnaire de publicités (adsmanager.facebook.com) »
        # a été retirée le 2026-09-04 : le lien du portail, rendu juste au-dessus de
        # la première étape, dit déjà exactement cela. Ce qu'elle portait d'utile —
        # « sélectionnez le bon compte si vous en avez plusieurs » — est descendu
        # dans l'étape ci-dessous, qui est celle où le choix se voit.
        CredStep("Ouvre le portail ci-dessus et connecte-toi. Si tu gères "
                 "**plusieurs comptes publicitaires**, sélectionne d'abord celui que "
                 "tu veux suivre : c'est lui que l'adresse va nommer."),
        # « act_ ou pas act_ ? » — signalé le 2026-09-04 : « c'est confus ». Les deux
        # sont acceptés (`_handle_save` normalise), donc la réponse n'est pas une
        # règle de plus à retenir : c'est de dire qu'il n'y a rien à découper. Le
        # champ accepte désormais l'URL ENTIÈRE, comme Spotify et SoundCloud
        # acceptent déjà un lien — le geste est « copier la barre d'adresse », que
        # tout le monde sait faire, au lieu de « sélectionner la bonne sous-chaîne ».
        CredStep("**Le plus simple : copie l'adresse entière.** Clique dans la "
                 "**barre d'adresse** de ton navigateur (tout en haut), copie tout, "
                 "et colle-le tel quel — on en extrait le numéro de compte.\n\n"
                 "`adsmanager.facebook.com/adsmanager/manage/campaigns?`**`act=123456789012345`**`&business_id=…`\n\n"
                 "Si tu préfères ne coller que le numéro, prends celui qui suit "
                 "**`act=`** et s'arrête au `&`. **Avec ou sans le préfixe `act_`, "
                 "les deux marchent** : `act_123456789012345` et `123456789012345` "
                 "sont acceptés à l'identique.",
                 "meta_url_id.png", "Le nombre après act= dans la barre d'adresse"),
        CredStep("⚠️ Ne confondez pas avec `business_id=…` (votre Business Manager) ni "
                 "avec un **ID d'ensemble de publicités** (ad set) : seul le nombre "
                 "après **`act=`** est le bon."),
        # Cette étape existait, formulée comme « **Prérequis admin** », dans la note
        # de bas de page. L'étiquette disait à l'artiste que ce n'était pas son
        # affaire — alors que c'est SON compte publicitaire, dans SON Business
        # Manager, et que personne d'autre ne peut le faire à sa place. Il ne le
        # faisait donc pas, le test de connexion échouait, et rien ne disait
        # pourquoi. C'est ce qui a bloqué la session du 2026-06-19.
        CredStep("⚠️ **Étape indispensable, et c'est vous qui la faites.** Tant que "
                 "ce compte n'est pas partagé, la collecte ne verra rien — même avec "
                 "le bon ID.\n\n"
                 f"Ouvrez [Business Manager → Applications]({_META_BM_APPS_URL}) et "
                 f"cherchez **{META_APP_DISPLAY_NAME}** — c'est le nom sous lequel "
                 "**notre application apparaît chez Meta** ; si elle n'est pas dans "
                 "la liste, demandez-nous de vous l'ajouter. Puis, dans "
                 f"[Comptes publicitaires]({_META_BM_ADACCOUNTS_URL}) → **Ajouter "
                 "des personnes / des applications**, sélectionnez le vôtre et "
                 "donnez-lui l'autorisation **Analyste** (ou Annonceur)."),
        CredStep("Colle la valeur dans le champ **Ad Account ID**, puis "
                 "**💾 Enregistrer** — la connexion est testée dans la foulée. "
                 "Un ❌ ici pointe presque toujours vers l'étape de partage "
                 "ci-dessus."),
        CredStep("**Instagram (optionnel mais recommandé).** Pour suivre vos followers "
                 "et vos posts, il faut l'**ID du compte Instagram Business** — pas votre "
                 "@pseudo. Ouvrez **Meta Business Suite → Paramètres → Comptes → Comptes "
                 "Instagram**, sélectionnez votre compte : l'**ID numérique** est affiché "
                 "sous le nom. Collez-le dans le champ *Instagram Business Account ID*."),
        CredStep("⚠️ Prérequis Instagram : le compte doit être en **Business** ou "
                 "**Créateur** (pas personnel) et être relié à une **Page Facebook**. "
                 "Un compte personnel ne renvoie aucune statistique via l'API."),
    ),
    fields=(
        CredField("Ad Account ID (act_… ou numérique)", "act_1234567890",
                  note="l'URL entière du Gestionnaire de publicités convient aussi — "
                       "`act_1234567890` et `1234567890` sont acceptés à l'identique"),
        CredField("Instagram Business Account ID", "17841400000000000",
                  note="optionnel — ~17 chiffres, pour les stats Instagram"),
    ),
    admin_note=(
        "Côté admin : System User créé, token à 5 scopes en place, et le rattachement "
        "Instagram fait au niveau de la Page Facebook."
    ),
)

CREDENTIAL_GUIDES: tuple[PlatformCred, ...] = (_SOUNDCLOUD, _SPOTIFY, _YOUTUBE, _META)
