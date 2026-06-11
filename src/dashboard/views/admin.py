"""Vue Admin — Gestion des artistes SaaS, utilisateurs et upload CSV.

Accessible uniquement au rôle 'admin'.
"""
import streamlit as st
import pandas as pd

from src.dashboard.utils import get_db_connection
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin
from src.database.postgres_handler import validate_table


def _guard():
    """Bloque l'accès si non-admin."""
    if not is_admin():
        st.error(t("admin.access_denied", "⛔ Accès réservé à l'administrateur."))
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
    # Bust the process-global plan-row cache so the edited tier takes effect at once
    # (the cache is cross-session, so this reaches artist X's session too).
    from src.dashboard.auth import _cached_plan_row
    _cached_plan_row.clear()


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
    st.subheader(t("admin.tokens_header", "🔑 Tokens & rafraîchissement — référence"))
    st.caption(t(
        "admin.tokens_caption",
        "Régime permanent : **aucune action récurrente** pour l'artiste ni pour "
        "l'admin — chaque token est soit non-expirant, soit auto-renouvelé. Le seul "
        "geste admin possible est la réparation après une révocation/rotation manuelle "
        "côté plateforme."
    ))
    st.dataframe(pd.DataFrame(_TOKEN_MATRIX), hide_index=True, width="stretch")
    st.info(t(
        "admin.tokens_info",
        "Persistance des rotations : `update_platform_secret` (Fernet) — nécessite "
        "`FERNET_KEY` dans le conteneur Airflow. Apps partagées (SoundCloud/Meta) : "
        "`SOUNDCLOUD_CLIENT_ID/SECRET`, `META_ACCESS_TOKEN/APP_ID/APP_SECRET` en `.env`."
    ))


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


_COST_CATEGORIES = [
    ("domain", "🌐 Domaine"),
    ("vps", "🖥️ VPS / hébergement"),
    ("claude_code", "🤖 Claude Code"),
    ("stripe", "💳 Frais Stripe"),
    ("other", "📦 Autre"),
]
_COST_BILLING = [
    ("monthly", "Mensuel"),
    ("yearly", "Annuel (amorti /12)"),
    ("one_off", "Ponctuel"),
]


def _load_costs(db) -> list[dict]:
    """Operating-cost rows as dicts for the expansion engine (newest/active first)."""
    rows = db.fetch_query(
        "SELECT id, category, label, amount_eur, billing_period, start_month, "
        "end_month, active, note FROM app_operating_costs "
        "ORDER BY active DESC, start_month DESC, id DESC"
    )
    keys = ["id", "category", "label", "amount_eur", "billing_period",
            "start_month", "end_month", "active", "note"]
    out = []
    for r in rows or []:
        d = dict(zip(keys, r))
        d["amount_eur"] = float(d["amount_eur"] or 0)
        out.append(d)
    return out


