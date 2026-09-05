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

# Notre Business Manager, celui à qui l'artiste attribue son compte publicitaire.
#
# C'est LA valeur qui rend l'étape faisable, et elle manquait. Le guide disait
# « cherche ETL_DASHBOARD_SPOTIFY dans ta liste d'applications » — un artiste ne
# peut pas l'y voir : chez Meta, une app n'apparaît dans un Business Manager que si
# ce BM la possède. La nôtre appartient au nôtre. Le geste qui marche est l'inverse
# et se fait avec un NUMÉRO : l'artiste attribue son compte à notre Business en
# partenaire. Signalé le 2026-09-05 — « je ne comprends pas comment l'utilisateur
# peut voir le nom de mon application ».
#
# Non défini ⇒ le guide dit de nous le demander, plutôt que d'afficher un trou.
def _business_id() -> str:
    """Notre Business ID, en chargeant `.env` si l'appelant ne l'a pas fait.

    Le dashboard tourne sous `streamlit run`, qui charge l'environnement ; le
    GÉNÉRATEUR DE GUIDE, lui, tourne en `python -m` depuis le Makefile et ne le
    chargeait pas. Résultat mesuré le 2026-09-05 : le PDF **envoyé à l'inscription**
    disait « demande-nous notre numéro de Business » au lieu de le porter — un
    aller-retour par e-mail imposé à chaque nouvel artiste, pour une valeur que nous
    connaissons.

    Le module ne peut pas exiger que ses appelants pensent à charger l'env : il y en
    a trois (dashboard, générateur de PDF, tests) et seul le premier le faisait.
    """
    value = os.getenv("META_BUSINESS_ID", "").strip()
    if value:
        return value
    try:
        from src.utils.env_files import load_project_env
        load_project_env()
    except Exception:  # noqa: BLE001 — pas de `.env` = le repli, pas une panne
        return ""
    return os.getenv("META_BUSINESS_ID", "").strip()


