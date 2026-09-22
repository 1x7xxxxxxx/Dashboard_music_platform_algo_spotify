"""EN strings for the Hypeddit view."""

EN = {
    "hypeddit.db_unreachable": "❌ Database unreachable.",
    "hypeddit.invalid_session": "❌ Invalid session.",
    "hypeddit.save_success": "✅ Data saved successfully",
    "hypeddit.save_error": "❌ Error: {err}",
    "hypeddit.global_stats": "📊 Global statistics",
    "hypeddit.no_data_period": "📭 No data found for the selected period.",
    "hypeddit.visits": "Visits",
    "hypeddit.chart_title": "My Hypeddit campaigns ({label})",
    "hypeddit.volume_axis": "Volume",
    "hypeddit.history_header": "📋 History",
    "hypeddit.session_invalid": "Invalid session.",
    "hypeddit.empty_history": "History empty.",
    "hypeddit.entry_header": "📝 Enter data",
    "hypeddit.type_existing": "Existing",
    "hypeddit.type_new": "New",
    "hypeddit.type_label": "Type",
    "hypeddit.campaign": "🎯 Campaign",
    "hypeddit.campaign_name": "🎯 Campaign name",
    "hypeddit.date": "📅 Date",
    "hypeddit.visits_input": "👁️ Visits",
    "hypeddit.clicks_input": "🖱️ Clicks",
    "hypeddit.save_btn": "💾 Save",
    "hypeddit.reset_btn": "🔄 Reset",
    "hypeddit.campaign_name_required": "Campaign name required",
    # Les campagnes nommées + le taux de conversion (2026-09-21).
    "hypeddit.panel_volume": "Visits and clicks, per campaign",
    "hypeddit.panel_conv": "Conversion rate — clicks ÷ visits",
    "hypeddit.clicks": "Clicks",
    "hypeddit.conversion": "Conversion",
    "hypeddit.conv_axis": "%",
    "hypeddit.conv_caption": "**{n} campaign(s)** over the period. The **conversion "
                             "rate** is what judges a smart link: its whole purpose is "
                             "to turn a visit into a click through to a platform. Here it "
                             "runs from **{mini:.0f} %** to **{maxi:.0f} %** — **{best}** "
                             "converts best. A visit that does not click is budget spent "
                             "for nothing.\n\n"
                             "⚠️ {solo} campaign(s) carry only **one reading**: their bar "
                             "is a campaign TOTAL, not a day. {zero}",
    "hypeddit.zero_campaigns": "{k} campaign(s) have nothing but zero readings over this "
                               "period: their conversion is incomputable, not null.",
    "hypeddit.both_zero": "Nothing to save: visits and clicks are both **0**. A zero day "
                          "is written to the database as a measurement and drags the "
                          "averages down — while what it means is « I did not read ». "
                          "Enter at least one value, or leave the day out.",
}
