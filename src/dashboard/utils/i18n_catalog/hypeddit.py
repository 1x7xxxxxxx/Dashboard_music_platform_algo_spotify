"""EN strings for the Hypeddit view."""

EN = {
    "hypeddit.db_unreachable": "❌ Database unreachable.",
    "hypeddit.invalid_session": "❌ Invalid session.",
    "hypeddit.save_success": "✅ Data saved successfully",
    "hypeddit.save_error": "❌ Error: {err}",
    "hypeddit.global_stats": "📊 Global statistics",
    "hypeddit.no_data_period": "📭 No data found for the selected period.",
    "hypeddit.chart_title": "My Hypeddit campaigns ({label})",
    "hypeddit.cmp_title": "Volumes compared, campaign by campaign",
    "hypeddit.cmp_visits": "Visits",
    "hypeddit.cmp_clicks": "Clicks",
    "hypeddit.cmp_meta": "Meta ads ±14 d (€)",
    "hypeddit.history_header": "📋 History",
    "hypeddit.campaign_filter": "🎯 Campaigns compared",
    "hypeddit.campaign_filter_help": "By default, the two most recent campaigns — your two "
                                     "latest releases.",
    "hypeddit.no_campaign": "Pick at least one campaign to compare.",
    "hypeddit.label_campaigns": "{n} campaign(s)",
    "hypeddit.fetch_header": "📥 Get your numbers from Hypeddit",
    "hypeddit.fetch_steps": ("1. Open **hypeddit.com** and log in.\n"
                             "2. In your dashboard, open your release's campaign.\n"
                             "3. Open its stats and set them to the day you are entering.\n"
                             "4. Enter the campaign, the date, the **visits** and the "
                             "**clicks** here, then **Save**."),
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
    "hypeddit.conv_caption": "**{n} campaign(s)** compared. The **conversion "
                             "rate** is what judges a smart link: its whole purpose is "
                             "to turn a visit into a click through to a platform. Here it "
                             "runs from **{mini:.0f} %** to **{maxi:.0f} %** — **{best}** "
                             "converts best. A visit that does not click is budget spent "
                             "for nothing.\n\n"
                             "⚠️ {solo} campaign(s) carry only **one reading**: their ring "
                             "is a campaign TOTAL, not a day. {zero}",
    "hypeddit.zero_campaigns": "{k} campaign(s) have nothing but zero readings: their "
                               "conversion is incomputable, not null.",
    "hypeddit.both_zero": "Nothing to save: visits and clicks are both **0**. A zero day "
                          "is written to the database as a measurement and drags the "
                          "averages down — while what it means is « I did not read ». "
                          "Enter at least one value, or leave the day out.",
    "hypeddit.ring_clicked": "Clicked through",
    "hypeddit.ring_left": "Left",
    "hypeddit.rings_capped": "Rings: the {k} most recent campaigns; {h} older one(s) stay in the detail.",
    "hypeddit.ring_visits": "visits",
    "hypeddit.ring_clicks": "clicks",
    "hypeddit.ring_meta": "Meta ads ±14 d: {eur} €",
}
