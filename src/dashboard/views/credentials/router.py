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
from src.dashboard.utils.setup_completion import FIRST_RUN_FOCUS
from src.dashboard.utils.setup_focus import (
    connected_platforms, get_focus, progress, remaining,
)

from ._core import (_load_credentials, _fetch_dag_last_states, fernet_state,
                    artist_display_name)
from ._registry import PLATFORMS
from ._render import _render_platform_tab
from src.dashboard.utils.status_matrix import render_status_matrix


# La sélection d'onboarding est par PLATEFORME ; les onglets de cette page sont par
# CREDENTIAL. Instagram n'a pas d'onglet à lui : il se saisit dans celui de Meta.
# Apple Music n'en a aucun (c'est un import CSV) et disparaît donc de la
# traduction — ce qui est correct : il n'y a rien à saisir ici pour lui.
_TAB_FOR_PLATFORM = {"instagram": "meta"}


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
        render_status_matrix(db, target_artist_id, key_suffix="creds")
        st.caption(t(
            "credentials.matrix_legend",
            "**Configuré** : tu as saisi l'identifiant. **Répond** : la plateforme "
            "nous a répondu correctement. **Données** : des chiffres sont bien "
            "arrivés. Aucune vérification n'est lancée tant que tu ne cliques pas."))
        st.markdown("---")

        # ── Reprise de la sélection faite à l'onboarding ──────────────────
        # Without this the artist arrives on six equal tabs and has to remember
        # what they had decided one page earlier.
        focus = get_focus()
        connected = connected_platforms(existing)
        if focus:
            done, total = progress(focus, connected)
            left = remaining(focus, connected)
            if left:
                nxt = BY_KEY.get(left[0])
                st.info(t(
                    "credentials.focus_banner",
                    "🎯 **Ta sélection : {done}/{total} connectée(s).** "
                    "Suivante : **{icon} {label}** — à fournir : {need}.\n\n"
                    "👇 Son onglet est le **premier ci-dessous**, déjà ouvert."
                ).format(done=done, total=total,
                         icon=nxt.icon if nxt else "", label=nxt.label if nxt else left[0],
                         need=nxt.need if nxt else ""))
            else:
                st.success(t(
                    "credentials.focus_done",
                    "🎯 **Sélection terminée ({total}/{total}).** Les données "
                    "arrivent sous ~2 min ; la page **🚦 Santé onboarding** dira "
                    "si chaque source ramène vraiment quelque chose."
                ).format(total=total))
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
            head = remaining(focus, connected)[:1]      # celle que le bandeau nomme
            rank = {k: i for i, k in enumerate(head + [f for f in focus if f not in head])}
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
            tabs_wanted = {_TAB_FOR_PLATFORM.get(k, k) for k in focus}
            keep = [kv for kv in ordered if kv[0] in tabs_wanted]
            hidden = [kv for kv in ordered if kv[0] not in tabs_wanted]
            if keep:
                ordered = keep

        tab_labels = [info['label'] for _, info in ordered]
        tabs = st.tabs(tab_labels)

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
