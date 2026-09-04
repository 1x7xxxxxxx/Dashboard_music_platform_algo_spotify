"""Post-register onboarding wizard — 3-step setup guide.

Type: Feature
Uses: get_db_connection, get_artist_id, get_artist_plan, PLAN_FEATURES
Depends on: artist_credentials table, saas_artists table
Accessible via /?page=onboarding (authenticated route).
"""
import json
import logging
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.tz import to_local_datetime
from src.utils.tenant_identity import declared_identities
from src.dashboard.utils.i18n import get_lang, t
from src.dashboard.auth import tenant_scope, get_artist_plan, is_admin
from src.database.stripe_schema import PLAN_FEATURES
from src.dashboard.content.platform_value import (
    COLUMN_CSV, COLUMN_LONGER, COLUMN_QUICK, SETUP_COLUMN_ORDER,
    BY_KEY, setup_columns, total_effort,
)
from src.dashboard.utils.setup_focus import FOCUS_KEY
from src.dashboard.utils.status_matrix import render_status_matrix
from src.dashboard.utils.navigation import goto


# Platforms and which plan they require — all platform connectors are Free-tier.
_PLATFORM_META = {
    'spotify':    {'label': 'Spotify API',  'plan': 'free', 'icon': '🎵'},
    'youtube':    {'label': 'YouTube',       'plan': 'free', 'icon': '🎬'},
    'meta':       {'label': 'Meta Ads',      'plan': 'free', 'icon': '📱'},
    'instagram':  {'label': 'Instagram',     'plan': 'free', 'icon': '📸'},
    'soundcloud': {'label': 'SoundCloud',    'plan': 'free', 'icon': '☁️'},
    'apple_music':{'label': 'Apple Music',   'plan': 'free', 'icon': '🎎'},
}

_STEP_KEY = '_onboarding_step'


def _goto(page_key: str) -> None:
    """Délègue à `utils.navigation.goto` — une seule règle de navigation dans l'app.

    Cette fonction portait sa propre copie ; l'accueil en a eu besoin le 2026-08-23 et
    recopier la règle une deuxième fois l'aurait laissée diverger. La version partagée
    fait en plus ce que celle-ci oubliait : désélectionner les radios de section, sans
    quoi le menu reste sur l'entrée précédente pendant que la page a changé.
    """
    goto(page_key)


def _get_configured_platforms(artist_id: int, db) -> set[str]:
    """Platforms the artist has actually connected.

    "Connected" means an IDENTITY was declared, not that a row exists: a tab opened
    and saved blank left a row behind and counted as connected here while the
    readiness matrix said ⚪. Instagram has no row of its own — it rides the `meta`
    row via `ig_user_id` — and the registry knows that, so this no longer restates it.

    The caller owns the connection and hands it in. This view is capped at ONE
    opened connection by `tests/test_view_connection_budget.py` — a textual count —
    and `_step_credentials` needs the same one for the status matrix.
    """
    if db is None or artist_id is None:
        return set()
    try:
        rows = db.fetch_query(
            "SELECT platform, extra_config FROM artist_credentials "
            "WHERE artist_id = %s AND (token_encrypted IS NOT NULL OR extra_config IS NOT NULL)",
            (artist_id,),
        )
        extra_by_platform = {}
        for platform, extra in rows:
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except ValueError:
                    extra = {}
            extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
        return declared_identities(extra_by_platform)
    except Exception as e:
        # NOT a silent `return set()`: a DB error and "this artist has connected
        # nothing" are different facts, and rendering the first as the second
        # tells an artist who configured everything that they configured nothing.
        st.warning(t(
            "onboarding.status_unavailable",
            "⚠️ Impossible de lire l'état de tes connexions ({err}). La liste "
            "ci-dessous peut afficher « non connecté » à tort — réessaie dans un "
            "instant avant de tout reconfigurer."
        ).format(err=type(e).__name__))
        return set()


def _trial_deadline(artist_id: int | None, db) -> str | None:
    """La date de fin de l'essai premium, ou None. Jamais d'exception.

    `_grant_welcome_trial` pose `promo_plan_expires_at` à la création du compte. Rien
    ne le disait à l'artiste : il lisait « votre compte a été créé avec le plan
    Premium » et en déduisait que c'était acquis. Signalé en test le 2026-08-30.

    Prend la connexion de `show()` : elle ouvrait la sienne via `project_db()`, ce qui
    faisait DEUX connexions par rendu dès que `show()` a eu besoin de lire l'état de
    configuration. Attrapé par `tests/test_a_render_opens_one_connection.py`, qui
    compte à l'exécution — le compteur textuel, lui, ne voit pas `project_db()`.
    """
    if artist_id is None or db is None:
        return None
    try:
        row = db.fetch_query(
            "SELECT promo_plan_expires_at FROM saas_artists WHERE id = %s",
            (artist_id,))
        if row and row[0][0]:
            return to_local_datetime(row[0][0]).strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001 — une date manquante n'empêche pas l'onboarding
        return None
    return None


