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
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.setup_focus import (
    connected_platforms, get_focus,
)

from ._core import (_load_credentials, _fetch_dag_last_states, fernet_state,
                    artist_display_name)
from ._registry import PLATFORMS
from ._render import _render_platform_tab


# La sélection d'onboarding est par PLATEFORME ; les onglets de cette page sont par
# CREDENTIAL. Instagram n'a pas d'onglet à lui : il se saisit dans celui de Meta.
# Apple Music n'en a aucun (c'est un import CSV) et disparaît donc de la
# traduction — ce qui est correct : il n'y a rien à saisir ici pour lui.
_TAB_FOR_PLATFORM = {"instagram": "meta"}

# Les plateformes de la sélection qui ne se saisissent PAS ici, avec la page qui les
# porte vraiment. Apple Music est un import de fichier : elle n'a aucun onglet, et
# jusqu'au 2026-09-04 un artiste qui la cochait à la mise en route ne la retrouvait
# NULLE PART — ni en onglet, ni dans le repli « les autres plateformes », qui se
# construit à partir des onglets. Elle disparaissait de son plan sans un mot, ce qui
# est la forme exacte du défaut qu'il a signalé le même jour sur SoundCloud.
# Les deux plateformes qui ne se CONNECTENT pas : on y dépose un fichier. Elles
# partagent la même page — « 📂 Ajouter mes chiffres Spotify for Artists & Apple ».
_PAGE_FOR_PLATFORM = {"apple_music": "upload_csv", "s4a": "upload_csv"}


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

    « Suivante : Instagram » envoie chercher un onglet Instagram qui n'existe pas —
    il se saisit dans « 📱 Meta / Instagram ». Nommer les deux coûte six mots et
    supprime la seule question que la phrase pose.
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
            st.warning(t(
                "credentials.fernet_missing",
                "⚠️ `fernet_key` absent de `config/config.yaml`. "
                "La sauvegarde est désactivée. "
                "Générez une clé : "
                "`python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"`"
            ))

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
        focus = get_focus()
        connected = connected_platforms(existing)
        if focus:
            # Il n'y a plus de récapitulatif ni de bandeau « Suivante ». Ils
            # disaient, en huit lignes, ce que les onglets montrent :
            #
            #   « 🎯 Ce que tu as choisi de brancher (0/3) : ⬜ Spotify ⬜ SoundCloud
            #     ⬜ Instagram — dans l'onglet Meta / Instagram »
            #   « 👉 Suivante : 🎵 Spotify — à fournir : le lien de ta page Spotify
            #     Artist. Son onglet est le premier ci-dessous, déjà ouvert. »
            #
            # « Trop long et inutile » (2026-09-04). C'est exact, et pour une raison
            # qui n'existait pas quand ces lignes ont été écrites : depuis, les
            # onglets sont RÉDUITS à la sélection le premier jour et ORDONNÉS pour que
            # le premier soit celui qu'on annonçait. Le bandeau décrivait donc une
            # mise en page devenue lisible d'elle-même — et son propre texte le
            # disait, « son onglet est le premier ci-dessous, déjà ouvert ».
            #
            # Ce qui reste ci-dessous est ce qu'aucun onglet ne peut montrer : une
            # plateforme cochée qui ne se configure PAS sur cette page.
            # Ce que l'artiste a coché et qui ne se configure PAS ici. Sans cette
            # ligne, la plateforme s'évaporait entre les deux pages : ni onglet, ni
            # repli, ni message. Elle reste comptée dans sa sélection — c'est bien
            # son plan — mais elle nomme la page qui la porte, et y mène.
            elsewhere = [k for k in focus
                         if platform_destination(k).startswith("page:")]
            if elsewhere:
                names = ", ".join(f"{BY_KEY[k].icon} {BY_KEY[k].label}"
                                  for k in elsewhere if k in BY_KEY)
                st.info(t(
                    "credentials.focus_elsewhere",
                    "📂 **{names}** ne se connecte pas par identifiant : c'est un "
                    "fichier à déposer. Sa page est **📂 Ajouter mes chiffres "
                    "Spotify for Artists & Apple**."
                ).format(names=names))
                if st.button(t("credentials.focus_elsewhere_go",
                               "📂 Aller y déposer mes fichiers →"),
                             key="_creds_focus_elsewhere"):
                    goto(_PAGE_FOR_PLATFORM[elsewhere[0]])
        elif not existing:
            st.info(t(
                "credentials.no_creds_banner",
                "💡 **Aucun credential configuré.** "
                "Sélectionnez une plateforme ci-dessous et suivez le guide "
                "pour connecter vos sources de données. "
                "Commencez par **SoundCloud** (le plus rapide : un seul identifiant)."
            ))

        st.markdown("---")

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

        tab_labels = [info['label'] for _, info in ordered]
        _CSV_TAB = t("credentials.csv_tab", "📂 Mes fichiers (Spotify for Artists, Apple)")
        tabs = st.tabs(tab_labels + [_CSV_TAB])

        # Ce que le verdict de sauvegarde annonce ensuite. Calculé UNE fois, ici,
        # sur l'état rechargé après le rerun : à ce moment la plateforme qui vient
        # d'être enregistrée compte déjà comme connectée, donc `left_here` désigne
        # bien la suivante et non celle qu'on vient de faire.
        # « La suivante » n'est plus tirée d'une sélection — il n'y en a plus. C'est
        # le prochain ONGLET non connecté dans l'ordre conseillé, ce qui est la même
        # promesse en plus simple : le parcours incite à tout faire, dans cet ordre.
        def _next_after(key: str) -> tuple | None:
            keys = [k for k, _ in ordered]
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
        for tab, (platform_key, platform_info) in zip(tabs, ordered):
            with tab:
                _render_platform_tab(
                    db=db,
                    platform_key=platform_key,
                    platform_info=platform_info,
                    artist_id=target_artist_id,
                    existing_row=existing.get(platform_key),
                    fernet_ok=fernet_ok,
                    dag_states=dag_states,
                    artist_name=artist_name,
                    next_platform=_next_after(platform_key),
                )

        with tabs[-1]:
            st.caption(t(
                "credentials.csv_tab_help",
                "Ces deux sources ne se connectent pas par identifiant : elles vous "
                "laissent télécharger un fichier tableau. Déposez-le ici — le type "
                "est reconnu tout seul, vous n'avez pas à l'ouvrir."))
            from src.dashboard.views.upload_csv import render_uploader
            render_uploader(db, target_artist_id)

        # L'accordéon « ➕ Les N autres plateformes » a disparu avec le repli qu'il
        # servait : elles sont toutes des onglets maintenant, au même niveau.

    finally:
        db.close()


if __name__ == "__main__":
    show()
