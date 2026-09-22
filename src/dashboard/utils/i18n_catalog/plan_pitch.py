"""EN strings for the single plan-pitch catalogue (`utils/plan_pitch.py`).

Les clés `pitch.*` sont des DONNÉES, pas des appels `t("…")` littéraux : elles
vivent dans le tuple `_PITCH`. Le balayage des orphelines ne les voit donc pas, et
c'est `test_the_plan_pitch_matches_the_gate.py` qui tient l'autre bout — il exige
une entrée ici pour chaque ligne d'argumentaire.
"""

EN = {
    # ── Free ────────────────────────────────────────────────────────────────
    "pitch.spotify": ("🎵 **Your Spotify streams**, track by track, with your "
                      "releases and listeners on the same chart"),
    "pitch.apple": "🎎 **Apple Music** — streams and Shazams",
    "pitch.youtube": "🎬 **YouTube** — channel and videos",
    "pitch.soundcloud": "☁️ **SoundCloud** — plays and engagement",
    "pitch.instagram": "📸 **Instagram** — followers and posts",
    "pitch.meta_overview": ("📱 **Your Meta Ads campaigns** — spend, cost per "
                            "result, campaign by campaign"),
    "pitch.hypeddit": "📱 **Hypeddit** — visits and clicks on your smart links",
    "pitch.imusician": ("💰 **What your streams earned you** — iMusician, "
                        "DistroKid, and the break-even point against your ads"),
    "pitch.sacem": "🎼 **Your SACEM royalties**",
    "pitch.mapping": ("🔗 **Link your tracks across platforms** — automatic "
                      "suggestions"),
    "pitch.export_csv": ("⬇️ **Your data stays yours** — full CSV export, on "
                         "both plans"),
    "pitch.credentials": ("🔑 **Connect your accounts** and import your CSV / "
                          "XLSX exports"),
    "pitch.saisie": ("📝 **Enter your playlist adds** — they feed the "
                     "predictions"),
    "pitch.wrapped": "🎁 **Your yearly Data Wrapped**",
    "pitch.referral": "🎁 **Referrals** — 1 free month per referred artist",
    # ── Premium ─────────────────────────────────────────────────────────────
    "pitch.trigger": ("🚀 **Know whether a track will trigger Discover Weekly** "
                      "— before spending on promo"),
    "pitch.money": ("💰 **Where your money goes, and when you break even** — "
                    "revenue, advertising and release costs on a single chart, "
                    "with the break-even date"),
    "pitch.meta_x": ("🔀 **Which ad euro produced which streams** — Meta × "
                     "Spotify × Hypeddit, and the cost of a stream country by "
                     "country"),
    "pitch.cpr": ("💶 **How much to put back on which campaign** — raise, hold "
                  "or cut, based on cost per result and your audience's age"),
    "pitch.creatives": ("🎨 **Which creative and which hook cost the least** per "
                        "result"),
    "pitch.breakdowns": "🌍 **Who saw your ads** — country, age, placement",
    "pitch.pdf": ("📄 **Your filterable PDF report** — on demand, and e-mailed "
                  "every week"),
    # ── Hors page ───────────────────────────────────────────────────────────
    "pitch.one_artist": "1 artist",
    "pitch.ten_artists": "Up to 10 artists on the same account",
    "pitch.support": "Priority support",
}
