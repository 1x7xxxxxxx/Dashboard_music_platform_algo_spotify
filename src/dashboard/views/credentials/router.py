"""Vue Credentials — Gestion des credentials API par plateforme (Brick 4).

Type: Feature
Uses: get_db_connection, get_artist_id/is_admin, _core, _registry, _render
Persists in: artist_credentials

Accessible à tous les utilisateurs authentifiés.
- Artiste : gère ses propres credentials (artist_id depuis session).
- Admin    : sélectionne n'importe quel artiste.

Stockage :
- token_encrypted (TEXT) : JSON de tous les champs secrets, chiffré Fernet.
- extra_config    (JSONB) : champs non-secrets (client_id, redirect_uri, account_id…).
"""
import streamlit as st

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import get_artist_id, is_admin

from src.dashboard.content.platform_value import (
    BY_KEY, SETUP_COLUMN_ORDER, setup_columns,
)
from src.dashboard.utils.setup_focus import (
    connected_platforms,
)

from ._core import (_load_credentials, _fetch_dag_last_states, fernet_state,
                    fernet_key_command_block,
                    artist_display_name)
from ._registry import PLATFORMS
from ._render import AUTOSTART_KEY, VERDICT_KEY, _render_platform_tab


# La sélection d'onboarding est par PLATEFORME ; les onglets de cette page sont par
# CREDENTIAL. Instagram n'a pas d'onglet à lui : il se saisit dans celui de Meta.
# Apple Music n'en a aucun (c'est un import CSV) et disparaît donc de la
# traduction — ce qui est correct : il n'y a rien à saisir ici pour lui.
# La clé de l'onglet de dépôt. Au niveau du module, et non dans `show()`, parce que
# `_TAB_FOR_PLATFORM` juste en dessous en a besoin — et parce qu'un lien profond
# (`?page=credentials&tab=__csv__`) la nomme depuis l'extérieur.
CSV_TAB_KEY = "__csv__"

# Instagram se saisit dans l'onglet de Meta Ads : même ligne de stockage, même
# jeton, même app. Il a eu son propre onglet une heure le 2026-09-05 — deux
# onglets pour une seule configuration se cherchent, et la traduction oubliée
# ICI a produit trois défauts d'un coup (« Suivante » vers le mauvais onglet,
# pastilles d'Instagram dans Meta, repli des « autres plateformes »).
# Vide depuis le 2026-09-05 : 📸 Instagram a son propre onglet, sur la mesure
# qui prouve qu'il collecte sans Meta Ads (`business_discovery`). La ligne de
# STOCKAGE reste `meta` — c'est `storage_platform` qui le dit, pas ceci.
_TAB_FOR_PLATFORM: dict[str, str] = {"apple_music": CSV_TAB_KEY,
                                     "s4a": CSV_TAB_KEY}

# Les plateformes de la sélection qui ne se saisissent PAS ici, avec la page qui les
# porte vraiment. Apple Music est un import de fichier : elle n'a aucun onglet, et
# jusqu'au 2026-09-04 un artiste qui la cochait à la mise en route ne la retrouvait
# NULLE PART — ni en onglet, ni dans le repli « les autres plateformes », qui se
# construit à partir des onglets. Elle disparaissait de son plan sans un mot, ce qui
# est la forme exacte du défaut qu'il a signalé le même jour sur SoundCloud.
# PLUS AUCUNE plateforme ne se configure hors de cette page (2026-09-06). Spotify
# for Artists et Apple Music pointaient vers `upload_csv`, une page sortie du menu
# le 2026-09-04 mais toujours routée, qui rendait sa PROPRE zone de dépôt : deux
# `st.file_uploader` pour un seul geste, donc deux états de session, donc un fichier
# déposé d'un côté invisible de l'autre. Elles pointent maintenant sur l'onglet de
# dépôt, qui est le seul.
#
# Le dictionnaire reste, vide : `platform_destination` sait rendre `page:…`, et une
# plateforme future pourrait légitimement vivre ailleurs. Ce qui n'existe plus, ce
# sont les DEUX cas qui l'utilisaient.
_PAGE_FOR_PLATFORM: dict[str, str] = {}

