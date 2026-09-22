"""Les comptes : utilisateurs, révocation, et l'effacement RGPD.

Type: Sub
Uses: streamlit, pandas, psycopg2 (via PostgresHandler)
Triggers: views/admin.py (section « 👥 Comptes »)
Persists in: PostgreSQL spotify_etl (saas_users, saas_artists, et les tables purgées)

Sorti de `views/admin.py` le 2026-09-22, le jour où la page a franchi 1 200 lignes en
gagnant son sélecteur à six sections. Le cliquet
`tests/test_a_file_only_gets_shorter.py` laisse deux issues et elles ne se valent pas :
« les ajouter à FROZEN fige la dette ; les découper la retire ». C'est le deuxième
découpage de cette page en une journée, après `admin_service_pricing.py`.

Pourquoi CES fonctions ensemble : elles répondent toutes à « qui a un compte, et que
peut-on lui faire » — révoquer, restaurer, renvoyer une vérification, supprimer. Et
l'effacement RGPD (Art. 17) est le cas extrême de la même question, pas un sujet à
part.

⚠️ `_erase_artist_gdpr` est la seule fonction irréversible de ce fichier. Elle voyage
avec l'écran qui la déclenche, et non dans un utilitaire : un effacement définitif ne
doit pas être appelable depuis une surface qui ne l'a pas explicitement demandé.
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.tz import to_local_datetime
from src.dashboard.utils.ui import flash
from src.database.postgres_handler import validate_table

logger = logging.getLogger(__name__)

# La liste voyage avec l'effacement qui la lit — elle n'a qu'un lecteur, et
# une liste de tables à PURGER n'a rien à faire dans un module que d'autres
# surfaces importent.
# Platform data tables with artist_id — ordered to satisfy FK constraints
_GDPR_PLATFORM_TABLES = [
    # Subscriptions / billing
    "artist_subscriptions",
    "promo_events",
    "referral_events",
    "referral_codes",
    # Credentials
    "artist_credentials",
    # Platform analytics
    "s4a_song_timeline",
    "s4a_spotify_data",
    "track_popularity_history",
    "youtube_channel_history",
    "youtube_video_stats",
    "soundcloud_tracks_daily",
    "soundcloud_stats_daily",
    "instagram_daily_stats",
    "instagram_posts",
    "meta_campaigns",
    "meta_adsets",
    "meta_ads",
    "meta_insights",
    "meta_insights_performance_day",
    "meta_creative_assets",
    "meta_creative_targeting",
    "meta_ads_api_raw",
    "meta_custom_conversions",
    "apple_songs_history",
    "apple_songs_performance",
    "apple_top_content",
    "hypeddit_overview",
    "hypeddit_campaigns",
    "ml_song_predictions",
    "ml_training_features",
    # Operations
    "etl_run_log",
    "etl_circuit_breaker",
    "imusician_revenues",
]


def _erase_artist_gdpr(db, artist_id: int, admin_user_id: int, reason: str) -> dict:
    """RGPD Art. 17 — full erasure of all data for one artist.

    Deletes platform data rows, then saas_users row(s), then saas_artists.
    Returns {table: rows_deleted} summary logged to gdpr_erasure_log.
    """
    import json
    # Capture identity before deletion for the audit record
    id_rows = db.fetch_query(
        "SELECT u.username, u.email FROM saas_users u WHERE u.artist_id = %s LIMIT 1",
        (artist_id,),
    )
    username = id_rows[0][0] if id_rows else None
    email    = id_rows[0][1] if id_rows else None

    deleted: dict[str, int] = {}

    # ⚠️ Trois issues DISTINCTES depuis le 2026-09-18. Avant, elles valaient toutes
    # `-1`, et le commentaire l'assumait : « same semantics as a missing table ».
    # C'est le contraire de ce qu'un reçu d'effacement doit faire — **un ÉCHEC réel
    # d'effacement de données personnelles se lisait exactement comme un nom de table
    # mort**, et ce reçu est la preuve qu'on produirait si on nous la demandait.
    #
    # Mesuré ce jour-là : **11 des 33 noms de `_GDPR_PLATFORM_TABLES` n'existent dans
    # aucune base** (122 tables réelles) — `s4a_spotify_data`, `soundcloud_stats_daily`,
    # `instagram_posts`, `meta_creative_assets`, `meta_creative_targeting`,
    # `meta_ads_api_raw`, `meta_custom_conversions`, `apple_top_content`,
    # `hypeddit_overview`, `ml_training_features`, `imusician_revenues`. Un tiers du
    # reçu était donc du bruit indistinguable d'une panne.
    #
    # Les noms morts sont CONSERVÉS dans la liste à dessein : les retirer effacerait la
    # trace qu'on a un jour cru ces plateformes couvertes. Le reçu dit maintenant
    # laquelle des trois choses s'est produite.
    for table in _GDPR_PLATFORM_TABLES:
        try:
            # CLAUDE.md rule #8 — explicit allowlist check before f-string SQL.
            validate_table(table)
        except Exception:
            deleted[table] = "non-allowlistée"
            continue
        try:
            existe = db.fetch_query(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = %s", (table,))
        except Exception:
            existe = None
        if not existe:
            deleted[table] = "absente de ce déploiement"
            continue
        try:
            rows = db.fetch_query(
                f"DELETE FROM {table} WHERE artist_id = %s RETURNING 1",
                (artist_id,),
            )
            deleted[table] = len(rows) if rows else 0
        except Exception as exc:
            # LE seul cas qui veut dire « des données personnelles peuvent subsister ».
            deleted[table] = f"ÉCHEC: {type(exc).__name__}"

    # Delete user accounts linked to this artist
    user_rows = db.fetch_query(
        "DELETE FROM saas_users WHERE artist_id = %s RETURNING 1", (artist_id,)
    )
    deleted["saas_users"] = len(user_rows) if user_rows else 0

    # Delete the artist record itself
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    deleted["saas_artists"] = 1

    # Audit log
    try:
        db.execute_query(
            """
            INSERT INTO gdpr_erasure_log
                (admin_user_id, erased_artist_id, erased_username, erased_email, rows_deleted, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (admin_user_id, artist_id, username, email, json.dumps(deleted), reason),
        )
    except Exception:
        pass  # audit log failure must not prevent erasure completion

    return deleted