# `_setup_roadmap()` vivait ici et a été SUPPRIMÉE le 2026-09-04 : « ça sert à rien
# la section "ta mise en route" ». Elle annonçait trois étapes dont les deux premières
# sont sous les yeux de celui qui lit — « tu choisis tes plateformes » juste au-dessus
# des cases, « tu saisis tes identifiants » sur la page où le bouton l'emmène. Décrire
# un parcours qu'on est en train de faire est du commentaire, pas de l'aide.
#
# Sa troisième ligne, elle, disait quelque chose qu'aucun écran ne montre — ce qui se
# passe APRÈS, quand l'artiste a fermé l'onglet. Elle a rejoint le bloc du guide, qui
# est devenu « Ton guide, et ce qui se passe ensuite ».


_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "assets" / "examples"


def _example_chart(name: str) -> None:
    """Une figure d'exemple, construite hors ligne par `make example-charts`.

    Un PNG et non un graphique rendu : il n'y a AUCUNE donnée à tracer le jour où
    cette page compte, la figure doit être identique en app, en mail et en PDF, et
    `kaleido` est absent de toutes les images — Plotly ne saurait pas l'exporter.
    Absente, l'image ne casse rien : le texte au-dessus dit déjà la promesse.
    """
    path = _EXAMPLES_DIR / name
    if not path.exists():
        return
    st.image(str(path), use_container_width=True)


def _language_buttons() -> None:
    """Bloc 0 — choisir sa langue SUR la page, et que ça se retienne.

    Deux BOUTONS, pas un `st.radio`, et c'est la seule contrainte technique de ce
    bloc : la barre latérale porte déjà un radio de langue (`_lang_sel`). Deux widgets
    ne peuvent pas partager une clé, et deux radios indépendants se réécrivent l'un
    l'autre à chaque rerun — celui de la page annulerait le choix fait dans la barre,
    et réciproquement. Un bouton ne porte aucun état : il pose la valeur, met à jour
    la clé du radio de la barre AVANT que celui-ci soit instancié au run suivant, et
    relance. C'est la même règle que pour les radios du menu.

    La mémoire longue existait déjà (`saas_users.lang`, migration 079) : ce qui
    manquait était de pouvoir choisir sans aller chercher dans la barre latérale, le
    jour où la barre est justement réduite au minimum.
    """
    from src.dashboard.utils.i18n import set_lang

    cur = get_lang()
    st.markdown("### " + t("onboarding.b0_title", "0. Ta langue"))
    st.caption(t("onboarding.b0_help",
                 "Elle vaut pour toute l'application et pour ton guide PDF. "
                 "On la retient : tu ne la choisiras qu'une fois."))
    cols = st.columns([1, 1, 3])
    for col, (code, label) in zip(cols, (("fr", "🇫🇷 Français"), ("en", "🇬🇧 English"))):
        with col:
            if st.button(label, key=f"_onb_lang_{code}", use_container_width=True,
                         type="primary" if cur == code else "secondary",
                         disabled=(cur == code)):
                set_lang(code)
                # PAS d'écriture sur `_lang_sel`. Ce fut la première version, et elle
                # plantait : ce radio vit dans la barre latérale, donc il est déjà
                # instanciué quand cette fonction tourne, et Streamlit refuse. `app.py`
                # ne rend simplement pas le sélecteur de barre sur cette page — un seul
                # propriétaire du réglage à la fois.
                try:
                    from src.dashboard.utils.lang_pref import remember_lang
                    remember_lang(code)
                except Exception:      # noqa: BLE001 — la langue change à l'écran quoi qu'il arrive
                    logger.warning("lang preference not persisted")
                st.rerun()
    st.markdown("---")


