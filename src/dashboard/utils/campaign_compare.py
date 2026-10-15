"""« Comparer mes campagnes » — the cross-campaign questions of « Tout mon funnel ».

Type: Feature
Uses: pandas, streamlit, src.dashboard.utils.campaign_funnel (streams_gained, best_lag)
Depends on: v_meta_campaign_daily, v_meta_ad_daily, v_s4a_song_daily, v_hypeddit_daily,
            campaign_track_mapping, track_platform_link
Triggers: views/meta_ads_overview.py (« 🏁 Comparer mes campagnes »)

R567 (2026-10-15): the three tables became Pareto bars — best on the left, details on hover.
Persists in: nothing

R234 (2026-09-27), the owner's funnel questions answered ACROSS campaigns:
  - which campaign bought an extra stream cheapest (cost per stream gained);
  - engagement campaigns against traffic campaigns;
  - which track turns store clicks into streams best;
  - the delay between exposure (spend) and listening.
The country question is already answered, per campaign, by the « 🌍 Par pays » tab.

FIVE queries for the whole table, never one per campaign (code-critic, R234): the
campaign → track resolution is one join, the streams are one read over the widest
window, the arithmetic is pandas. The two biases of « streams gained » are WRITTEN under
the table, not hidden: two campaigns on the same track at the same time both claim the
same streams, and a baseline can contain another campaign's paid days.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st

from src.dashboard.utils import charts
from src.dashboard.utils.campaign_funnel import BASELINE_DAYS, best_lag, streams_gained
from src.dashboard.utils.i18n import t

_FAMILY = {
    "OUTCOME_ENGAGEMENT": "engagement", "POST_ENGAGEMENT": "engagement",
    "VIDEO_VIEWS": "engagement", "PAGE_LIKES": "engagement",
    "LINK_CLICKS": "trafic", "OUTCOME_TRAFFIC": "trafic",
    "CONVERSIONS": "conversion", "OUTCOME_SALES": "conversion",
    "OUTCOME_LEADS": "conversion",
}
# Below this, the « best » lag is the least bad of eight noises: 0.3 is the conventional
# floor of a weak positive correlation. A delay is named only above it (measured
# 2026-09-27, artist 1: « 6 j » came out of a correlation of −0.09).
MIN_LAG_CORR = 0.3
# The optimisation goals whose « result » is a conversion: a CPR is only a price of a
# result on them. Single definition — `views/meta_creatives.py` reads it from here.
_CONVERSION_GOALS_SQL = "('OFFSITE_CONVERSIONS','ONSITE_CONVERSIONS','LEAD_GENERATION','QUALITY_LEAD')"


def objective_family(objective) -> str:
    """engagement · trafic · conversion · autre — Meta's objective, grouped. Pure."""
    return _FAMILY.get(str(objective or "").upper(), "autre")


def _df(db, sql: str, params: tuple) -> pd.DataFrame:
    try:
        return db.fetch_df(sql, params)
    except Exception:      # noqa: BLE001 — une source absente ne casse pas la comparaison
        return pd.DataFrame()


def campaign_songs(db, artist_id: int) -> pd.DataFrame:
    """[campaign_name, song] — each mapped campaign's S4A title (one definition, R594)."""
    return _df(db, """
        SELECT DISTINCT ON (m.campaign_name) m.campaign_name, s4a.platform_title AS song
          FROM campaign_track_mapping m
          JOIN track_platform_link any_l
            ON any_l.artist_id = m.artist_id AND any_l.status = 'confirmed'
           AND TRIM(any_l.platform_title) = TRIM(m.track_name)
          JOIN track_platform_link s4a
            ON s4a.artist_id = any_l.artist_id AND s4a.match_key = any_l.match_key
           AND s4a.platform = 's4a' AND s4a.status = 'confirmed'
         WHERE m.artist_id = %s ORDER BY m.campaign_name""", (artist_id,))