def _load_users(db) -> pd.DataFrame:
    return db.fetch_df(
        """
        SELECT u.id, u.username, u.email, u.role, u.active, u.email_verified,
               u.created_at, a.name AS artist_name
        FROM saas_users u
        LEFT JOIN saas_artists a ON u.artist_id = a.id
        ORDER BY u.id
        """
    )

def _toggle_user_active(db, user_id: int, active: bool):
    """Flip `active`, and on deactivation invalidate every token already issued.

    Setting `active = FALSE` alone stopped the next LOGIN and nothing else (R24): the
    account's live dashboard session and its API tokens — up to 24 h of them — kept
    working. Bumping `token_version` is what makes "désactiver" mean "out now".
    Reactivation does not bump: there is nothing to revoke, and doing so would evict
    an admin who fat-fingered the toggle.
    """
    if active:
        db.execute_query("UPDATE saas_users SET active = TRUE WHERE id = %s", (user_id,))
    else:
        db.execute_query(
            "UPDATE saas_users SET active = FALSE, token_version = token_version + 1 "
            "WHERE id = %s",
            (user_id,),
        )

def _delete_user(db, user_id: int):
    """Hard-delete saas_users row. saas_artists row is preserved (FK ON DELETE SET NULL)."""
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))

def _resend_verification(db, user_id: int, email: str, username: str) -> bool:
    import secrets
    from src.utils.verification_email import send_verification_email
    from src.dashboard.utils.i18n import get_lang
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "UPDATE saas_users SET verification_token = %s WHERE id = %s",
        (token, user_id)
    )
    return send_verification_email(email, username, token, lang=get_lang())

