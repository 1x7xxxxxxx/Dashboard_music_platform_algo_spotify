"""« Comparer mes campagnes » — the cross-campaign questions of « Tout mon funnel ».

Type: Feature
Uses: pandas, streamlit, src.dashboard.utils.campaign_funnel (streams_gained, best_lag)
Depends on: v_meta_campaign_daily, v_meta_ad_daily, v_s4a_song_daily, v_hypeddit_daily,
            campaign_track_mapping, track_platform_link
Triggers: views/meta_x_spotify.py (tab « 🏁 Comparer mes campagnes »)
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

from src.dashboard.utils.campaign_funnel import BASELINE_DAYS, best_lag, streams_gained
from src.dashboard.utils import charts
from src.dashboard.utils.i18n import t

_FAMILY = {
    "OUTCOME_ENGAGEMENT": "engagement", "POST_ENGAGEMENT": "engagement",
    "VIDEO_VIEWS": "engagement", "PAGE_LIKES": "engagement",
    "LINK_CLICKS": "trafic", "OUTCOME_TRAFFIC": "trafic",
    "CONVERSIONS": "conversion", "OUTCOME_SALES": "conversion",
    "OUTCOME_LEADS": "conversion",
}
MIN_PER_FAMILY = 2
# Below this, the « best » lag is the least bad of eight noises: 0.3 is the conventional
# floor of a weak positive correlation. A delay is named only above it (measured
# 2026-09-27, artist 1: « 6 j » came out of a correlation of −0.09).
MIN_LAG_CORR = 0.3


def objective_family(objective) -> str:
    """engagement · trafic · conversion · autre — Meta's objective, grouped. Pure."""
    return _FAMILY.get(str(objective or "").upper(), "autre")


