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

from src.dashboard.content.platform_value import BY_KEY
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.setup_completion import FIRST_RUN_FOCUS
from src.dashboard.utils.setup_focus import (
    connected_platforms, get_focus, progress, remaining,
)

from ._core import (_load_credentials, _fetch_dag_last_states, fernet_state,
                    artist_display_name)
from ._registry import PLATFORMS
from ._render import _render_platform_tab, render_save_verdict
from src.dashboard.utils.status_matrix import render_status_matrix


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
    st.title(t("credentials.title", "🔑 Credentials API"))
    st.caption(t(
        "credentials.caption",
        "Gérez vos credentials d'accès API par plateforme. "
        "Les secrets sont chiffrés (Fernet) avant stockage en base."
    ))

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

        # ── Matrice de setup ─────────────────────────────────────────────
        # Remplace l'ancien bandeau KPI, dont le second axe était l'état Airflow de
        # la FLOTTE : il pouvait afficher 🟢 pendant que ce locataire-ci n'avait pas
        # une seule ligne. Et il itérait les 4 onglets, donc Instagram — qui est une
        # plateforme partout ailleurs — n'y figurait pas.
        st.markdown(t("credentials.matrix_header",
                      "#### 📋 État de tes plateformes"))
        # La légende n'est plus recopiée ici : `render_status_matrix` la porte, une
        # seule fois, à côté des colonnes qu'elle explique. Trois surfaces en
        # écrivaient chacune une version, et deux d'entre elles ne disaient pas ce
        # que « Répond » et « Données » veulent dire.
        render_status_matrix(db, target_artist_id, key_suffix="creds")
        st.markdown("---")

        # ── Reprise de la sélection faite à l'onboarding ──────────────────
        # Without this the artist arrives on six equal tabs and has to remember
        # what they had decided one page earlier.
        focus = get_focus()
        connected = connected_platforms(existing)
        if focus:
            done, total = progress(focus, connected)
            # « Suivante » ne nomme QUE ce qui se saisit sur cette page. Apple Music
            # n'est jamais « connectée » au sens des identités — c'est un fichier —
            # donc elle restait éternellement en tête de `remaining`, et le bandeau
            # promettait un onglet qui n'existe pas. Elle a sa propre ligne, plus bas.
            left_here = [k for k in remaining(focus, connected)
                         if platform_destination(k).startswith("tab:")]
            left = remaining(focus, connected)
            # La sélection ÉNUMÉRÉE, pas seulement comptée. « 1/3 connectée(s) »
            # oblige l'artiste à compter des onglets pour savoir si son plan est
            # arrivé entier — c'est ce qu'il a fait le 2026-09-04, et il a conclu
            # « il me montre uniquement spotify & meta ». Une liste nommée répond à
            # la question sans compter : ce qu'il a coché est écrit, ligne à ligne,
            # avec son état. Si une case s'est perdue en route, l'écart se voit ici
            # au lieu de se déduire.
            st.markdown(t("credentials.focus_recap",
                          "🎯 **Ce que tu as choisi de brancher ({done}/{total}) :**"
                          ).format(done=done, total=total))
            for key in focus:
                pv = BY_KEY.get(key)
                name = f"{pv.icon} {pv.label}" if pv else key
                if key in connected:
                    st.markdown(t("credentials.focus_item_done",
                                  "- ✅ **{name}** — connecté").format(name=name))
                elif platform_destination(key).startswith("page:"):
                    st.markdown(t("credentials.focus_item_csv",
                                  "- 📂 **{name}** — par fichier, page "
                                  "**📂 Ajouter mes chiffres Spotify for Artists "
                                  "& Apple**"
                                  ).format(name=name))
                else:
                    st.markdown(t("credentials.focus_item_todo",
                                  "- ⬜ {label}").format(label=_next_label(key)))

            if left_here:
                nxt = BY_KEY.get(left_here[0])
                st.info(t(
                    "credentials.focus_banner",
                    "👉 **Suivante : {label}** — à fournir : {need}.\n\n"
                    "Son onglet est le **premier ci-dessous**, déjà ouvert."
                ).format(label=_next_label(left_here[0]),
                         need=nxt.need if nxt else ""))
            elif not left:
                # Rien de « suivant » à annoncer quand il ne reste que du hors-page :
                # la ligne dédiée plus bas s'en charge, et deux bandeaux qui se
                # contredisent valent moins qu'un seul qui dit vrai.
                st.success(t(
                    "credentials.focus_done",
                    "🎯 **Sélection terminée ({total}/{total}).** Les données "
                    "arrivent sous ~2 min ; la page **🚦 Santé onboarding** dira "
                    "si chaque source ramène vraiment quelque chose."
                ).format(total=total))

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
        ordered = list(PLATFORMS.items())
        if focus:
            head = [k for k in remaining(focus, connected)
                    if platform_destination(k).startswith("tab:")][:1]
            # Le rang est calculé sur les clés d'ONGLET, pas sur les clés logiques —
            # et c'est le correctif du 2026-09-04.
            #
            # Il était bâti sur `focus`, qui contient `instagram`. Or `instagram`
            # n'est jamais une clé d'onglet : il se saisit dans celui de `meta`. Son
            # rang 0 ne s'appliquait donc à personne, `meta` tombait dans le rang par
            # défaut, et `spotify` — deuxième de la liste, mais bien présent comme
            # onglet — restait en tête. Après avoir connecté Spotify, l'artiste
            # rouvrait donc l'onglet Spotify, pendant que le bandeau au-dessus lui
            # annonçait « Suivante : Instagram ». Vu au navigateur.
            #
            # C'est la même classe que le défaut d'hier sur `_TAB_FOR_PLATFORM` : une
            # traduction logique → onglet posée à un endroit et oubliée à l'autre.
            # `platform_destination` est le seul traducteur ; ici aussi.
            def _tab_of(key: str) -> str:
                dest = platform_destination(key)
                return dest.split(":", 1)[1] if dest.startswith("tab:") else ""

            wanted = [_tab_of(k) for k in head + [f for f in focus if f not in head]]
            rank: dict = {}
            for i, tab in enumerate(t for t in wanted if t):
                rank.setdefault(tab, i)
            ordered.sort(key=lambda kv: (rank.get(kv[0], len(rank)),))

        # ── Première connexion : SEULEMENT ce qui a été coché ──────────────
        #
        # Réordonner ne suffisait pas. Signalé le 2026-09-04 : « il y avait uniquement
        # les items qu'on avait sélectionnés, il faudrait le remettre, il y a trop
        # d'infos au début — le plus simple possible, mais c'est peut-être uniquement
        # après création du compte ? » La dernière moitié est la bonne réponse et
        # c'est l'artiste qui la formule : la réduction n'a de sens que le premier
        # jour. Le drapeau qui la porte est déjà celui de l'ARRIVÉE
        # (`FIRST_RUN_FOCUS`), pas de la page, et il meurt dès que l'artiste est
        # ailleurs — sa sélection (`FOCUS_KEY`) vit dans la même session, les deux
        # apparaissent et disparaissent ensemble.
        #
        # Les autres plateformes ne sont pas cachées, elles sont REPLIÉES : masquer
        # ce qui existe fait chercher, et le dépôt a déjà payé « du code correct que
        # rien n'atteignait » six fois en une séance.
        #
        # `instagram` n'a PAS d'onglet : il vit dans celui de `meta` (« 📱 Meta /
        # Instagram »), et `apple_music` n'en a pas du tout — c'est un import CSV.
        # Traduire la sélection en onglets est donc obligatoire : sans ça, un artiste
        # qui coche Instagram voyait son onglet REPLIÉ, ce qui est pire que six
        # onglets. Vu au navigateur, à la première tentative.
        hidden = []
        first_run = bool(st.session_state.get(FIRST_RUN_FOCUS))
        if first_run and focus:
            tabs_wanted = {platform_destination(k).split(":", 1)[1] for k in focus
                           if platform_destination(k).startswith("tab:")}
            keep = [kv for kv in ordered if kv[0] in tabs_wanted]
            hidden = [kv for kv in ordered if kv[0] not in tabs_wanted]
            if keep:
                ordered = keep

        tab_labels = [info['label'] for _, info in ordered]
        tabs = st.tabs(tab_labels)

        # Ce que le verdict de sauvegarde annonce ensuite. Calculé UNE fois, ici,
        # sur l'état rechargé après le rerun : à ce moment la plateforme qui vient
        # d'être enregistrée compte déjà comme connectée, donc `left_here` désigne
        # bien la suivante et non celle qu'on vient de faire.
        _left_here = [k for k in remaining(focus, connected)
                      if platform_destination(k).startswith("tab:")] if focus else []
        next_platform = (_left_here[0], _next_label(_left_here[0])) if _left_here else None
        selection_complete = bool(focus) and not remaining(focus, connected)

        # Le verdict de la sauvegarde qui vient d'avoir lieu — AU-DESSUS des onglets.
        # Dans l'onglet, il tombait dans celui qu'on venait de quitter : la page se
        # réordonne pour ouvrir la plateforme SUIVANTE, donc le « ✅ … est connecté »
        # s'affichait dans un onglet fermé. Ici, il est lu quoi qu'il arrive.
        render_save_verdict(next_platform, selection_complete)

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
                )

        if hidden:
            with st.expander(t("credentials.other_platforms",
                               "➕ Les {n} autres plateformes ({names})").format(
                                   n=len(hidden),
                                   names=", ".join(i['label'] for _, i in hidden))):
                st.caption(t(
                    "credentials.other_platforms_help",
                    "Repliées parce que tu ne les as pas cochées à la mise en route. "
                    "Elles restent connectables ici, maintenant ou plus tard — et le "
                    "menu complet réapparaît dès que tu entres dans l'application."))
                sub = st.tabs([i['label'] for _, i in hidden])
                for tab, (platform_key, platform_info) in zip(sub, hidden):
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
                        )
    finally:
        db.close()


if __name__ == "__main__":
    show()
