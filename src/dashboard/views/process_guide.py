"""Process Guide — onboarding runbook (credentials → collection → mapping).

Type: Feature
Uses: streamlit, weasyprint (optional, for the downloadable PDF)
Depends on: none (static content)
Persists in: nothing — read-only help page

Step-by-step guide shown just above the Credentials page: how to enter API
credentials, launch data collection, and map Meta Ads campaign names to Spotify
track names. Offers a downloadable PDF of the same content.
"""
import streamlit as st


# Single source of truth for both the on-screen render and the PDF.
_STEPS = [
    (
        "1. Saisir vos credentials API",
        [
            "Ouvrez la page **🔑 Credentials API**.",
            "Pour chaque plateforme (Spotify, YouTube, Meta Ads, SoundCloud, "
            "Instagram), collez les clés/tokens demandés dans l'onglet correspondant.",
            "Spotify et YouTube peuvent déjà être configurés au niveau de "
            "l'application (clé plateforme) — dans ce cas le statut affiche "
            "« Configuré (clé plateforme) » et aucune saisie n'est nécessaire.",
            "Cliquez sur **Tester la connexion** puis **Enregistrer**. "
            "L'enregistrement déclenche automatiquement la première collecte.",
        ],
    ),
    (
        "2. Lancer la collecte",
        [
            "Dans la barre latérale, cliquez sur **🚀 Lancer TOUTES les collectes** "
            "pour déclencher tous les DAGs d'un coup.",
            "Vous pouvez aussi laisser les collectes quotidiennes programmées s'exécuter.",
            "Suivez l'état des collectes dans **🔑 Credentials API** (badge de dernier "
            "run par plateforme) ou dans **🏗️ Monitoring ETL** (admin).",
            "Pour les sources CSV (Spotify for Artists, Apple Music, iMusician), "
            "importez vos fichiers depuis **📂 Import CSV**.",
        ],
    ),
    (
        "3. Mapper Meta Ads ↔ Spotify",
        [
            "Ouvrez la page **🔗 Mapping Spotify × Meta Ads (nom de campagne)**.",
            "Associez chaque **nom de campagne Meta Ads** au **nom de track Spotify** "
            "correspondant. C'est ce lien qui permet de rapprocher dépenses publicitaires "
            "et streams (ROI, vue META × Spotify).",
            "Astuce : nommez vos campagnes Meta Ads avec le titre du morceau pour "
            "faciliter le mapping (ex. campagne « KSD - Kimono à semelle de fer »).",
            "Une fois le mapping enregistré, les vues **META × Spotify** et "
            "**ROI Breakheaven** (Distributeur) se peuplent automatiquement.",
        ],
    ),
]


def _build_html() -> str:
    body = []
    for title, items in _STEPS:
        body.append(f"<h2 style='color:#1DB954;'>{title}</h2>")
        body.append("<ul>" + "".join(f"<li>{_strip_md(i)}</li>" for i in items) + "</ul>")
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:Arial,sans-serif;max-width:720px;margin:auto;padding:24px;}"
        "h1{color:#1DB954;} h2{margin-top:24px;} li{margin:6px 0;}"
        "</style></head><body>"
        "<h1>🎵 streaMLytics — Guide de démarrage</h1>"
        "<p>Comment saisir vos credentials, lancer la collecte et mapper "
        "vos campagnes Meta Ads à vos titres Spotify.</p>"
        + "".join(body)
        + "</body></html>"
    )


def _strip_md(text: str) -> str:
    """Convert the minimal **bold** markdown used above to HTML."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def show():
    st.title("📋 Guide de démarrage")
    st.caption(
        "Les 3 étapes pour configurer vos credentials, lancer la collecte de "
        "données et relier vos campagnes Meta Ads à vos titres Spotify."
    )
    st.markdown("---")

    for title, items in _STEPS:
        st.subheader(title)
        for item in items:
            st.markdown(f"- {item}")
        st.markdown("")

    st.markdown("---")

    # Downloadable PDF (falls back to HTML if WeasyPrint is unavailable).
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=_build_html()).write_pdf()
        st.download_button(
            "⬇️ Télécharger le guide (PDF)",
            data=pdf_bytes,
            file_name="streamlytics_guide_demarrage.pdf",
            mime="application/pdf",
        )
    except Exception:
        st.download_button(
            "⬇️ Télécharger le guide (HTML)",
            data=_build_html(),
            file_name="streamlytics_guide_demarrage.html",
            mime="text/html",
        )
        st.caption("Génération PDF indisponible (WeasyPrint absent) — export HTML proposé.")
