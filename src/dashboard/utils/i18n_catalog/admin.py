"""EN catalog for the admin view."""

EN = {
    # Guard / title / tabs
    "admin.access_denied": "⛔ Administrator access only.",
    "admin.title": "⚙️ Administration",
    "admin.tab_supervision": "📊 Supervision",
    "admin.tab_artists": "👥 Artists",
    "admin.tab_users": "👤 Users",
    "admin.tab_upload": "📂 CSV Upload",
    "admin.tab_gdpr": "🗑️ GDPR Erasure",
    "admin.tab_tokens": "🔑 Tokens",
    # Token management
    "admin.tokens_header": "🔑 Tokens & refresh — reference",
    "admin.tokens_caption": (
        "Steady state: **no recurring action** for the artist or the admin — "
        "every token is either non-expiring or auto-renewed. The only possible "
        "admin gesture is repair after a manual revocation/rotation on the "
        "platform side."
    ),
    "admin.tokens_info": (
        "Rotation persistence: `update_platform_secret` (Fernet) — requires "
        "`FERNET_KEY` in the Airflow container. Shared apps (SoundCloud/Meta): "
        "`SOUNDCLOUD_CLIENT_ID/SECRET`, `META_ACCESS_TOKEN/APP_ID/APP_SECRET` in `.env`."
    ),
    # Supervision — business
    "admin.business_header": "📊 Business — signups & subscriptions",
    "admin.metric_signups_7d": "Signups 7 d",
    "admin.metric_signups_30d": "Signups 30 d",
    "admin.metric_verified": "Verified accounts",
    "admin.metric_active_artists": "Active artists",
    "admin.metric_mrr": "MRR (active subscriptions)",
    "admin.metric_paying": "Paying subscribers",
    "admin.metric_arpu": "ARPU",
    "admin.no_paid_subs": "No active paid subscription (all on Free / welcome trial).",
    # Supervision — operating costs & margin
    "admin.costs_header": "💸 Operating costs & margin",
    "admin.costs_intro": ("Platform costs (domain, VPS, Claude Code, Stripe fees…) — global, "
                          "not per-artist. A recurring cost auto-repeats every month "
                          "(yearly amortised /12) until deactivated."),
    "admin.costs_add": "➕ Add a cost",
    "admin.costs_category": "Category",
    "admin.costs_amount": "Amount (€)",
    "admin.costs_period": "Billing",
    "admin.costs_start": "Start month",
    "admin.costs_ongoing": "Always active",
    "admin.costs_end": "End month",
    "admin.costs_label": "Label (e.g. Hetzner CX22)",
    "admin.costs_save": "💾 Save",
    "admin.costs_need_amount": "Amount required (> 0).",
    "admin.costs_added": "Cost added.",
    "admin.costs_empty": "No cost recorded yet.",
    "admin.costs_metric_month": "Cost this month",
    "admin.costs_metric_mrr": "MRR",
    "admin.costs_metric_margin": "Net margin / month",
    "admin.costs_chart_title": "Monthly costs by category",
    "admin.costs_stop_select": "Deactivate a cost (ID)",
    "admin.costs_stop": "Deactivate",
    # Supervision — technical
    "admin.tech_header": "🩺 Technical — per-platform data freshness",
    "admin.tech_legend": (
        "🟢 ≤ 2 d · 🟠 ≤ 7 d · 🔴 > 7 d · ❓ table missing/unreadable. "
        "Details: pages **Airflow KPI**, **ETL Logs**, **DB Health**."
    ),
    # Artists tab
    "admin.artists_header": "📋 Registered artists",
    "admin.no_artists": "No artist in database.",
    "admin.load_artists_error": "Error loading artists: {err}",
    "admin.create_artist_expander": "➕ Create a new artist",
    "admin.field_name": "Name",
    "admin.field_name_required": "Name *",
    "admin.field_slug_required": "Slug * (unique, lowercase)",
    "admin.field_tier": "Tier",
    "admin.btn_create": "Create",
    "admin.name_slug_required": "Name and slug are required.",
    "admin.artist_created": "✅ Artist “{name}” created.",
    "admin.generic_error": "Error: {err}",
    "admin.edit_artist_expander": "✏️ Edit an artist",
    "admin.field_artist": "Artist",
    "admin.field_active": "Active",
    "admin.btn_save": "Save",
    "admin.artist_updated": "✅ Artist updated.",
    # Users tab
    "admin.users_header": "👤 User accounts",
    "admin.no_users": "No user in database.",
    "admin.load_users_error": "Error loading users: {err}",
    "admin.field_select_user": "Select a user",
    "admin.btn_revoke": "🔴 Revoke access",
    "admin.access_revoked": "Access revoked for {user}.",
    "admin.btn_restore": "✅ Restore access",
    "admin.access_restored": "Access restored for {user}.",
    "admin.btn_resend_verif": "📧 Resend verification",
    "admin.verif_sent": "Verification email resent to {email}.",
    "admin.verif_not_sent": "Email not sent — check SMTP config in config/config.yaml.",
    "admin.btn_delete_account": "🗑️ Delete account",
    "admin.confirm_delete_user": (
        "⚠️ Delete **{user}**? "
        "This action is irreversible. The linked artist is preserved."
    ),
    "admin.btn_confirm_delete": "Confirm deletion",
    "admin.account_deleted": "Account deleted.",
    "admin.btn_cancel": "Cancel",
    # Marketing list
    "admin.marketing_header": "📧 Marketing email list (opt-in)",
    "admin.metric_optin": "Opt-in contacts",
    "admin.btn_export_csv": "⬇️ Export CSV",
    "admin.no_optin": "No user has consented to marketing communications yet.",
    # Upload tab
    "admin.upload_header": "📂 Import a CSV for an artist",
    "admin.upload_caption": "Supported formats: Spotify for Artists (timeline), Apple Music (performance)",
    "admin.no_active_artist": "No active artist. Create one in the Artists tab.",
    "admin.field_target_artist": "Target artist",
    "admin.field_platform": "Platform",
    "admin.field_csv_file": "CSV file",
    "admin.field_csv_help": "Drop the CSV exported from the platform.",
    "admin.btn_import": "⬆️ Import",
    "admin.import_success": "✅ {n} row(s) imported for artist #{artist_id}.",
    "admin.import_error": "❌ Import error: {err}",
    # GDPR tab
    "admin.gdpr_header": "🗑️ GDPR Erasure — Art. 17 (right to be forgotten)",
    "admin.gdpr_warning": (
        "⚠️ This action **permanently deletes** all of an artist's data: "
        "user account, credentials, analytics history, subscription. "
        "No restoration is possible. An audit log is kept."
    ),
    "admin.db_unreachable": "❌ Database unreachable.",
    "admin.field_artist_to_erase": "Artist to erase",
    "admin.field_reason": "Reason (required)",
    "admin.field_reason_placeholder": "e.g. user request from 2026-03-28",
    "admin.btn_run_erasure": "🗑️ Run erasure",
    "admin.reason_required": "The reason is required before running the erasure.",
    "admin.gdpr_final_confirm": (
        "⛔ FINAL CONFIRMATION — Erase **{label}**? "
        "All data will be permanently deleted."
    ),
    "admin.btn_confirm_erasure": "✅ Confirm permanent erasure",
    "admin.erasure_done": (
        "✅ Erasure complete — {total} rows deleted across "
        "{tables} tables. Audit log recorded."
    ),
    "admin.erasure_detail": "Detail per table",
    "admin.erasure_error": "Error during erasure: {err}",
    "admin.gdpr_history_header": "📋 Erasure history",
}