def _step_welcome(plan: str, artist_id: int, db) -> None:
    """Quatre blocs numérotés, dans l'ordre où l'artiste en a besoin.

    La page disait la même chose, dans le désordre : la langue vivait dans la barre
    latérale, l'offre n'annonçait sa durée qu'en petit, le guide PDF était noyé et la
    feuille de route ne donnait un temps que pour le total. Numérotés le 2026-09-04
    à partir des notes de terrain — 0 langue · 1 à quoi ça sert · 2 ce que tu as et ce
    que tu perds · 3 le guide et le temps que ça coûte.
    """
    st.title(t("onboarding.welcome_title", "🎵 Bienvenue sur streaMLytics !"))

    # Un ADMIN qui ouvre cette page ne verra jamais le parcours qu'elle décrit, et
    # rien ne le lui disait. `_setup_is_unfinished` renvoie False dès la première
    # ligne pour `role == 'admin'` — c'est voulu (un admin n'a pas de configuration
    # à faire, `artist_id` vaut NULL) mais c'est invisible : il se connecte, atterrit
    # sur l'accueil avec le menu complet, ouvre l'assistant depuis le menu, et conclut
    # que l'atterrissage est cassé. Demandé deux fois le 2026-09-04, dans ces termes :
    # « on n'arrive pas directement sur mise en route, c'est normal ? »
    #
    # La réponse tient en deux phrases et n'a de sens que pour lui — d'où le garde
    # `is_admin()`, et pas une note générale que sept artistes liraient sans raison.
    if is_admin():
        st.info(t(
            "onboarding.admin_preview",
            "🔧 **Compte admin.** L'atterrissage automatique sur cette page ne "
            "s'arme que pour un compte **artiste** dont la configuration n'est pas "
            "terminée — un admin n'a pas d'`artist_id`, donc pas de mise en route. "
            "Tu vois cette page telle qu'un artiste la voit, mais tu n'y seras "
            "jamais amené tout seul.\n\n"
            "Pour rejouer le parcours en entier, connecte-toi avec le compte "
            "**bac à sable** (`sandbox`) : c'est le locataire créé pour ça."))

    _language_buttons()

    # « streaMLytics en bref » — demandé après le test du 2026-08-30. Un artiste qui
    # vient de créer son compte sait ce qu'il a acheté ; il ne sait pas encore ce que
    # l'outil FAIT. Trois phrases, avant l'offre et avant le guide.
    # Trois promesses, trois images. Un artiste sans données ne peut pas voir les
    # siennes : l'illustration est la seule façon HONNÊTE de montrer ce qui l'attend,
    # et chaque figure porte « Exemple — données fictives » dans l'image elle-même.
    # Le dépôt a déjà été mordu par une valeur de démo lue comme réelle (le compteur
    # public qui comptait nos propres canaris) : un exemple qui ne s'annonce pas est
    # un mensonge avec un graphique autour.
    st.markdown("### " + t("onboarding.b1_title", "1. streaMLytics en bref"))
    # TROIS COLONNES, pas trois blocs empilés. Demandé le 2026-09-04 : « les
    # graphiques en plus petit sur la même ligne pour que ça soit visuel ». Empilées,
    # les trois figures faisaient défiler l'écran d'accueil sur trois hauteurs avant
    # que l'artiste n'atteigne son offre ; côte à côte, elles se lisent d'un regard
    # comme ce qu'elles sont — trois promesses, pas trois chapitres.
    #
    # L'image AVANT son texte dans chaque colonne : c'est elle qui porte la promesse,
    # le texte l'explique. `use_container_width` la met à la largeur de la colonne,
    # donc au tiers — c'est là que « plus petit » se décide, pas dans le PNG, qui
    # doit rester à sa résolution native pour le PDF et l'e-mail.
    _cols = st.columns(3)
    for _col, (key, default, image) in zip(_cols, (
        ("onboarding.brief_1",
         "**Toutes tes données au même endroit, récupérées chaque jour, "
         "automatiquement** — Spotify, Instagram, Meta Ads, YouTube, SoundCloud, "
         "Apple Music. Tes identifiants sont chiffrés ; tu ne ressaisis rien.",
         "dashboard-global.png"),
        ("onboarding.brief_2",
         "**La prédiction des algorithmes Spotify** — quand un titre a des chances "
         "de déclencher Discover Weekly ou Release Radar, via des modèles de machine "
         "learning entraînés sur tes données.",
         "prediction-discover-weekly.png"),
        ("onboarding.brief_3",
         "**L'optimisation de tes campagnes marketing (Instagram Ads, Meta Ads)** — "
         "en reliant ce que tu dépenses en promo à ce que ça produit réellement en "
         "écoutes.",
         "meta-x-s4a.png"),
    )):
        with _col:
            _example_chart(image)
            st.markdown(t(key, default))
    st.markdown("---")

    st.markdown("### " + t("onboarding.b2_title",
                          "2. Ton offre de bienvenue"))
    # L'offre, avec sa DURÉE et son échéance. Un essai dont on ne dit pas qu'il est un
    # essai n'est pas une offre, c'est une surprise à J+30.
    deadline = _trial_deadline(st.session_state.get("artist_id"), db)
    if plan == "premium" and deadline:
        st.success(t(
            "onboarding.trial_offer",
            "🎁 **Premium offert pendant 1 mois** (30 jours), "
            "jusqu'au **{date}**.\n\n"
            "Ensuite ton compte repasse en **Free** : tu gardes tes données, tes "
            "connexions et tes exports. Tu perds **🚀 Road to Algo** (les prédictions "
            "de déclenchement Discover Weekly), les **prévisions de revenus** et les "
            "**analyses croisées Meta × Spotify**."
        ).format(date=deadline))
    else:
        st.markdown(
            t("onboarding.welcome_body",
              "Votre compte a été créé avec le plan **{plan}**. "
              "Voici ce qui est inclus dans votre plan actuel :").format(plan=plan.capitalize())
        )

    st.caption(t("onboarding.b2_after",
                 "Ci-dessous, ce que tu gardes pour toujours (Free) et ce que tu perds "
                 "au bout du mois si tu ne prends pas Premium. **Tes données restent "
                 "les tiennes dans les deux cas** — rien n'est effacé, et l'export CSV "
                 "reste gratuit."))
    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible

    col_free, col_premium = st.columns(2)

    # Les noms sont ceux que l'artiste connaît, pas les nôtres : « S4A » et
    # « iMusician » sont du vocabulaire interne — le premier est un sigle, le second
    # un fournisseur parmi d'autres. Signalé le 2026-09-04.
    plan_data = [
        ('free',    'Free',    [t("nav.item.home", "🏠 Accueil"),
                                t("onboarding.feat_spotify", "🎵 Spotify + Spotify for Artists"),
                                '🎬 YouTube',
                                '📱 Meta Ads', '📸 Instagram', '☁️ SoundCloud',
                                '🎎 Apple Music',
                                t("onboarding.feat_distributors",
                                  "💰 Distributeurs (iMusician, DistroKid…)"),
                                t("nav.item.upload_csv", "📂 Ajouter mes chiffres Spotify for Artists & Apple"),
                                # « Export CSV » ne dit rien à qui n'est pas
                                # développeur. La glose est plus longue que le nom,
                                # et c'est le bon rapport : le nom ne se comprend pas.
                                t("onboarding.feat_export_csv",
                                  "⬇️ Export CSV — un fichier tableur (type Excel) "
                                  "avec tes données brutes"),
                                '🎁 Data Wrapped']),
        ('premium', 'Premium', [t("onboarding.feat_algo",
                                  "+ 🚀 **Savoir si un titre va déclencher Discover "
                                  "Weekly** — avant de dépenser en promo"),
                                t("onboarding.feat_revenue",
                                  "+ 📈 **Ce que tes écoutes vont rapporter** le mois "
                                  "prochain"),
                                t("onboarding.feat_meta_x",
                                  "+ 🔀 **Quel euro de pub a produit quelles écoutes**"),
                                # « quel euro de pub ET SON PARAMÉTRAGE », demandé le
                                # 2026-09-04. Le constat sans le geste laisse
                                # l'artiste devant un chiffre : ce qui se vend ici,
                                # c'est la recommandation de budget par campagne
                                # (+30 % / +10 % / = / −30 %, `meta_cpr_optimizer`).
                                # La ligne dit le geste, pas la formule — et elle ne
                                # promet que ce que cette vue calcule réellement.
                                t("onboarding.feat_meta_budget",
                                  "+ 💶 **Combien remettre sur quelle campagne** — "
                                  "augmenter, tenir ou couper, campagne par "
                                  "campagne, d'après le coût par écoute gagnée"),
                                t("onboarding.feat_creatives",
                                  "+ 🎨 **Quelle créative coûte le moins cher** par "
                                  "écoute gagnée"),
                                # Déplacé de Free vers Premium le 2026-09-04 : ce qui
                                # se paie n'est pas le PDF, c'est le rapport filtrable
                                # envoyé chaque semaine sans qu'on y pense.
                                t("onboarding.feat_pdf_weekly",
                                  "+ 📄 Ton rapport PDF filtrable — à la demande, et "
                                  "envoyé par mail chaque semaine")]),
    ]

    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    for col, (tier_key, tier_label, features) in zip(
        [col_free, col_premium], plan_data
    ):
        with col:
            tier_rank = plan_ranks[tier_key]
            is_current = tier_key == plan
            is_locked = tier_rank > current_rank and not is_all

            # « ← votre plan » en plus gros : c'est l'information que l'artiste
            # cherche dans ce tableau, et elle était de la même taille que le reste.
            if is_current:
                st.markdown(f"### {tier_label}"
                            + t("onboarding.your_plan", " ← *votre plan*"))
            else:
                st.markdown(f"**{tier_label}**")

            for feat in features:
                icon = "✅" if not is_locked or tier_rank <= current_rank else "🔒"
                st.markdown(f"{icon} {feat}")

            if is_locked:
                if st.button(t("onboarding.upgrade_to", "Passer à {tier} →").format(tier=tier_label),
                             key=f"_onb_upgrade_{tier_key}"):
                    _goto('billing')

    st.markdown("---")

    # Il n'y a PAS de bloc 3. Ce qui s'y trouvait a été retiré le 2026-09-04, en
    # une fois, parce que les quatre morceaux avaient le même défaut : ils parlaient
    # au lieu de faire avancer.
    #
    #   « 3. Ton guide, et ce qui se passe ensuite »  — un titre pour deux boutons ;
    #   « Tu l'as aussi reçu en pièce jointe… »       — une phrase pour dire qu'on
    #                                                   répète le mail ;
    #   les deux boutons de téléchargement du PDF     — « ça sert à rien, on l'envoie
    #                                                   par mail, et sinon je préfère
    #                                                   qu'il suive la page
    #                                                   d'onboarding » ;
    #   « La collecte tourne cette nuit »             — vrai, et sans effet sur le
    #                                                   geste demandé juste après ;
    #   « Tu peux t'arrêter après une seule… »        — une permission que personne
    #                                                   n'avait demandée.
    #
    # Le guide reste téléchargeable là où il sert vraiment : sur l'écran qui suit
    # l'inscription, pendant qu'on attend le mail de vérification et qu'il n'y a rien
    # d'autre à faire (`register._guide_download`, couvert par son propre test). Ici,
    # l'écran a une suite — la page de mise en route — et c'est elle qu'on veut faire
    # suivre, pas un PDF qui ouvre un autre contexte.

    # Le choix, ICI. Il vivait sur une deuxième page qui commençait par redire la
    # liste que la feuille de route venait d'énumérer. Une page de moins, un
    # inventaire de moins, et le geste au même endroit que ce qui l'explique.
    selection = _platform_picker(plan, artist_id, db)

    st.markdown("---")
    if selection:
        label = t("onboarding.configure_selection",
                  "Configurer ma sélection ({n}) → ≈{mins} min").format(
                      n=len(selection), mins=total_effort(selection))
    else:
        label = t("onboarding.next_finish", "Continuer sans rien connecter →")
    if st.button(label, type="primary"):
        # Carried to the credentials page, which walks the selection in order and
        # tracks what is left — so "I picked two things" survives the navigation.
        st.session_state[FOCUS_KEY] = selection
        st.session_state[_STEP_KEY] = 2
        if selection:
            # DIRECTEMENT sur la page de saisie : un écran intermédiaire ne ferait
            # que reposer la question à laquelle ce bouton vient de répondre
            # (2026-09-04). L'étape 2 reste atteignable par la barre latérale, et
            # c'est là qu'on revient voir où on en est.
            _goto('credentials')
            return
        st.rerun()