def _tab_users(db) -> None:
    """Onglet « users » de la page Administration.

    Extrait de `show()` le 2026-08-30, qui faisait 401 lignes. Chaque bloc
    d'onglet n'avait que `db` comme variable libre — vérifié sur l'AST avant
    de couper, pas supposé. Aucune ligne de logique n'est modifiée.

    L'appelant garde son `with tab_…:`. Sans lui le contenu se rend HORS de
    l'onglet, sans lever — et ni le render-smoke, ni les tests de boutons, ni
    une empreinte À PLAT du rendu ne le voient. C'est l'erreur commise au
    premier jet de cette extraction, attrapée seulement en comparant le
    contenu PAR ONGLET (`tests/test_a_tab_renders_inside_its_tab.py`).
    """
    try:
        df_users = _load_users(db)
    except Exception as e:
        st.error(t("admin.load_users_error", "Erreur chargement utilisateurs : {err}").format(err=e))
        return

    st.subheader(t("admin.users_header", "👤 Comptes utilisateurs"))

    if df_users.empty:
        st.info(t("admin.no_users", "Aucun utilisateur en base."))
    else:
        def _fmt_bool(v, yes="✅", no="🔴"):
            return yes if v else no

        df_display = df_users.copy()
        df_display['Accès'] = df_display['active'].apply(lambda v: _fmt_bool(v, "✅ Actif", "🔴 Révoqué"))
        df_display['Email vérifié'] = df_display['email_verified'].apply(lambda v: _fmt_bool(v, "✅ Oui", "⏳ Non"))
        # `created_at` is timestamptz: rows either side of a DST change carry
        # different offsets and plain to_datetime raises. See utils/tz.py.
        df_display['created_at'] = to_local_datetime(df_display['created_at']).dt.strftime('%d/%m/%Y')
        st.dataframe(
            df_display[['id', 'username', 'email', 'role', 'artist_name', 'Accès', 'Email vérifié', 'created_at']].rename(columns={
                'id': 'ID', 'username': 'Utilisateur', 'email': 'Email',
                'role': 'Rôle', 'artist_name': 'Artiste', 'created_at': 'Créé le'
            }),
            hide_index=True,
            width="stretch",
        )

    st.markdown("---")

    if not df_users.empty:
        user_options = {
            f"{row['id']} — {row['username']} ({row['email']})": row
            for _, row in df_users.iterrows()
        }
        sel_label = st.selectbox(t("admin.field_select_user", "Sélectionner un utilisateur"), list(user_options.keys()), key="user_sel")
        sel_user = user_options[sel_label]

        col1, col2, col3 = st.columns(3)

        # Revoke / restore access
        with col1:
            if sel_user['active']:
                if st.button(t("admin.btn_revoke", "🔴 Révoquer l'accès"), key="revoke_user"):
                    _toggle_user_active(db, sel_user['id'], False)
                    flash(t("admin.access_revoked", "Accès révoqué pour {user}.").format(user=sel_user['username']))
                    st.rerun()
            else:
                if st.button(t("admin.btn_restore", "✅ Restaurer l'accès"), key="restore_user"):
                    _toggle_user_active(db, sel_user['id'], True)
                    flash(t("admin.access_restored", "Accès restauré pour {user}.").format(user=sel_user['username']))
                    st.rerun()

        # Resend verification email
        with col2:
            resend_disabled = bool(sel_user['email_verified'])
            if st.button(t("admin.btn_resend_verif", "📧 Renvoyer vérification"), disabled=resend_disabled, key="resend_verif"):
                ok = _resend_verification(db, sel_user['id'], sel_user['email'], sel_user['username'])
                if ok:
                    st.success(t("admin.verif_sent", "Email de vérification renvoyé à {email}.").format(email=sel_user['email']))
                else:
                    st.warning(t("admin.verif_not_sent", "Email non envoyé — vérifiez la config SMTP dans config/config.yaml."))

        # Delete user account
        with col3:
            if st.button(t("admin.btn_delete_account", "🗑️ Supprimer le compte"), type="secondary", key="delete_user"):
                st.session_state['_confirm_delete_user'] = sel_user['id']

        if st.session_state.get('_confirm_delete_user') == sel_user['id']:
            st.warning(t(
                "admin.confirm_delete_user",
                "⚠️ Supprimer **{user}** ? "
                "Cette action est irréversible. L'artiste lié est conservé."
            ).format(user=sel_user['username']))
            cc1, cc2 = st.columns(2)
            if cc1.button(t("admin.btn_confirm_delete", "Confirmer la suppression"), type="primary", key="confirm_del_user"):
                _delete_user(db, sel_user['id'])
                st.session_state.pop('_confirm_delete_user', None)
                flash(t("admin.account_deleted", "Compte supprimé."))
                st.rerun()
            if cc2.button(t("admin.btn_cancel", "Annuler"), key="cancel_del_user"):
                st.session_state.pop('_confirm_delete_user', None)
                st.rerun()

    # ── Export liste marketing ────────────────────────────────────
    st.markdown("---")
    st.subheader(t("admin.marketing_header", "📧 Liste email marketing (opt-in)"))

    try:
        df_optin = db.fetch_df(
            """
            SELECT u.username, u.email, a.name AS artist_name,
                   u.marketing_consent_at, u.created_at
            FROM saas_users u
            LEFT JOIN saas_artists a ON u.artist_id = a.id
            WHERE u.marketing_consent = TRUE AND u.active = TRUE
            ORDER BY u.created_at DESC
            """
        )
    except Exception:
        df_optin = None

    if df_optin is not None and not df_optin.empty:
        st.metric(t("admin.metric_optin", "Contacts opt-in"), len(df_optin))
        st.dataframe(
            df_optin.rename(columns={
                'username': 'Utilisateur', 'email': 'Email',
                'artist_name': 'Artiste', 'marketing_consent_at': 'Opt-in le',
                'created_at': 'Inscrit le',
            }),
            hide_index=True,
            width="stretch",
        )
        from src.dashboard.utils.csv_exporter import defang_formulas
        csv_bytes = defang_formulas(
            df_optin[['username', 'email', 'artist_name']]
        ).to_csv(index=False).encode()
        # RGPD Art. 5(1)(f) — record every access to personal data in audit log
        clicked = st.download_button(
            t("admin.btn_export_csv", "⬇️ Exporter CSV"),
            data=csv_bytes,
            file_name="optin_emails.csv",
            mime="text/csv",
        )
        if clicked:
            try:
                _admin_id = st.session_state.get('user_id')
                db.execute_query(
                    """
                    INSERT INTO admin_audit_log (admin_user_id, action, detail)
                    VALUES (%s, 'marketing_export', %s)
                    """,
                    (_admin_id, f"Exported {len(df_optin)} opt-in contacts"),
                )
            except Exception:
                pass  # audit log failure must not block the download
    else:
        st.info(t("admin.no_optin", "Aucun utilisateur n'a consenti aux communications marketing pour l'instant."))