def load(db, artist_id: int, acct: str, acct_p: tuple) -> dict:
    """The five batched reads. Each frame may be empty — absent, never an error."""
    daily = _df(db, f"""
        SELECT campaign_name, day AS date, SUM(spend) AS spend,
               SUM(impressions) AS impressions, SUM(link_clicks) AS link_clicks
          FROM v_meta_campaign_daily WHERE artist_id = %s{acct}
         GROUP BY campaign_name, day""", (artist_id, *acct_p))
    objective = _df(db, """
        SELECT campaign_name, MAX(objective) AS objective
          FROM v_meta_ad_daily WHERE artist_id = %s
         GROUP BY campaign_name""", (artist_id,))
    tracks = campaign_songs(db, artist_id)
    songs = sorted(tracks["song"].dropna().unique()) if not tracks.empty else []
    streams = pd.DataFrame()
    if songs and not daily.empty:
        start = pd.to_datetime(daily["date"]).min().date() - _dt.timedelta(days=BASELINE_DAYS)
        streams = _df(db, """
            SELECT song, day AS date, streams FROM v_s4a_song_daily
             WHERE artist_id = %s AND song = ANY(%s) AND day >= %s
               AND song NOT ILIKE '%%1x7xxxxxxx%%'""", (artist_id, songs, start))
    store = _df(db, """
        SELECT s4a.platform_title AS song, SUM(h.clicks) AS store_clicks,
               SUM(h.visits) AS visits
          FROM v_hypeddit_daily h
          JOIN track_platform_link hl
            ON hl.artist_id = h.artist_id AND hl.platform = 'hypeddit'
           AND hl.status = 'confirmed'
           AND LOWER(TRIM(hl.platform_title)) = LOWER(TRIM(h.campaign_name))
          JOIN track_platform_link s4a
            ON s4a.artist_id = hl.artist_id AND s4a.match_key = hl.match_key
           AND s4a.platform = 's4a' AND s4a.status = 'confirmed'
         WHERE h.artist_id = %s GROUP BY s4a.platform_title""", (artist_id,))
    creatives = _df(db, f"""
        SELECT campaign_name, creative_name, SUM(spend) AS spend,
               SUM(conversions) AS results,
               BOOL_OR(optimization_goal IN {_CONVERSION_GOALS_SQL}) AS conv
          FROM v_meta_creative_daily WHERE artist_id = %s{acct}
         GROUP BY campaign_name, creative_name HAVING SUM(spend) > 0""", (artist_id, *acct_p))
    # R590 — the ad set of each creative: only the raw catalogue names it. Not filtered by
    # account: it is merged onto `creatives`, which already is. Tenant named at each join.
    adsets = _df(db, """
        SELECT d.ad_name AS creative_name, c.campaign_name, s.adset_name
          FROM meta_ads d
          JOIN meta_adsets s ON s.adset_id = d.adset_id AND s.artist_id = d.artist_id
          JOIN meta_campaigns c ON c.campaign_id = d.campaign_id AND c.artist_id = d.artist_id
         WHERE d.artist_id = %s AND d.ad_name IS NOT NULL""", (artist_id,))
    return {"daily": daily, "objective": objective, "tracks": tracks,
            "streams": streams, "store": store, "creatives": creatives, "adsets": adsets}


