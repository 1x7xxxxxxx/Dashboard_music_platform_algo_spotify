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

from src.dashboard.utils.guide_assets import credentials_guide_pdf, pdf_from_html
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
            t("process_guide.s2csv_title", "2. Importer vos fichiers CSV"),
            [
                t("process_guide.s2csv_i1",
                  "Ouvrez la page **📂 Ajouter mes chiffres Spotify for Artists & Apple** "
                  "et déposez vos fichiers (jusqu'à une "
                  "dizaine d'un coup) — le type est détecté automatiquement d'après le nom et "
                  "les colonnes."),
                t("process_guide.s2csv_i2",
                  "Sources reconnues : **Spotify for Artists** (timeline + songs-global — le "
                  "songs-global reconstruit le **référentiel de sorties** utilisé par le mapping "
                  "et le scoring ML), **Apple Music**, **iMusician / DistroKid** (revenus), "
                  "**SACEM** (.xlsx, relevé de compte)."),
                t("process_guide.s2csv_i3",
                  "⚠️ Importez vos CSV **avant** de lancer la collecte : le bouton **🚀 Lancer "
                  "TOUTES les collectes** déclenche aussi les watchers CSV, qui ne ramassent que "
                  "les fichiers **déjà déposés**."),
            ],
        ),
        (
            t("process_guide.s2_title", "3. Lancer la collecte"),
            [
                t("process_guide.s2_i1",
                  "Dans la barre latérale, clique sur **🚀 Lancer TOUTES les collectes** — "
                  "toutes tes plateformes sont interrogées d'un coup."),
                t("process_guide.s2_i2",
                  "Vous pouvez aussi laisser les collectes quotidiennes programmées s'exécuter."),
                t("process_guide.s2_i3",
                  "Suivez l'état des collectes dans **🔑 Credentials API** (badge de dernier "
                  "run par plateforme) ou dans **🏗️ Monitoring ETL** (admin)."),
            ],
        ),
        (
            t("process_guide.s3_title", "4. Mapper Meta Ads ↔ Spotify"),
            [
                t("process_guide.s3_why",
                  "ℹ️ **Pourquoi mapper ?** Un même titre porte souvent un **nom différent** "
                  "selon la plateforme (S4A, Spotify, YouTube, SoundCloud, Apple) et dans vos "
                  "campagnes Meta Ads (acronymes, codes, noms d'adsets…). Le mapping **relie "
                  "ces noms au même titre** pour consolider streams, vues et dépenses pub sur "
                  "la bonne référence."),
                t("process_guide.s3_i1",
                  "Ouvrez la page **🔗 Mapping cross-plateforme**. Onglet **📣 Campagnes "
                  "Meta** : des **suggestions automatiques** (similarité du nom + proximité "
                  "avec la date de sortie) apparaissent **en haut**, avec un indice de "
                  "fiabilité 🟢/🟡/🔴 — cochez **Associer** pour valider les bonnes."),
                t("process_guide.s3_i2",
                  "Sur le même écran, l'onglet **🎵 Titres cross-plateformes** relie vos "
                  "titres Spotify/Apple/SoundCloud/YouTube. Sinon, associez une campagne à "
                  "la main (onglet **Ajout manuel**). C'est ce lien qui rapproche dépenses "
                  "publicitaires et streams (ROI, vue META × Spotify)."),
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




def _render_guide_web_link() -> None:
    """Point at the web version, which is the one that is never stale.

    `st.link_button` and a new tab, not `components.html`: the dashboard's own CSP
    sets `frame-ancestors 'none'` (deploy/Caddyfile), so the page cannot be framed
    inside Streamlit — an iframe would render an empty box with nothing in the logs.
    """
    import os

    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    if not base:
        return
    st.link_button(
        t("process_guide.web_version", "🌐 Ouvrir le guide complet dans un onglet"),
        f"{base}/guide", use_container_width=False,
    )
    st.caption(t("process_guide.web_version_note",
                 "Version web : toujours à jour, images nettes, liens cliquables."))


def _render_credentials_pdf() -> None:
    """Le guide d'identifiants COMPLET, avec ses captures — téléchargeable ici.

    Ce PDF (`guides/guide_pdf.py`) porte les copies d'écran de chaque plateforme et les
    valeurs exactes à coller. Jusqu'au 2026-08-23 il n'était livré QUE par l'e-mail de
    vérification : e-mail perdu, PDF perdu, et aucun bouton nulle part dans
    l'application. Note d'origine : « mettre lien de dl du pdf dans guide de démarrage ».

    Le fichier de `docs/guides/` peut ne pas exister dans un conteneur fraîchement
    bâti, et le régénérer coûte moins qu'un lien mort — mais le régénérer à CHAQUE
    rerun coûtait 573 ms mesurés en prod, déplier un accordéon suffisant à les
    repayer. `credentials_guide_pdf` préfère la copie pré-rendue et met en cache le
    reste ; voir `src/dashboard/utils/guide_assets.py`.
    """
    st.subheader(t("process_guide.cred_pdf_title",
                   "📘 Guide des identifiants (PDF, avec captures d'écran)"))
    lang = st.session_state.get("lang", "fr")
    pdf_bytes = credentials_guide_pdf(lang)
    if pdf_bytes:
        st.download_button(
            t("process_guide.cred_pdf_dl", "⬇️ Télécharger le guide des identifiants"),
            data=pdf_bytes,
            file_name=f"streamlytics_guide_identifiants_{lang}.pdf",
            mime="application/pdf",
            key="dl_cred_guide_pdf",
        )
        st.caption(t("process_guide.cred_pdf_note",
                     "C'est le même document que celui joint à ton e-mail de "
                     "vérification — plateforme par plateforme, avec les captures."))
    else:                  # WeasyPrint absent ou guide introuvable : on le dit, on ne casse pas
        st.info(t("process_guide.cred_pdf_unavailable",
                  "Le PDF n'a pas pu être généré ici. Il reste disponible en pièce "
                  "jointe de ton e-mail de vérification, et les mêmes étapes sont "
                  "dépliables sur la page **🔑 Credentials API**."))


def _render_csv_definitions() -> None:
    """Ce que chaque CSV contient, et le fichier attendu — hors du dépliant replié.

    Les définitions existaient déjà (`content/csv_guides.py` : intitulé, colonnes
    attendues, nom de fichier) mais n'étaient rendues QUE sur la page Import CSV, dans un
    dépliant fermé par défaut. Un artiste qui se demande « c'est quoi ce CSV ? » est au
    guide, pas sur la page d'import. Note d'origine : « csv a détailler definition ».
    """
    st.subheader(t("process_guide.csv_defs_title", "📄 Les CSV attendus, et ce qu'ils contiennent"))
    try:
        from src.dashboard.content.csv_guides import CSV_GUIDES
    except Exception:      # noqa: BLE001 — le guide reste lisible sans cette section
        return
    for guide in CSV_GUIDES:
        with st.expander(f"{guide.icon} {guide.title}", expanded=False):
            st.markdown(guide.intro)
            for exp in guide.expected:
                st.markdown(
                    t("process_guide.csv_expected",
                      "**{label}** — fichier `{hint}`").format(
                          label=exp.label, hint=exp.filename_hint))
                if exp.columns:
                    st.caption(
                        t("process_guide.csv_columns", "Colonnes attendues : {cols}")
                        .format(cols=", ".join(exp.columns)))


def _render_platform_links() -> None:
    """Les portails où l'artiste va réellement chercher ses données.

    `views/useful_links.py` les portait déjà — mais cette page est **réservée admin**,
    donc aucun artiste n'a jamais vu le lien vers Apple Music for Artists. Note
    d'origine : « intégrer lien apple music ».
    """
    st.subheader(t("process_guide.links_title", "🔗 Où récupérer tes données"))
    links = [
        ("🎎 Apple Music for Artists", "https://artists.apple.com",
         t("process_guide.link_apple", "Export CSV « Songs Performance » — "
                                       "règle la période sur **Depuis le début**.")),
        ("🎵 Spotify for Artists", "https://artists.spotify.com",
         t("process_guide.link_s4a", "Exports timeline et audience. **N'utilise pas** "
                                     "« Depuis le début » ici : Spotify y renvoie des zéros.")),
        ("☁️ SoundCloud", "https://soundcloud.com",
         t("process_guide.link_sc", "Ton profil — l'identifiant numérique se lit dans "
                                    "le code source de la page.")),
        ("🎬 YouTube Studio", "https://studio.youtube.com",
         t("process_guide.link_yt", "L'identifiant de chaîne (UC…) est dans "
                                    "Paramètres → Chaîne → Paramètres avancés.")),
    ]
    for label, url, note in links:
        st.markdown(f"- [{label}]({url}) — {note}")


def show():
    st.title(t("process_guide.title", "📋 Guide de démarrage"))
    st.caption(
        t("process_guide.caption",
          "Les 4 étapes pour configurer vos credentials, importer vos CSV, lancer la "
          "collecte de données et relier vos campagnes Meta Ads à vos titres Spotify.")
    )
    st.markdown("---")

    # Quatre listes à puces PLATES, toutes déroulées en même temps : un artiste en test
    # a demandé « guide : onglet clickable développer ». Cooper (*About Face*, p.271)
    # appelle ça la **divulgation progressive** — ce qui est rare ou avancé se replie
    # derrière un dépliant, et le dépliant reste ouvert une fois ouvert.
    #
    # La PREMIÈRE étape non faite est dépliée d'office : c'est la seule que l'artiste ait
    # à lire maintenant. Sans état de progression sous la main ici, on ouvre la première.
    for idx, (title, items) in enumerate(_get_steps()):
        with st.expander(title, expanded=(idx == 0)):
            for item in items:
                st.markdown(f"- {item}")

    st.markdown("---")

    _render_guide_web_link()
    _render_credentials_pdf()
    _render_csv_definitions()
    _render_platform_links()

    st.markdown("---")

    # Downloadable PDF (falls back to HTML if WeasyPrint is unavailable).
    # `pdf_from_html` is cached on the HTML string: the document is a pure function of
    # the session language, so re-rendering it on every rerun bought nothing and cost
    # 148 ms measured in production.
    html = _build_html()
    pdf_bytes = pdf_from_html(html)
    if pdf_bytes:
        st.download_button(
            t("process_guide.download_pdf", "⬇️ Télécharger le guide (PDF)"),
            data=pdf_bytes,
            file_name="streamlytics_guide_demarrage.pdf",
            mime="application/pdf",
        )
    else:
        st.download_button(
            t("process_guide.download_html", "⬇️ Télécharger le guide (HTML)"),
            data=html,
            file_name="streamlytics_guide_demarrage.html",
            mime="text/html",
        )
        st.caption(t("process_guide.pdf_unavailable",
                     "Génération PDF indisponible (WeasyPrint absent) — export HTML proposé."))