def _platform_picker(plan: str, artist_id: int, db) -> list[str]:
    """Les cases à cocher, et la sélection qu'elles rendent.

    Extraite de l'étape 2 le 2026-09-04 et remontée sur la page de bienvenue —
    « il faudrait faire venir la section *coche ce que tu veux configurer* sur la
    première page ».

    Elle y remplace une liste qui disait la même chose en moins : nom, durée,
    « À fournir », sans la valeur ni le piège de chaque plateforme. Deux inventaires
    des mêmes six lignes à deux écrans d'intervalle, c'est la duplication signalée.
    Ici, l'inventaire EST l'action : on lit et on coche au même endroit.
    """
    configured = _get_configured_platforms(artist_id, db)

    accessible = PLAN_FEATURES.get(plan, set())
    is_all = '*' in accessible
    plan_ranks = {'free': 0, 'premium': 1}
    current_rank = plan_ranks.get(plan, 0)

    # L'ACTION en gros, l'info en petit — demandé après le test du 2026-08-30 :
    # « mettre en gros gras surbrillance de section les ACTIONS à effectuer, en plus
    # petit les infos ».
    # ACTION → surbrillance. Voir le commentaire de `_render_platform_tab` sur le
    # choix de `:orange-background[…]` plutôt qu'un `<style>`.
    st.markdown("### :orange-background["
                + t("onboarding.pick_action", "👉 Coche ce que tu veux configurer maintenant")
                + "]")
    # Il n'y a plus de ligne « ⭐ Recommandé pour démarrer : … ». Elle a été le pavé
    # bleu, puis une ligne sous l'action, et le 2026-09-04 elle est devenue le TITRE
    # de la première colonne — « ⭐ Commence par là ». Trois formes de la même phrase
    # en une journée, dont la dernière la MONTRE au lieu de la dire : la colonne
    # groupe exactement ce que la ligne énumérait, et son total est déjà sur le bouton
    # (« Configurer ma sélection (3) → ≈9 min »).
    #
    # La liste des recommandées non encore connectées, qu'elle calculait, part avec
    # elle : personne d'autre ne la lisait, et `setup_columns()` regroupe déjà.
    st.caption(t("onboarding.pick_hint",
                 "Tu n'as pas besoin de tout connecter. Le reste attendra dans "
                 "l'onglet **Credentials API**, plus tard, dans l'application."))
    # La SEULE chose que la liste supprimée disait et que les cases ne disaient pas :
    # que ces durées sont le coût de la PREMIÈRE fois. Le reste — icône, nom, minutes,
    # ⭐, « À fournir » — chaque case le porte déjà, et y ajoute la valeur de la
    # plateforme et son piège. Une phrase, pas un second inventaire : c'est ce qui la
    # distingue du bloc retiré le 2026-09-04.
    st.caption(t("onboarding.pick_first_time",
                 "Les minutes indiquées sont celles de **la première fois**. "
                 "Ensuite, tout se met à jour tout seul."))

    # Le récapitulatif replié des six coûts a vécu ici quelques heures, le
    # 2026-09-04, et il a été retiré le jour même : « on le redit après, donc c'est
    # redondant ». C'est exact, et le repli n'y changeait rien — il rangeait la
    # répétition sans la supprimer. Chaque case porte déjà sa durée ; comparer les
    # six ne vaut pas un bloc de plus sur l'écran qui demande de choisir.
    #
    # Ce qui reste de son intention est la ligne au-dessus : ces minutes sont celles
    # de la première fois. C'était la seule chose qu'aucune case ne disait.

    # TROIS COLONNES, et pas six cases empilées. Demandé le 2026-09-04 : « mettre à
    # gauche et cochées celles qu'on recommande, à droite les autres, et ranger par
    # colonne pour bien comprendre ».
    #
    # Une pile ne hiérarchise rien : le ⭐ posé sur trois lignes d'une même liste est
    # un ornement, pas un ordre. Les colonnes, elles, disent la seule chose qui aide à
    # choisir — combien de travail chaque groupe demande. Le découpage vient de
    # `setup_columns()`, donc d'un champ des plateformes, pas de trois listes de clés
    # recopiées ici (voir son commentaire).
    selection: list[str] = []
    groups = setup_columns(configured)
    cols = st.columns(len(SETUP_COLUMN_ORDER), gap="medium")
    for _col, _name in zip(cols, SETUP_COLUMN_ORDER):
        # Une cellule ENCADRÉE par colonne — « des lignes démarcatrices comme un
        # tableau entre les 3 colonnes » (2026-09-04). `st.columns` ne trace aucune
        # séparation : trois listes côte à côte se lisent comme une seule au fil de
        # l'œil. Le cadre est celui de Streamlit (`st.container(border=True)`), pas
        # du CSS visant le DOM — un sélecteur sur la structure interne se casse à la
        # première montée de version, en silence.
        with _col.container(border=True):
            st.markdown("**" + t(f"onboarding.col.{_name}", _COLUMN_TITLES[_name]) + "**")
            for pv in groups[_name]:
                selection.extend(_platform_checkbox(
                    pv, configured, is_all, plan_ranks, current_rank))

    return selection