def creative_streams(df: pd.DataFrame, creatives: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """(one row per creative that ran ALONE in its campaign, campaigns not separable). Pure.

    R239. A campaign that spent on ONE creative gives that creative its streams gained —
    a measure, not a split. Sharing the gain between several creatives by their clicks
    would assume every click converts alike: that assumption is what R213 c refused.
    """
    if df.empty or creatives is None or creatives.empty:
        return pd.DataFrame(), 0
    n = creatives.groupby("campaign_name")["creative_name"].nunique()
    alone = creatives[creatives["campaign_name"].isin(n[n == 1].index)]
    out = df.merge(alone[["campaign_name", "creative_name"]], on="campaign_name",
                   validate="one_to_one")
    split = int(df["campaign_name"].isin(n[n > 1].index).sum())
    return out[["creative_name", "campaign_name", "song", "spend", "gained",
                "cost_per_gained", "overlap"]].sort_values(
        "cost_per_gained", na_position="last"), split


def _overlaps(camps: pd.DataFrame) -> set:
    """Campaigns whose window, baseline included, meets another one's on the same track."""
    out = set()
    rows = camps.dropna(subset=["song"]).to_dict("records")
    for a in rows:
        lo = a["d0"] - _dt.timedelta(days=BASELINE_DAYS)
        for b in rows:
            if a is not b and a["song"] == b["song"] and b["d0"] <= a["d1"] and b["d1"] >= lo:
                out.add(a["campaign_name"])
    return out


def compare(data: dict) -> pd.DataFrame:
    """One row per campaign: track, family, spend, streams gained, € per gained stream,
    overlap flag and exposure → listening delay. Pure — the test holds it."""
    daily = data["daily"]
    if daily is None or daily.empty:
        return pd.DataFrame()
    d = daily.assign(date=pd.to_datetime(daily["date"]).dt.date,
                     spend=pd.to_numeric(daily["spend"], errors="coerce"))
    camps = d.groupby("campaign_name").agg(d0=("date", "min"), d1=("date", "max"),
                                           spend=("spend", "sum")).reset_index()
    camps = camps.merge(data["tracks"], on="campaign_name", how="left",
                        validate="one_to_one") \
        if not data["tracks"].empty else camps.assign(song=None)
    obj = data["objective"]
    camps["family"] = camps["campaign_name"].map(
        dict(zip(obj["campaign_name"], obj["objective"])) if not obj.empty else {}
    ).map(objective_family)
    overlap = _overlaps(camps)
    streams = data["streams"]
    rows = []
    for c in camps.to_dict("records"):
        s = streams[streams["song"] == c["song"]] if not streams.empty and c["song"] else None
        g = streams_gained(s[["date", "streams"]], c["d0"], c["d1"]) if s is not None else None
        rows.append({**c, "gained": g["gained"] if g else None,
                     "cost_per_gained": (c["spend"] / g["gained"])
                     if g and g["gained"] > 0 and c["spend"] else None,
                     "overlap": c["campaign_name"] in overlap,
                     "lag": _lag(d, s, c)})
    return pd.DataFrame(rows).sort_values("d1", ascending=False, ignore_index=True)


def _lag(daily: pd.DataFrame, streams: pd.DataFrame | None, c: dict) -> dict | None:
    """Delay (days) at which this campaign's daily spend best precedes its track's streams."""
    if streams is None or streams.empty:
        return None
    spend = daily[daily["campaign_name"] == c["campaign_name"]][["date", "spend"]]
    s = streams.assign(date=pd.to_datetime(streams["date"]).dt.date)
    s = s[(s["date"] >= c["d0"]) & (s["date"] <= c["d1"] + _dt.timedelta(days=7))]
    master = spend.merge(s[["date", "streams"]], on="date", how="outer",
                         validate="one_to_one")
    return best_lag(master, "spend", "streams")


def track_conversion(df: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Per track: store clicks (Hypeddit), streams gained, streams gained per click. Pure."""
    if df.empty or store is None or store.empty:
        return pd.DataFrame()
    gained = df.dropna(subset=["gained", "song"]).groupby("song")["gained"].sum()
    out = store.assign(store_clicks=pd.to_numeric(store["store_clicks"], errors="coerce"))
    out["gained"] = out["song"].map(gained)
    out["per_click"] = out["gained"] / out["store_clicks"].where(out["store_clicks"] > 0)
    return out.sort_values("per_click", ascending=False, na_position="last")


def _lag_text(lag) -> str:
    if not isinstance(lag, dict) or lag["corr"] < MIN_LAG_CORR:
        return "—"
    return t("campaign_compare.lag_days", "{n} j").format(n=lag["lag"])


def render(db, artist_id: int, acct: str, acct_p: tuple) -> None:
    """The tab body: the tracks, the creatives' funnel (R577 — the campaign ranking « quelle campagne a
    acheté l'écoute la moins chère » is gone, owner 2026-10-15)."""
    data = load(db, artist_id, acct, acct_p)
    df = compare(data)
    if df.empty:
        st.info(t("campaign_compare.empty", "Aucune campagne à comparer sur ce compte."))
        return
    _render_tracks(df, data["store"])
    _render_creative_funnel(df, data)
    st.caption(t("campaign_compare.countries",
                 "Le pays qui transforme le mieux : onglet **🌍 Par pays**, campagne par "
                 "campagne."))


def _render_tracks(df: pd.DataFrame, store: pd.DataFrame) -> None:
    tracks = track_conversion(df, store)
    st.markdown(t("campaign_compare.tracks_head",
                  "**Quel titre transforme le mieux les clics en écoutes ?** — clics vers "
                  "les plateformes (Hypeddit) et écoutes gagnées pendant ses campagnes."))
    if tracks.empty:
        st.caption(t("campaign_compare.tracks_empty",
                     "Aucun lien Hypeddit rattaché à un titre Spotify : rattache-les dans "
                     "**🔗 Mapping cross-plateforme**."))
        return
    fig = tracks_figure(tracks)
    if fig is not None:
        charts.plotly_chart(fig, width="stretch")


def tracks_figure(tracks: pd.DataFrame):
    """R578 — one dot per track: store clicks across, streams gained up, the slope is the
    conversion. Pure.

    Owner, 2026-10-15: « autre visuel que Pareto ». A ratio alone hides its volume: 3
    streams per click on 4 clicks and on 400 are the same bar. The dot keeps both, and the
    dotted rays (1, 2, 5 streams per click) read the ratio off the slope."""
    import plotly.graph_objects as go
    from src.dashboard.utils.labels import unique_short_labels
    from src.dashboard.utils.platform_colors import DISTINCT

    d = tracks.dropna(subset=["store_clicks", "gained"])
    d = d[d["store_clicks"] > 0]
    if d.empty:
        return None
    names = unique_short_labels(d["song"].astype(str).tolist(), 24)
    x_max = float(d["store_clicks"].max()) * 1.25
    y_max = max(float(d["gained"].max()), 0.0) * 1.25 or 1.0
    fig = go.Figure()
    for k in _RAYS:
        end = min(x_max, y_max / k)
        fig.add_trace(go.Scatter(
            x=[0, end], y=[0, end * k], mode="lines+text", showlegend=False,
            line={"color": "#BDBDBD", "width": 1, "dash": "dot"}, hoverinfo="skip",
            text=["", t("campaign_compare.ray", "{k} écoute(s) / clic").format(k=k)],
            textposition="top left", textfont={"size": 10, "color": "#9E9E9E"}))
    fig.add_trace(go.Scatter(
        x=d["store_clicks"], y=d["gained"], mode="markers+text", text=names,
        textposition="top center", showlegend=False, cliponaxis=False,
        marker={"size": 14, "color": [DISTINCT[i % len(DISTINCT)] for i in range(len(d))]},
        customdata=d["per_click"],
        hovertemplate="<b>%{text}</b><br>" + t("campaign_compare.c_clicks", "Clics plateformes")
                      + " : %{x:,.0f}<br>" + t("campaign_compare.c_gained", "Écoutes gagnées")
                      + " : %{y:,.0f}<br>%{customdata:,.2f} / clic<extra></extra>"))
    fig.update_layout(height=380, margin={"t": 20, "b": 10},
                      xaxis={"title": t("campaign_compare.c_clicks", "Clics plateformes"),
                             "range": [0, x_max]},
                      yaxis={"title": t("campaign_compare.c_gained", "Écoutes gagnées"),
                             "range": [min(0.0, float(d["gained"].min()) * 1.25), y_max]})
    return fig


_RAYS = (1, 2, 5)   # streams per click — the slopes drawn behind the dots


def _render_creative_funnel(df: pd.DataFrame, data: dict) -> None:
    """R590 — the second funnel: budget › campaign › ad set › creative (replaces R239's
    « quelle créa a rapporté des écoutes », which only saw the creatives that ran alone)."""
    fig = creative_tree_figure(creative_tree(df, data.get("creatives"), data.get("adsets")))
    if fig is not None:
        charts.plotly_chart(fig, width="stretch")


def creative_tree(df: pd.DataFrame, creatives: pd.DataFrame,
                  adsets: pd.DataFrame) -> pd.DataFrame:
    """R590 — one row per box of the creatives' funnel: budget › campaign › ad set › creative.

    Columns: id, parent, level (0 budget … 3 creative), label, campaign, spend, cpr, gained.
    Streams gained are written on a campaign (its track's gain) and on a creative only when
    it ran ALONE in its campaign (R239): an ad set or a shared creative has none. Pure."""
    cols = ["id", "parent", "level", "label", "campaign", "spend", "cpr", "gained"]
    if creatives is None or creatives.empty:
        return pd.DataFrame(columns=cols)
    c = creatives.assign(spend=pd.to_numeric(creatives["spend"], errors="coerce").fillna(0.0),
                         results=pd.to_numeric(creatives.get("results"), errors="coerce"))
    c["conv"] = c["conv"].fillna(False).astype(bool) if "conv" in c else False
    keys = ["creative_name", "campaign_name"]
    names = (adsets.dropna(subset=["adset_name"]).groupby(keys)["adset_name"]
             .agg(lambda s: " / ".join(sorted(set(s)))).reset_index()
             if adsets is not None and not adsets.empty
             else pd.DataFrame(columns=[*keys, "adset_name"]))
    c = c.merge(names, on=keys, how="left", validate="many_to_one")
    c["adset_name"] = c["adset_name"].fillna("—")
    camp_gain = dict(zip(df["campaign_name"], df["gained"])) if not df.empty else {}
    alone, _ = creative_streams(df, creatives)
    lone = ({(r["campaign_name"], r["creative_name"]): r["gained"]
             for r in alone.to_dict("records")} if not alone.empty else {})
    rows = [_box("budget", "", 0, t("campaign_compare.tree_root", "Budget"), None, c, None)]
    order = c.groupby("campaign_name")["spend"].sum().sort_values(ascending=False).index
    for camp in order:
        g = c[c["campaign_name"] == camp]
        rows.append(_box(camp, "budget", 1, camp, camp, g, camp_gain.get(camp)))
        for adset, h in g.groupby("adset_name", sort=False):
            aid = f"{camp} › {adset}"
            rows.append(_box(aid, camp, 2, adset, camp, h, None))
            for r in h.sort_values("spend", ascending=False).to_dict("records"):
                rows.append(_box(f"{aid} › {r['creative_name']}", aid, 3, r["creative_name"],
                                 camp, pd.DataFrame([r]),
                                 lone.get((camp, r["creative_name"]))))
    return pd.DataFrame(rows, columns=cols)


def _box(box_id, parent, level, label, campaign, g: pd.DataFrame, gained) -> dict:
    """One box: its spend, its CPR (spend per result, conversion goals only), its gain."""
    spend, results = float(g["spend"].sum()), g["results"].sum(min_count=1)
    cpr = (spend / float(results)
           if bool(g["conv"].any()) and pd.notna(results) and results > 0 else None)
    return {"id": box_id, "parent": parent, "level": level, "label": str(label),
            "campaign": campaign, "spend": spend, "cpr": cpr,
            "gained": float(gained) if gained is not None and pd.notna(gained) else None}


_BOX_CHARS = 40   # a box label longer than this is cut; the hover keeps the whole name


def creative_tree_figure(tree: pd.DataFrame):
    """R590 — the second funnel, read top to bottom: budget, then each campaign's share of
    it, its ad sets, its creatives; each box says its spend, its CPR, its streams gained.
    Pure."""
    import plotly.graph_objects as go
    from src.dashboard.utils.formats import num
    from src.dashboard.utils.platform_colors import DISTINCT

    if tree.empty or len(tree) < 2:
        return None
    camps = list(dict.fromkeys(tree["campaign"].dropna()))
    colour = {c: DISTINCT[i % len(DISTINCT)] for i, c in enumerate(camps)}
    text = []
    for r in tree.to_dict("records"):
        line = f"{num(r['spend'], 0)} €"
        if pd.notna(r["cpr"]):
            line += f" · CPR {num(r['cpr'], 3)} €"
        if pd.notna(r["gained"]):
            line += "<br>" + t("campaign_compare.tree_gained", "{g} écoutes gagnées").format(
                g=f"{r['gained']:+,.0f}".replace(",", " "))
        text.append(line)
    fig = go.Figure(go.Icicle(
        # A creative run in five ad sets names all five: the box shows the start, the
        # hover the whole name (PNG read 2026-10-15, artist 1).
        ids=tree["id"], parents=tree["parent"],
        labels=[x if len(x) <= _BOX_CHARS else x[:_BOX_CHARS - 1] + "…" for x in tree["label"]],
        customdata=tree["label"],
        # Leaves carry the money, every box above is the sum of its children.
        values=[s if lv == 3 else 0 for s, lv in zip(tree["spend"], tree["level"])],
        branchvalues="remainder", text=text, texttemplate="<b>%{label}</b><br>%{text}",
        hovertemplate="<b>%{customdata}</b><br>%{text}<br><i>"
                      + t("campaign_compare.tree_cpr_note",
                          "CPR : dépense par résultat, un clic sortant ou une conversion")
                      + "</i><extra></extra>",
        tiling={"orientation": "v"}, sort=False, textfont={"size": 14},
        marker={"colors": ["#9E9E9E" if c is None else colour[c] for c in tree["campaign"]]}))
    fig.update_layout(height=520, margin={"t": 10, "b": 10, "l": 10, "r": 10})
    return fig


def creative_gains(db, artist_id: int, acct: str, acct_p: tuple) -> dict[str, dict]:
    """{creative: {gained, spend, campaign}} for the creatives that ran ALONE (R239 rule).

    R246 (fiche 34) — the creative page shows it beside the funnel, never as a funnel stage:
    streams gained are not nested under clicks (a title gains listens that no ad click
    brought), so as a stage they would widen the funnel."""
    data = load(db, artist_id, acct, acct_p)
    alone, _ = creative_streams(compare(data), data.get("creatives"))
    if alone is None or alone.empty:
        return {}
    return {r["creative_name"]: {"gained": r["gained"], "spend": r["spend"],
                                 "campaign": r["campaign_name"]}
            for r in alone.to_dict("records")}
