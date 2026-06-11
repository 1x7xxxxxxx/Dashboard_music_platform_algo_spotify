"""EN catalog for the process_guide view."""

EN = {
    "process_guide.title": "📋 Getting started guide",
    "process_guide.caption": "The 3 steps to set up your credentials, launch data "
                             "collection and link your Meta Ads campaigns to your Spotify tracks.",
    # Step 1
    "process_guide.s1_title": "1. Enter your API credentials",
    "process_guide.s1_i1": "Open the **🔑 API Credentials** page.",
    "process_guide.s1_i2": "For each platform (Spotify, YouTube, Meta Ads, SoundCloud, "
                           "Instagram), paste the requested keys/tokens in the matching tab.",
    "process_guide.s1_i3": "Spotify and YouTube may already be configured at the "
                           "application level (platform key) — in that case the status shows "
                           "\"Configured (platform key)\" and no input is needed.",
    "process_guide.s1_i4": "Click **Test connection** then **Save**. "
                           "Saving automatically triggers the first collection.",
    # Step 2
    "process_guide.s2_title": "2. Launch data collection",
    "process_guide.s2_i1": "In the sidebar, click **🚀 Launch ALL collections** "
                           "to trigger every DAG at once.",
    "process_guide.s2_i2": "You can also let the scheduled daily collections run on their own.",
    "process_guide.s2_i3": "Track collection status in **🔑 API Credentials** (last-run "
                           "badge per platform) or in **🏗️ ETL monitoring** (admin).",
    "process_guide.s2_i4": "For CSV sources (Spotify for Artists, Apple Music, iMusician), "
                           "import your files from **📂 CSV Import**.",
    # Step 3
    "process_guide.s3_title": "3. Map Meta Ads ↔ Spotify",
    "process_guide.s3_i1": "Open the **🔗 Meta × Spotify** page. **Automatic suggestions** "
                           "(campaign-name similarity + release-date proximity) appear **at the "
                           "top**, with a 🟢/🟡/🔴 reliability marker — tick **Associate** to "
                           "confirm the correct ones.",
    "process_guide.s3_i2": "Otherwise, manually link each **Meta Ads campaign** to the matching "
                           "**track** (the **Manual add** tab). This link is what reconciles ad "
                           "spend with streams (ROI, META × Spotify view).",
    "process_guide.s3_i3": "Tip: name your Meta Ads campaigns after the track title for better "
                           "automatic suggestions (e.g. campaign \"Track 1\").",
    "process_guide.s3_i4": "Once the mapping is saved, the **META × Spotify** and "
                           "**ROI Breakheaven** (Distributor) views populate automatically.",
    # PDF
    "process_guide.pdf_title": "🎵 streaMLytics — Getting started guide",
    "process_guide.pdf_intro": "How to enter your credentials, launch data collection and map "
                               "your Meta Ads campaigns to your Spotify tracks.",
    "process_guide.download_pdf": "⬇️ Download the guide (PDF)",
    "process_guide.download_html": "⬇️ Download the guide (HTML)",
    "process_guide.pdf_unavailable": "PDF generation unavailable (WeasyPrint missing) — "
                                     "HTML export offered instead.",
}