def _render_costs(db, mrr: float) -> None:
    """Admin-global operating costs + net margin vs MRR (recurring auto-expanded)."""
    import datetime as _dt

    from src.dashboard.utils.app_costs import (
        current_month_cost,
        expand_monthly_costs,
    )

    st.markdown("---")
    st.subheader(t("admin.costs_header", "💸 Coûts d'exploitation & marge"))
    st.caption(t("admin.costs_intro",
                 "Coûts plateforme (domaine, VPS, Claude Code, frais Stripe…) — globaux, "
                 "pas par artiste. Un coût récurrent se reporte automatiquement chaque mois "
                 "(annuel amorti /12) jusqu'à sa désactivation."))

    rows = _load_costs(db)
    cat_labels = dict(_COST_CATEGORIES)
    bill_labels = dict(_COST_BILLING)

    with st.expander(t("admin.costs_add", "➕ Ajouter un coût"), expanded=not rows):
        with st.form("add_operating_cost", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            category = c1.selectbox(t("admin.costs_category", "Catégorie"),
                                    [c for c, _ in _COST_CATEGORIES],
                                    format_func=lambda c: cat_labels[c])
            amount = c2.number_input(t("admin.costs_amount", "Montant (€)"),
                                     min_value=0.0, step=1.0, value=0.0)
            period = c3.selectbox(t("admin.costs_period", "Facturation"),
                                  [b for b, _ in _COST_BILLING],
                                  format_func=lambda b: bill_labels[b])
            c4, c5 = st.columns(2)
            start = c4.date_input(t("admin.costs_start", "Mois de début"), value=_dt.date.today())
            ongoing = c5.checkbox(t("admin.costs_ongoing", "Toujours actif"), value=True)
            end = None if ongoing else c5.date_input(
                t("admin.costs_end", "Mois de fin"), value=_dt.date.today())
            label = st.text_input(t("admin.costs_label", "Libellé (ex. Hetzner CX22)"))
            if st.form_submit_button(t("admin.costs_save", "💾 Enregistrer"), type="primary"):
                if amount <= 0:
                    st.warning(t("admin.costs_need_amount", "Montant requis (> 0)."))
                else:
                    db.execute_query(
                        "INSERT INTO app_operating_costs (category, label, amount_eur, "
                        "billing_period, start_month, end_month) VALUES (%s, %s, %s, %s, %s, %s)",
                        (category, label or None, float(amount), period,
                         start.replace(day=1), end.replace(day=1) if end else None))
                    st.success(t("admin.costs_added", "Coût ajouté."))
                    st.rerun()

    if not rows:
        st.info(t("admin.costs_empty", "Aucun coût enregistré pour l'instant."))
        return

    cur = current_month_cost(rows)
    margin = mrr - cur
    k1, k2, k3 = st.columns(3)
    k1.metric(t("admin.costs_metric_month", "Coût ce mois"), f"{cur:.2f} €")
    k2.metric(t("admin.costs_metric_mrr", "MRR"), f"{mrr:.2f} €")
    k3.metric(t("admin.costs_metric_margin", "Marge nette / mois"), f"{margin:.2f} €",
              delta=f"{margin:.2f} €")

    df = expand_monthly_costs(rows)
    if not df.empty:
        import plotly.express as px
        df = df.copy()
        df["mois"] = pd.to_datetime(df["month"])
        df["Catégorie"] = df["category"].map(lambda c: cat_labels.get(c, c))
        fig = px.bar(df, x="mois", y="eur", color="Catégorie",
                     labels={"eur": "€", "mois": ""},
                     title=t("admin.costs_chart_title", "Coûts mensuels par catégorie"))
        if mrr > 0:
            fig.add_hline(y=mrr, line_dash="dash", line_color="green",
                          annotation_text=f"MRR {mrr:.0f} €")
        st.plotly_chart(fig, width="stretch")

    active_rows = [r for r in rows if r["active"]]
    if active_rows:
        tbl = pd.DataFrame([{
            "ID": r["id"], "Catégorie": cat_labels.get(r["category"], r["category"]),
            "Libellé": r["label"] or "—", "Montant (€)": r["amount_eur"],
            "Facturation": bill_labels.get(r["billing_period"], r["billing_period"]),
            "Début": str(r["start_month"]), "Fin": str(r["end_month"] or "—"),
        } for r in active_rows])
        st.dataframe(tbl, hide_index=True, width="stretch")
        cc1, cc2 = st.columns([3, 1])
        to_stop = cc1.selectbox(t("admin.costs_stop_select", "Désactiver un coût (ID)"),
                                [r["id"] for r in active_rows])
        if cc2.button(t("admin.costs_stop", "Désactiver")):
            db.execute_query("UPDATE app_operating_costs SET active = FALSE WHERE id = %s",
                             (int(to_stop),))
            st.rerun()


def _render_supervision(db):
    # ── Business ──────────────────────────────────────────────────────────
    st.subheader(t("admin.business_header", "📊 Business — inscriptions & abonnements"))
    su = db.fetch_query(
        "SELECT COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days'), "
        "       COUNT(*) FILTER (WHERE created_at >= now() - interval '30 days'), "
        "       COUNT(*) FILTER (WHERE email_verified), COUNT(*) "
        "FROM saas_users WHERE role <> 'admin'"
    )
    s7, s30, verified, total_u = (su[0] if su else (0, 0, 0, 0))
    na = db.fetch_query("SELECT COUNT(*) FROM saas_artists WHERE active")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("admin.metric_signups_7d", "Inscriptions 7 j"), s7 or 0)
    c2.metric(t("admin.metric_signups_30d", "Inscriptions 30 j"), s30 or 0)
    c3.metric(t("admin.metric_verified", "Comptes vérifiés"), f"{verified or 0}/{total_u or 0}")
    c4.metric(t("admin.metric_active_artists", "Artistes actifs"), na[0][0] if na else 0)

    rev = db.fetch_query(
        "SELECT sp.name, COUNT(*), SUM(sp.price_monthly) "
        "FROM artist_subscriptions a JOIN subscription_plans sp ON sp.id = a.plan_id "
        "WHERE a.status = 'active' GROUP BY sp.name, sp.price_monthly ORDER BY sp.price_monthly"
    )
    mrr = sum(float(r[2] or 0) for r in rev) if rev else 0.0
    if rev:
        paying = sum(int(r[1]) for r in rev)
        m1, m2, m3 = st.columns(3)
        m1.metric(t("admin.metric_mrr", "MRR (abonnements actifs)"), f"{mrr:.2f} €")
        m2.metric(t("admin.metric_paying", "Abonnés payants"), paying)
        m3.metric(t("admin.metric_arpu", "ARPU"), f"{mrr / paying:.2f} €" if paying else "—")
        st.dataframe(pd.DataFrame(rev, columns=["Plan", "Abonnés", "MRR (€)"]),
                     hide_index=True, width="stretch")
    else:
        st.caption(t("admin.no_paid_subs",
                     "Aucun abonnement payant actif (tous en Free / essai de bienvenue)."))

    # ── Coûts & marge ─────────────────────────────────────────────────────
    _render_costs(db, mrr)

    # ── Technique ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader(t("admin.tech_header", "🩺 Technique — fraîcheur des données par plateforme"))
    st.dataframe(_supervision_freshness(db), hide_index=True, width="stretch")
    st.caption(t(
        "admin.tech_legend",
        "🟢 ≤ 2 j · 🟠 ≤ 7 j · 🔴 > 7 j · ❓ table absente/illisible. "
        "Détails : pages **Airflow KPI**, **ETL Logs**, **DB Health**."
    ))


