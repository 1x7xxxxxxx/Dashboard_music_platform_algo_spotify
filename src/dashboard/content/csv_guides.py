"""Single source of truth for the CSV download+import guides (S4A / Apple / iMusician).

Type: Sub
Uses: src.utils.config_loader (asset path resolution)
Depends on: nothing at import time (pure data)
Persists in: nothing

The same content feeds TWO renderers — the Streamlit Import-CSV view
(`csv_guides_st.render_csv_guides`) and the static onboarding PDF
(`src.dashboard.guides.guide_pdf`). Edit the prose ONCE here; both update.
Screenshots are referenced by filename only and resolved under
`assets/csv_guides/`; a missing file degrades gracefully in both renderers.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuideStep:
    """One numbered step; `screenshot` is a filename under assets/csv_guides/."""
    text: str
    screenshot: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class ExpectedCsv:
    """A CSV the platform produces and that the importer auto-detects."""
    label: str
    filename_hint: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class PlatformGuide:
    key: str
    title: str
    icon: str
    intro: str
    steps: tuple[GuideStep, ...]
    expected: tuple[ExpectedCsv, ...]


def assets_dir() -> Path:
    """Absolute path to the bundled screenshot directory (assets/csv_guides/)."""
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "assets" / "csv_guides"


def screenshot_path(filename: str) -> Path:
    """Resolve a screenshot by filename anywhere under assets/csv_guides/.

    Supports both a flat layout and per-platform subfolders (s4a/, apple_music/,
    imusician/). Falls back to the flat path (non-existent → graceful placeholder).
    """
    base = assets_dir()
    flat = base / filename
    if flat.exists():
        return flat
    return next(base.rglob(filename), flat)


# ─────────────────────────────────────────────────────────────────────────────
# Content — edit here only.
# ─────────────────────────────────────────────────────────────────────────────

_S4A = PlatformGuide(
    key="s4a",
    title="Spotify for Artists",
    icon="🎵",
    intro=(
        "3 types de fichiers à exporter, **tous avec le filtre « 12 mois »**. "
        "Pour N titres, vous obtenez **N + 2 fichiers** (N timelines + 1 résumé + "
        "1 audience). Exemple : 11 titres → 13 fichiers."
    ),
    steps=(
        GuideStep(
            "Connectez-vous sur artists.spotify.com et ouvrez l'onglet **Musique** "
            "(icône disque, barre latérale gauche).",
            "s4a_music_pannel.png", "Barre latérale → onglet Musique",
        ),
        GuideStep(
            "Cliquez sur le sous-onglet **Titres**.",
            "s4a_music_titre_pannel.png", "Musique → Titres",
        ),
        GuideStep(
            "Ouvrez **Filtres** et réglez la période sur **12 mois**.",
            "s4a_music_titre_12monthFilter.png", "Filtre Période → 12 mois",
        ),
        GuideStep(
            "Cliquez sur l'icône de **téléchargement** (↓) à gauche du filtre : vous "
            "obtenez le résumé `…-songs-1year.csv` (auditeurs, streams, sauvegardes, "
            "date de sortie par titre).",
            "s4a_music_titre_filter12month_DOWNLOAD_csv.png", "Télécharger le résumé titres",
        ),
        GuideStep(
            "Pour les timelines par titre : dans la liste, **ouvrez un titre** "
            "(clic sur la ligne du morceau).",
            "s4a_music_select1Track.png", "Liste des titres → ouvrir un titre",
        ),
        GuideStep(
            "Sur la page du titre, réglez le filtre sur **12 mois** puis cliquez sur "
            "**téléchargement** (↓) : `<titre>-timeline.csv` (streams quotidiens). "
            "Répétez pour **chaque** titre.",
            "s4a_music_titreselect_12month_Download.png", "Page d'un titre → 12 mois → télécharger",
        ),
        GuideStep(
            "Ouvrez l'onglet **Public** (icône audience, barre latérale gauche).",
            "s4a_public.png", "Barre latérale → onglet Public",
        ),
        GuideStep(
            "Sur **Vue d'ensemble**, filtre **12 mois**, cliquez sur **téléchargement** "
            "(↓) : `…-audience-timeline.csv` (auditeurs/streams/followers au niveau artiste).",
            "s4a_public_12monthfilter_download.png", "Public → Vue d'ensemble → télécharger",
        ),
        GuideStep(
            "⚠️ N'utilisez **pas** le filtre « Depuis le début » pour le résumé : "
            "Spotify y renvoie auditeurs et sauvegardes à 0. Le fichier "
            "`…-songs-all.csv` est d'ailleurs rejeté à l'import.",
        ),
    ),
    expected=(
        ExpectedCsv("Timeline par titre", "<titre>-timeline.csv", ("date", "streams")),
        ExpectedCsv("Résumé titres (12 mois)", "…-songs-1year.csv",
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
        "Apple Music for Artists n'a pas d'API : l'export CSV de la performance "
        "par morceau est la seule source (**1 seul fichier**). Réglez bien la période "
        "sur **Depuis le début** pour un historique complet. En-têtes FR et EN reconnus."
    ),
    steps=(
        GuideStep(
            "Connectez-vous sur artists.apple.com, sélectionnez votre artiste, puis sur "
            "l'onglet **Aperçu** réglez le sélecteur de période (en haut à droite) sur "
            "**Depuis le début**.",
            "apple_music_aperçu_filtre_depuisledébut.png",
            "Aperçu → période → Depuis le début",
        ),
        GuideStep(
            "Cliquez sur l'onglet **Musique**.",
            "apple_music_ongletmusique.png", "Onglet Musique",
        ),
        GuideStep(
            "Dans la section **Morceaux**, cliquez sur **Tout afficher** (en haut à droite).",
            "apple_music_tout_afficher_button.png", "Morceaux → Tout afficher",
        ),
        GuideStep(
            "Cliquez sur l'icône de **téléchargement** (↓, en haut à droite) : vous obtenez "
            "`songs_….csv` (Morceau, Écoutes, Moy. d'auditeurs, Shazam, Radio Spins, Achats).",
            "apple_music_tout_télécharger.png", "Télécharger le CSV",
        ),
    ),
    expected=(
        ExpectedCsv("Performance par morceau", "songs_….csv",
                    ("Morceau / Song Title", "Écoutes / Plays", "Auditeurs / Listeners (opt.)")),
    ),
)

_IMUSICIAN = PlatformGuide(
    key="imusician",
    title="iMusician (distributeur)",
    icon="💰",
    intro=(
        "Deux types de rapports, à demander **par année** (itérez sur toutes vos "
        "années de catalogue) : le **résumé par sortie** (totaux mensuels par release) "
        "et le **rapport de ventes** (détail par ISRC/shop/pays). L'import détecte "
        "chaque type automatiquement."
    ),
    steps=(
        GuideStep(
            "Onglet **Revenus** (barre latérale) → **Rapports** → cliquez sur "
            "**Télécharger le rapport** (en haut à droite).",
            "imusician_dl_rapport.png", "Revenus → Rapports → Télécharger le rapport",
        ),
        GuideStep(
            "Période **An**, sélectionnez une **année**, type **Résumé par sortie**, "
            "puis **Demander le rapport**. Répétez pour **chaque année**.",
            "imusician_annuel_résumé_par_sortie.png",
            "An → année → Résumé par sortie → Demander",
        ),
        GuideStep(
            "Refaites l'opération en choisissant **Rapport de ventes** (pour chaque "
            "année également).",
            "imusician_annuel_rapportdevente.png",
            "An → année → Rapport de ventes → Demander",
        ),
        GuideStep(
            "Onglet **Compte** → **Téléchargements** : téléchargez (↓) **tous** les "
            "rapports annuels générés (résumés + ventes).",
            "imusician_compte_téléchargements_download.png",
            "Compte → Téléchargements → tout télécharger",
        ),
    ),
    expected=(
        ExpectedCsv("Résumé par sortie", "*.csv",
                    ("Statement date", "Release title", "Track streams", "Total revenue")),
        ExpectedCsv("Rapport de vente", "*.csv",
                    ("Sales date", "ISRC", "Shop", "Revenue EUR")),
    ),
)

_DISTROKID = PlatformGuide(
    key="distrokid",
    title="DistroKid (distributeur)",
    icon="🏦",
    intro=(
        "Un seul export couvre tout votre historique : le rapport détaillé de la "
        "**Bank** (une ligne par plateforme × titre × pays × mois, montants en **USD** "
        "— le taux de conversion USD→EUR se règle au moment de l'import). "
        "Format `.tsv` ou `.csv`, les deux sont reconnus automatiquement."
    ),
    steps=(
        GuideStep(
            "Connectez-vous sur distrokid.com → menu **Bank** (vos revenus)."
        ),
        GuideStep(
            "En bas de la page Bank, cliquez sur **« SEE EXCRUCIATING DETAIL »** "
            "(le détail complet ligne par ligne)."
        ),
        GuideStep(
            "Cliquez sur **Download** pour télécharger le fichier. Au-delà de "
            "50 000 lignes, DistroKid demande de filtrer (période / plateforme / "
            "release) avant de générer l'export — répétez si besoin."
        ),
        GuideStep(
            "Importez le fichier ici tel quel (.tsv ou .csv) et ajustez le **taux "
            "USD→EUR** proposé avant de confirmer."
        ),
    ),
    expected=(
        ExpectedCsv("Bank details (détail des revenus)", "*.tsv / *.csv",
                    ("Sale Month", "Store", "Title", "ISRC", "Quantity",
                     "Earnings (USD)")),
    ),
)

CSV_GUIDES: tuple[PlatformGuide, ...] = (_S4A, _APPLE, _IMUSICIAN, _DISTROKID)

# NOTE: API-credential guides are NOT here — they live (with their screenshots) in
# src/dashboard/content/credential_guides.py (CREDENTIAL_GUIDES), the single source
# shared by the in-app "Process — Credentials" view and the onboarding PDF.
