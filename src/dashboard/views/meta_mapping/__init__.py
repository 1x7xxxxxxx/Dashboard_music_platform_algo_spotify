"""Cross-platform mapping — one home for all track/campaign links.

Type: Feature
Uses: view_session, track_matching (canonical reference + canonical_song),
      track_mapping_suggest (scoring engine)
Persists in: track_platform_link (cross-platform tracks) + campaign_track_mapping
             (Meta campaigns) — both in PostgreSQL spotify_etl

Free-tier. Two tabs:
  1. Cross-platform tracks (_tracks.py) — each platform's free-text titles scored
     against the canonical track_release_reference (title similarity + release-date
     proximity where the platform exposes a date); accept/reject → track_platform_link,
     plus a coverage recap grid.
  2. Meta campaigns (_campaigns.py) — auto-suggestions (title + campaign-start
     proximity) on top, backlog recap, manual add + existing list → campaign_track_mapping.
Both campaign paths feed meta_x_spotify, the ROI Breakeven and the PDF export.
Confidence is stored in [0,1]; only the displayed % column is scaled ×100 (a raw
[0,1] value in a ProgressColumn with a "%" format would render "0%").
"""
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.utils.track_matching import rebuild_release_reference

from ._campaigns import render_campaign_tab
from ._common import _load_canonical
from ._tracks import render_overview_tab


def show():
    st.title(t("meta_mapping.title", "🔗 Mapping cross-plateforme"))
    st.caption(t("meta_mapping.subtitle",
                 "Reliez vos titres entre plateformes (Spotify, Apple, SoundCloud, YouTube) "
                 "et associez vos campagnes Meta Ads aux titres. Suggestions automatiques + "
                 "saisie manuelle alimentent META × Spotify et le ROI Breakheaven."))

    with view_session() as (db, artist_id):
        canonical = _load_canonical(db, artist_id)
        if not canonical:
            st.info(t("track_mapping.no_reference",
                      "Aucune référence de titres trouvée. Importez vos CSV S4A puis "
                      "reconstruisez la référence ci-dessous."))
            if st.button(t("track_mapping.rebuild_button",
                           "🔄 Reconstruire la référence des titres")):
                n = rebuild_release_reference(db, artist_id)
                st.success(t("track_mapping.rebuilt",
                             "{n} titre(s) de référence reconstruits.").format(n=n))
                st.rerun()
            return

        tab_overview, tab_camp = st.tabs(
            [t("meta_mapping.tab_overview", "🎵 Titres & couverture"),
             t("meta_mapping.tab_campaigns", "📣 Campagnes Meta")])

        with tab_overview:
            render_overview_tab(db, artist_id, canonical)
        with tab_camp:
            render_campaign_tab(db, artist_id, canonical)
