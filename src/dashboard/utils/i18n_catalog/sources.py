"""EN catalog for the data sources — what each one brings, and how to connect it.

Namespace `src.<source>.{valeur,geste}`, declared next to `SOURCES_CONFIG`
(`src/dashboard/utils/kpi_helpers.py`).

⚠️ **No plumbing vocabulary here, in either language.** The raw reasons live in
`etl_run_log.error_message` and read like `no SoundCloud user_id and no claimed
track`. Copying them onto an artist's screen is the defect this repo measured on
2026-09-XX, when 14 artist-facing messages named a DAG and six told the reader to
launch `ml_scoring_daily`, which nobody can launch. Yifrah, *Microcopy* p.138 says
it in one line: never write about the system to your users.

Each `geste` is therefore an instruction a human can follow without knowing that a
column, a table or a scheduler exists.
"""

EN = {
    # ── Ce que chaque source apporte ────────────────────────────────────────
    "src.spotify_api.valeur": "your Spotify followers and how popular your tracks are",
    "src.s4a.valeur": (
        "your streams day by day, track by track — the foundation every prediction "
        "is built on"),
    "src.youtube.valeur": "your channel's views and subscribers",
    "src.soundcloud.valeur": "your plays, likes and reposts, every day",
    "src.instagram.valeur": "your followers and how far your posts reach",
    "src.apple.valeur": (
        "your Apple Music plays — and your Shazams, which only arrive this way"),
    "src.meta.valeur": (
        "what each bought stream costs you, and what actually works in your ads"),
    "src.imusician.valeur": "what your music earns you, month by month",
    "src.hypeddit.valeur": "the click-through rate of your release pages",
    "src.sacem.valeur": "your royalties, gross and net of contributions",

    # ── Le geste, en une phrase qu'un humain peut suivre ────────────────────
    "src.spotify_api.geste": "Paste the link to your Spotify profile",
    "src.s4a.geste": "Drop your Spotify for Artists export",
    "src.youtube.geste": "Paste the link to your YouTube channel",
    "src.soundcloud.geste": "Paste the link to your SoundCloud profile",
    "src.instagram.geste": "Connect your Instagram professional account",
    "src.apple.geste": "Drop your Apple Music for Artists export",
    "src.meta.geste": "Connect your Meta ad account",
    "src.imusician.geste": "Enter or drop your distributor statement",
    "src.hypeddit.geste": "Enter the numbers from your latest Hypeddit campaign",
    "src.sacem.geste": "Drop your SACEM account statement",

    # ── Le rendu d'absence (`utils/absence_cta.py`) ────────────────────────
    "absence.manque": "you are missing {valeur}",
    "absence.cta": "Take me there \u2192",
    "absence.cta_verrouille": "\U0001F512 Included in Premium",
    "absence.reste": "And {n} more source(s) to connect",

    # ── La note de plan (`utils/plan_gate.py`) ─────────────────────────────
    "plan_gate.ferme": "Included in Premium",
    "plan_gate.ouvert": "Included in your plan",
}