# Les sous-titres de colonne ont vécu une journée : « Un lien à copier, rien à
# installer. » / « Un identifiant à aller chercher… » / « Un export à télécharger… ».
# Ils expliquaient le critère de groupement à quelqu'un qui n'a pas à le connaître —
# le titre de la colonne suffit à dire dans quel ordre s'y prendre.
_COLUMN_TITLES = {
    COLUMN_QUICK: "⭐ Commence par là",
    COLUMN_LONGER: "Un peu plus long",
    COLUMN_CSV: "Par fichier (CSV)",
}


def _platform_checkbox(pv, configured: set[str], is_all: bool,
                       plan_ranks: dict, current_rank: int) -> list[str]:
    """Une case et ce qu'elle dit — extraite le 2026-09-04 pour tenir en colonne.

    Renvoie une liste plutôt qu'un booléen : l'appelant l'`extend`, donc une case
    verrouillée ou déjà connectée n'ajoute rien sans que personne ait à filtrer.
    """
    meta = _PLATFORM_META.get(pv.key, {})
    required_rank = plan_ranks.get(meta.get('plan', 'free'), 0)
    if not (is_all or required_rank <= current_rank):
        st.markdown(
            t("onboarding.locked_platform",
              "🔒 {icon} **{label}** — *Disponible en plan {plan}*").format(
                  icon=pv.icon, label=pv.label,
                  plan=meta.get('plan', 'free').capitalize())
        )
        return []

    connected = pv.key in configured
    head = f"{pv.icon} **{pv.label}**"
    if connected:
        head += t("onboarding.already_connected", " — ✅ déjà connecté")
    head += t("onboarding.effort", " · ≈{mins} min").format(mins=pv.effort_min)

    # Le ⭐ de la ligne a disparu avec la pile : dans une colonne intitulée
    # « Commence par là », le répéter sur chacune de ses cases ne dit rien de plus.
    checked = st.checkbox(head, value=(pv.recommended and not connected),
                          disabled=connected, key=f"_onb_pick_{pv.key}")
    # RIEN sous la case. Trois légendes l'accompagnaient — la valeur de la
    # plateforme, « À fournir : … », et le piège qui la fait échouer — soit vingt et
    # une lignes de prose sur un écran dont le geste tient en sept clics.
    #
    # Elles avaient chacune une raison d'être, et le mot juste est « avaient » :
    #
    #   la VALEUR répondait à « pourquoi celle-là ? » — la colonne y répond
    #     maintenant, en groupant par effort ;
    #   « À FOURNIR » répondait à « qu'est-ce qu'on va me demander ? » — le guide de
    #     chaque onglet le dit à l'instant où c'est utile, c'est-à-dire quand on le
    #     fournit, et la matrice d'état le redit dans sa dernière colonne ;
    #   le PIÈGE (compte Business, titres publics, chaîne « … - Topic », asset
    #     sharing) reste dans le guide de sa plateforme, où il est lisible parce
    #     qu'on y est déjà.
    #
    # Aucune n'est perdue : elles sont dites là où elles servent, au lieu d'être
    # dites toutes ensemble avant que rien ne serve.
    return [pv.key] if (checked and not connected) else []


