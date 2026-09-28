"""R282 — chart PROPOSALS for the owner's marketing question, drawn on the review snapshot.

Type: Utility
Uses: the local snapshot `spotify_etl_review` (capture.point_at_snapshot), gold views
      v_meta_daily, v_meta_campaign_daily, v_meta_ad_daily, v_s4a_song_daily,
      v_hypeddit_daily, bronze s4a_song_playlist_adds ; plotly + kaleido (dev extra)
Triggers: tools/dev/charts_dossier/main.py (`make charts-dossier`), or directly:
          `python3 tools/dev/charts_dossier/proposals.py <out>` then `main.py --rebuild <out>`
Persists in: <out>/proposals/*.png and <out>/proposals.json — outside the repository

The owner's question (notes L167, L482): « qu'est-ce que nous apporte la campagne Meta Ads
sur nos streams ». Each proposal answers ONE decision and is drawn on real data so the owner
judges a chart, not a sentence. None is in the app: a proposal the owner keeps becomes a
roadmap row, with its gold view and its test (`tests/test_the_bronze_boundary_only_tightens.py`
refuses a new raw read in the app).

What these figures do NOT prove: a day with ads is also often a release week, so a lift
measured around a campaign is an association, never a causal effect — every figure says so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ARTIST = 1
MIN_POINTS = 10            # below this a figure is not drawn — the reason is printed instead
BEFORE_DAYS = 28


def lag_correlation(spend: pd.Series, streams: pd.Series, max_lag: int = 14) -> pd.Series:
    """Correlation of daily spend with the streams `lag` days LATER, streams detrended by
    their 28-day rolling median (a catalogue growing for a year correlates with anything).
    Both series indexed by day. Pure."""
    s = streams.asfreq("D").fillna(0)
    detrended = s - s.rolling(28, min_periods=7, center=True).median()
    sp = spend.reindex(s.index).fillna(0)
    return pd.Series({lag: sp.corr(detrended.shift(-lag)) for lag in range(max_lag + 1)})


def campaign_uplift(campaigns: pd.DataFrame, streams: pd.Series,
                    before_days: int = BEFORE_DAYS) -> pd.DataFrame:
    """Per campaign: streams/day DURING it against the `before_days` before it, and what one
    extra stream cost. `campaigns` has campaign_name, start, end, spend. Pure."""
    from src.dashboard.utils.ratios import per
    s = streams.asfreq("D").fillna(0)
    rows = []
    for c in campaigns.itertuples():
        during = s.loc[c.start:c.end]
        before = s.loc[c.start - pd.Timedelta(days=before_days):c.start - pd.Timedelta(days=1)]
        if during.empty or before.empty:
            continue
        lift = during.mean() - before.mean()
        extra = lift * len(during)
        rows.append({"campaign": c.campaign_name, "spend": float(c.spend),
                     "before": before.mean(), "during": during.mean(), "lift": lift,
                     "cost_per_extra_stream": per(c.spend, extra) if extra > 0 else None})
    return pd.DataFrame(rows)


def ad_fatigue(ads: pd.DataFrame) -> pd.DataFrame:
    """CTR by week of age since each ad's first day, weighted over ads. Pure."""
    from src.dashboard.utils.ratios import per_series
    a = ads.copy()
    a["week"] = (a["day"] - a.groupby("ad_id")["day"].transform("min")).dt.days // 7
    w = a.groupby("week", as_index=False)[["clicks", "impressions"]].sum()
    w["ads"] = a.groupby("week")["ad_id"].nunique().values
    w["ctr"] = per_series(w["clicks"], w["impressions"], 100)
    return w


