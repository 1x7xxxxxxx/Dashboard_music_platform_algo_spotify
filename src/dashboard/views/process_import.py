"""Process page — how to download + import your CSV files (full guide).

Type: Feature
Uses: streamlit, src.dashboard.content.csv_guides_st.render_csv_guides
Depends on: assets/csv_guides/*.png (optional)
Persists in: nothing

Holds the full download/import walkthrough so the actionable "📂 Import CSV"
page stays focused on the uploader. Single content source: csv_guides.
"""
import streamlit as st

from src.dashboard.content.csv_guides_st import render_csv_guides


def show():
    st.title("📖 Process — Import CSV")
    st.markdown(
        "Comment **télécharger** vos fichiers depuis Spotify for Artists, Apple Music "
        "for Artists et iMusician, puis les **importer**. Une fois vos fichiers prêts, "
        "rendez-vous sur **📂 Import CSV** (section 📁 Données) pour les déposer."
    )
    st.markdown("---")
    render_csv_guides()