def _step_status(db, artist_id: int) -> None:
    """Étape 2 : où tu en es, et par où sortir.

    Ce que l'ancienne étape 2 faisait — demander de choisir — se fait maintenant sur
    la page de bienvenue, juste sous la feuille de route. Il ne reste ici que ce qui
    n'a de sens qu'APRÈS le choix : l'état réel, plateforme par plateforme.

    Elle absorbe aussi l'ancienne étape « 🎉 C'est parti ! ». Trois écrans pour une
    mise en route dont deux ne portaient qu'un bouton chacun, c'était le contraire de
    « le plus simple possible ».
    """
    focus = st.session_state.get(FOCUS_KEY) or []
    st.title(t("onboarding.status_title", "📋 Où tu en es"))

    if focus:
        names = " + ".join(f"{BY_KEY[k].icon} {BY_KEY[k].label}" for k in focus if k in BY_KEY)
        st.success(
            t("onboarding.ready_focus",
              "Ta sélection : **{names}** (≈{mins} min). La page Credentials t'attend "
              "avec le guide de chacune — et te dira si la connexion ramène "
              "vraiment des données.").format(names=names, mins=total_effort(focus))
        )

    if db is not None and artist_id is not None:
        render_status_matrix(db, artist_id, key_suffix="onboarding")
        # Même raison qu'à la page Credentials : la légende vit dans la matrice.
        st.caption(t(
            "onboarding.matrix_legend",
            "🟢 vert = fait · ⚪ blanc = pas encore · 🔴 rouge = à corriger."))

    st.markdown("---")
    col_back, col_creds, col_home = st.columns([1, 2, 2])
    if col_back.button(t("onboarding.back", "← Retour")):
        st.session_state[_STEP_KEY] = 1
        st.rerun()
    if col_creds.button(t("onboarding.go_configure", "🔑 Connecter ma sélection →"),
                        type="primary" if focus else "secondary",
                        key="_onb_done_creds"):
        _goto('credentials')
    if col_home.button(t("onboarding.go_dashboard", "🏠 Aller au dashboard →"),
                       type="secondary" if focus else "primary",
                       key="_onb_done_home"):
        _goto('home')