def _df(db, sql: str, params: tuple) -> pd.DataFrame:
    try:
        return db.fetch_df(sql, params)
    except Exception:      # noqa: BLE001 — une source absente ne casse pas la comparaison
        return pd.DataFrame()


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
    tracks = _df(db, """
        SELECT DISTINCT ON (m.campaign_name) m.campaign_name, s4a.platform_title AS song
          FROM campaign_track_mapping m
          JOIN track_platform_link any_l
            ON any_l.artist_id = m.artist_id AND any_l.status = 'confirmed'
           AND TRIM(any_l.platform_title) = TRIM(m.track_name)
          JOIN track_platform_link s4a
            ON s4a.artist_id = any_l.artist_id AND s4a.match_key = any_l.match_key
           AND s4a.platform = 's4a' AND s4a.status = 'confirmed'
         WHERE m.artist_id = %s ORDER BY m.campaign_name""", (artist_id,))
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
        SELECT campaign_name, creative_name, SUM(spend) AS spend
          FROM v_meta_creative_daily WHERE artist_id = %s{acct}
         GROUP BY campaign_name, creative_name HAVING SUM(spend) > 0""", (artist_id, *acct_p))
    return {"daily": daily, "objective": objective, "tracks": tracks,
            "streams": streams, "store": store, "creatives": creatives}


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


def cohort_sentence(df: pd.DataFrame) -> str:
    """Engagement against traffic, in one sentence — or why it cannot be said. Pure."""
    m = df.dropna(subset=["cost_per_gained"]) if not df.empty else df
    med = {f: g["cost_per_gained"].median() for f, g in m.groupby("family")
           if len(g) >= MIN_PER_FAMILY} if not m.empty else {}
    if "engagement" in med and "trafic" in med:
        cheap, dear = sorted(("engagement", "trafic"), key=lambda f: med[f])
        return t("campaign_compare.cohort",
                 "Tes campagnes **{a}** ont acheté l'écoute gagnée moins cher que tes "
                 "campagnes **{b}** : {x} € contre {y} € (médianes).").format(
            a=cheap, b=dear, x=_eur(med[cheap]), y=_eur(med[dear]))
    counts = m["family"].value_counts().to_dict() if not m.empty else {}
    return t("campaign_compare.cohort_thin",
             "Engagement contre trafic : il faut au moins {n} campagnes mesurées de "
             "chaque sorte pour comparer — tu en as {e} en engagement et {tr} en trafic.").format(
        n=MIN_PER_FAMILY, e=counts.get("engagement", 0), tr=counts.get("trafic", 0))


def track_conversion(df: pd.DataFrame, store: pd.DataFrame) -> pd.DataFrame:
    """Per track: store clicks (Hypeddit), streams gained, streams gained per click. Pure."""
    if df.empty or store is None or store.empty:
        return pd.DataFrame()
    gained = df.dropna(subset=["gained", "song"]).groupby("song")["gained"].sum()
    out = store.assign(store_clicks=pd.to_numeric(store["store_clicks"], errors="coerce"))
    out["gained"] = out["song"].map(gained)
    out["per_click"] = out["gained"] / out["store_clicks"].where(out["store_clicks"] > 0)
    return out.sort_values("per_click", ascending=False, na_position="last")


def _eur(v) -> str:
    return f"{v:,.3f}".replace(",", " ").replace(".", ",")


def _fmt(v, digits: int = 0) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{digits}f}".replace(",", " ").replace(".", ",")


def _lag_text(lag) -> str:
    if not isinstance(lag, dict) or lag["corr"] < MIN_LAG_CORR:
        return "—"
    return t("campaign_compare.lag_days", "{n} j").format(n=lag["lag"])


def render(db, artist_id: int, acct: str, acct_p: tuple) -> None:
    """The tab body: the ranking, the cohort sentence, the tracks, the biases."""
    data = load(db, artist_id, acct, acct_p)
    df = compare(data)
    if df.empty:
        st.info(t("campaign_compare.empty", "Aucune campagne à comparer sur ce compte."))
        return
    st.markdown(t("campaign_compare.head",
                  "**Quelle campagne a acheté l'écoute la moins chère ?** — écoutes du "
                  "titre lié pendant la campagne, au-dessus de son niveau des {n} jours "
                  "d'avant.").format(n=BASELINE_DAYS))
    ranked = df.sort_values("cost_per_gained", na_position="last")
    st.dataframe(pd.DataFrame({
        t("campaign_compare.c_campaign", "Campagne"): ranked["campaign_name"],
        t("campaign_compare.c_track", "Titre lié"): ranked["song"].fillna("—"),
        t("campaign_compare.c_family", "Objectif"): ranked["family"],
        t("campaign_compare.c_spend", "Dépense (€)"): ranked["spend"].map(lambda v: _fmt(v, 2)),
        t("campaign_compare.c_gained", "Écoutes gagnées"): ranked["gained"].map(_fmt),
        t("campaign_compare.c_cost", "€ / écoute gagnée"):
            ranked["cost_per_gained"].map(lambda v: _fmt(v, 3)),
        t("campaign_compare.c_lag", "Délai pub → écoute"): ranked["lag"].map(_lag_text),
        t("campaign_compare.c_overlap", "Chevauche une autre"):
            ranked["overlap"].map(lambda b: "⚠️" if b else ""),
    }), hide_index=True, width="stretch")
    st.markdown(cohort_sentence(df))
    st.caption(t("campaign_compare.biases",
                 "Deux limites, écrites pour ne pas les oublier. ⚠️ = une autre campagne a "
                 "poussé le même titre pendant celle-ci ou ses {n} jours d'avant : les deux "
                 "réclament les mêmes écoutes, et le niveau « d'avant » contient déjà de la "
                 "pub. « — » = pas de titre lié confirmé, moins de 14 jours mesurés avant, "
                 "ou aucune écoute gagnée. Le délai n'apparaît que si la dépense ET les "
                 "écoutes ont varié sur au moins 14 jours : une campagne à budget constant "
                 "n'en a pas, et c'est normal.").format(n=BASELINE_DAYS))
    _render_tracks(df, data["store"])
    _render_track_funnel(df, data)
    _render_creatives(df, data.get("creatives"))
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
    st.dataframe(pd.DataFrame({
        t("campaign_compare.c_track", "Titre lié"): tracks["song"],
        t("campaign_compare.c_clicks", "Clics plateformes"): tracks["store_clicks"].map(_fmt),
        t("campaign_compare.c_gained", "Écoutes gagnées"): tracks["gained"].map(_fmt),
        t("campaign_compare.c_per_click", "Écoutes gagnées / clic"):
            tracks["per_click"].map(lambda v: _fmt(v, 2)),
    }), hide_index=True, width="stretch")


def _render_creatives(df: pd.DataFrame, creatives: pd.DataFrame) -> None:
    """R239 — streams gained PER CREATIVE, where it can be measured."""
    alone, split = creative_streams(df, creatives)
    st.markdown(t("campaign_compare.crea_head",
                  "**Quelle créa a rapporté des écoutes ?** — mesuré quand la créa a "
                  "tourné SEULE dans sa campagne : ses écoutes gagnées sont alors les "
                  "siennes, sans répartition supposée."))
    if not alone.empty:
        st.dataframe(pd.DataFrame({
            t("campaign_compare.c_crea", "Créa"): alone["creative_name"],
            t("campaign_compare.c_campaign", "Campagne"): alone["campaign_name"],
            t("campaign_compare.c_spend", "Dépense (€)"): alone["spend"].map(lambda v: _fmt(v, 2)),
            t("campaign_compare.c_gained", "Écoutes gagnées"): alone["gained"].map(_fmt),
            t("campaign_compare.c_cost", "€ / écoute gagnée"):
                alone["cost_per_gained"].map(lambda v: _fmt(v, 3)),
            t("campaign_compare.c_overlap", "Chevauche une autre"):
                alone["overlap"].map(lambda b: "⚠️" if b else ""),
        }), hide_index=True, width="stretch")
    st.caption(t("campaign_compare.crea_split",
                 "{n} campagne(s) ont fait tourner plusieurs créas ensemble : leurs écoutes "
                 "ne se séparent pas par créa. Pour mesurer une créa, lance-la seule dans sa "
                 "campagne, ou donne-lui son propre lien Hypeddit.").format(n=split))


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



# ── R246 (fiche 40) — the whole funnel per TRACK, comparable across up to five ────────
# Two CHAINS, not one funnel: a smart-link visit does not always come from an ad click
# (bio link, shares, organic) — measured 2026-09-27, visits exceed ad clicks on every track
# that has both. Chained, « ad click → platform click » would claim a conversion that the
# data does not hold. Each chain is nested inside itself; they sit side by side.
CHAINS = (
    ("meta", "Côté pub (Meta)", (("impressions", "Impressions de la pub"), ("link_clicks", "Clics sur la pub"))),
    ("hypeddit", "Côté smart link (Hypeddit)", (("visits", "Visites du smart link"), ("store_clicks", "Clics vers les plateformes"))),
)
FUNNEL_STAGES = tuple(st_ for _, _, chain in CHAINS for st_ in chain)
MAX_COMPARED = 5
from src.dashboard.utils.platform_colors import DISTINCT as _PALETTE   # noqa: E402


def track_funnel(data: dict, df: pd.DataFrame) -> pd.DataFrame:
    """One row per linked track: each funnel stage summed over its campaigns, and the
    streams gained. Impressions and clicks are additive across campaigns; reach is not
    (and is not here). Pure."""
    daily, tracks = data["daily"], data["tracks"]
    if daily is None or daily.empty or tracks is None or tracks.empty:
        return pd.DataFrame()
    d = daily.merge(tracks, on="campaign_name", validate="many_to_one").dropna(subset=["song"])
    for c in ("impressions", "link_clicks"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    meta = d.groupby("song")[["impressions", "link_clicks"]].sum(min_count=1)
    store = data["store"].set_index("song") if not data["store"].empty else pd.DataFrame()
    out = meta.join(store[["visits", "store_clicks"]] if not store.empty else None, how="left")
    gained = df.dropna(subset=["song"]).groupby("song")["gained"].sum(min_count=1) \
        if not df.empty else pd.Series(dtype=float)
    out["gained"] = gained
    return out.apply(pd.to_numeric, errors="coerce").reset_index()


def nested_stages(rows: pd.DataFrame, stages=FUNNEL_STAGES) -> tuple[list[str], list[str]]:
    """(stages kept, stages dropped) of ONE chain: a stage enters only if it is measured for
    every compared track and never exceeds the stage before it — a funnel does not widen
    (`test_a_creative_funnel_never_widens`). Pure."""
    kept, dropped = [], []
    for col, _ in stages:
        vals = pd.to_numeric(rows[col], errors="coerce") if col in rows else None
        if vals is None or vals.isna().any():
            dropped.append(col)
            continue
        if kept and (vals > pd.to_numeric(rows[kept[-1]], errors="coerce")).any():
            dropped.append(col)
            continue
        kept.append(col)
    return kept, dropped


def track_funnel_figure(rows: pd.DataFrame, kept_by_chain: dict[str, list[str]]):
    """Stages top to bottom, one bar per track, on a LOG axis — a 1 % click rate is
    invisible on a linear funnel (render, 2026-09-27). The « % » links a stage only to the
    one before it IN ITS CHAIN: nothing claims that an ad click became a platform click."""
    import plotly.graph_objects as go
    names = dict(FUNNEL_STAGES)
    order = [c for key, _, _ in CHAINS for c in kept_by_chain.get(key, [])]
    prev = {c: (chain_kept[i - 1] if i else None)
            for chain_kept in kept_by_chain.values() for i, c in enumerate(chain_kept)}
    labels = {c: t(f"campaign_compare.stage_{c}", names[c]) for c in order}
    fig = go.Figure()
    for j, r in enumerate(rows.to_dict("records")):
        text = []
        for c in order:
            share = (f" · {100 * r[c] / r[prev[c]]:.1f} %".replace(".", ",")
                     if prev[c] and r[prev[c]] else "")
            text.append(f"{r[c]:,.0f}".replace(",", " ") + share)
        fig.add_trace(go.Bar(y=[labels[c] for c in order], x=[r[c] for c in order],
                             orientation="h", name=str(r["song"])[:40], text=text,
                             textposition="outside", cliponaxis=False,
                             marker_color=_PALETTE[j % len(_PALETTE)]))
    fig.update_layout(barmode="group", height=110 * len(order) + 140,
                      xaxis=dict(type="log", title=t("campaign_compare.log_axis",
                                                     "Volume (échelle log : chaque trait ×10)")),
                      yaxis=dict(autorange="reversed", automargin=True),
                      legend=dict(orientation="h", y=-0.2), margin=dict(r=90))
    return fig


def _render_track_funnel(df: pd.DataFrame, data: dict) -> None:
    tf = track_funnel(data, df)
    if tf.empty:
        return
    st.markdown(t("campaign_compare.funnel_head",
                  "**Tout le parcours, titre par titre** — de l'impression de la pub au clic "
                  "vers les plateformes, pour comparer jusqu'à {n} titres.").format(n=MAX_COMPARED))
    songs = tf.sort_values("impressions", ascending=False, na_position="last")["song"].tolist()
    pick = st.multiselect(t("campaign_compare.funnel_pick", "Titres à comparer"), songs,
                          default=songs[:3], max_selections=MAX_COMPARED, key="cmp_funnel")
    rows = tf[tf["song"].isin(pick)]
    if rows.empty:
        return
    kept_by_chain, dropped = {}, []
    for key, _, chain in CHAINS:
        kept, drop = nested_stages(rows, chain)
        kept_by_chain[key] = kept
        dropped += drop
    if any(len(k) >= 2 for k in kept_by_chain.values()):
        charts.plotly_chart(track_funnel_figure(rows, kept_by_chain), width="stretch")
    names = dict(FUNNEL_STAGES)
    st.caption(t("campaign_compare.funnel_chains",
                 "Deux outils, deux chaînes : une visite du smart link ne vient pas toujours "
                 "d'un clic sur la pub (lien en bio, partages), donc les deux côtés ne se "
                 "suivent pas — chacun se lit de haut en bas."))
    if dropped:
        st.caption(t("campaign_compare.funnel_dropped",
                     "Étape(s) retirée(s) : {s} — non mesurée pour un des titres, ou plus grande "
                     "que l'étape d'avant.").format(
            s=", ".join(t(f"campaign_compare.stage_{c}", names[c]) for c in dropped)))
    gains = " · ".join(f"{r['song'][:30]} : {_fmt(r['gained'])}" for r in rows.to_dict("records"))
    st.caption(t("campaign_compare.funnel_gained",
                 "Écoutes gagnées pendant les campagnes du titre (au-dessus des 28 jours d'avant, "
                 "hors parcours car une écoute ne vient pas toujours d'un clic) : {g}").format(g=gains))
