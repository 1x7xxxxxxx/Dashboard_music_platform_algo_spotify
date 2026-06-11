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

from src.dashboard.utils.i18n import t


# Single source of truth for both the on-screen render and the PDF.
# Built per-render (not at import) so t() resolves the session language.
def _get_steps() -> list[tuple[str, list[str]]]:
    return [
        (
            t("process_guide.s1_title", "1. Saisir vos credentials API"),
            [
                t("process_guide.s1_i1", "Ouvrez la page **🔑 Credentials API**."),
                t("process_guide.s1_i2",
                  "Pour chaque plateforme (Spotify, YouTube, Meta Ads, SoundCloud, "
                  "Instagram), collez les clés/tokens demandés dans l'onglet correspondant."),
                t("process_guide.s1_i3",
                  "Spotify et YouTube peuvent déjà être configurés au niveau de "
                  "l'application (clé plateforme) — dans ce cas le statut affiche "
                  "« Configuré (clé plateforme) » et aucune saisie n'est nécessaire."),
                t("process_guide.s1_i4",
                  "Cliquez sur **Tester la connexion** puis **Enregistrer**. "
                  "L'enregistrement déclenche automatiquement la première collecte."),
            ],
        ),
        (
            t("process_guide.s2_title", "2. Lancer la collecte"),
            [
                t("process_guide.s2_i1",
                  "Dans la barre latérale, cliquez sur **🚀 Lancer TOUTES les collectes** "
                  "pour déclencher tous les DAGs d'un coup."),
                t("process_guide.s2_i2",
                  "Vous pouvez aussi laisser les collectes quotidiennes programmées s'exécuter."),
                t("process_guide.s2_i3",
                  "Suivez l'état des collectes dans **🔑 Credentials API** (badge de dernier "
                  "run par plateforme) ou dans **🏗️ Monitoring ETL** (admin)."),
                t("process_guide.s2_i4",
                  "Pour les sources CSV (Spotify for Artists, Apple Music, iMusician), "
                  "importez vos fichiers depuis **📂 Import CSV**."),
            ],
        ),
        (
            t("process_guide.s3_title", "3. Mapper Meta Ads ↔ Spotify"),
            [
                t("process_guide.s3_i1",
                  "Ouvrez la page **🔗 Meta × Spotify**. Des **suggestions automatiques** "
                  "(similarité du nom de campagne + proximité avec la date de sortie) "
                  "apparaissent **en haut**, avec un indice de fiabilité 🟢/🟡/🔴 — cochez "
                  "**Associer** pour valider celles qui sont correctes."),
                t("process_guide.s3_i2",
                  "Sinon, associez à la main chaque **campagne Meta Ads** au **titre** "
                  "correspondant (onglet **Ajout manuel**). C'est ce lien qui rapproche "
                  "dépenses publicitaires et streams (ROI, vue META × Spotify)."),
                t("process_guide.s3_i3",
                  "Astuce : nommez vos campagnes Meta Ads avec le titre du morceau pour de "
                  "meilleures suggestions automatiques (ex. campagne « Track 1 »)."),
                t("process_guide.s3_i4",
                  "Une fois le mapping enregistré, les vues **META × Spotify** et "
                  "**ROI Breakheaven** (Distributeur) se peuplent automatiquement."),
            ],
        ),
    ]


def _build_html() -> str:
    body = []
    for title, items in _get_steps():
        body.append(f"<h2 style='color:#1DB954;'>{title}</h2>")
        body.append("<ul>" + "".join(f"<li>{_strip_md(i)}</li>" for i in items) + "</ul>")
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:Arial,sans-serif;max-width:720px;margin:auto;padding:24px;}"
        "h1{color:#1DB954;} h2{margin-top:24px;} li{margin:6px 0;}"
        "</style></head><body>"
        f"<h1>{t('process_guide.pdf_title', '🎵 streaMLytics — Guide de démarrage')}</h1>"
        f"<p>{t('process_guide.pdf_intro', 'Comment saisir vos credentials, lancer la collecte et mapper vos campagnes Meta Ads à vos titres Spotify.')}</p>"
        + "".join(body)
        + "</body></html>"
    )


def _strip_md(text: str) -> str:
    """Convert the minimal **bold** markdown used above to HTML."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def show():
    st.title(t("process_guide.title", "📋 Guide de démarrage"))
    st.caption(
        t("process_guide.caption",
          "Les 3 étapes pour configurer vos credentials, lancer la collecte de "
          "données et relier vos campagnes Meta Ads à vos titres Spotify.")
    )
    st.markdown("---")

    for title, items in _get_steps():
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
            t("process_guide.download_pdf", "⬇️ Télécharger le guide (PDF)"),
            data=pdf_bytes,
            file_name="streamlytics_guide_demarrage.pdf",
            mime="application/pdf",
        )
    except Exception:
        st.download_button(
            t("process_guide.download_html", "⬇️ Télécharger le guide (HTML)"),
            data=_build_html(),
            file_name="streamlytics_guide_demarrage.html",
            mime="text/html",
        )
        st.caption(t("process_guide.pdf_unavailable",
                     "Génération PDF indisponible (WeasyPrint absent) — export HTML proposé."))
