"""Vue Admin — Gestion des artistes SaaS, utilisateurs et upload CSV.

Accessible uniquement au rôle 'admin'.
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import is_admin
from src.database.postgres_handler import validate_table


def _guard():
    """Bloque l'accès si non-admin."""
    if not is_admin():
        st.error("⛔ Accès réservé à l'administrateur.")
        st.stop()


# ─────────────────────────────────────────────
# CRUD helpers
# ─────────────────────────────────────────────

def _load_artists(db) -> pd.DataFrame:
    return db.fetch_df(
        "SELECT id, name, slug, tier, active, created_at FROM saas_artists ORDER BY id"
    )


def _create_artist(db, name: str, slug: str, tier: str):
    db.execute_query(
        "INSERT INTO saas_artists (name, slug, tier, active) VALUES (%s, %s, %s, TRUE)",
        (name.strip(), slug.strip().lower(), tier)
    )


def _update_artist(db, artist_id: int, name: str, tier: str):
    db.execute_query(
        "UPDATE saas_artists SET name = %s, tier = %s WHERE id = %s",
        (name.strip(), tier, artist_id)
    )
    # Audit the plan transition for the Alerts plan-evolution chart.
    from src.utils.plan_history import log_plan_change
    log_plan_change(db, artist_id, tier, 'admin_edit')


def _toggle_active(db, artist_id: int, active: bool):
    db.execute_query(
        "UPDATE saas_artists SET active = %s WHERE id = %s",
        (active, artist_id)
    )


# ─────────────────────────────────────────────
# User management helpers
# ─────────────────────────────────────────────

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
    db.execute_query(
        "UPDATE saas_users SET active = %s WHERE id = %s",
        (active, user_id)
    )


def _delete_user(db, user_id: int):
    """Hard-delete saas_users row. saas_artists row is preserved (FK ON DELETE SET NULL)."""
    db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))


def _delete_artist_and_users(db, artist_id: int):
    """Hard-delete a saas_artists row. Linked saas_users rows get artist_id = NULL (FK cascade)."""
    db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))


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

    for table in _GDPR_PLATFORM_TABLES:
        try:
            # CLAUDE.md rule #8 — explicit allowlist check before f-string SQL.
            # ValueError (table not allowlisted) falls into the except below and
            # records -1, same semantics as a missing table.
            validate_table(table)
            rows = db.fetch_query(
                f"DELETE FROM {table} WHERE artist_id = %s RETURNING 1",
                (artist_id,),
            )
            deleted[table] = len(rows) if rows else 0
        except Exception:
            deleted[table] = -1  # table may not exist in all deployments OR not in _ALLOWED_TABLES

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


def _resend_verification(db, user_id: int, email: str, username: str) -> bool:
    import secrets
    from src.utils.verification_email import send_verification_email
    token = secrets.token_urlsafe(32)
    db.execute_query(
        "UPDATE saas_users SET verification_token = %s WHERE id = %s",
        (token, user_id)
    )
    return send_verification_email(email, username, token)


# ─────────────────────────────────────────────
# CSV Upload helpers
# ─────────────────────────────────────────────

def _upload_s4a(db, artist_id: int, file):
    """Parse un CSV Spotify for Artists (timeline) et insère en DB."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from src.transformers.s4a_csv_parser import S4ACSVParser

    df = pd.read_csv(file)
    parser = S4ACSVParser()
    rows = parser.parse_timeline(df, artist_id=artist_id)
    if not rows:
        return 0
    db.upsert_many(
        table='s4a_song_timeline',
        data=rows,
        conflict_columns=['artist_id', 'song', 'date'],
        update_columns=['streams', 'collected_at']
    )
    return len(rows)


def _upload_apple(db, artist_id: int, file):
    """Parse un CSV Apple Music et insère en DB."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
    from src.transformers.apple_music_csv_parser import AppleMusicCSVParser

    df = pd.read_csv(file)
    parser = AppleMusicCSVParser()
    rows = parser.parse(df, artist_id=artist_id)
    if not rows:
        return 0
    db.upsert_many(
        table='apple_songs_performance',
        data=rows,
        conflict_columns=['artist_id', 'song_name'],
        update_columns=['plays', 'listeners', 'shazam_count']
    )
    return len(rows)