# L'onglet actif de la page Credentials — un état comme la page, pas une propriété
# invisible du rendu. Dans l'URL pour être adressable (lien profond, bouton
# Précédent), et dans `session_state` sous la clé du widget pour être pilotable.
_TAB_PARAM = "tab"
_TAB_STATE = "_creds_tab"


def _resolve_active_tab(keys: list[str], done: set | None = None) -> str:
    """L'onglet à ouvrir : la session d'abord, l'URL ensuite, le premier À FAIRE sinon.

    L'ORDRE compte. La session porte ce que l'artiste vient de choisir ou ce qu'une
    redirection vient d'écrire ; l'URL porte ce qu'il a collé ou mis en signet. Lire
    l'URL en premier ferait gagner un paramètre périmé sur un clic frais — c'est
    exactement le défaut qui a été corrigé sur la PAGE le 2026-09-04, et il n'y a
    aucune raison de le réintroduire un niveau plus bas.

    Une valeur inconnue (onglet renommé, lien ancien) retombe sur le premier au lieu
    de rendre une page vide.
    """
    for candidate in (st.session_state.get(_TAB_STATE),
                      st.query_params.get(_TAB_PARAM)):
        if candidate in keys:
            return candidate
    # Par défaut, le premier onglet qui reste À FAIRE — pas le premier tout court.
    # Demandé le 2026-09-05 : « on ne doit pas arriver sur l'onglet vert déjà
    # configuré, ça passe à celui directement à droite ». Depuis que les liens
    # d'inscription se matérialisent seuls, un artiste peut arriver avec Spotify déjà
    # branché ; l'ouvrir lui montre un formulaire qu'il vient de remplir ailleurs.
    #
    # Ce défaut ne s'applique qu'à l'ABSENCE de choix : une session ou une URL qui
    # nomment un onglet gagnent toujours, y compris un onglet vert — on n'empêche
    # personne de revenir sur ce qui est fait.
    for key in keys:
        if key not in (done or set()):
            return key
    # Tout est configuré : le premier, faute de mieux, plutôt qu'une page vide.
    return keys[0]


def _storage_for_tab(tab_key: str) -> str:
    """La ligne `artist_credentials` que cet onglet lit et écrit.

    Depuis la séparation de 📸 Instagram (2026-09-05), deux onglets partagent la
    ligne `meta`. Confondre l'onglet et la ligne ferait lire un `existing_row` vide
    à Instagram — donc un formulaire qui paraît neuf alors que la valeur est là.
    """
    from src.utils.tenant_identity import storage_platform
    return storage_platform(tab_key)


def all_tab_keys() -> list[str]:
    """Les onglets que cette page rend RÉELLEMENT : les plateformes, puis le dépôt.

    Une seule définition, parce qu'il y en avait deux et qu'elles ont divergé. La
    liste vivait dans le corps de `show()` (`[k for k, _ in ordered] + [_CSV_KEY]`)
    et `tests/test_every_setup_choice_has_a_destination.py` interrogeait `PLATFORMS`
    seul — donc l'onglet de dépôt n'était un onglet pour personne d'autre que la
    fonction qui le rendait. Le jour où S4A et Apple Music ont pointé dessus
    (2026-09-06), le garde a annoncé « onglet inexistant » sur un onglet visible à
    l'écran.
    """
    return list(PLATFORMS) + [CSV_TAB_KEY]


def platform_destination(key: str) -> str:
    """Où cette plateforme se configure : `tab:<clé d'onglet>` ou `page:<clé de page>`.

    Une seule fonction répond pour TOUTES les clés de `PLATFORM_VALUES` — c'est ce que
    `tests/test_every_setup_choice_has_a_destination.py` vérifie. Une plateforme
    qu'on peut cocher et qui n'a pas de destination est une case à cocher qui ne mène
    à rien.
    """
    if key in _PAGE_FOR_PLATFORM:
        return f"page:{_PAGE_FOR_PLATFORM[key]}"
    return f"tab:{_TAB_FOR_PLATFORM.get(key, key)}"