def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Through the one door onto the database — pointed at the snapshot by capture.py."""
    from src.database.postgres_handler import PostgresHandler
    db = PostgresHandler.from_env_or_config()
    try:
        return db.fetch_df(sql, params)
    finally:
        db.close()


def _streams() -> pd.Series:
    df = _query("SELECT day, SUM(streams) AS streams FROM v_s4a_song_daily "
                "WHERE artist_id = %s AND song NOT ILIKE %s GROUP BY day ORDER BY day",
                (ARTIST, "%1x7xxxxxxx%"))
    return df.set_index(pd.to_datetime(df["day"]))["streams"].astype(float)


def _spend() -> pd.Series:
    df = _query("SELECT day, SUM(spend) AS spend FROM v_meta_daily WHERE artist_id = %s "
                "GROUP BY day ORDER BY day", (ARTIST,))
    return df.set_index(pd.to_datetime(df["day"]))["spend"].astype(float)


def _fig_lag(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    spend, streams = _spend(), _streams()
    streams = streams.loc[spend.index.min() - pd.Timedelta(days=30):
                          spend.index.max() + pd.Timedelta(days=30)]
    if (spend > 0).sum() < MIN_POINTS:
        return {"reason": f"{int((spend > 0).sum())} jour(s) de dépense Meta"}
    corr = lag_correlation(spend, streams)
    best = int(corr.idxmax())
    fig = go.Figure(go.Bar(x=corr.index, y=corr.values, marker_color=platform_color("meta")))
    fig.update_layout(xaxis_title="délai après le jour de dépense (jours)",
                      yaxis_title="corrélation dépense → écoutes Spotify")
    strength = "faible" if abs(corr[best]) < 0.3 else "net"
    return {"fig": fig, "finding": f"le lien le plus fort tombe à J+{best} "
            f"(corrélation {corr[best]:.2f}, lien {strength}), sur "
            f"{int((spend > 0).sum())} jours de dépense"}


def _fig_uplift(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    camp = _query("SELECT campaign_name, MIN(day) AS start, MAX(day) AS \"end\", "
                  "SUM(spend) AS spend FROM v_meta_campaign_daily WHERE artist_id = %s "
                  "GROUP BY campaign_name HAVING SUM(spend) > 0", (ARTIST,))
    camp["start"], camp["end"] = pd.to_datetime(camp["start"]), pd.to_datetime(camp["end"])
    up = campaign_uplift(camp, _streams())
    if len(up) < 2:
        return {"reason": f"{len(up)} campagne(s) mesurable(s)"}
    up = up.sort_values("spend", ascending=False).head(15).sort_values("lift")
    # A campaign followed by a DROP has no cost per extra stream: its bar says it (negative),
    # and a label drawn left of zero would sit on the campaign names.
    text = [f"{c:.3f} €/écoute" if pd.notna(c) else "" for c in up["cost_per_extra_stream"]]
    # Campaign names run to 200 characters (Meta targeting strings): cut, never wrapped.
    names = [n if len(n) <= 42 else n[:40] + "…" for n in up["campaign"]]
    fig = go.Figure(go.Bar(y=names, x=up["lift"], orientation="h", text=text,
                           textposition="outside", cliponaxis=False,
                           marker_color=platform_color("spotify")))
    fig.update_layout(xaxis_title=f"écoutes/jour pendant la campagne − les {BEFORE_DAYS} jours avant",
                      margin={"l": 290, "r": 110})
    fig.update_yaxes(automargin=True)
    paid = up.dropna(subset=["cost_per_extra_stream"])
    return {"fig": fig, "height": 120 + 32 * len(up), "finding":
            f"{len(paid)} campagne(s) sur {len(up)} suivies d'une hausse ; "
            + (f"coût médian {paid['cost_per_extra_stream'].median():.3f} € par écoute gagnée"
               if len(paid) else "aucune hausse mesurée")}


def _fig_cta(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    from src.dashboard.utils.ratios import per_series
    df = _query("SELECT COALESCE(call_to_action, 'non renseigné') AS bouton, SUM(spend) AS spend, "
                "SUM(clicks) AS clicks FROM v_meta_ad_daily WHERE artist_id = %s GROUP BY 1",
                (ARTIST,))
    df["cpc"] = per_series(df["spend"].astype(float), df["clicks"].astype(float))
    df = df.dropna(subset=["cpc"]).sort_values("cpc")
    if len(df) < 2:
        return {"reason": f"{len(df)} type(s) de bouton avec des clics"}
    fig = go.Figure(go.Bar(x=df["bouton"], y=df["cpc"], marker_color=platform_color("meta"),
                           text=[f"{int(c)} clics" for c in df["clicks"]]))
    fig.update_layout(yaxis_title="coût par clic (€)")
    return {"fig": fig, "finding": f"le bouton le moins cher : « {df.iloc[0]['bouton']} » "
            f"({df.iloc[0]['cpc']:.2f} € le clic)"}


def _fig_fatigue(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    ads = _query("SELECT ad_id, day, clicks, impressions FROM v_meta_ad_daily "
                 "WHERE artist_id = %s AND impressions > 0", (ARTIST,))
    if ads.empty:
        return {"reason": "aucune annonce avec des impressions"}
    ads["day"] = pd.to_datetime(ads["day"])
    w = ad_fatigue(ads)
    w = w[w["ads"] >= 3]                     # a week seen on fewer ads is one ad's story
    if len(w) < 3:
        return {"reason": f"{len(w)} semaine(s) d'âge portée(s) par 3 annonces ou plus"}
    fig = go.Figure(go.Scatter(x=w["week"], y=w["ctr"], mode="lines+markers",
                               marker_color=platform_color("meta"),
                               text=[f"{n} annonces" for n in w["ads"]]))
    fig.update_xaxes(dtick=1)
    fig.update_layout(xaxis_title="semaines depuis le lancement de l'annonce",
                      yaxis_title="taux de clic (%)")
    return {"fig": fig, "finding": f"taux de clic semaine 0 : {w.iloc[0]['ctr']:.2f} %, "
            f"semaine {int(w.iloc[-1]['week'])} : {w.iloc[-1]['ctr']:.2f} %"}


def _fig_playlist(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    # S4A gives ROLLING windows counted back from the day of the export (7d, 28d, 12m):
    # period_start/end are empty, so the 28-day window ends at `collected_at`.
    adds = _query("SELECT song, count AS adds, collected_at::date AS \"end\" "
                  "FROM s4a_song_playlist_adds WHERE artist_id = %s AND time_window = '28d' "
                  "AND song NOT ILIKE %s", (ARTIST, "%1x7xxxxxxx%"))
    if len(adds) < MIN_POINTS:
        return {"reason": f"{len(adds)} relevé(s) d'ajouts en playlist sur 28 jours"}
    daily = _query("SELECT song, day, streams FROM v_s4a_song_daily WHERE artist_id = %s",
                   (ARTIST,))
    daily["day"] = pd.to_datetime(daily["day"])
    adds["streams"] = [daily[(daily.song == r.song)
                             & (daily.day > pd.Timestamp(r.end) - pd.Timedelta(days=28))
                             & (daily.day <= pd.Timestamp(r.end))]["streams"].sum()
                       for r in adds.itertuples()]
    fig = go.Figure(go.Scatter(x=adds["adds"], y=adds["streams"], mode="markers",
                               text=adds["song"], marker_color=platform_color("spotify")))
    fig.update_layout(xaxis_title="ajouts en playlist sur 28 jours",
                      yaxis_title="écoutes Spotify sur les mêmes 28 jours")
    return {"fig": fig, "finding": f"{len(adds)} relevés de 28 jours sur "
            f"{adds['song'].nunique()} titres ; corrélation "
            f"{adds['adds'].astype(float).corr(adds['streams'].astype(float)):.2f} "
            "(portée par peu de titres : à relire avec les points)"}


def _fig_hypeddit(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    hyp = _query("SELECT day, SUM(visits) AS visits FROM v_hypeddit_daily WHERE artist_id = %s "
                 "GROUP BY day", (ARTIST,))
    if len(hyp) < MIN_POINTS:
        return {"reason": f"{len(hyp)} jour(s) Hypeddit dans l'instantané — trop peu pour une figure"}
    hyp["spend"] = [float(_spend().get(pd.Timestamp(d), 0.0)) for d in hyp["day"]]
    fig = go.Figure(go.Scatter(x=hyp["spend"], y=hyp["visits"], mode="markers",
                               marker_color=platform_color("hypeddit")))
    fig.update_layout(xaxis_title="dépense Meta du jour (€)", yaxis_title="visites Hypeddit")
    return {"fig": fig, "finding": f"{len(hyp)} jours ; corrélation "
            f"{hyp['spend'].corr(hyp['visits'].astype(float)):.2f}"}


#: (id, title, the decision it serves, the data it reads, builder)
PROPOSALS = [
    ("delai", "Combien de jours après la pub les écoutes bougent-elles ?",
     "à quel moment juger une campagne, et quand relancer", "v_meta_daily · v_s4a_song_daily",
     _fig_lag),
    ("campagnes", "Ce que chaque campagne a rapporté en écoutes, et le prix d'une écoute gagnée",
     "quelle campagne refaire, et combien payer une écoute", "v_meta_campaign_daily · v_s4a_song_daily",
     _fig_uplift),
    ("bouton", "Le coût par clic selon le bouton de l'annonce",
     "quel bouton mettre sur la prochaine annonce", "v_meta_ad_daily (call_to_action)", _fig_cta),
    ("fatigue", "La fatigue d'une annonce : le taux de clic semaine après semaine",
     "quand couper ou renouveler une créa", "v_meta_ad_daily (clics / impressions)", _fig_fatigue),
    ("playlists", "Les ajouts en playlist face aux écoutes de la même période",
     "une playlist a-t-elle payé", "s4a_song_playlist_adds · v_s4a_song_daily", _fig_playlist),
    ("hypeddit", "Les visites Hypeddit face à la dépense Meta du même jour",
     "le lien intelligent capte-t-il le trafic payé", "v_hypeddit_daily · v_meta_daily",
     _fig_hypeddit),
]


def render(out: Path) -> list[dict]:
    """Draw every proposal; a proposal that cannot be drawn keeps its line with its reason."""
    figs = out / "proposals"
    figs.mkdir(exist_ok=True)
    done = []
    for pid, title, decision, data, build in PROPOSALS:
        entry = {"id": pid, "title": title, "decision": decision, "data": data,
                 "png": None, "reason": None, "finding": None}
        try:
            res = build(out)
        except Exception as exc:          # noqa: BLE001 — one proposal never sinks the dossier
            res = {"reason": f"non dessinée : {type(exc).__name__}"}
        if res.get("fig") is not None:
            res["fig"].update_layout(template="plotly_white", title=None,
                                     margin={**{"t": 20, "b": 50, "r": 20},
                                             **(res["fig"].layout.margin.to_plotly_json() or {})})
            res["fig"].write_image(figs / f"{pid}.png", width=1000,
                                   height=res.get("height", 380), scale=1)
            entry["png"] = f"proposals/{pid}.png"
        entry["reason"], entry["finding"] = res.get("reason"), res.get("finding")
        done.append(entry)
    (out / "proposals.json").write_text(json.dumps(done, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return done


if __name__ == "__main__":
    import capture
    target = Path(sys.argv[1]).resolve()
    capture.point_at_snapshot()
    for e in render(target):
        print(f"{'✅' if e['png'] else '⚪'} {e['id']}: {e['finding'] or e['reason']}")
