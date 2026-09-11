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
    st.image(str(path), width="stretch")


def _tenant_series(db, artist_id):
    """Les séries du locataire pour la première figure, ou `None` s'il n'y a rien.

    Rend `({plateforme: [(jour, écoutes du jour), …]}, {plateforme: série cumulée})`
    — les deux formes que `render_platform_chart` attend — et `None` quand
    `figure_source` dit « exemple ».
    Un seul point de décision : le libellé et la courbe ne peuvent pas diverger.

    `tenant_daily_streams` reste la porte d'entrée parce que c'est elle qui décide
    « assez de données pour tracer » (7 jours, `MIN_POINTS`). Ce qui est TRACÉ, en
    revanche, ne vient plus d'elle : sa requête additionnait un cumul et un
    quotidien. Voir `platform_timeseries`.
    """
    from src.dashboard.utils.welcome_figures import figure_source, tenant_daily_streams

    rows = tenant_daily_streams(db, artist_id)
    if figure_source(rows) != "tenant":
        return None
    from src.dashboard.utils.platform_timeseries import (
        MIN_POINTS_DRAWN, combined_daily_streams, daily_streams_by_platform,
    )
    series = daily_streams_by_platform(db, artist_id)
    # « Assez de lignes en base » ne veut pas dire « assez de points à tracer » : les
    # compteurs cumulatifs ne rendent un point qu'entre deux jours consécutifs. Sans
    # cette seconde condition, le libellé « Tes chiffres » s'afficherait au-dessus
    # d'une figure vide — le mélange exact que `figure_source` existe pour empêcher.
    if len(combined_daily_streams(series)) < MIN_POINTS_DRAWN:
        return None
    # La figure est tracée en mode CUMULÉ (le défaut de `render_platform_chart`), et
    # le cumul des plateformes à compteur ne se déduit pas de leur série quotidienne :
    # les journées non consécutives en sont absentes. C'est la deuxième moitié du même
    # reproche — « les datas sont incohérentes » — sur l'autre axe.
    from src.dashboard.utils.platform_timeseries import cumulative_by_platform
    return series, cumulative_by_platform(db, artist_id)


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
            if st.button(label, key=f"_onb_lang_{code}", width="stretch",
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
    # Lu AVANT la boucle : une requête, pas trois, et la décision est prise une fois.
    _mine = _tenant_series(db, artist_id)

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
            # R58, la moitié qui n'attendait pas R1 : la PREMIÈRE figure devient
            # celle du locataire dès qu'il a de quoi tracer. Les deux autres restent
            # des illustrations — une prédiction d'algorithme et un croisement Meta ×
            # Spotify n'existent pas avant d'avoir collecté, et une figure vide dirait
            # « ça ne marche pas » là où « voilà ce que tu auras » est la vérité.
            #
            # `figure_source` décide la courbe ET le libellé, ensemble. C'est le
            # piège que la tâche nommait d'avance : une figure réelle et une figure
            # d'exemple côte à côte, sans que rien ne les distingue, est pire que
            # trois exemples.
            if image == "dashboard-global.png" and _mine is not None:
                st.caption(t("onboarding.figure_mine", "📈 **Tes chiffres**"))
                # `st.line_chart` sur une série bricolée a été remplacé le 2026-09-08,
                # et les deux moitiés du reproche — « pas beau » et « les datas sont
                # incohérentes » — avaient chacune une cause distincte :
                #
                #   * la SÉRIE additionnait des streams quotidiens et le cumul
                #     SoundCloud depuis toujours (23 560 « écoutes » chaque jour) ;
                #   * le RENDU était un `line_chart` nu, sans couleurs de plateforme,
                #     sans légende et sans distinction entre « zéro » et « pas mesuré ».
                #
                # Les deux sont maintenant réglés au même endroit que l'accueil.
                from src.dashboard.utils.platform_chart import render_platform_chart
                render_platform_chart(_mine[0], cumulative=_mine[1],
                                      key="onb_trend")
            else:
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
    # PLUS DE CASES À COCHER. Décidé le 2026-09-05 : « on ne va pas demander les
    # cases à cocher de ce qu'il veut configurer, on propose tout directement par
    # ordre de simplicité et de plus-value, mais le parcours incite à tout faire ».
    #
    # Ce que le sélecteur coûtait, et qui ne se voyait pas en le regardant : il
    # demandait un ARBITRAGE avant d'avoir montré quoi que ce soit. Un artiste qui
    # n'a encore rien vu ne peut pas savoir si Meta Ads lui servira ; cocher trois
    # cases sur sept était donc moins un choix qu'un abandon des quatre autres, et
    # c'est exactement ce que la page de saisie faisait ensuite — elle repliait ce
    # qu'il n'avait pas coché.
    #
    # Le tri par effort survit, lui : il est devenu l'ORDRE des onglets. Ce qui était
    # une colonne « Commence par là » est maintenant le premier onglet, ce qui n'est
    # pas la même information — l'un demande de trancher, l'autre suggère par où
    # entrer et laisse tout atteignable.
    # PAS de second `st.markdown("---")` ici. Le bloc 2 se termine déjà par le sien,
    # ligne 412 ; les deux se suivaient sans rien de rendu entre eux — seulement le
    # commentaire ci-dessus — et produisaient deux filets empilés, donc le double
    # blanc signalé le 2026-09-05. Un séparateur sépare deux choses ; deux
    # séparateurs à la file ne séparent rien.
    #
    # Le bouton est CENTRÉ et large : c'est la seule action de la page, et la seule
    # chose qu'on ait à y faire. Trois colonnes 1-2-1 plutôt qu'un `<style>` visant
    # le DOM de Streamlit — un sélecteur sur sa structure interne se casse à la
    # montée de version en silence, la page continuant de s'afficher sans le
    # centrage. Même raison que pour les cellules encadrées du sélecteur.
    _l, _mid, _r = st.columns([1, 2, 1])
    with _mid:
        if st.button(t("onboarding.go_configure", "🔑 Connecter mes sources →"),
                     type="primary", width="stretch", key="_onb_go_creds"):
            st.session_state[_STEP_KEY] = 2
            _goto('credentials')
            return


# `_platform_picker` et `_platform_checkbox` ont été supprimés le 2026-09-05 avec le
# choix qu'ils portaient. Les trois colonnes qu'ils rendaient — « Commence par là »,
# « Un peu plus long », « Par fichier (CSV) » — vivent désormais dans l'ORDRE des
# onglets de la page de saisie, où elles suggèrent au lieu de demander.
#
# `setup_columns()` reste : c'est elle qui donne cet ordre, et c'est le seul endroit
# qui décide « par où commencer ».


def _step_status(db, artist_id: int) -> None:
    """Étape 2 : où tu en es, et par où sortir.

    Ce que l'ancienne étape 2 faisait — demander de choisir — se fait maintenant sur
    la page de bienvenue, juste sous la feuille de route. Il ne reste ici que ce qui
    n'a de sens qu'APRÈS le choix : l'état réel, plateforme par plateforme.

    Elle absorbe aussi l'ancienne étape « 🎉 C'est parti ! ». Trois écrans pour une
    mise en route dont deux ne portaient qu'un bouton chacun, c'était le contraire de
    « le plus simple possible ».
    """
    # Plus de « Ta sélection : … » : il n'y a plus de sélection depuis le
    # 2026-09-05. Ce bloc lisait `FOCUS_KEY`, que plus personne n'écrit — il était
    # devenu du code correct que rien n'atteint, la forme que ce dépôt a payée six
    # fois en une séance. Retiré avec le mécanisme, pas laissé « au cas où ».
    st.title(t("onboarding.status_title", "📋 Où tu en es"))

    if db is not None and artist_id is not None:
        render_status_matrix(db, artist_id, key_suffix="onboarding")
        # Même raison qu'à la page Credentials : la légende vit dans la matrice.
        st.caption(t(
            "onboarding.matrix_legend",
            "🟢 vert = fait · ⚪ blanc = pas encore · 🔴 rouge = à corriger."))

    # UN SEUL bouton. Il y en avait QUATRE sur cet écran : « ← Retour »,
    # « 🔑 Connecter mes sources → », « 🏠 Aller au dashboard → » ici, et un SECOND
    # « 🔑 Connecter mes sources → » juste dessous, rendu par `_render_landing_choice`.
    # Signalé le 2026-09-06 : deux fois la même action à trois centimètres d'écart, et
    # deux sorties qui doublent la barre latérale.
    #
    # Ce qui part, et pourquoi chacun :
    #   * le doublon — deux boutons identiques font douter qu'ils fassent la même
    #     chose, donc lire les deux ;
    #   * « ← Retour » — les étapes de la barre latérale y mènent déjà, et depuis que
    #     l'assistant rouvre sur l'étape 1 il n'y a plus de retour à faire ;
    #   * « 🏠 Aller au dashboard » — c'est « 🏠 Accueil », première entrée du menu.
    #
    # Reste l'action que le parcours incite à faire, seule et primaire.
    st.markdown("---")
    _l, _mid, _r = st.columns([1, 2, 1])
    with _mid:
        if st.button(t("onboarding.go_configure", "🔑 Connecter mes sources →"),
                     type="primary", width="stretch", key="_onb_done_creds"):
            _goto('credentials')


def sync_step_on_arrival() -> None:
    """Remet l'assistant à l'étape 1 quand on vient d'ARRIVER d'une autre page.

    UN SEUL endroit qui décide, appelé par les DEUX lecteurs de `_STEP_KEY` : la
    barre latérale (rendue en premier) et le corps de la page. La première version ne
    corrigeait que le corps, et la barre restait sur l'étape mémorisée — un écran qui
    se contredisait lui-même, ce qui est pire que le défaut d'origine.

    Idempotente : le second appel du même run relit une valeur déjà remise à 1.
    """
    if _entering_from_elsewhere() or _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = 1


def _step_labels() -> list[str]:
    # DEUX étapes. Il y en avait trois, dont deux ne portaient qu'un bouton chacune.
    return [
        t("onboarding.step1", "1. Bienvenue & choix"),
        t("onboarding.step2", "2. Où tu en es"),
    ]


def render_sidebar_steps() -> None:
    """Les étapes, cliquables, EN HAUT de la barre latérale — sans son titre.

    Retirées entièrement le 2026-09-05, remises le même jour : la demande était
    « retire … Étapes … », et j'ai lu le BLOC là où l'énumération listait des éléments
    à retirer un par un. « J'avais pas demandé de les enlever » — le mot désignait le
    titre `### Étapes`, pas les deux lignes sous lui.

    Ce qu'elles font et que rien d'autre ne fait : elles MÈNENT aux étapes. Elles
    étaient du `st.markdown` jusqu'au 2026-09-04, donc elles les nommaient sans y
    conduire — « impossible de revenir aux différentes étapes de config ». L'étape
    courante reste du texte : il n'y a rien à y aller.
    """
    # LA MÊME SYNCHRONISATION QUE LE CORPS, et c'est tout l'objet de cet appel.
    # La barre latérale est rendue AVANT `show()` : sans cette ligne elle lisait
    # l'étape mémorisée pendant que le corps, quelques instants plus tard, la
    # remettait à 1. Signalé le 2026-09-06 : « quand on clique sur assistant, on
    # arrive sur la deuxième page "où tu en es" alors qu'on visualise "bienvenue sur
    # streaMLytics" » — les deux moitiés du même écran en désaccord, exactement le
    # mode de panne que j'avais annoncé en déplaçant le marqueur et pas la remise à
    # zéro. Déplacer le repère ne suffit pas si les deux lecteurs n'en tirent pas la
    # même conclusion.
    sync_step_on_arrival()
    step = st.session_state[_STEP_KEY]

    # De l'AIR sous le logo. Signalé le 2026-09-05 : « c'est collé au logo
    # streaMLytics ». Le titre `### Étapes` faisait cet espacement sans qu'on le
    # sache — le retirer a rapproché les deux boutons du logo, ce qui est la trace
    # d'une suppression, comme les deux filets à la file de la veille : un élément
    # qui portait un espacement l'emporte avec lui.
    #
    # Un espace vide et non un titre : c'est bien le mot « Étapes » qu'on ne veut
    # plus, pas la respiration.
    #
    # 18 px → 44 px le 2026-09-06 : « descends un peu le menu bienvenue & choix pour
    # faciliter la compréhension ». Collée au logo, la liste se lisait comme une
    # suite du titre ; détachée, elle se lit comme ce qu'elle est — deux endroits où
    # aller.
    st.sidebar.markdown("<div style='height:44px'></div>", unsafe_allow_html=True)
    for i, label in enumerate(_step_labels(), 1):
        # LA FLÈCHE DIT OÙ VA LE CLIC, pas seulement où l'on en est. Demandé le
        # 2026-09-06. Les pastilles ✅/▶️/⬜ décrivaient un ÉTAT — fait, en cours, à
        # venir — et rien ne disait que ces lignes étaient cliquables : deux d'entre
        # elles le sont, la troisième non, et elles se ressemblaient toutes.
        #
        # `⬅` pour revenir en arrière, `➡` pour avancer : la direction est calculée
        # par rapport à l'étape courante, elle n'est pas écrite dans le libellé.
        if i == step:
            st.sidebar.markdown(f"**▶️ {label}**")
            continue
        arrow = "⬅" if i < step else "➡"
        done = "✅ " if i < step else ""
        if st.sidebar.button(f"{arrow} {done}{label}", key=f"_onb_jump_{i}",
                             width="stretch"):
            st.session_state[_STEP_KEY] = i
            st.rerun()


# `_render_landing_choice` a été SUPPRIMÉE le 2026-09-06. Elle ne rendait plus qu'un
# `st.markdown("---")` et un bouton « 🔑 Connecter mes sources → » — exactement le
# bouton que `_step_status` rend déjà quinze lignes plus haut, sur le même écran.
#
# Elle avait porté un compteur « Configuration : 2/4 » et une case « afficher cette
# page à la connexion », retirés le 2026-09-05. Ce qui restait était le résidu d'un
# bloc vidé : un doublon que personne n'avait vu parce qu'il était rendu par une
# AUTRE fonction, appelée depuis `show()`. Deux fonctions qui écrivent sur le même
# écran ne se lisent jamais ensemble.
#
# La préférence `show_setup_on_login` existe toujours en base et reste écrite par
# `--reset` : ce qui disparaît est le rendu, pas le mécanisme.


def _entering_from_elsewhere() -> bool:
    """Vient-on d'ARRIVER sur l'assistant, ou y était-on déjà ?

    `app.py` publie la page rendue au run précédent (`_page_arrived_from`). Streamlit
    ré-exécute le script à chaque clic, donc sans ce repère la vue ne peut pas faire
    la différence entre « il vient de cliquer sur Mise en route » et « il est dessus
    et vient de cliquer sur un bouton » — et l'étape gardée en session survivait à la
    navigation.

    Une clé ABSENTE (premier run de la session, tests headless qui appellent `show()`
    sans passer par `app.py`) n'est PAS une arrivée : sans quoi chaque rerun
    remettrait l'étape à 1 et l'assistant deviendrait impossible à traverser.
    """
    arrived_from = st.session_state.get('_page_arrived_from')
    return arrived_from is not None and arrived_from != 'onboarding'


def show() -> None:
    # ROUVRIR SUR L'ÉTAPE 1. Signalé le 2026-09-06 : « dès qu'on clique sur
    # l'assistant, ça devrait nous ramener à bienvenue et choix au lieu de directement
    # où tu en es ».
    #
    # `_STEP_KEY` vit dans `session_state`, qui survit à la navigation : un artiste
    # passé une fois à l'étape 2 rouvrait l'assistant sur « Où tu en es » pour le
    # reste de sa session. Ce n'est pas un état de session, c'est l'endroit où l'on
    # en était dans un parcours qu'on vient de reprendre depuis le début.
    #
    # On ne remet pas à 1 à chaque run — seulement quand on ARRIVE d'une autre page.
    # Les deux boutons d'étape de la barre latérale continuent de fonctionner, et
    # `_step_welcome` peut toujours pousser vers l'étape 2.
    sync_step_on_arrival()

    step = st.session_state[_STEP_KEY]
    plan = get_artist_plan()
    artist_id = tenant_scope()

    # Une seule connexion pour tout le rendu — l'état de configuration, la matrice et
    # la liste de cases posent la même question à la même base (règle transverse #9).
    db = get_db_connection()
    try:
        # `read_setup_state` n'est plus appelée ICI. Elle l'était pour décider
        # d'afficher un bloc de sortie en bas de l'étape 2 — bloc supprimé le
        # 2026-09-06 parce qu'il rendait un doublon du bouton de `_step_status`.
        # L'atterrissage au login, lui, la lit depuis `app.py` : ce qui disparaît est
        # une lecture devenue sans lecteur, pas le mécanisme.
        #
        # Elle est retirée plutôt que gardée « au cas où » : une requête dont
        # personne ne lit le résultat est une connexion dépensée pour rien, et la
        # règle transverse #9 plafonne cette page à une seule.

        if step == 1:
            _step_welcome(plan, artist_id, db)
        else:
            _step_status(db, artist_id)
    finally:
        if db is not None:
            db.close()