def show():
    _guard()

    st.title(t("admin.title", "⚙️ Administration"))
    st.markdown("---")

    (tab_supervision, tab_artists, tab_users, tab_upload,
     tab_gdpr, tab_tokens) = st.tabs(
        [t("admin.tab_supervision", "📊 Supervision"),
         t("admin.tab_artists", "👥 Artistes"),
         t("admin.tab_users", "👤 Utilisateurs"),
         t("admin.tab_upload", "📂 Upload CSV"),
         t("admin.tab_gdpr", "🗑️ Effacement RGPD"),
         t("admin.tab_tokens", "🔑 Tokens")])

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
            st.error(t("admin.load_artists_error", "Erreur chargement artistes : {err}").format(err=e))
            db.close()
            return

        st.subheader(t("admin.artists_header", "📋 Artistes enregistrés"))

        if df_artists.empty:
            st.info(t("admin.no_artists", "Aucun artiste en base."))
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
        with st.expander(t("admin.create_artist_expander", "➕ Créer un nouvel artiste"), expanded=False):
            with st.form("create_artist"):
                c1, c2, c3 = st.columns(3)
                new_name = c1.text_input(t("admin.field_name_required", "Nom *"))
                new_slug = c2.text_input(t("admin.field_slug_required", "Slug * (unique, minuscules)"))
                new_tier = c3.selectbox(t("admin.field_tier", "Tier"), ["free", "premium"])
                if st.form_submit_button(t("admin.btn_create", "Créer"), type="primary"):
                    if not new_name or not new_slug:
                        st.error(t("admin.name_slug_required", "Nom et slug obligatoires."))
                    else:
                        try:
                            _create_artist(db, new_name, new_slug, new_tier)
                            st.success(t("admin.artist_created", "✅ Artiste « {name} » créé.").format(name=new_name))
                            st.rerun()
                        except Exception as e:
                            st.error(t("admin.generic_error", "Erreur : {err}").format(err=e))

        # ── Modifier / activer-désactiver ─────
        if not df_artists.empty:
            with st.expander(t("admin.edit_artist_expander", "✏️ Modifier un artiste"), expanded=False):
                artist_options = {
                    f"{row['id']} — {row['name']}": row
                    for _, row in df_artists.iterrows()
                }
                sel_label = st.selectbox(t("admin.field_artist", "Artiste"), list(artist_options.keys()))
                sel = artist_options[sel_label]

                with st.form("edit_artist"):
                    c1, c2 = st.columns(2)
                    edit_name = c1.text_input(t("admin.field_name", "Nom"), value=sel['name'])
                    edit_tier = c2.selectbox(
                        t("admin.field_tier", "Tier"),
                        ["free", "premium"],
                        index=0 if sel['tier'] == 'free' else 1
                    )
                    edit_active = st.checkbox(t("admin.field_active", "Actif"), value=bool(sel['active']))

                    if st.form_submit_button(t("admin.btn_save", "Enregistrer"), type="primary"):
                        try:
                            _update_artist(db, sel['id'], edit_name, edit_tier)
                            _toggle_active(db, sel['id'], edit_active)
                            st.success(t("admin.artist_updated", "✅ Artiste mis à jour."))
                            st.rerun()
                        except Exception as e:
                            st.error(t("admin.generic_error", "Erreur : {err}").format(err=e))

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 2 : GESTION DES UTILISATEURS
    # ══════════════════════════════════════════
    with tab_users:
        db = get_db_connection()
        try:
            df_users = _load_users(db)
        except Exception as e:
            st.error(t("admin.load_users_error", "Erreur chargement utilisateurs : {err}").format(err=e))
            db.close()
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
            sel_label = st.selectbox(t("admin.field_select_user", "Sélectionner un utilisateur"), list(user_options.keys()), key="user_sel")
            sel_user = user_options[sel_label]

            col1, col2, col3 = st.columns(3)

            # Revoke / restore access
            with col1:
                if sel_user['active']:
                    if st.button(t("admin.btn_revoke", "🔴 Révoquer l'accès"), key="revoke_user"):
                        _toggle_user_active(db, sel_user['id'], False)
                        st.success(t("admin.access_revoked", "Accès révoqué pour {user}.").format(user=sel_user['username']))
                        st.rerun()
                else:
                    if st.button(t("admin.btn_restore", "✅ Restaurer l'accès"), key="restore_user"):
                        _toggle_user_active(db, sel_user['id'], True)
                        st.success(t("admin.access_restored", "Accès restauré pour {user}.").format(user=sel_user['username']))
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
                    st.success(t("admin.account_deleted", "Compte supprimé."))
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
            csv_bytes = df_optin[['username', 'email', 'artist_name']].to_csv(index=False).encode()
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

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 3 : UPLOAD CSV
    # ══════════════════════════════════════════
    with tab_upload:
        st.subheader(t("admin.upload_header", "📂 Importer un CSV pour un artiste"))
        st.caption(t("admin.upload_caption", "Formats supportés : Spotify for Artists (timeline), Apple Music (performance)"))

        db = get_db_connection()
        try:
            df_active = db.fetch_df(
                "SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id"
            )
        except Exception as e:
            st.error(t("admin.generic_error", "Erreur : {err}").format(err=e))
            db.close()
            return

        if df_active.empty:
            st.warning(t("admin.no_active_artist", "Aucun artiste actif. Créez-en un dans l'onglet Artistes."))
            db.close()
            return

        c1, c2 = st.columns(2)
        with c1:
            artist_choices = {f"{r['id']} — {r['name']}": r['id'] for _, r in df_active.iterrows()}
            sel_artist_label = st.selectbox(t("admin.field_target_artist", "Artiste cible"), list(artist_choices.keys()))
            target_artist_id = artist_choices[sel_artist_label]

        with c2:
            platform = st.selectbox(t("admin.field_platform", "Plateforme"), ["Spotify for Artists (S4A)", "Apple Music"])

        uploaded = st.file_uploader(
            t("admin.field_csv_file", "Fichier CSV"),
            type=["csv"],
            help=t("admin.field_csv_help", "Glissez le CSV exporté depuis la plateforme.")
        )

        if uploaded and st.button(t("admin.btn_import", "⬆️ Importer"), type="primary"):
            try:
                if platform.startswith("Spotify"):
                    n = _upload_s4a(db, target_artist_id, uploaded)
                else:
                    n = _upload_apple(db, target_artist_id, uploaded)
                st.success(t("admin.import_success", "✅ {n} ligne(s) importée(s) pour l'artiste #{artist_id}.").format(n=n, artist_id=target_artist_id))
            except Exception as e:
                st.error(t("admin.import_error", "❌ Erreur import : {err}").format(err=e))
                st.exception(e)

        db.close()

    # ══════════════════════════════════════════
    # ONGLET 4 : EFFACEMENT RGPD ART. 17
    # ══════════════════════════════════════════
    with tab_gdpr:
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

        db = get_db_connection()
        if db is None:
            st.error(t("admin.db_unreachable", "❌ Base de données inaccessible."))
        else:
            try:
                df_all = db.fetch_df(
                    "SELECT a.id, a.name, a.slug, u.email "
                    "FROM saas_artists a "
                    "LEFT JOIN saas_users u ON u.artist_id = a.id "
                    "ORDER BY a.id"
                )
            except Exception as e:
                st.error(t("admin.generic_error", "Erreur : {err}").format(err=e))
                db.close()
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
                db.close()
