"""Promo codes admin page — admin-only.

Type: Feature
Uses: get_db_connection, is_admin
Depends on: promo_codes, promo_events, saas_artists tables
Persists in: PostgreSQL spotify_etl (promo_codes)

Allows admins to create, list, and disable promotional codes that grant
free access to Basic or Premium for a fixed duration.
Distinct from the referral system.
"""
import secrets
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.auth import is_admin


def _guard():
    if not is_admin():
        st.error(t("promo_admin.admin_only", "⛔ Admin access only."))
        st.stop()


def _generate_code() -> str:
    return secrets.token_hex(3).upper()  # e.g. "F2A9C1"


def _create_code(db, code: str, plan: str, duration_days: int,
                 max_uses: int, expires_at, notes: str) -> None:
    db.fetch_query(
        """
        INSERT INTO promo_codes (code, plan_target, duration_days, max_uses, expires_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (code.upper(), plan, duration_days, max_uses,
         expires_at if expires_at else None,
         notes.strip() or None),
    )


def _toggle_active(db, code_id: int, new_state: bool) -> None:
    db.fetch_query(
        "UPDATE promo_codes SET active = %s WHERE id = %s",
        (new_state, code_id),
    )


def show():
    _guard()
    st.title(t("promo_admin.title", "🎟️ Promo Codes"))
    st.caption(t("promo_admin.caption", "Create codes that give free Basic or Premium access for a fixed period."))
    st.markdown("---")

    with project_db() as db:
        tab_list, tab_create = st.tabs([
            t("promo_admin.tab_all", "All codes"),
            t("promo_admin.tab_create", "Create new code"),
        ])

        # ── Tab: list ─────────────────────────────────────────────────────
        with tab_list:
            rows = db.fetch_query(
                """
                SELECT pc.id, pc.code, pc.plan_target, pc.duration_days,
                       pc.uses_count, pc.max_uses, pc.active,
                       pc.expires_at::date, pc.notes, pc.created_at::date
                FROM promo_codes pc
                ORDER BY pc.created_at DESC
                """
            )

            if not rows:
                st.info(t("promo_admin.no_codes", "No promo codes yet. Create one in the tab above."))
            else:
                df = pd.DataFrame(rows, columns=[
                    t("promo_admin.col_id", "ID"),
                    t("promo_admin.col_code", "Code"),
                    t("promo_admin.col_plan", "Plan"),
                    t("promo_admin.col_duration", "Duration (days)"),
                    t("promo_admin.col_uses", "Uses"),
                    t("promo_admin.col_max_uses", "Max uses"),
                    t("promo_admin.col_active", "Active"),
                    t("promo_admin.col_code_expires", "Code expires"),
                    t("promo_admin.col_notes", "Notes"),
                    t("promo_admin.col_created_on", "Created on"),
                ])
                col_expires = t("promo_admin.col_code_expires", "Code expires")
                col_max = t("promo_admin.col_max_uses", "Max uses")
                col_notes = t("promo_admin.col_notes", "Notes")
                df[col_expires] = df[col_expires].apply(
                    lambda x: str(x) if x else t("promo_admin.never", "Never"))
                df[col_max] = df[col_max].apply(
                    lambda x: t("promo_admin.unlimited", "Unlimited") if x == 0 else x)
                df[col_notes] = df[col_notes].fillna("")
                st.dataframe(
                    df.drop(columns=[t("promo_admin.col_id", "ID")]),
                    hide_index=True, width="stretch")

                st.markdown("---")
                st.subheader(t("promo_admin.toggle_header", "Disable / re-enable a code"))
                col1, col2, col3 = st.columns([2, 1, 1])
                selected_code = col1.selectbox(
                    t("promo_admin.select_code", "Select code"),
                    options=[r[1] for r in rows],
                    label_visibility="collapsed",
                )
                selected_row = next((r for r in rows if r[1] == selected_code), None)
                if selected_row:
                    code_id, _, _, _, _, _, is_active = selected_row[:7]
                    label = (t("promo_admin.btn_disable", "Disable") if is_active
                             else t("promo_admin.btn_reenable", "Re-enable"))
                    btn_type = "secondary" if is_active else "primary"
                    if col2.button(label, type=btn_type):
                        _toggle_active(db, code_id, not is_active)
                        msg = (t("promo_admin.toggle_disabled",
                                 "Code **{code}** disabled.")
                               if is_active else
                               t("promo_admin.toggle_reenabled",
                                 "Code **{code}** re-enabled."))
                        st.success(msg.format(code=selected_code))
                        st.rerun()

            st.markdown("---")

            # Usage log
            st.subheader(t("promo_admin.redemption_log", "Redemption log"))
            log_rows = db.fetch_query(
                """
                SELECT pc.code, sa.name AS artist, pe.applied_at::date,
                       sa.promo_plan, sa.promo_plan_expires_at::date
                FROM promo_events pe
                JOIN promo_codes pc ON pc.id = pe.promo_code_id
                JOIN saas_artists sa ON sa.id = pe.artist_id
                ORDER BY pe.applied_at DESC
                """
            )
            if log_rows:
                col_access = t("promo_admin.col_access_expires", "Access expires")
                df_log = pd.DataFrame(log_rows, columns=[
                    t("promo_admin.col_code", "Code"),
                    t("promo_admin.col_artist", "Artist"),
                    t("promo_admin.col_redeemed_on", "Redeemed on"),
                    t("promo_admin.col_plan_granted", "Plan granted"),
                    col_access,
                ])
                df_log[col_access] = df_log[col_access].apply(lambda x: str(x) if x else "—")
                st.dataframe(df_log, hide_index=True, width="stretch")
            else:
                st.info(t("promo_admin.no_redemptions", "No redemptions yet."))

        # ── Tab: create ───────────────────────────────────────────────────
        with tab_create:
            with st.form("create_promo"):
                col1, col2 = st.columns(2)

                suggested = _generate_code()
                code_input = col1.text_input(
                    t("promo_admin.field_code", "Code *"),
                    value=suggested,
                    help=t("promo_admin.field_code_help", "Uppercase alphanumeric. Auto-suggested — change if you want something memorable."),
                ).strip().upper()

                plan_input = col2.selectbox(
                    t("promo_admin.field_plan", "Plan granted *"),
                    options=["premium"],
                    format_func=str.capitalize,
                )

                col3, col4 = st.columns(2)
                duration_input = col3.number_input(
                    t("promo_admin.field_duration", "Duration (days) *"),
                    min_value=1, max_value=365, value=30,
                    help=t("promo_admin.field_duration_help", "How long the plan stays active after the code is redeemed."),
                )
                max_uses_input = col4.number_input(
                    t("promo_admin.field_max_uses", "Max uses *"),
                    min_value=0, value=1,
                    help=t("promo_admin.field_max_uses_help", "0 = unlimited. 1 = single use (recommended for personal invites)."),
                )

                expires_at_input = st.date_input(
                    t("promo_admin.field_expiry", "Code expiry date (optional)"),
                    value=None,
                    help=t("promo_admin.field_expiry_help", "Date after which the code can no longer be redeemed. Leave empty for no expiry."),
                )

                notes_input = st.text_input(
                    t("promo_admin.field_notes", "Notes (optional)"),
                    placeholder=t("promo_admin.field_notes_placeholder", "e.g. Sent to Thomas for beta testing"),
                )

                submitted = st.form_submit_button(t("promo_admin.btn_create", "Create code"), type="primary")

            if submitted:
                if not code_input:
                    st.error(t("promo_admin.code_required", "Code is required."))
                else:
                    existing = db.fetch_query(
                        "SELECT 1 FROM promo_codes WHERE code = %s", (code_input,)
                    )
                    if existing:
                        st.error(t("promo_admin.code_exists",
                                   "Code **{code}** already exists. Choose a different one.").format(code=code_input))
                    else:
                        expires_dt = None
                        if expires_at_input:
                            expires_dt = datetime(
                                expires_at_input.year,
                                expires_at_input.month,
                                expires_at_input.day,
                                tzinfo=timezone.utc,
                            )
                        _create_code(
                            db, code_input, plan_input,
                            int(duration_input), int(max_uses_input),
                            expires_dt, notes_input,
                        )
                        st.success(
                            t("promo_admin.code_created",
                              "✅ Code **{code}** created — grants **{plan}** for **{days} days**.").format(
                                  code=code_input,
                                  plan=plan_input.capitalize(),
                                  days=int(duration_input),
                              )
                        )
                        st.rerun()
