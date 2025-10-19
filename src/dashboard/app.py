"""Dashboard Streamlit principal."""
import streamlit as st
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

# Configuration de la page
st.set_page_config(
    page_title="Music Analytics Dashboard",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar navigation
st.sidebar.title("🎵 Navigation")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Sélectionnez une page",
    [
        "🏠 Accueil",
        "👤 Artist Stats (API Spotify)",
        "🎵 Top Tracks (API Spotify)",
        "📊 S4A - Vue d'ensemble",
        "🎸 S4A - Timeline par chanson",
        "👥 S4A - Audience"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Sources de données :**
    - API Spotify (artistes, tracks)
    - Spotify for Artists (streams quotidiens)
    """
)

# Router vers les pages
if page == "🏠 Accueil":
    from pages import home
    home.show()
elif page == "👤 Artist Stats (API Spotify)":
    from pages import artist_stats
    artist_stats.show()
elif page == "🎵 Top Tracks (API Spotify)":
    from pages import top_tracks
    top_tracks.show()
elif page == "📊 S4A - Vue d'ensemble":
    from pages import s4a_overview
    s4a_overview.show()
elif page == "🎸 S4A - Timeline par chanson":
    from pages import s4a_song_timeline
    s4a_song_timeline.show()
elif page == "👥 S4A - Audience":
    from pages import s4a_audience
    s4a_audience.show()