# ─────────────────────────────────────────────
# View
# ─────────────────────────────────────────────

_TOKEN_MATRIX = [
    {"Plateforme": "🎵 Spotify", "Type de token": "client_credentials (~1 h)",
     "Expiration": "1 h", "Rafraîchissement": "Auto à chaque collecte (re-grant)",
     "Action artiste": "Aucune", "Action admin": "Aucune (secret roté → re-coller)"},
    {"Plateforme": "🎬 YouTube", "Type de token": "Clé API statique",
     "Expiration": "Jamais", "Rafraîchissement": "N/A",
     "Action artiste": "Aucune", "Action admin": "Aucune (clé révoquée → remplacer)"},
    {"Plateforme": "☁️ SoundCloud", "Type de token": "client_credentials (app partagée)",
     "Expiration": "1 h", "Rafraîchissement": "Auto à chaque run",
     "Action artiste": "Aucune", "Action admin": "Aucune"},
    {"Plateforme": "📱 Meta (System User)", "Type de token": "Long-lived",
     "Expiration": "Jamais (expires_at = NULL)",
     "Rafraîchissement": "N/A — le DAG meta_token_refresh saute les tokens sans expiration",
     "Action artiste": "Aucune", "Action admin": "Seulement si révoqué manuellement"},
    {"Plateforme": "📱 Meta (perso 60 j, legacy)", "Type de token": "User token roulant",
     "Expiration": "60 jours",
     "Rafraîchissement": "Auto ×2 : DAG hebdo (<30 j) + collecteur proactif (<15 j), persistés",
     "Action artiste": "Aucune", "Action admin": "Aucune (migrer vers System User)"},
]


def _render_token_management() -> None:
    """Admin reference: per-platform token type, expiry and auto-refresh."""
    st.subheader("🔑 Tokens & rafraîchissement — référence")
    st.caption(
        "Régime permanent : **aucune action récurrente** pour l'artiste ni pour "
        "l'admin — chaque token est soit non-expirant, soit auto-renouvelé. Le seul "
        "geste admin possible est la réparation après une révocation/rotation manuelle "
        "côté plateforme."
    )
    st.dataframe(pd.DataFrame(_TOKEN_MATRIX), hide_index=True, width="stretch")
    st.info(
        "Persistance des rotations : `update_platform_secret` (Fernet) — nécessite "
        "`FERNET_KEY` dans le conteneur Airflow. Apps partagées (SoundCloud/Meta) : "
        "`SOUNDCLOUD_CLIENT_ID/SECRET`, `META_ACCESS_TOKEN/APP_ID/APP_SECRET` en `.env`."
    )


def _supervision_freshness(db) -> pd.DataFrame:
    """Per-platform last-data date + freshness flag. Each query guarded (autocommit
    handler → a missing table doesn't poison the next query)."""
    import datetime as _dt
    checks = [
        ("Spotify S4A",    "SELECT MAX(date) FROM s4a_song_timeline"),
        ("Meta Ads",       "SELECT MAX(day_date) FROM meta_insights_performance_day"),
        ("Instagram",      "SELECT MAX(collected_at)::date FROM instagram_daily_stats"),
        ("SoundCloud",     "SELECT MAX(collected_at)::date FROM soundcloud_tracks_daily"),
        ("YouTube",        "SELECT MAX(collected_at)::date FROM youtube_video_stats"),
        ("Apple Music",    "SELECT MAX(collected_at)::date FROM apple_songs_history"),
        ("ML prédictions", "SELECT MAX(prediction_date) FROM ml_song_predictions"),
    ]
    today = _dt.date.today()
    rows = []
    for label, sql in checks:
        try:
            r = db.fetch_query(sql)
            last = r[0][0] if r and r[0] else None
        except Exception:
            last = None
        if last is None or not hasattr(last, "year"):
            rows.append((label, "—", "❓ inconnu"))
            continue
        age = (today - last).days
        flag = ("🟢 à jour" if age <= 2 else "🟠 en retard" if age <= 7 else "🔴 obsolète")
        rows.append((label, str(last), f"{flag} ({age} j)"))
    return pd.DataFrame(rows, columns=["Plateforme", "Dernière donnée", "État"])


