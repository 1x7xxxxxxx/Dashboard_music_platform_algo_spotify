"""trigger_algo — « Tes meilleurs réglages Meta » for the releases being judged (R598).

Type: Sub
Uses: src.dashboard.utils.best_settings, src.dashboard.utils.best_settings_data,
      src.dashboard.utils.campaign_compare (campaign_songs)
Depends on: campaign_track_mapping, track_platform_link, the Meta views
Persists in: nothing

The campaigns are the ones mapped to the releases picked at the top of the page. The figure
compares the two most recently launched (one colour each, named in the legend); the photo,
drawn below it, pools every mapped campaign into one best value per setting.
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils import best_settings, best_settings_data, charts
from src.dashboard.utils.campaign_pair import PAIR_COLORS
from src.dashboard.utils.i18n import t


def linked_campaigns(mapping: pd.DataFrame, creatives: pd.DataFrame,
                     songs: list[str]) -> list[str]:
    """The campaigns mapped to `songs`, most recently launched first. Pure."""
    if mapping.empty or not songs:
        return []
    names = set(mapping.loc[mapping["song"].isin(songs), "campaign_name"])
    if creatives.empty:
        return sorted(names)
    start = (creatives[creatives["campaign_name"].isin(names)]
             .groupby("campaign_name")["campaign_start"].max())
    return _newest_first(names, start)


def _newest_first(names: set[str], start: pd.Series) -> list[str]:
    """Dated campaigns newest first, then the undated ones by name."""
    dated = sorted((c for c in names if pd.notna(start.get(c))),
                   key=lambda c: pd.Timestamp(start[c]), reverse=True)
    return dated + sorted(c for c in names if pd.isna(start.get(c)))


def show_settings(db, artist_id: int, songs: list[str]) -> None:
    from src.dashboard.utils.campaign_compare import campaign_songs
    mapping = campaign_songs(db, artist_id)
    creatives = best_settings_data.creatives(db, artist_id)
    linked = linked_campaigns(mapping, creatives, songs)
    every = set(creatives["campaign_name"]) if not creatives.empty else set()
    st.caption(t("trigger_algo.settings_scope",
                 "{n} campagne(s) rattachée(s) à ces titres, {m} non rattachée(s).").format(
        n=len(linked), m=len(every - set(mapping["campaign_name"]) if not mapping.empty
                             else every)))
    if not linked:
        st.info(t("trigger_algo.settings_none",
                  "Aucune campagne Meta rattachée à ces titres — rattache-les dans "
                  "**🔗 Mapping cross-plateforme**."))
        return
    raw = best_settings_data.raw_panels(db, artist_id, linked, creatives)
    compared = linked[:2]
    fig = best_settings.figure(
        best_settings_data.by_campaign(
            [(lab, f[f["campaign_name"].isin(compared)] if not f.empty else f, c, s, r)
             for lab, f, c, s, r in raw]),
        colours=dict(zip(compared, PAIR_COLORS)))
    if fig is None:
        st.info(t("meta_creatives.bs_empty", "Pas encore assez de dépense mesurée pour "
                  "comparer tes réglages."))
    else:
        charts.plotly_chart(fig, width="stretch")
        st.caption(best_settings.caption())
    photo = best_settings.photo_figure(best_settings_data.photo(raw))
    if photo is not None:
        st.markdown(t("trigger_algo.settings_photo",
                      "**📸 La photo de tes réglages optimaux** — toutes ces campagnes "
                      "réunies, la valeur à garder pour chaque paramètre"))
        charts.plotly_chart(photo, width="stretch")
