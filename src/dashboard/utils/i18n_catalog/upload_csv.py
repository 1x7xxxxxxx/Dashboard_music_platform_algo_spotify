"""EN catalog for the upload_csv view."""

EN = {
    "upload_csv.auto_import": (
        "🚀 All {n} files are recognised — import started automatically."),
    "upload_csv.err_songs_all_zero": (
        "« Since start » export: Spotify returns listeners and saves as **zero** "
        "there, whatever the file is called. Export again with the period set to "
        "**12 months**."),
    "upload_csv.autostart_ok": (
        "🚀 Your setup is complete — collection just started on its own ({n} "
        "sources). Your first figures arrive within minutes."),
    "upload_csv.autostart_failed": (
        "⚠️ Automatic collection could not start. Launch it from the sidebar, or "
        "try again later."),
    # Header / intro (pre-existing keys)
    "upload_csv.uploader_label": "CSV / TSV / TXT / XLSX files",
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
    # `sacem_howto_header` / `_body` retirées le 2026-09-06 avec le doublon qu'elles
    # traduisaient : le mode d'emploi du relevé SACEM vit dans la vue 🎼 Royalties
    # SACEM (`sacem.howto_*`), là où on se trouve quand on en cherche un.
    # Detection table
    "upload_csv.detection_header": "🔍 Detection — {n} file(s)",
    "upload_csv.err_unknown_type": "Unrecognized type — check the filename and the file columns.",
    "upload_csv.err_unknown_cols": " Columns seen: {cols}",
    "upload_csv.err_no_valid_rows": "No valid rows detected after parsing.",
    "upload_csv.status_ready": "✅ Ready",
    "upload_csv.status_needs_answer": "❓ One detail is asked just below this table",
    "upload_csv.col_file": "File",
    "upload_csv.col_detected_type": "Detected type",
    "upload_csv.col_song": "Title used",
    "upload_csv.col_rows": "Rows",
    "upload_csv.col_status": "Status",
    # What the file does not say — we ask for it
    "upload_csv.asks_header": (
        "❓ {n} file(s) are valid but are missing a detail that Spotify only puts "
        "in the filename. Fill it in here — the file will import on its own."),
    "upload_csv.ask_song": "Track title",
    "upload_csv.ask_song_ph": "e.g. Kimono à semelle de fer",
    "upload_csv.ask_window": "Period covered by this export",
    "upload_csv.ask_window_ph": "— pick the period —",
    "upload_csv.window_12m": "12 months",
    "upload_csv.window_28d": "28 days",
    # Previews
    "upload_csv.err_no_valid_file": "No valid file to import.",
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
    "upload_csv.col_merged": "Merged",
    "upload_csv.status_ok": "✅ OK",
    "upload_csv.err_songs_all": "The « Since start » export cannot be used: Spotify returns listeners and saves as **zero** there. It is not the filename — renaming it changes nothing. Re-export with the period set to **12 months** (`…-songs-1year.csv`).",
}