META_BUSINESS_ID = _business_id()
_META_PARTNERS_URL = "https://business.facebook.com/settings/partners"



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
    # `None` quand le guide n'a pas besoin d'un résumé — c'est le cas dès qu'il tient
    # en deux étapes, où l'intro ne fait que les annoncer (SoundCloud, 2026-09-04).
    # Reste POSITIONNEL, sans valeur par défaut : chaque guide dit explicitement s'il
    # en a une. Un défaut à `None` aurait fait disparaître la question, et c'est celle
    # qui distingue un guide court d'un guide bavard.
    intro: str | None
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
    # Pas d'intro. « Une seule valeur à coller : le lien de ta page Spotify Artist »
    # annonçait les trois étapes qui suivent — et la troisième les dit mieux, parce
    # qu'elle fait faire quelque chose. Retirée le 2026-09-04, avec la même consigne
    # que le reste de ce guide : « on doit à tout prix éviter le blabla ».
    intro=None,
    portal_url="https://open.spotify.com",
    portal_search_url="https://open.spotify.com/search/{q}/artists",
    # TROIS impératifs, rien d'autre. Chaque mot retiré ci-dessous décrivait un
    # contexte que l'artiste a déjà sous les yeux :
    #
    #   « Sur Spotify, ouvre ta page artiste, puis… »  il y est ;
    #   « — les trois petits points, à droite du
    #     bouton Suivre / Abonné »                     la capture le montre ;
    #   « Dans le menu qui s'ouvre : »                 il vient de l'ouvrir.
    #
    # Ce qui RESTE est ce qu'on ne peut pas deviner : quel bouton, quelle entrée de
    # menu, quel champ. Le glyphe garde son fond de code — `⋯` nu se lisait comme une
    # coupure de texte — et la capture reste sur l'étape où deux testeurs se sont
    # arrêtés.
    # UNE ligne, pas trois. Demandé le 2026-09-04 : « modifie le texte pour qu'il
    # apparaisse sur une seule ligne avec des flèches ». Trois étapes numérotées pour
    # trois clics consécutifs dans le MÊME menu font lire trois fois « voici une
    # étape » là où il n'y a qu'un geste continu ; la chaîne le montre d'un coup
    # d'œil, et se relit sans compter.
    #
    # « au-dessus » et non « ⬅ » : depuis la mise en page en trois bandes, le champ
    # est AU-DESSUS du guide, plus à sa gauche. Une direction ne survit pas au
    # déplacement de ce qu'elle désigne — c'est la quatrième formulation de cette
    # étape, et les trois précédentes sont mortes de ça.
    steps=(
        CredStep("Bouton `•••` → **Partager** → **Copier le lien vers l'artiste** → "
                 "colle-le dans **URL profil artiste**, au-dessus.",
                 "spotify_share_artist_link.png",
                 "Le bouton ••• → Partager → Copier le lien vers l'artiste"),
    ),
    fields=(
        # « Spotify Artist ID ou URL profil » offrait un choix qui n'en est pas un :
        # on ne colle jamais l'ID, on colle l'URL, et le code en extrait l'ID.
        CredField("URL profil artiste",
                  "https://open.spotify.com/artist/4qG1qjeHfkASTdyRGbLWbV",
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
    # UNE étape. Le guide en portait sept, dont cinq qui décrivaient la création
    # d'une clé Google Cloud — un geste d'ADMIN, fait une fois, déjà fait, et que
    # personne d'autre ne peut ni ne doit refaire. L'intro le disait (« saute
    # directement à l'étape 6 »), ce qui est l'aveu qu'on fait lire au mauvais
    # lecteur : demandé le 2026-09-05, « à quoi sert tout ça si c'est uniquement
    # pour l'admin ? ». La procédure n'est pas perdue — elle est passée dans
    # `admin_note`, que `credential_guides_st` ne rend que si `is_admin()`.
    intro=None,
    portal_url="https://www.youtube.com/account_advanced",
    steps=(
        CredStep("[youtube.com/account_advanced](https://www.youtube.com/account_advanced) "
                 "→ **ID de la chaîne** → **Copier**, et colle-le au-dessus. "
                 "C'est ta chaîne principale : on trouve la « — Topic » à partir "
                 "d'elle, tu n'as pas à la chercher."),
    ),
    fields=(
        # La clé API a QUITTÉ cette liste : elle est `admin_only` dans le registre,
        # et le DAG retombe sur `YOUTUBE_API_KEY`, la clé partagée. La faire figurer
        # ici disait à l'artiste qu'il devait en fournir une.
        CredField("Lien de ta chaîne YouTube",
                  "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",
                  note="l'identifiant `UC…`, un lien de chaîne ou ton @pseudo — "
                       "on résout et on te montre ce qu'on a trouvé"),
    ),
    note="Quota gratuit ~10 000 unités/jour ; un dépassement renvoie 403 (temporaire).",
    admin_note=(
        "**Admin (une seule fois, déjà fait)** : la clé est partagée par tous les "
        "locataires via `YOUTUBE_API_KEY`. Pour la régénérer — "
        "[console.cloud.google.com/apis/dashboard](https://console.cloud.google.com/apis/dashboard) "
        "→ créer un projet (le bouton *Activer les API* reste grisé tant qu'aucun "
        "projet n'existe) → **+ Activer les API et les services** → "
        "[Bibliothèque](https://console.cloud.google.com/apis/library) → "
        "**YouTube Data API v3** → **Activer** → "
        "[Identifiants](https://console.cloud.google.com/apis/credentials) → "
        "**Créer des identifiants → Clé API** → **Afficher la clé**. Le champ "
        "« API Key (surcharge) » de l'onglet ne sert qu'à déroger à cette clé pour "
        "un locataire précis."
    ),
)

_SOUNDCLOUD = PlatformCred(
    key="soundcloud",
    title="SoundCloud",
    icon="☁️",
    # Pas d'intro. Elle disait « une seule chose à fournir : le lien de votre profil ;
    # on en déduit votre identifiant » — c'est-à-dire l'étape 1, l'étape 2 et la note
    # du champ, annoncées avant d'être dites. Un guide de deux lignes n'a pas besoin
    # d'un résumé (2026-09-04).
    intro=None,
    portal_url="https://soundcloud.com",
    steps=(
        CredStep("Ouvrez votre **profil SoundCloud** et copiez l'adresse affichée "
                 "dans la barre du navigateur — elle ressemble à "
                 "`https://soundcloud.com/votre-nom`."),
        # « Collez ce lien dans 🔑 Credentials API → SoundCloud » situait une page à
        # quelqu'un qui est dessus, et la suite — « votre User ID est retrouvé
        # automatiquement et affiché en confirmation » — décrivait une confirmation
        # que l'écran affiche lui-même une seconde plus tard.
        CredStep("Collez-le dans **Saisir tes identifiants**, la colonne de gauche, "
                 "puis **Enregistrer**."),
    ),
    fields=(
        # Le champ prend le LIEN. Il s'est appelé « User ID numérique » jusqu'au
        # 2026-09-04, ce que la remarque a relevé : « tu demandes de saisir l'URL
        # d'artiste et tu me demandes mon user ID numérique ». Les deux étaient vrais
        # à des moments différents — la conversion se fait à l'enregistrement — mais
        # un artiste ne lit pas deux moments, il lit un formulaire.
        CredField("Profil SoundCloud", "https://soundcloud.com/votre-nom",
                  note="le lien de votre page — rien à découper"),
    ),
)

_META = PlatformCred(
    key="meta",
    title="Meta Ads",
    icon="📱",
    intro=None,
    portal_url="https://adsmanager.facebook.com/",
    # DEUX étapes. Instagram est parti avec son onglet le 2026-09-05 (soir) — le
    # laisser ici faisait lire une consigne Instagram à qui vient brancher des
    # campagnes. Le reste a été coupé pour la même raison : « il y a trop de
    # blabla ». Ce qui survit est ce qu'on ne peut pas deviner.
    steps=(
        # UNE LIGNE, sans capture et sans répéter le lien. Le « 🔗 Portail : … »
        # rendu juste au-dessus par le gabarit portait DÉJÀ ce lien — l'étape le
        # redisait mot pour mot (« on dit 2 fois la même chose », 2026-09-05).
        # Reste ce que le portail ne dit pas : QUEL compte, et OÙ est le sélecteur.
        CredStep("Sélectionne ton compte (flèche déroulante en haut de Meta) → "
                 "**copie l'URL** → colle-la au-dessus."),
        # Le seul geste que nous ne pouvons pas faire : Meta refuse l'appel qui
        # l'automatiserait (`(#3) capability`, ADR-017). L'ID à coller est rendu par
        # l'onglet dans un bloc copiable — pas ici, où il faudrait le sélectionner
        # à la souris au milieu d'une phrase.
        # Le numéro est ÉCRIT ICI, en plus du bloc copiable de l'onglet. Ce n'est
        # pas une redite : ce guide part aussi en PDF à l'inscription, et là il n'y
        # a pas d'onglet — un lecteur hors ligne resterait avec « le numéro est
        # au-dessus du formulaire », c'est-à-dire nulle part.
        # UNE LIGNE, et le geste détaillé vit dans le bloc de l'onglet — avec le
        # numéro copiable et un lien qui ouvre DIRECTEMENT l'onglet Partenaires
        # du compte saisi — mais le numéro est ÉCRIT ICI, en plus du bloc copiable de l'onglet — et un
        # test l'a rattrapé DEUX FOIS. Ce guide part aussi en PDF à
        # l'inscription, où il n'y a pas d'onglet : « le bloc au-dessus porte le
        # numéro » y désigne le vide. Une ligne, mais complète.
        CredStep("🤝 [Partenaires](" + _META_PARTNERS_URL + ") → **Ajouter** → "
                 "**Donner à un partenaire l'accès à tes assets** → "
                 + (f"colle **`{META_BUSINESS_ID}`**" if META_BUSINESS_ID
                    else "colle **notre numéro** (demande-le nous)")
                 + " → coche ton compte publicitaire → rôle **Analyste**. "
                   "Sans ce partage, aucune donnée."),
    ),
    fields=(
        CredField("Lien de ton compte publicitaire",
                  "https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=123456789012345",
                  note="colle l'URL entière du Gestionnaire de publicités — on en "
                       "extrait le numéro de compte"),
    ),
    admin_note=(
        "Côté admin : System User créé, token à 5 scopes en place."
    ),
)


_INSTAGRAM = PlatformCred(
    key="instagram",
    title="Instagram",
    icon="📸",
    intro=None,
    portal_url="https://www.instagram.com/",
    # UNE étape, et c'est vrai : rien à configurer chez Meta. Mesuré le 2026-09-05
    # sur un compte tiers — `business_discovery` rend abonnés, publications,
    # permaliens et commentaires SANS aucun partage de Business Manager. Ce qui
    # reste hors de portée, ce sont les insights (reach, impressions, vues de
    # profil) : eux exigent que le compte soit relié à une Page de notre Business.
    steps=(
        CredStep("Colle l'adresse de ton profil au-dessus. Ton compte doit être "
                 "**Business** ou **Créateur** — un compte personnel ne renvoie "
                 "rien. (Instagram → Paramètres → Type de compte)"),
    ),
    fields=(
        CredField("Lien de ton profil Instagram",
                  "https://instagram.com/ton-pseudo",
                  note="on s'occupe du reste — rien à chercher dans Business Manager"),
    ),
    admin_note=(
        "Côté admin : même jeton System User que Meta Ads. La collecte passe par "
        "business_discovery, qui ne demande aucun partage."
    ),
)


CREDENTIAL_GUIDES: tuple[PlatformCred, ...] = (
    _SOUNDCLOUD, _SPOTIFY, _YOUTUBE, _META, _INSTAGRAM,
)