def _step_labels() -> list[str]:
    # DEUX étapes. Il y en avait trois, dont deux ne portaient qu'un bouton chacune :
    # « 2. Données » commençait par redire la liste de plateformes de la page 1, et
    # « 3. Prêt ! » redemandait ce que le bouton précédent venait de décider.
    # Demandé le 2026-09-04 : « je veux le plus simple possible ».
    return [
        t("onboarding.step1", "1. Bienvenue & choix"),
        t("onboarding.step2", "2. Où tu en es"),
    ]


def render_sidebar_steps() -> None:
    """Les trois étapes, EN HAUT de la barre latérale, et cliquables.

    Deux défauts en un, tous deux rapportés depuis une vraie deuxième connexion le
    2026-09-04.

    **La position.** Ce bloc vivait dans `show()`, donc il s'écrivait pendant la phase
    de CONTENU — après le logo, la langue, le menu et le bouton de déconnexion. Il
    atterrissait sous tout le reste : « c'est tout en bas du volet de navigation ».
    `app._main_body` l'appelle maintenant depuis la phase BARRE LATÉRALE, ce qui a
    demandé de séparer « quelle est la page ? » de « dessine le menu ».

    **L'atteignabilité.** Les trois lignes étaient du `st.markdown` : elles NOMMAIENT
    les étapes sans y mener — « impossible de revenir aux différentes étapes de
    config ». Même forme que les quatre étapes de l'accueil, corrigées le 2026-08-30
    pour la même raison. L'étape courante reste du texte : il n'y a rien à y aller.
    """
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1
    step = st.session_state[_STEP_KEY]

    st.sidebar.markdown(t("onboarding.steps_header", "### Étapes"))
    for i, label in enumerate(_step_labels(), 1):
        prefix = "✅" if i < step else ("▶️" if i == step else "⬜")
        if i == step:
            st.sidebar.markdown(f"**{prefix} {label}**")
        elif st.sidebar.button(f"{prefix} {label}", key=f"_onb_jump_{i}",
                               use_container_width=True):
            st.session_state[_STEP_KEY] = i
            st.rerun()
    st.sidebar.markdown("---")


