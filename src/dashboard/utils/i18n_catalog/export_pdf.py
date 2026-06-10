"""EN catalog for the export_pdf view."""

EN = {
    "export_pdf.title": "📄 PDF Export — Artist Report",
    "export_pdf.caption": (
        "Configure the report, pick the sections and songs to include, "
        "then generate the downloadable PDF."
    ),
    # Artist + period
    "export_pdf.artist_header": "**👤 Artist**",
    "export_pdf.no_active_artist": "No active artist in the database.",
    "export_pdf.period_header": "**📅 Period**",
    "export_pdf.period_caption": (
        "Ad & revenue sections (Meta, Hypeddit, ROI…) are always computed "
        "**since the beginning**; the period above only filters streaming "
        "(S4A, YouTube, etc.). “Since the track's release” uses the release "
        "date of the selected song (the earliest if several)."),
    "export_pdf.dates_header": "**📅 Dates**",
    "export_pdf.date_from": "From",
    "export_pdf.date_to": "To",
    # Sections
    "export_pdf.sections_header": "**📑 Sections to include**",
    "export_pdf.premium_locked_caption": (
        "🔒 **Premium** sections (ML, forecasts, advanced Meta) require the "
        "Premium plan — locked below."),
    "export_pdf.premium_section_help": (
        "Premium section — upgrade to the Premium plan to include it."),
    # S4A song selector
    "export_pdf.s4a_songs_header": "**🎵 S4A — Songs to include** (leave empty = all)",
    "export_pdf.s4a_songs_label": "S4A songs",
    "export_pdf.s4a_songs_placeholder": "All songs (default top 15)…",
    "export_pdf.all_songs": "All",
    "export_pdf.no_s4a_data": "No S4A data available for this artist.",
    # ML song selector
    "export_pdf.ml_songs_header": "**🔬 ML Focus — Songs to include**",
    "export_pdf.ml_songs_label": "ML songs",
    "export_pdf.ml_songs_placeholder": "Choose one or more songs…",
    "export_pdf.ml_songs_warning": (
        "Select at least one song to enable the ML Focus section."),
    # Period resolution / summary
    "export_pdf.no_release_date": (
        "No known release date for the selection — the report will cover the "
        "full history. Select a song that has a release date."),
    "export_pdf.report_summary": (
        "Report for **{name}** · Period: {period} · Sections: {sections}"),
    "export_pdf.no_sections": "⚠️ none",
    "export_pdf.check_one_section": (
        "Check at least one section to generate the report."),
    # Generation + download
    "export_pdf.generate_btn": "📄 Generate PDF report",
    "export_pdf.spinner": "Generating the PDF…",
    "export_pdf.gen_error": "Error during generation: {err}",
    "export_pdf.ready": "✅ Report ready. Download started — otherwise, use the button below.",
    "export_pdf.download_btn": "⬇️ Download the report",
    # Period option labels (format_func)
    "export_pdf.period.last_28d": "Last 28 days",
    "export_pdf.period.last_3m": "Last 3 months",
    "export_pdf.period.last_6m": "Last 6 months",
    "export_pdf.period.last_12m": "Last 12 months",
    "export_pdf.period.this_year": "This year",
    "export_pdf.period.all_time": "Since the beginning",
    "export_pdf.period.since_release": "Since the track's release",
    "export_pdf.period.custom": "Custom",
    # Section display labels (ALL_SECTIONS)
    "export_pdf.section.overview": "🏠 Overview",
    "export_pdf.section.data_setup": "📁 Connections & mapping",
    "export_pdf.section.freshness": "📡 Source freshness",
    "export_pdf.section.streams": "🎵 S4A — trend",
    "export_pdf.section.s4a_songs": "🎵 S4A — songs",
    "export_pdf.section.meta_x_spotify": "🔗 Meta × Spotify",
    "export_pdf.section.apple": "🍎 Apple Music",
    "export_pdf.section.youtube": "🎬 YouTube",
    "export_pdf.section.soundcloud_detail": "☁️ SoundCloud",
    "export_pdf.section.instagram": "📸 Instagram",
    "export_pdf.section.hypeddit": "📣 Hypeddit",
    "export_pdf.section.songs": "🔮 Algo prediction",
    "export_pdf.section.ml_explain": "🔬 Explainability (SHAP)",
    "export_pdf.section.meta": "📱 Meta Ads",
    "export_pdf.section.meta_breakdowns": "🌍 Meta — Breakdowns",
    "export_pdf.section.roi": "💹 ROI Breakeven",
    "export_pdf.section.revenue_forecast": "📈 Revenue forecasts",
}
