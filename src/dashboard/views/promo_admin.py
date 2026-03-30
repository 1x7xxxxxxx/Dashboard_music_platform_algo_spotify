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

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import is_admin


def _guard():
    if not is_admin():
        st.error("⛔ Admin access only.")
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
    st.title("🎟️ Promo Codes")
    st.caption("Create codes that give free Basic or Premium access for a fixed period.")
    st.markdown("---")

    db = get_db_connection()
    if db is None:
        st.error("❌ Database unreachable.")
        return

    try:
        tab_list, tab_create = st.tabs(["All codes", "Create new code"])

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
                st.info("No promo codes yet. Create one in the tab above.")
            else:
                df = pd.DataFrame(rows, columns=[
                    "ID", "Code", "Plan", "Duration (days)",
                    "Uses", "Max uses", "Active",
                    "Code expires", "Notes", "Created on",
                ])
                df["Code expires"] = df["Code expires"].apply(lambda x: str(x) if x else "Never")
                df["Max uses"] = df["Max uses"].apply(lambda x: "Unlimited" if x == 0 else x)
                df["Notes"] = df["Notes"].fillna("")
                st.dataframe(df.drop(columns=["ID"]), hide_index=True, use_container_width=True)

                st.markdown("---")
                st.subheader("Disable / re-enable a code")
                col1, col2, col3 = st.columns([2, 1, 1])
                selected_code = col1.selectbox(
                    "Select code",
                    options=[r[1] for r in rows],
                    label_visibility="collapsed",
                )
                selected_row = next((r for r in rows if r[1] == selected_code), None)
                if selected_row:
                    code_id, _, _, _, _, _, is_active = selected_row[:7]
                    label = "Disable" if is_active else "Re-enable"
                    btn_type = "secondary" if is_active else "primary"
                    if col2.button(label, type=btn_type):
                        _toggle_active(db, code_id, not is_active)
                        st.success(f"Code **{selected_code}** {'disabled' if is_active else 're-enabled'}.")
                        st.rerun()

            st.markdown("---")

            # Usage log
            st.subheader("Redemption log")
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
                df_log = pd.DataFrame(log_rows, columns=[
                    "Code", "Artist", "Redeemed on", "Plan granted", "Access expires"
                ])
                df_log["Access expires"] = df_log["Access expires"].apply(lambda x: str(x) if x else "—")
                st.dataframe(df_log, hide_index=True, use_container_width=True)
            else:
                st.info("No redemptions yet.")

        # ── Tab: create ───────────────────────────────────────────────────
        with tab_create:
            with st.form("create_promo"):
                col1, col2 = st.columns(2)

                suggested = _generate_code()
                code_input = col1.text_input(
                    "Code *",
                    value=suggested,
                    help="Uppercase alphanumeric. Auto-suggested — change if you want something memorable.",
                ).strip().upper()

                plan_input = col2.selectbox(
                    "Plan granted *",
                    options=["basic", "premium"],
                    format_func=str.capitalize,
                )

                col3, col4 = st.columns(2)
                duration_input = col3.number_input(
                    "Duration (days) *",
                    min_value=1, max_value=365, value=30,
                    help="How long the plan stays active after the code is redeemed.",
                )
                max_uses_input = col4.number_input(
                    "Max uses *",
                    min_value=0, value=1,
                    help="0 = unlimited. 1 = single use (recommended for personal invites).",
                )

                expires_at_input = st.date_input(
                    "Code expiry date (optional)",
                    value=None,
                    help="Date after which the code can no longer be redeemed. Leave empty for no expiry.",
                )

                notes_input = st.text_input(
                    "Notes (optional)",
                    placeholder="e.g. Sent to Thomas for beta testing",
                )

                submitted = st.form_submit_button("Create code", type="primary")

            if submitted:
                if not code_input:
                    st.error("Code is required.")
                else:
                    existing = db.fetch_query(
                        "SELECT 1 FROM promo_codes WHERE code = %s", (code_input,)
                    )
                    if existing:
                        st.error(f"Code **{code_input}** already exists. Choose a different one.")
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
                            f"✅ Code **{code_input}** created — grants **{plan_input.capitalize()}** "
                            f"for **{int(duration_input)} days**."
                        )
                        st.rerun()

    finally:
        db.close()