def _tab_gdpr(db) -> None:
    """Onglet « gdpr » de la page Administration.

    Extrait de `show()` le 2026-08-30, qui faisait 401 lignes. Chaque bloc
    d'onglet n'avait que `db` comme variable libre — vérifié sur l'AST avant
    de couper, pas supposé. Aucune ligne de logique n'est modifiée.

    L'appelant garde son `with tab_…:`. Sans lui le contenu se rend HORS de
    l'onglet, sans lever — et ni le render-smoke, ni les tests de boutons, ni
    une empreinte À PLAT du rendu ne le voient. C'est l'erreur commise au
    premier jet de cette extraction, attrapée seulement en comparant le
    contenu PAR ONGLET (`tests/test_a_tab_renders_inside_its_tab.py`).
    """
    st.subheader(t("admin.gdpr_header", "🗑️ Effacement RGPD — Art. 17 (droit à l'oubli)"))
    st.warning(
        t(
            "admin.gdpr_warning",
            "⚠️ Cette action **supprime définitivement** toutes les données d'un artiste : "
            "compte utilisateur, credentials, historiques analytiques, abonnement. "
            "Aucune restauration n'est possible. Un log d'audit est conservé.",
        ),
        icon="⚠️",
    )

    try:
        df_all = db.fetch_df(
            "SELECT a.id, a.name, a.slug, u.email "
            "FROM saas_artists a "
            "LEFT JOIN saas_users u ON u.artist_id = a.id "
            "ORDER BY a.id"
        )
    except Exception as e:
        st.error(t("admin.generic_error", "Erreur : {err}").format(err=e))
        df_all = None

    if df_all is not None and not df_all.empty:
        gdpr_options = {
            f"{r['id']} — {r['name']} ({r['email'] or '?'})": r['id']
            for _, r in df_all.iterrows()
        }
        sel_gdpr = st.selectbox(t("admin.field_artist_to_erase", "Artiste à effacer"), list(gdpr_options.keys()), key="gdpr_sel")
        gdpr_artist_id = gdpr_options[sel_gdpr]

        reason = st.text_input(
            t("admin.field_reason", "Motif (obligatoire)"),
            placeholder=t("admin.field_reason_placeholder", "ex : demande utilisateur du 28/03/2026"),
            key="gdpr_reason",
        )

        if st.button(t("admin.btn_run_erasure", "🗑️ Lancer l'effacement"), type="primary", key="gdpr_erase_btn"):
            if not reason.strip():
                st.error(t("admin.reason_required", "Le motif est obligatoire avant de lancer l'effacement."))
            else:
                st.session_state['_confirm_gdpr'] = gdpr_artist_id

        if st.session_state.get('_confirm_gdpr') == gdpr_artist_id:
            st.error(t(
                "admin.gdpr_final_confirm",
                "⛔ DERNIÈRE CONFIRMATION — Effacer **{label}** ? "
                "Toutes les données seront supprimées de façon irréversible."
            ).format(label=sel_gdpr))
            cc1, cc2 = st.columns(2)
            if cc1.button(t("admin.btn_confirm_erasure", "✅ Confirmer l'effacement définitif"), type="primary", key="gdpr_confirm"):
                admin_id = st.session_state.get('user_id')
                try:
                    summary = _erase_artist_gdpr(db, gdpr_artist_id, admin_id, reason.strip())
                    st.session_state.pop('_confirm_gdpr', None)
                    total = sum(v for v in summary.values() if v > 0)
                    st.success(t(
                        "admin.erasure_done",
                        "✅ Effacement terminé — {total} lignes supprimées dans "
                        "{tables} tables. Log d'audit enregistré."
                    ).format(total=total, tables=len(summary)))
                    with st.expander(t("admin.erasure_detail", "Détail par table")):
                        for tbl, cnt in summary.items():
                            st.write(f"- `{tbl}` : {cnt} ligne(s)")
                    st.rerun()
                except Exception as e:
                    st.error(t("admin.erasure_error", "Erreur lors de l'effacement : {err}").format(err=e))
            if cc2.button(t("admin.btn_cancel", "Annuler"), key="gdpr_cancel"):
                st.session_state.pop('_confirm_gdpr', None)
                st.rerun()

    elif df_all is not None:
        st.info(t("admin.no_artists", "Aucun artiste en base."))

    if db:
        try:
            df_log = db.fetch_df(
                "SELECT erased_artist_id, erased_username, erased_email, reason, executed_at "
                "FROM gdpr_erasure_log ORDER BY executed_at DESC LIMIT 50"
            )
            if not df_log.empty:
                st.markdown("---")
                st.subheader(t("admin.gdpr_history_header", "📋 Historique des effacements"))
                st.dataframe(df_log, hide_index=True, width="stretch")
        except Exception:
            pass
