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

from ._core import _get_fernet, _load_credentials, _fetch_dag_last_states
from ._registry import PLATFORMS
from ._render import _render_global_kpi, _render_platform_tab


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
        fernet_ok = _get_fernet() is not None
        if not fernet_ok:
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

        # ── Statut DAGs (non-bloquant) ────────────────────────────────────
        with st.spinner(t("credentials.fetching_dag_status",
                          "Récupération du statut des DAGs…")):
            dag_states = _fetch_dag_last_states()

        # ── KPI global ───────────────────────────────────────────────────
        _render_global_kpi(existing, dag_states)

        # ── First-time setup banner ───────────────────────────────────────
        if not existing:
            st.info(t(
                "credentials.no_creds_banner",
                "💡 **Aucun credential configuré.** "
                "Sélectionnez une plateforme ci-dessous et suivez le guide "
                "pour connecter vos sources de données. "
                "Commencez par **SoundCloud** (le plus rapide : un seul identifiant)."
            ))

        st.markdown("---")

        # ── Onglets plateforme ────────────────────────────────────────────
        tab_labels = [info['label'] for info in PLATFORMS.values()]
        tabs = st.tabs(tab_labels)

        for tab, (platform_key, platform_info) in zip(tabs, PLATFORMS.items()):
            with tab:
                _render_platform_tab(
                    db=db,
                    platform_key=platform_key,
                    platform_info=platform_info,
                    artist_id=target_artist_id,
                    existing_row=existing.get(platform_key),
                    fernet_ok=fernet_ok,
                    dag_states=dag_states,
                )
    finally:
        db.close()


if __name__ == "__main__":
    show()
