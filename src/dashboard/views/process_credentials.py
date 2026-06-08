"""Process page — where to find each platform's API credentials.

Type: Feature
Uses: streamlit, src.dashboard.views.credentials._registry
Depends on: per-platform guides in credentials/_platform_*.py
Persists in: nothing

Surfaces the existing per-platform setup guides outside the credentials form, so
the actionable "🔑 Credentials API" page stays focused on entering the values.
"""
import streamlit as st

from src.dashboard.views.credentials._registry import PLATFORMS, _render_platform_guide


def show():
    st.title("📖 Process — Credentials API")
    st.markdown(
        "Comment obtenir les identifiants API de chaque plateforme. Une fois "
        "récupérés, saisissez-les dans **🔑 Credentials API** (section 📁 Données). "
        "Spotify et YouTube peuvent déjà être configurés au niveau de l'application."
    )
    st.markdown("---")
    for key, cfg in PLATFORMS.items():
        st.subheader(cfg["label"])
        _render_platform_guide(key)
