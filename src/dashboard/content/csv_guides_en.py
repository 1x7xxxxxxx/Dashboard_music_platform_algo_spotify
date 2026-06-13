"""EN translation of the CSV onboarding guides (mirror of csv_guides.CSV_GUIDES).

Type: Sub
Depends on: csv_guides (dataclasses + screenshot resolver reused as-is)

Same structure/screenshots as the FR source — only the prose is translated. The
guide PDF renderer selects this module when lang == 'en'. Screenshots are shared
(they show the platform UI, which may be in French for FR accounts).
"""
from src.dashboard.content.csv_guides import GuideStep, ExpectedCsv, PlatformGuide

_S4A = PlatformGuide(
    key="s4a",
    title="Spotify for Artists",
    icon="🎵",
    intro=(
        "3 file types to export, **all with the « 12 months » filter**. "
        "For N tracks you get **N + 2 files** (N timelines + 1 summary + "
        "1 audience). Example: 11 tracks → 13 files."
    ),
    steps=(
        GuideStep(
            "Sign in at artists.spotify.com and open the **Music** tab "
            "(disc icon, left sidebar).",
            "s4a_music_pannel.png", "Sidebar → Music tab",
        ),
        GuideStep(
            "Click the **Songs** sub-tab.",
            "s4a_music_titre_pannel.png", "Music → Songs",
        ),
        GuideStep(
            "Open **Filters** and set the period to **12 months**.",
            "s4a_music_titre_12monthFilter.png", "Period filter → 12 months",
        ),
        GuideStep(
            "Click the **download** icon (↓) left of the filter: you get the "
            "`…-songs-1year.csv` summary (listeners, streams, saves, release "
            "date per song).",
            "s4a_music_titre_filter12month_DOWNLOAD_csv.png", "Download the songs summary",
        ),
        GuideStep(
            "For per-track timelines: in the list, **open a song** (click its row).",
            "s4a_music_select1Track.png", "Song list → open a song",
        ),
        GuideStep(
            "On the song page, set the filter to **12 months** then click "
            "**download** (↓): `<song>-timeline.csv` (daily streams). "
            "Repeat for **each** song.",
            "s4a_music_titreselect_12month_Download.png", "Song page → 12 months → download",
        ),
        GuideStep(
            "Open the **Audience** tab (audience icon, left sidebar).",
            "s4a_public.png", "Sidebar → Audience tab",
        ),
        GuideStep(
            "On **Overview**, **12 months** filter, click **download** (↓): "
            "`…-audience-timeline.csv` (artist-level listeners/streams/followers).",
            "s4a_public_12monthfilter_download.png", "Audience → Overview → download",
        ),
        GuideStep(
            "⚠️ Do **not** use the « All time » filter for the summary: Spotify "
            "returns 0 listeners and saves there. The `…-songs-all.csv` file is "
            "also rejected on import.",
        ),
    ),
    expected=(
        ExpectedCsv("Per-track timeline", "<song>-timeline.csv", ("date", "streams")),
        ExpectedCsv("Songs summary (12 months)", "…-songs-1year.csv",
                    ("song", "listeners", "streams", "saves", "release_date")),
        ExpectedCsv("Audience", "…-audience-timeline.csv",
                    ("date", "listeners", "streams", "followers", "playlist adds", "saves")),
    ),
)

_APPLE = PlatformGuide(
    key="apple",
    title="Apple Music for Artists",
    icon="🎎",
    intro=(
        "Apple Music for Artists has no API: the per-song performance CSV export "
        "is the only source (**a single file**). Make sure to set the period to "
        "**All Time** for a complete history. FR and EN headers are both recognized."
    ),
    steps=(
        GuideStep(
            "Sign in at artists.apple.com, pick your artist, then on the "
            "**Overview** tab set the period selector (top right) to **All Time**.",
            "apple_music_aperçu_filtre_depuisledébut.png",
            "Overview → period → All Time",
        ),
        GuideStep(
            "Click the **Music** tab.",
            "apple_music_ongletmusique.png", "Music tab",
        ),
        GuideStep(
            "In the **Songs** section, click **See All** (top right).",
            "apple_music_tout_afficher_button.png", "Songs → See All",
        ),
        GuideStep(
            "Click the **download** icon (↓, top right): you get "
            "`songs_….csv` (Song, Plays, Avg. Listeners, Shazams, Radio Spins, Purchases).",
            "apple_music_tout_télécharger.png", "Download the CSV",
        ),
    ),
    expected=(
        ExpectedCsv("Per-song performance", "songs_….csv",
                    ("Morceau / Song Title", "Écoutes / Plays", "Auditeurs / Listeners (opt.)")),
    ),
)

_IMUSICIAN = PlatformGuide(
    key="imusician",
    title="iMusician (distributor)",
    icon="💰",
    intro=(
        "Two report types, requested **per year** (iterate over every year of "
        "your catalogue): the **release summary** (monthly totals per release) "
        "and the **sales report** (detail per ISRC/shop/country). The importer "
        "auto-detects each type."
    ),
    steps=(
        GuideStep(
            "**Revenue** tab (sidebar) → **Reports** → click **Download report** (top right).",
            "imusician_dl_rapport.png", "Revenue → Reports → Download report",
        ),
        GuideStep(
            "Period **Year**, select a **year**, type **Release summary**, then "
            "**Request report**. Repeat for **each year**.",
            "imusician_annuel_résumé_par_sortie.png",
            "Year → year → Release summary → Request",
        ),
        GuideStep(
            "Do it again choosing **Sales report** (for each year as well).",
            "imusician_annuel_rapportdevente.png",
            "Year → year → Sales report → Request",
        ),
        GuideStep(
            "**Account** tab → **Downloads**: download (↓) **all** the generated "
            "yearly reports (summaries + sales).",
            "imusician_compte_téléchargements_download.png",
            "Account → Downloads → download all",
        ),
    ),
    expected=(
        ExpectedCsv("Release summary", "*.csv",
                    ("Statement date", "Release title", "Track streams", "Total revenue")),
        ExpectedCsv("Sales report", "*.csv",
                    ("Sales date", "ISRC", "Shop", "Revenue EUR")),
    ),
)

_DISTROKID = PlatformGuide(
    key="distrokid",
    title="DistroKid (distributor)",
    icon="🏦",
    intro=(
        "A single export covers your whole history: the detailed **Bank** report "
        "(one row per platform × title × country × month, amounts in **USD** — "
        "the USD→EUR conversion rate is set at import time). Format `.tsv` or "
        "`.csv`, both are auto-detected."
    ),
    steps=(
        GuideStep(
            "Sign in at distrokid.com → **Bank** menu — that's your earnings page."
        ),
        GuideStep(
            "At the bottom of the page, click **« SEE EXCRUCIATING DETAIL »** — "
            "the full row-by-row breakdown."
        ),
        GuideStep(
            "Click **Download** to get the file. Above 50,000 rows, DistroKid asks "
            "you to filter (period / platform / release) before generating the "
            "export — repeat as needed."
        ),
        GuideStep(
            "Import the file here as-is (.tsv or .csv) and adjust the suggested "
            "**USD→EUR rate** before confirming."
        ),
    ),
    expected=(
        ExpectedCsv("Bank details (earnings breakdown)", "*.tsv / *.csv",
                    ("Sale Month", "Store", "Title", "ISRC", "Quantity",
                     "Earnings (USD)")),
    ),
)

CSV_GUIDES_EN: tuple[PlatformGuide, ...] = (_S4A, _APPLE, _IMUSICIAN, _DISTROKID)