def _render_supervision(db):
    # ── Business ──────────────────────────────────────────────────────────
    st.subheader("📊 Business — inscriptions & abonnements")
    su = db.fetch_query(
        "SELECT COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days'), "
        "       COUNT(*) FILTER (WHERE created_at >= now() - interval '30 days'), "
        "       COUNT(*) FILTER (WHERE email_verified), COUNT(*) "
        "FROM saas_users WHERE role <> 'admin'"
    )
    s7, s30, verified, total_u = (su[0] if su else (0, 0, 0, 0))
    na = db.fetch_query("SELECT COUNT(*) FROM saas_artists WHERE active")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Inscriptions 7 j", s7 or 0)
    c2.metric("Inscriptions 30 j", s30 or 0)
    c3.metric("Comptes vérifiés", f"{verified or 0}/{total_u or 0}")
    c4.metric("Artistes actifs", na[0][0] if na else 0)

    rev = db.fetch_query(
        "SELECT sp.name, COUNT(*), SUM(sp.price_monthly) "
        "FROM artist_subscriptions a JOIN subscription_plans sp ON sp.id = a.plan_id "
        "WHERE a.status = 'active' GROUP BY sp.name, sp.price_monthly ORDER BY sp.price_monthly"
    )
    if rev:
        mrr = sum(float(r[2] or 0) for r in rev)
        paying = sum(int(r[1]) for r in rev)
        m1, m2, m3 = st.columns(3)
        m1.metric("MRR (abonnements actifs)", f"{mrr:.2f} €")
        m2.metric("Abonnés payants", paying)
        m3.metric("ARPU", f"{mrr / paying:.2f} €" if paying else "—")
        st.dataframe(pd.DataFrame(rev, columns=["Plan", "Abonnés", "MRR (€)"]),
                     hide_index=True, width="stretch")
    else:
        st.caption("Aucun abonnement payant actif (tous en Free / essai de bienvenue).")

    # ── Technique ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🩺 Technique — fraîcheur des données par plateforme")
    st.dataframe(_supervision_freshness(db), hide_index=True, width="stretch")
    st.caption(
        "🟢 ≤ 2 j · 🟠 ≤ 7 j · 🔴 > 7 j · ❓ table absente/illisible. "
        "Détails : pages **Airflow KPI**, **ETL Logs**, **DB Health**."
    )