def _render_landing_choice(db, state) -> None:
    """La sortie, et le droit de ne plus revenir.

    Demandé le 2026-09-04 : « un gros bouton d'accès à l'app si on le souhaite avec
    case à cocher qui nous dit qu'on souhaite garder cette page de connexion au début
    ou non ». Les deux comptent, et pour la même raison : l'assistant redevient
    l'atterrissage tant que la configuration n'est pas finie, ce qui n'est utile que si
    on peut le traverser **et** le désactiver. Un écran qu'on ne peut pas quitter n'est
    pas une aide, c'est une porte.

    L'écriture est synchrone, pas dans un `on_change` : le callback tournerait au début
    du run SUIVANT, quand la connexion de `show()` est déjà fermée.
    """
    from src.dashboard.utils.setup_completion import FIRST_RUN_FOCUS, set_show_on_login

    st.markdown("---")
    if state.complete:
        st.success(t("onboarding.setup_complete",
                     "✅ Ta configuration est complète ({done}/{total}). "
                     "Cette page ne s'affichera plus à la connexion.")
                   .format(done=state.done_count, total=state.total))
    else:
        st.progress(state.done_count / state.total if state.total else 0.0)
        st.caption(t("onboarding.setup_progress",
                     "Configuration : **{done}/{total}** — tant que ce n'est pas "
                     "complet, tu retombes ici à la connexion.")
                   .format(done=state.done_count, total=state.total))

    col_go, col_keep = st.columns([2, 3])
    with col_go:
        if st.button(t("onboarding.enter_app", "🏠 Accéder à l'application →"),
                     type="primary", use_container_width=True, key="_onb_enter_app"):
            _goto('home')
    with col_keep:
        keep = st.checkbox(
            t("onboarding.keep_landing",
              "Afficher cette page à la connexion tant que ma configuration "
              "n'est pas terminée"),
            value=state.show_on_login, key="_onb_keep_landing")
        user_id = st.session_state.get('user_id')
        if keep != state.show_on_login and user_id and db is not None:
            try:
                set_show_on_login(db, user_id, keep)
            except Exception as exc:      # noqa: BLE001 — une préférence, jamais un mur
                logger.warning("show_setup_on_login not saved: %s", type(exc).__name__)
                st.caption(t("onboarding.keep_landing_unsaved",
                             "⚠️ Préférence non enregistrée — réessaie plus tard."))
            else:
                if not keep:
                    # Décocher rend le menu TOUT DE SUITE. La barre latérale de ce run
                    # est déjà dessinée sans lui : sans ce rerun, l'artiste décoche et
                    # ne voit rien changer avant sa prochaine action.
                    st.session_state.pop(FIRST_RUN_FOCUS, None)
                    st.rerun()


def show() -> None:
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1

    step = st.session_state[_STEP_KEY]
    plan = get_artist_plan()
    artist_id = tenant_scope()

    # Une seule connexion pour tout le rendu — l'état de configuration, la matrice et
    # la liste de cases posent la même question à la même base (règle transverse #9).
    db = get_db_connection()
    try:
        from src.dashboard.utils.setup_completion import read_setup_state
        state = read_setup_state(db, artist_id, st.session_state.get('user_id'))

        if step == 1:
            _step_welcome(plan, artist_id, db)
        else:
            _step_status(db, artist_id)

        # En BAS, et SEULEMENT à l'étape 2 — deux corrections du même jour, dans le
        # même sens.
        #
        # Le matin : ce bloc était au-dessus du titre de l'étape, donc la première
        # chose qu'un artiste voyait en arrivant sur sa mise en route était le bouton
        # pour en sortir. « Le bouton accéder à l'application [doit être] à la fin ».
        #
        # Le soir : il ne s'affiche plus du tout sur la page de bienvenue. « Sur cette
        # page de bienvenue, supprime configuration 0/4 et bouton accéder à l'appli…
        # elle apparaît uniquement au step 2. » La page 1 pose une question — que
        # veux-tu brancher ? — et son bouton y répond ; y ajouter une jauge « 0/4 »,
        # une sortie et une préférence de connexion donne trois façons de partir avant
        # d'avoir répondu. Ce qui a un sens APRÈS le choix se lit après le choix.
        if state.steps and step != 1:
            _render_landing_choice(db, state)
    finally:
        if db is not None:
            db.close()