def _next_label(key: str) -> str:
    """Le nom de la plateforme, et celui de son onglet quand ils diffèrent.

    Écrit quand Instagram se saisissait dans « 📱 Meta / Instagram » : « Suivante :
    Instagram » envoyait alors chercher un onglet qui n'existait pas. Depuis qu'il a
    le sien, la mention n'était plus déclenchée — `_TAB_FOR_PLATFORM` était vide.
    Elle l'est de nouveau depuis le 2026-09-06 : Spotify for Artists et Apple
    Music partagent l'onglet de dépôt, donc « Suivante : 🎵 Spotify for Artists »
    doit nommer l'onglet « 📂 Mes fichiers » où l'artiste va réellement.
    """
    pv = BY_KEY.get(key)
    name = f"{pv.icon} {pv.label}" if pv else key
    dest = platform_destination(key)
    if dest.startswith("tab:"):
        tab_key = dest.split(":", 1)[1]
        tab_label = (PLATFORMS.get(tab_key) or {}).get("label", "")
        if tab_key != key and tab_label:
            return t("credentials.next_in_tab", "{name} — dans l'onglet **{tab}**"
                     ).format(name=name, tab=tab_label)
        return name
    return name


def show():
    # « Credentials API + imports CSV » : la page porte maintenant les DEUX façons de
    # brancher une source — coller un identifiant, déposer un fichier. Demandé le
    # 2026-09-04, avec le motif : cliquer sur l'entrée de menu séparée « Ajouter mes
    # chiffres… » ramenait à la mise en route (régression corrigée le même jour), et
    # deux entrées pour un seul geste — « connecter mes sources » — se cherchent.
    st.title(t("credentials.title", "🔑 Credentials API + imports CSV"))
    # La légende technique est partie : « Gérez vos credentials d'accès API par
    # plateforme. Les secrets sont chiffrés (Fernet) avant stockage en base. » Elle
    # décrivait une implémentation à quelqu'un qui vient coller un lien, et surtout
    # elle repoussait les onglets — « on arrive avec les différents onglets cliquables
    # tout en haut pour faciliter le parcours ».

    db = get_db_connection()
    try:
        # ── Sélection artiste ──────────────────────────────────────────────
        if is_admin():
            df_artists = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
            if df_artists.empty:
                st.warning(t("credentials.no_active_artist",
                             "Aucun artiste actif. Créez-en un dans l'onglet Admin."))
                return
            choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_artists.iterrows()}
            sel_label = st.selectbox(t("credentials.target_artist", "Artiste cible"),
                                     list(choices.keys()))
            target_artist_id = choices[sel_label]
        else:
            target_artist_id = get_artist_id()
            if target_artist_id is None:
                st.error(t("credentials.no_artist_id",
                           "Impossible de déterminer votre identifiant artiste."))
                return

        # ── Vérification Fernet ───────────────────────────────────────────
        # Say WHICH failure. "absent" and "malformed" call for opposite gestures —
        # generate a new key, versus repair the one that is already there — and the
        # banner used to say "absent" for both.
        _fernet_state = fernet_state()
        fernet_ok = _fernet_state == 'ok'
        if _fernet_state == 'malformed':
            st.error(t(
                "credentials.fernet_malformed",
                "⚠️ La clé de chiffrement (`FERNET_KEY`) est **présente mais "
                "invalide** — elle a probablement été tronquée à la copie. "
                "N'en génère pas une nouvelle : les credentials déjà enregistrées "
                "ne se déchiffreraient plus. Répare celle-ci."
            ))
        elif _fernet_state == 'absent':
            # Le message donnait la commande `python -c ...` seule, en Markdown inline.
            # Elle n'est pas exécutable telle qu'affichée : le seul interpréteur qui a
            # `cryptography` est celui du `venv/`, et PowerShell refuse `Activate.ps1`
            # sous sa politique par défaut. Le bloc rend les trois lignes dans l'ordre,
            # copiables d'un clic — et `st.code` évite que le lecteur reparte avec les
            # backticks du Markdown collés à la commande.
            st.warning(t(
                "credentials.fernet_missing",
                "⚠️ `fernet_key` absent de `config/config.yaml`. "
                "La sauvegarde est désactivée. Générez une clé en collant ces "
                "lignes dans un terminal ouvert à la racine du projet :"
            ))
            _fernet_lang, _fernet_cmd = fernet_key_command_block()
            st.code(_fernet_cmd, language=_fernet_lang)

        # ── Chargement credentials existants ─────────────────────────────
        existing = _load_credentials(db, target_artist_id)
        # Une seule lecture pour les quatre onglets — chacun la passe à son guide,
        # qui s'en sert pour viser le portail sur CET artiste.
        artist_name = artist_display_name(db, target_artist_id)

        # ── Statut DAGs (non-bloquant, ADMIN seulement) ───────────────────
        # Seul `_render_platform_tab` l'affiche, et seulement à un admin depuis le
        # 2026-08-30. Le chercher pour un artiste, c'était payer un aller-retour
        # Airflow — sous un spinner qui nomme un objet dont il n'entendra jamais
        # parler — pour une valeur que personne ne lit.
        dag_states: dict = {}
        if is_admin():
            with st.spinner(t("credentials.fetching_dag_status",
                              "Récupération du statut des DAGs…")):
                dag_states = _fetch_dag_last_states()

        # La matrice « 📋 État de tes plateformes » a vécu ici jusqu'au 2026-09-04.
        # Elle a sa page à elle depuis : « on l'enlève de Credentials API pour
        # faciliter la vie à l'utilisateur ».
        #
        # Mesuré avant de la déplacer, et c'est ce qui tranche : elle occupait les
        # 900 premiers pixels d'une page de 2141, et poussait le champ à remplir à
        # y=1475 — donc la capture d'écran qui l'accompagne à y=1569. Un artiste a
        # signalé QUATRE FOIS qu'« il n'y a pas le screen » : il y était, sous la
        # ligne de flottaison d'une page de configuration, ce qui revient au même.
        #
        # Les deux blocs ne répondent d'ailleurs pas à la même question. La matrice
        # dit « où j'en suis », la page dit « que dois-je saisir ». Mettre un bilan
        # au-dessus d'un formulaire, c'est faire lire avant de faire agir.

        # ── Reprise de la sélection faite à l'onboarding ──────────────────
        # Without this the artist arrives on six equal tabs and has to remember
        # what they had decided one page earlier.
        connected = connected_platforms(existing)
        # `get_focus()` ne sert plus ICI. Son `if focus:` ne portait plus que trois
        # bandeaux, retirés l'un après l'autre : le récapitulatif et « Suivante » le
        # 2026-09-04, parce que les onglets — réduits à la sélection et ordonnés —
        # disaient déjà la même chose ; le renvoi « ça se configure sur une autre
        # page » le 2026-09-06, avec la seconde zone de dépôt qu'il annonçait.
        #
        # La sélection d'onboarding continue de compter, mais par l'ORDRE des onglets
        # (`setup_columns()` plus bas), pas par un bandeau qui la répète.

        # Pas de bandeau « Aucun credential configuré » non plus. Il disait trois
        # choses, toutes redondantes avec l'écran : qu'il n'y a rien (le formulaire le
        # montre), de choisir une plateforme ci-dessous (la barre d'onglets est juste
        # là), et de commencer par SoundCloud (c'est l'ORDRE des onglets qui le dit
        # depuis le 2026-09-05 — et il dit Spotify, ce que le bandeau contredisait).

        # Aucune règle horizontale entre le titre et les boutons. Demandé le
        # 2026-09-05 : « la première ligne visible doit être celle des boutons ».
        # La barre de plateformes était prise en sandwich entre deux `---` — deux
        # traits qui séparent ce qui va ensemble et font descendre la seule chose
        # à cliquer. « Ça rajoute des trucs pour rien. »

        # ── Onglets plateforme ────────────────────────────────────────────
        # L'ordre EST la sélection : `st.tabs` ouvre toujours le premier onglet et
        # n'expose aucun index actif. Le bandeau ci-dessus annonçait « Suivante :
        # 🎵 Spotify » pendant que la page s'ouvrait sur SoundCloud, premier du dict
        # PLATFORMS — signalé par un artiste en test le 2026-08-30 : « ça nous
        # emmène sur l'onglet soundcloud donc c'est incohérent ».
        #
        # On met donc en tête la plateforme que le bandeau vient de nommer, puis le
        # reste de sa sélection, puis les autres. Chaque groupe garde l'ordre du
        # registre, pour que la page ne se réorganise pas sous ses yeux à chaque
        # rerun.
        # TOUS les onglets, au même niveau, dans l'ordre où l'on conseille de s'y
        # prendre. Décidé le 2026-09-05 : « on propose tout directement par ordre de
        # simplicité et de plus-value, mais le parcours incite à tout faire ».
        #
        # Ce qui disparaît avec ce bloc :
        #
        #   * le RÉORDONNANCEMENT par la sélection — il n'y a plus de sélection ;
        #   * le REPLI des plateformes non cochées dans « ➕ Les N autres » — un
        #     accordéon au bas de la page pour ce que le même écran présente en
        #     onglets, c'est deux niveaux pour une seule liste ;
        #   * la réduction « première connexion » : elle existait pour ne pas noyer
        #     un nouvel artiste sous six onglets, et sa vraie réponse est l'ORDRE.
        #
        # L'ordre vient de `setup_columns()`, le seul endroit qui décide « par où
        # commencer » : les trois rapides d'abord (un lien à coller), puis celles qui
        # demandent d'aller chercher un identifiant, puis le dépôt de fichiers. C'est
        # la même information que les trois colonnes de l'ancien sélecteur — elle
        # suggère au lieu de demander.
        _rank = {}
        for _col in SETUP_COLUMN_ORDER:
            for _pv in setup_columns().get(_col, []):
                dest = platform_destination(_pv.key)
                if dest.startswith("tab:"):
                    _rank.setdefault(dest.split(":", 1)[1], len(_rank))
        ordered = sorted(PLATFORMS.items(),
                         key=lambda kv: (_rank.get(kv[0], len(_rank)), kv[0]))

        _CSV_TAB = t("credentials.csv_tab", "📂 Mes fichiers (Spotify for Artists, Apple, distributeur)")
        # « La suivante » n'est plus tirée d'une sélection — il n'y en a plus. C'est
        # le prochain ONGLET non connecté dans l'ordre conseillé, ce qui est la même
        # promesse en plus simple : le parcours incite à tout faire, dans cet ordre.
        def _next_after(key: str) -> tuple | None:
            # L'ONGLET DE DÉPÔT FAIT PARTIE DE LA SUITE. `keys` n'énumérait que les
            # plateformes, donc « la suivante » ne pouvait jamais être « 📂 Mes
            # fichiers » : après la DERNIÈRE plateforme configurée, l'enchaînement
            # s'arrêtait net. Signalé le 2026-09-06 : « dès qu'on configure Meta Ads,
            # il n'y a pas le passage automatique vers fichiers CSV ».
            #
            # Il est en FIN de liste, et c'est ce qui le place au bon moment : la
            # boucle rend la première étape non faite, donc le dépôt n'est proposé
            # qu'une fois toutes les plateformes branchées. Spotify for Artists et
            # Apple Music n'étant jamais « connectés » au sens des identifiants — ils
            # n'ont pas d'identité à saisir — cet onglet reste la dernière étape tant
            # qu'aucun fichier n'est déposé, ce qui est exactement sa place.
            keys = [k for k, _ in ordered] + [_CSV_KEY]
            try:
                start = keys.index(key) + 1
            except ValueError:
                start = 0
            for nxt in keys[start:] + keys[:start]:
                if nxt == key:
                    continue
                logical = next((lg for lg in BY_KEY
                                if platform_destination(lg) == f"tab:{nxt}"), nxt)
                if logical not in connected:
                    return (logical, _next_label(logical))
            return None

        # OUVRIR l'onglet de la plateforme suivante après un enregistrement réussi.
        # Demandé le 2026-09-05 : « quand c'est marqué Suivante : SoundCloud, il
        # faudrait que ça redirige directement vers l'onglet SoundCloud ».
        #
        # `st.tabs(default=…)` existe en 1.54 et A ÉTÉ ESSAYÉ EN PREMIER : il ne suffit
        # pas. Sa docstring dit « the default tab to select », et c'est vrai au premier
        # MONTAGE du widget ; sur un rerun, Streamlit conserve l'onglet que l'artiste
        # avait sélectionné. Or l'enregistrement passe précisément par un rerun. Vu au
        # navigateur : l'onglet restait sur Spotify, `default` posé.
        #
        # Ce qui marche est de mettre la suivante EN TÊTE pour ce rerun-là : l'index
        # sélectionné (0, celui où l'artiste vient d'enregistrer) désigne alors la
        # plateforme suivante.
        #
        # Le réordonnancement avait été supprimé la veille parce qu'il déplaçait
        # l'onglet portant le verdict — « ✅ Spotify est connecté » s'affichait dans un
        # onglet fermé. Il revient SANS ce défaut parce que le verdict est maintenant
        # rendu par un onglet nommé (`owner`) : on le fait rendre par celui qui passe
        # en tête, c'est-à-dire par celui qui s'ouvre.
        # ── L'ONGLET ACTIF EST DANS L'URL ────────────────────────────────
        #
        # Refonte du 2026-09-05, demandée en ces termes : « on n'a pas un refactor
        # avec la meilleure logique possible pour les onglets, la redirection, etc. ? »
        # La réponse est oui, et les trois bugs signalés le même jour en sont les
        # symptômes, pas des accidents séparés.
        #
        # LE DÉFAUT DE CONCEPTION. `st.tabs` rend tous ses panneaux et n'expose AUCUN
        # contrôle de l'onglet actif. Chaque fois qu'il a fallu « ouvrir l'onglet X »,
        # on l'a donc obtenu en RÉORDONNANT la liste. Trois conséquences, toutes
        # constatées :
        #
        #   * la barre d'onglets bougeait sous l'artiste entre deux reruns — « ça nous
        #     ramène sur Spotify au lieu de Meta » : l'ordre était réordonné au rerun
        #     d'un enregistrement, puis revenait à sa place au suivant ;
        #   * « quel onglet montre le verdict » se découplait de « quel onglet est
        #     ouvert », d'où un rustine `verdict_owner` ;
        #   * rien n'était adressable : ni lien profond, ni bouton Précédent.
        #
        # LA CORRECTION. L'onglet devient un état comme la page : il vit dans l'URL
        # (`?page=credentials&tab=soundcloud`), et la barre est un vrai widget qu'on
        # peut piloter — le dépôt a déjà ce motif pour le menu (`_select_nav_radio`).
        # Un seul panneau est rendu, celui qui est actif : plus de DOM caché, et le
        # verdict s'affiche par construction là où l'artiste regarde.
        #
        # Rediriger n'est plus qu'écrire l'état : poser la clé du widget AVANT qu'il
        # soit instancié, comme le menu le fait déjà.
        _CSV_KEY = CSV_TAB_KEY
        _tab_keys = [k for k, _ in ordered] + [_CSV_KEY]  # = all_tab_keys(), réordonné
        # Un ✓ sur ce qui est DÉJÀ branché. Demandé le 2026-09-05 : « ceux qui sont
        # validés, on les propose différemment des plateformes qui restent à
        # configurer ». Depuis que les liens d'inscription se matérialisent tout
        # seuls, un artiste peut arriver ici avec deux onglets déjà faits sans avoir
        # rien saisi sur cette page — sans marque, il les refait.
        #
        # La marque dit « une identité est enregistrée », pas « ça marche » : ce
        # second verdict appartient aux pastilles et à la sonde, qui savent le
        # mesurer. Deux affirmations différentes ne partagent pas un glyphe.
        _connected_keys = connected_platforms(existing)
        # 🟢 = déclaré ET rien ne dit que ça ne marche pas. ⚠️ = déclaré mais la
        # dernière sonde a échoué : il RESTE une action.
        #
        # Le vert marquait la seule déclaration d'identité, et c'était trompeur —
        # signalé le 2026-09-05 : « l'onglet Meta Ads est vert alors qu'on a juste
        # rentré le lien du compte pub, on n'a pas donné l'accès ». Coller un
        # identifiant n'est pas se connecter : sur Meta il reste le partage du
        # compte, que nous ne pouvons pas faire à sa place, et la sonde le sait
        # (`SHARING_MISSING`).
        #
        # On ne fabrique aucun verdict ici : on lit celui qui est déjà mémorisé.
        from src.dashboard.utils.status_matrix import read_probes
        _probes = read_probes(db, target_artist_id)

        def _tab_state(tab_key: str) -> str:
            """'' | 'ok' | 'todo' — l'état AFFICHÉ de cet onglet."""
            logicals = [k for k in _connected_keys
                        if platform_destination(k) == f"tab:{tab_key}"]
            if not logicals:
                return ""
            failed = any((_probes.get(k) or (None,))[0] is False for k in logicals)
            return "todo" if failed else "ok"

        _MARK = {"ok": "🟢 ", "todo": "⚠️ ", "": ""}
        _tab_label = {
            k: f"{_MARK[_tab_state(k)]}{info['label']}"
            for k, info in ordered
        } | {_CSV_KEY: _CSV_TAB}

        def _tab_of(logical: str) -> str:
            dest = platform_destination(logical)
            return dest.split(":", 1)[1] if dest.startswith("tab:") else ""

        _pending = st.session_state.get(VERDICT_KEY)
        _verdict_next: tuple | None = None
        if _pending and _pending[1]:                       # sauvegarde RÉUSSIE
            _nxt = _next_after(_pending[0])
            _wanted = _tab_of(_nxt[0]) if _nxt else ""
            if _wanted in _tab_keys:
                # AVANT l'instanciation du widget : c'est la seule fenêtre où poser sa
                # valeur a un effet. Après, Streamlit considère que l'utilisateur a
                # choisi et refuse l'écriture.
                st.session_state[_TAB_STATE] = _wanted
                st.query_params[_TAB_PARAM] = _wanted
                # « Suivante » nomme l'onglet qu'on OUVRE, pas celui d'après : l'artiste
                # y est déjà.
                _verdict_next = _nxt

        # Les onglets DÉJÀ faits, dans l'espace des clés d'onglet — `connected_platforms`
        # rend des plateformes logiques, et Instagram n'a pas d'onglet à lui.
        # « Fait » = 🟢 seulement. Un onglet ⚠️ porte une action restante : l'ouvrir
        # est exactement ce qu'on veut, alors que le sauter renverrait l'artiste vers
        # une plateforme qu'il n'a pas encore branchée pendant qu'une autre attend un
        # geste de sa part.
        _done_tabs = {k for k, _ in ordered if _tab_state(k) == "ok"}
        _active = _resolve_active_tab(_tab_keys, _done_tabs)
        _chosen = st.segmented_control(
            t("credentials.tab_bar", "Plateforme"), _tab_keys,
            format_func=lambda k: _tab_label[k],
            default=_active, key=_TAB_STATE, label_visibility="collapsed",
        ) or _active
        # L'URL suit la sélection — un lien profond et le bouton Précédent marchent.
        if st.query_params.get(_TAB_PARAM) != _chosen:
            st.query_params[_TAB_PARAM] = _chosen

        # LE DÉMARRAGE AUTOMATIQUE, ANNONCÉ APRÈS LE RERUN.
        #
        # `_handle_save` le déclenche puis appelle `st.rerun()`, qui efface tout ce
        # qui est écrit à l'écran : un `st.success` posé là-bas n'aurait été lu par
        # personne — c'est le défaut exact qui avait rendu invisible le verdict de
        # sauvegarde, et la parade est la même, passer par la session.
        #
        # Au-dessus des onglets, pas dedans : la page se réordonne après un
        # enregistrement pour ouvrir la plateforme suivante, donc un message rendu
        # dans l'onglet tomberait dans celui qu'on vient de quitter.
        _auto = st.session_state.pop(AUTOSTART_KEY, None)
        if _auto:
            _ok, _ko = _auto
            if _ok:
                st.success(t(
                    "credentials.autostart_ok",
                    "🚀 Ta configuration est complète — la collecte vient de démarrer "
                    "toute seule ({n} sources). Tes premiers chiffres arrivent d'ici "
                    "quelques minutes.").format(n=_ok))
            elif _ko:
                st.warning(t(
                    "credentials.autostart_failed",
                    "⚠️ La collecte automatique n'a pas pu démarrer. Lance-la depuis "
                    "la barre latérale, ou réessaie plus tard."))

        # Ce que le verdict de sauvegarde annonce ensuite. Calculé UNE fois, ici,
        # sur l'état rechargé après le rerun : à ce moment la plateforme qui vient
        # d'être enregistrée compte déjà comme connectée, donc `left_here` désigne
        # bien la suivante et non celle qu'on vient de faire.

        # Le verdict de la sauvegarde qui vient d'avoir lieu — AU-DESSUS des onglets.
        # Dans l'onglet, il tombait dans celui qu'on venait de quitter : la page se
        # réordonne pour ouvrir la plateforme SUIVANTE, donc le « ✅ … est connecté »
        # s'affichait dans un onglet fermé. Ici, il est lu quoi qu'il arrive.
        # Le verdict ne se rend plus ICI : il descend DANS l'onglet, juste au-dessus
        # de « Saisir tes identifiants ». Demandé le 2026-09-05 : « dès que j'ai
        # collé mon URL Spotify, il faudrait mettre les infos au-dessus de saisir tes
        # identifiants ». Au-dessus des onglets il était à l'endroit qu'on venait de
        # quitter ; au-dessus du champ il est à l'endroit où l'on regarde.
        # Le dernier onglet est le DÉPÔT DE FICHIERS, pas une plateforme : Spotify for
        # Artists et Apple Music ne se connectent pas par identifiant. Ils avaient
        # leur page à part, dont l'entrée de menu a disparu le 2026-09-04 — deux
        # entrées pour un seul geste (« connecter mes sources ») se cherchent.
        #
        # UN onglet et non deux, contre la demande initiale, pour une raison mesurée :
        # le dépôt reconnaît la source depuis le fichier (« le type est reconnu tout
        # seul »). Deux onglets obligeraient l'artiste à classer son fichier AVANT de
        # le déposer — une décision que le code prend mieux que lui, sur une page où
        # aucun locataire n'a jamais terminé un import (mesuré le 2026-09-03).
        if _chosen == _CSV_KEY:
            # « Ces DEUX sources » était juste tant que l'onglet ne portait que
            # Spotify for Artists et Apple Music. Depuis que les distributeurs y
            # vivent aussi (2026-09-06), le compte est faux — et un compte faux dans
            # la première phrase d'une page est ce qui fait douter du reste.
            st.caption(t(
                "credentials.csv_tab_help",
                "Ces sources ne se connectent pas par identifiant : elles vous "
                "laissent télécharger un fichier tableau. Déposez-le ici — le type "
                "est reconnu tout seul."))
            from src.dashboard.views.upload_csv import render_uploader
            render_uploader(db, target_artist_id)
        else:
            _info = dict(ordered)[_chosen]
            _render_platform_tab(
                db=db,
                platform_key=_chosen,
                platform_info=_info,
                artist_id=target_artist_id,
                # La LIGNE, pas l'onglet : 📸 Instagram lit la ligne `meta`, où son
                # `ig_user_id` est stocké depuis toujours.
                existing_row=existing.get(_storage_for_tab(_chosen)),
                fernet_ok=fernet_ok,
                dag_states=dag_states,
                artist_name=artist_name,
                # Le panneau rendu EST celui qu'on regarde : plus de `verdict_owner`.
                # La rustine existait parce que l'onglet ouvert et l'onglet porteur du
                # verdict pouvaient différer ; ils ne le peuvent plus.
                next_platform=(_verdict_next or _next_after(_chosen)),
            )

    finally:
        db.close()


if __name__ == "__main__":
    show()