def show():
    _guard()

    st.title("⚙️ Administration")
    st.markdown("---")

    (tab_supervision, tab_artists, tab_users, tab_upload,
     tab_gdpr, tab_tokens) = st.tabs(
        ["📊 Supervision", "👥 Artistes", "👤 Utilisateurs", "📂 Upload CSV",
         "🗑️ Effacement RGPD", "🔑 Tokens"])

    # ══════════════════════════════════════════
    # ONGLET 0 : SUPERVISION (business + technique)
    # ══════════════════════════════════════════
    with tab_supervision:
        db = get_db_connection()
        try:
            _render_supervision(db)
        finally:
            db.close()

    # ══════════════════════════════════════════
    # ONGLET 5 : GESTION DES TOKENS (référence admin)
    # ══════════════════════════════════════════
    with tab_tokens:
        _render_token_management()

    # ══════════════════════════════════════════
    # ONGLET 1 : GESTION DES ARTISTES
    # ══════════════════════════════════════════
    with tab_artists:
        db = get_db_connection()
        try:
            df_artists = _load_artists(db)
        except Exception as e:
            st.error(f"Erreur chargement artistes : {e}")
            db.close()
            return

        st.subheader("📋 Artistes enregistrés")

        if df_artists.empty:
            st.info("Aucun artiste en base.")
        else:
            # Tableau avec statut coloré
            def _status(active):
                return "✅ Actif" if active else "🔴 Inactif"

            df_display = df_artists.copy()
            df_display['Statut'] = df_display['active'].apply(_status)
            df_display['created_at'] = pd.to_datetime(df_display['created_at']).dt.strftime('%d/%m/%Y')
            st.dataframe(
                df_display[['id', 'name', 'slug', 'tier', 'Statut', 'created_at']].rename(columns={
                    'id': 'ID', 'name': 'Nom', 'slug': 'Slug',
                    'tier': 'Tier', 'created_at': 'Créé le'
                }),
                hide_index=True,
                width="stretch",
            )

        st.markdown("---")

        # ── Créer un artiste ──────────────────
        with st.expander("➕ Créer un nouvel artiste", expanded=False):
            with st.form("create_artist"):
                c1, c2, c3 = st.columns(3)
                new_name = c1.text_input("Nom *")
                new_slug = c2.text_input("Slug * (unique, minuscules)")
                new_tier = c3.selectbox("Tier", ["free", "premium"])
                if st.form_submit_button("Créer", type="primary"):
                    if not new_name or not new_slug:
                        st.error("Nom et slug obligatoires.")
                    else:
                        try:
                            _create_artist(db, new_name, new_slug, new_tier)
                            st.success(f"✅ Artiste « {new_name} » créé.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        # ── Modifier / activer-désactiver ─────
        if not df_artists.empty:
            with st.expander("✏️ Modifier un artiste", expanded=False):
                artist_options = {
                    f"{row['id']} — {row['name']}": row
                    for _, row in df_artists.iterrows()
                }
                sel_label = st.selectbox("Artiste", list(artist_options.keys()))
                sel = artist_options[sel_label]

                with st.form("edit_artist"):
                    c1, c2 = st.columns(2)
                    edit_name = c1.text_input("Nom", value=sel['name'])
                    edit_tier = c2.selectbox(
                        "Tier",
                        ["free", "premium"],
                        index=0 if sel['tier'] == 'free' else 1
                    )
                    edit_active = st.checkbox("Actif", value=bool(sel['active']))

                    if st.form_submit_button("Enregistrer", type="primary"):
                        try:
                            _update_artist(db, sel['id'], edit_name, edit_tier)
                            _toggle_active(db, sel['id'], edit_active)
                            st.success("✅ Artiste mis à jour.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 2 : GESTION DES UTILISATEURS
    # ══════════════════════════════════════════
    with tab_users:
        db = get_db_connection()
        try:
            df_users = _load_users(db)
        except Exception as e:
            st.error(f"Erreur chargement utilisateurs : {e}")
            db.close()
            return

        st.subheader("👤 Comptes utilisateurs")

        if df_users.empty:
            st.info("Aucun utilisateur en base.")
        else:
            def _fmt_bool(v, yes="✅", no="🔴"):
                return yes if v else no

            df_display = df_users.copy()
            df_display['Accès'] = df_display['active'].apply(lambda v: _fmt_bool(v, "✅ Actif", "🔴 Révoqué"))
            df_display['Email vérifié'] = df_display['email_verified'].apply(lambda v: _fmt_bool(v, "✅ Oui", "⏳ Non"))
            df_display['created_at'] = pd.to_datetime(df_display['created_at']).dt.strftime('%d/%m/%Y')
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
            sel_label = st.selectbox("Sélectionner un utilisateur", list(user_options.keys()), key="user_sel")
            sel_user = user_options[sel_label]

            col1, col2, col3 = st.columns(3)

            # Revoke / restore access
            with col1:
                if sel_user['active']:
                    if st.button("🔴 Révoquer l'accès", key="revoke_user"):
                        _toggle_user_active(db, sel_user['id'], False)
                        st.success(f"Accès révoqué pour {sel_user['username']}.")
                        st.rerun()
                else:
                    if st.button("✅ Restaurer l'accès", key="restore_user"):
                        _toggle_user_active(db, sel_user['id'], True)
                        st.success(f"Accès restauré pour {sel_user['username']}.")
                        st.rerun()

            # Resend verification email
            with col2:
                resend_disabled = bool(sel_user['email_verified'])
                if st.button("📧 Renvoyer vérification", disabled=resend_disabled, key="resend_verif"):
                    ok = _resend_verification(db, sel_user['id'], sel_user['email'], sel_user['username'])
                    if ok:
                        st.success(f"Email de vérification renvoyé à {sel_user['email']}.")
                    else:
                        st.warning("Email non envoyé — vérifiez la config SMTP dans config/config.yaml.")

            # Delete user account
            with col3:
                if st.button("🗑️ Supprimer le compte", type="secondary", key="delete_user"):
                    st.session_state['_confirm_delete_user'] = sel_user['id']

            if st.session_state.get('_confirm_delete_user') == sel_user['id']:
                st.warning(
                    f"⚠️ Supprimer **{sel_user['username']}** ? "
                    "Cette action est irréversible. L'artiste lié est conservé."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button("Confirmer la suppression", type="primary", key="confirm_del_user"):
                    _delete_user(db, sel_user['id'])
                    st.session_state.pop('_confirm_delete_user', None)
                    st.success("Compte supprimé.")
                    st.rerun()
                if cc2.button("Annuler", key="cancel_del_user"):
                    st.session_state.pop('_confirm_delete_user', None)
                    st.rerun()

        # ── Export liste marketing ────────────────────────────────────
        st.markdown("---")
        st.subheader("📧 Liste email marketing (opt-in)")

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
            st.metric("Contacts opt-in", len(df_optin))
            st.dataframe(
                df_optin.rename(columns={
                    'username': 'Utilisateur', 'email': 'Email',
                    'artist_name': 'Artiste', 'marketing_consent_at': 'Opt-in le',
                    'created_at': 'Inscrit le',
                }),
                hide_index=True,
                width="stretch",
            )
            csv_bytes = df_optin[['username', 'email', 'artist_name']].to_csv(index=False).encode()
            # RGPD Art. 5(1)(f) — record every access to personal data in audit log
            clicked = st.download_button(
                "⬇️ Exporter CSV",
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
            st.info("Aucun utilisateur n'a consenti aux communications marketing pour l'instant.")

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 3 : UPLOAD CSV
    # ══════════════════════════════════════════
    with tab_upload:
        st.subheader("📂 Importer un CSV pour un artiste")
        st.caption("Formats supportés : Spotify for Artists (timeline), Apple Music (performance)")

        db = get_db_connection()
        try:
            df_active = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
        except Exception as e:
            st.error(f"Erreur : {e}")
            db.close()
            return

        if df_active.empty:
            st.warning("Aucun artiste actif. Créez-en un dans l'onglet Artistes.")
            db.close()
            return

        c1, c2 = st.columns(2)
        with c1:
            artist_choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_active.iterrows()}
            sel_artist_label = st.selectbox("Artiste cible", list(artist_choices.keys()))
            target_artist_id = artist_choices[sel_artist_label]

        with c2:
            platform = st.selectbox("Plateforme", ["Spotify for Artists (S4A)", "Apple Music"])

        uploaded = st.file_uploader(
            "Fichier CSV",
            type=["csv"],
            help="Glissez le CSV exporté depuis la plateforme."
        )

        if uploaded and st.button("⬆️ Importer", type="primary"):
            try:
                if platform.startswith("Spotify"):
                    n = _upload_s4a(db, target_artist_id, uploaded)
                else:
                    n = _upload_apple(db, target_artist_id, uploaded)
                st.success(f"✅ {n} ligne(s) importée(s) pour l'artiste #{target_artist_id}.")
            except Exception as e:
                st.error(f"❌ Erreur import : {e}")
                st.exception(e)

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 4 : EFFACEMENT RGPD ART. 17
    # ══════════════════════════════════════════
    with tab_gdpr:
        st.subheader("🗑️ Effacement RGPD — Art. 17 (droit à l'oubli)")
        st.warning(
            "⚠️ Cette action **supprime définitivement** toutes les données d'un artiste : "
            "compte utilisateur, credentials, historiques analytiques, abonnement. "
            "Aucune restauration n'est possible. Un log d'audit est conservé.",
            icon="⚠️",
        )

        db = get_db_connection()
        if db is None:
            st.error("❌ Base de données inaccessible.")
        else:
            try:
                df_all = db.fetch_df(
                    "SELECT a.id, a.name, a.slug, u.email "
                    "FROM saas_artists a "
                    "LEFT JOIN saas_users u ON u.artist_id = a.id "
                    "ORDER BY a.id"
                )
            except Exception as e:
                st.error(f"Erreur : {e}")
                db.close()
                df_all = None

            if df_all is not None and not df_all.empty:
                gdpr_options = {
                    f"{r['id']} — {r['name']} ({r['email'] or '?'})": r['id']
                    for _, r in df_all.iterrows()
                }
                sel_gdpr = st.selectbox("Artiste à effacer", list(gdpr_options.keys()), key="gdpr_sel")
                gdpr_artist_id = gdpr_options[sel_gdpr]

                reason = st.text_input(
                    "Motif (obligatoire)",
                    placeholder="ex : demande utilisateur du 28/03/2026",
                    key="gdpr_reason",
                )

                if st.button("🗑️ Lancer l'effacement", type="primary", key="gdpr_erase_btn"):
                    if not reason.strip():
                        st.error("Le motif est obligatoire avant de lancer l'effacement.")
                    else:
                        st.session_state['_confirm_gdpr'] = gdpr_artist_id

                if st.session_state.get('_confirm_gdpr') == gdpr_artist_id:
                    st.error(
                        f"⛔ DERNIÈRE CONFIRMATION — Effacer **{sel_gdpr}** ? "
                        "Toutes les données seront supprimées de façon irréversible."
                    )
                    cc1, cc2 = st.columns(2)
                    if cc1.button("✅ Confirmer l'effacement définitif", type="primary", key="gdpr_confirm"):
                        admin_id = st.session_state.get('user_id')
                        try:
                            summary = _erase_artist_gdpr(db, gdpr_artist_id, admin_id, reason.strip())
                            st.session_state.pop('_confirm_gdpr', None)
                            total = sum(v for v in summary.values() if v > 0)
                            st.success(
                                f"✅ Effacement terminé — {total} lignes supprimées dans "
                                f"{len(summary)} tables. Log d'audit enregistré."
                            )
                            with st.expander("Détail par table"):
                                for tbl, cnt in summary.items():
                                    st.write(f"- `{tbl}` : {cnt} ligne(s)")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de l'effacement : {e}")
                    if cc2.button("Annuler", key="gdpr_cancel"):
                        st.session_state.pop('_confirm_gdpr', None)
                        st.rerun()

            elif df_all is not None:
                st.info("Aucun artiste en base.")

            if db:
                try:
                    df_log = db.fetch_df(
                        "SELECT erased_artist_id, erased_username, erased_email, reason, executed_at "
                        "FROM gdpr_erasure_log ORDER BY executed_at DESC LIMIT 50"
                    )
                    if not df_log.empty:
                        st.markdown("---")
                        st.subheader("📋 Historique des effacements")
                        st.dataframe(df_log, hide_index=True, width="stretch")
                except Exception:
                    pass
                db.close()
