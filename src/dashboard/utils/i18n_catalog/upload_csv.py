"""EN catalog for the upload_csv view."""

EN = {
    # Header / intro (pre-existing keys)
    "upload_csv.title": "📂 CSV Import",
    "upload_csv.caption": (
        "Drop up to about ten CSV files at once. "
        "The type is detected automatically from the filename and the columns."
    ),
    "upload_csv.mapping_info": (
        "🔗 **Spotify × Meta Ads mapping** — after **running the collection "
        "from the home page**, remember to do the mapping "
        "(menu **📣 Meta Ads → Spotify × Meta Ads mapping (campaign name)**) "
        "to link your Meta campaigns to your Spotify tracks."
    ),
    "upload_csv.no_active_artist": "No active artist. Create one in the Admin tab.",
    "upload_csv.target_artist": "Target artist",
    "upload_csv.no_artist_id": "Unable to determine your artist identifier.",
    "upload_csv.uploader_label": "CSV / TSV / XLSX files",
    "upload_csv.uploader_help": (
        "Drag all your files at once. "
        "The type (S4A timeline, audience, songs-all, Apple, iMusician, "
        "DistroKid, SACEM statement .xlsx…) is detected automatically."
    ),
    # Platform labels
    "upload_csv.platform.s4a": "S4A — Per-title timeline",
    "upload_csv.platform.s4a_songs_global": "S4A — Tracks summary",
    "upload_csv.platform.s4a_audience": "S4A — Audience",
    "upload_csv.platform.apple": "Apple Music",
    "upload_csv.platform.imusician_summary": "iMusician — Per-release summary",
    "upload_csv.platform.imusician_sales": "iMusician — Sales report",
    "upload_csv.platform.distrokid_sales": "DistroKid — Bank details (TSV/CSV)",
    "upload_csv.platform.sacem": "SACEM — Account statement (xlsx)",
    "upload_csv.sacem_howto_header": "🎼 SACEM statement (.xlsx) — how to get it",
    "upload_csv.sacem_howto_body": "1. Log in to **sacem.fr** (member area).\n"
                                   "2. **Mes répartitions** → **Relevé de compte**.\n"
                                   "3. Set the **date filter to “since registration”**.\n"
                                   "4. **Download the `.xlsx`**, then drop it below "
                                   "(SACEM type auto-detected).",
    # Detection table
    "upload_csv.detection_header": "🔍 Detection — {n} file(s)",
    "upload_csv.err_unknown_type": "Unrecognized type — check the filename and the file columns.",
    "upload_csv.err_no_valid_rows": "No valid rows detected after parsing.",
    "upload_csv.status_ready": "✅ Ready",
    "upload_csv.col_file": "File",
    "upload_csv.col_detected_type": "Detected type",
    "upload_csv.col_rows": "Rows",
    "upload_csv.col_status": "Status",
    # Previews
    "upload_csv.err_no_valid_file": "No valid file to import.",
    "upload_csv.preview_label": "Preview — {filename} ({n} rows)",
    # FX rate
    "upload_csv.fx_label": "USD → EUR conversion rate (DistroKid)",
    "upload_csv.fx_help": (
        "DistroKid amounts are in USD; the monthly revenue "
        "shown in Distributor is converted to EUR using this rate. "
        "Default: DISTROKID_USD_EUR_RATE (.env) or 0.92."
    ),
    # Import button
    "upload_csv.import_button": "✅ Import {n} file(s)",
    "upload_csv.import_button_skip": "  (⚠️ {n} skipped)",
    # Non-blocking roll-up captions
    "upload_csv.ref_updated": "🎵 Release reference updated ({n} tracks).",
    "upload_csv.ref_failed": "⚠️ Release reference not updated: {err}",
    "upload_csv.monthly_aggregated": "💰 Monthly revenue aggregated ({n} months) — visible in Distributor.",
    "upload_csv.monthly_failed": "⚠️ Monthly revenue aggregation not performed: {err}",
    "upload_csv.dk_aggregated": (
        "💰 DistroKid revenue aggregated ({n} months, "
        "rate {rate:.4f}) — visible in Distributor."
    ),
    "upload_csv.dk_failed": "⚠️ DistroKid revenue aggregation not performed: {err}",
    # Results section
    "upload_csv.results_header": "📋 Import results",
    "upload_csv.metric_processed": "Files processed",
    "upload_csv.metric_inserted": "Rows inserted / updated",
    "upload_csv.metric_errors": "Files with errors",
    "upload_csv.metric_skipped": "Files skipped (unknown type)",
    "upload_csv.col_type": "Type",
    "upload_csv.col_table": "Table",
    "upload_csv.col_processed_rows": "Processed rows",
    "upload_csv.status_ok": "✅ OK",
}
