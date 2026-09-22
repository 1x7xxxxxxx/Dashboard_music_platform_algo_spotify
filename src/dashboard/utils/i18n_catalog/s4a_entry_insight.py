"""EN strings for the S4A entry-insight panel (freshness, coverage, the model's bet)."""

EN = {
    # ── Fraîcheur ────────────────────────────────────────────────────────────
    "s4a_insight.fresh_header": "🕐 How fresh are your entries?",
    "s4a_insight.stale": (
        "**{n} block(s) no longer describe today.** The model still reads them as if "
        "they were current: a value entered once keeps feeding this month's prediction."),
    "s4a_insight.col_block": "Block",
    "s4a_insight.col_last": "Last entry",
    "s4a_insight.col_age": "Age",
    "s4a_insight.col_rows": "Rows",
    "s4a_insight.fresh_legend": (
        "🟢 under {t} d · 🟠 under {p} d · 🔴 {p} d or more · ⬜ never entered · "
        "❓ table unreadable"),
    # ── Complétude ───────────────────────────────────────────────────────────
    "s4a_insight.complete_header": "🧩 Tracks covered by your entries",
    "s4a_insight.no_tracks": "No track to cover.",
    "s4a_insight.col_track": "Track",
    "s4a_insight.fam_adds": "Playlist adds",
    "s4a_insight.fam_nonalgo": "Non-algo streams",
    "s4a_insight.fam_outcomes": "Recorded outcomes",
    "s4a_insight.missing_outcomes": (
        "**{n} of {tot} track(s)** have no recorded outcome. Those are the ones the "
        "model is missing — a track with no outcome teaches it nothing, either way."),
    # ── Le pari du modèle ────────────────────────────────────────────────────
    "s4a_insight.bet_header": "🎲 What the model bet, and what happened",
    "s4a_insight.bet_unreadable": (
        "Comparison unavailable: the predictions table could not be read. That is not "
        "the same as « no prediction »."),
    "s4a_insight.bet_none": (
        "No track has BOTH a prediction and a recorded outcome. Fill in the recorded "
        "outcomes (previous tab) so the comparison can exist."),
    "s4a_insight.panel_pred": "Predicted probability",
    "s4a_insight.panel_real": "Algorithmic streams recorded (28 d)",
    "s4a_insight.bet_note": (
        "**{d} of {n} track(s)** actually triggered an algorithm. The model expected "
        "**{a:.1f}** across this selection (sum of probabilities). That gap is NOT an "
        "error rate: on a population of {n}, the gap expected from chance alone is of "
        "the same order. The figure shows the bet; it does not judge it."),
    # ── Historique ───────────────────────────────────────────────────────────
    "s4a_insight.hist_header": "📈 Playlist adds over time",
    "s4a_insight.hist_unreadable": "History unreadable — that is not « no history ».",
    "s4a_insight.hist_none": "No playlist-add entry yet.",
    "s4a_insight.hist_single": (
        "Only one entry so far ({d}) — two are needed to draw a trend. That entry's "
        "values are in the **Signals** tab."),
    "s4a_insight.hist_axis": "Adds (all tracks)",
    "s4a_insight.hist_note": (
        "Sum across all tracks, by entry date. The three windows OVERLAP — 28 days "
        "CONTAINS 7 days: they do not add up."),
}
