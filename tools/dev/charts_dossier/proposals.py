"""R282 — chart PROPOSALS for the owner's marketing question, drawn on the review snapshot.

Type: Utility
Uses: the local snapshot `spotify_etl_review` (capture.point_at_snapshot), gold views
      v_meta_daily, v_meta_campaign_daily, v_s4a_song_daily, v_hypeddit_daily ;
      src.dashboard.utils.meta_impact (waves, verdict_for) ; plotly + kaleido (dev extra)
Triggers: tools/dev/charts_dossier/main.py (`make charts-dossier`), or directly:
          `python3 tools/dev/charts_dossier/proposals.py <out>` then `main.py --rebuild <out>`
Persists in: <out>/proposals/*.png and <out>/proposals.json — outside the repository

The owner's question (notes L167, L482): « qu'est-ce que nous apporte la campagne Meta Ads
sur nos streams ». Each proposal answers ONE decision and is drawn on real data so the owner
judges a chart, not a sentence. A proposal the owner keeps becomes a roadmap row, with its
gold view and its test.

Owner's review, 2026-09-28: P2 kept (now in the app, R291 — judged per WAVE of campaigns);
the CTA button, ad fatigue and playlist proposals REFUSED (no decision follows); the lag bars
not understood — replaced by the stream curve around each wave; Hypeddit redrawn per
CAMPAIGN (it carries one total per campaign, not days). Every figure reuses the waves and
the refusals of `meta_impact` — never a second definition of the same claim.

What these figures do NOT prove: a wave often coincides with a release, so a lift is an
association, never a causal effect — every figure says so.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ARTIST = 1
MIN_POINTS = 3             # below this a figure is not drawn — the reason is printed instead
BEFORE_DAYS = 28
AFTER_DAYS = 42
#: Below this average before a wave, an index is a division by almost nothing: the first
#: wave of artist 1 started before its first release, and read « indice 1 332 800 ».
MIN_BASE_PER_DAY = 10.0


def event_study(series: pd.Series, starts: list[tuple[str, dt.date]],
                before: int = BEFORE_DAYS, after: int = AFTER_DAYS,
                min_base: float = MIN_BASE_PER_DAY) -> pd.DataFrame:
    """Streams around each wave start, as an index (100 = the average of the `before` days
    ahead of it), MEASURED days only. Columns: wave, offset (days), index. Pure."""
    idx = pd.to_datetime(pd.Series(series.index)).dt.date
    s = pd.Series(series.values, index=idx).dropna()
    rows = []
    for label, start in starts:
        base = s[(s.index >= start - dt.timedelta(days=before)) & (s.index < start)]
        if base.empty or base.mean() < min_base:
            continue
        win = s[(s.index >= start - dt.timedelta(days=before))
                & (s.index <= start + dt.timedelta(days=after))]
        rows += [{"wave": label, "offset": (d - start).days, "index": v / base.mean() * 100}
                 for d, v in win.items()]
    return pd.DataFrame(rows, columns=["wave", "offset", "index"])


def streams_per_click(gained: float | None, clicks: float) -> float | None:
    """Streams gained for one link click on the ads — None when nothing was gained. Pure."""
    from src.dashboard.utils.ratios import per
    return per(gained, clicks) if gained and gained > 0 else None


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


def _waves() -> list:
    """[(wave, names, verdict)] — the SAME waves and refusals as the app (R291)."""
    from src.dashboard.utils import meta_impact as mi
    spend = _query("SELECT ad_account_id, campaign_name, day, spend FROM v_meta_daily "
                   "WHERE artist_id = %s", (ARTIST,))
    grouped = mi.waves(mi.campaigns(spend))
    everyone = [w for w, _ in grouped]
    series = _streams()
    return [(w, n, mi.verdict_for(w, everyone, series, dt.date.today(), mi.STREAMS))
            for w, n in grouped]


def _label(w, names) -> str:
    return f"{w.start:%d/%m/%y} · {len(names)} camp."


def _fig_curve(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import DISTINCT
    waves = _waves()
    es = event_study(_streams(), [(_label(w, n), w.start) for w, n, _ in waves])
    dropped = len(waves) - es["wave"].nunique()
    if es["wave"].nunique() < 1:
        return {"reason": "aucune vague avec 28 jours d'écoutes mesurés avant elle"}
    fig = go.Figure()
    for i, (lab, g) in enumerate(es.groupby("wave", sort=False)):
        fig.add_trace(go.Scatter(x=g["offset"], y=g["index"], mode="lines", name=lab,
                                 line=dict(color=DISTINCT[i % len(DISTINCT)], width=2)))
    fig.add_hline(y=100, line_dash="dot", line_color="#999")
    fig.add_vline(x=0, line_dash="dash", line_color="#999")
    fig.update_layout(xaxis_title="jours depuis le début de la vague (0 = premier euro)",
                      yaxis_title="écoutes / jour (100 = les 28 jours avant)",
                      legend=dict(orientation="h", y=-0.25, x=0))
    peak = es[es["offset"] >= 0].sort_values("index", ascending=False).head(1)
    note = (f" ; {dropped} vague(s) écartée(s) : moins de {MIN_BASE_PER_DAY:.0f} écoutes/jour "
            "avant elles, un indice n'y voudrait rien dire") if dropped else ""
    return {"fig": fig, "height": 420, "finding": (
        f"{es['wave'].nunique()} vague(s) ; le plus haut : indice {peak['index'].iloc[0]:.0f} "
        f"à J+{int(peak['offset'].iloc[0])} ({peak['wave'].iloc[0]})" + note) if not peak.empty
        else f"{es['wave'].nunique()} vague(s){note}"}


def _fig_clicks(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    clicks = _query("SELECT day, SUM(link_clicks) AS clicks FROM v_meta_campaign_daily "
                    "WHERE artist_id = %s GROUP BY day", (ARTIST,))
    clicks["day"] = pd.to_datetime(clicks["day"]).dt.date
    rows = []
    for w, n, v in _waves():
        c = float(clicks[(clicks["day"] >= w.start) & (clicks["day"] <= w.end)]["clicks"].sum())
        gained = (v.lift_per_day * ((w.end - w.start).days + 1)
                  if v.conclusive and v.eur_per_listener_day is not None else None)
        rows.append((_label(w, n), c, streams_per_click(gained, c), v.text))
    judged = [r for r in rows if r[2] is not None]
    if not judged:
        return {"reason": "aucune vague au-dessus du bruit : pas d'écoute gagnée à rapporter"}
    fig = go.Figure(go.Bar(
        x=[r[0] for r in rows], y=[r[2] or 0 for r in rows],
        text=[f"{r[2]:.2f} écoute/clic · {r[1]:,.0f} clics".replace(",", " ") if r[2]
              else "non concluant" for r in rows],
        textposition="outside", cliponaxis=False, marker_color=platform_color("spotify")))
    fig.update_layout(yaxis_title="écoutes gagnées par clic sur la pub")
    return {"fig": fig, "finding": f"{len(judged)} vague(s) jugée(s) sur {len(rows)}"}


def _fig_hypeddit(out: Path) -> dict:
    import plotly.graph_objects as go
    from src.dashboard.utils.platform_colors import platform_color
    from src.dashboard.utils.ratios import per
    hyp = _query("SELECT campaign_name, day, SUM(visits) AS visits, SUM(clicks) AS clicks "
                 "FROM v_hypeddit_daily WHERE artist_id = %s GROUP BY 1, 2 ORDER BY 2",
                 (ARTIST,))
    if len(hyp) < MIN_POINTS:
        return {"reason": f"{len(hyp)} campagne(s) Hypeddit — trop peu pour une figure"}
    spend = _query("SELECT day, SUM(spend) AS spend FROM v_meta_daily WHERE artist_id = %s "
                   "GROUP BY day", (ARTIST,))
    spend["day"] = pd.to_datetime(spend["day"]).dt.date
    # Hypeddit carries ONE total per campaign, dated on its release: Meta's spend is read on
    # the 14 days on each side of that date.
    hyp["meta"] = [float(spend[(spend["day"] >= d - dt.timedelta(days=14))
                               & (spend["day"] <= d + dt.timedelta(days=14))]["spend"].sum())
                   for d in pd.to_datetime(hyp["day"]).dt.date]
    names = [n if len(n) <= 34 else n[:32] + "…" for n in hyp["campaign_name"]]
    fig = go.Figure([
        go.Bar(y=names, x=hyp["visits"], name="visites", orientation="h",
               marker_color="#b0dde5"),
        go.Bar(y=names, x=hyp["clicks"], name="clics vers les plateformes", orientation="h",
               marker_color=platform_color("hypeddit"),
               text=[f"{per(c, v, 100):.0f} % · pub autour : {m:,.0f} €".replace(",", " ")
                     for c, v, m in zip(hyp["clicks"], hyp["visits"], hyp["meta"])],
               textposition="outside", cliponaxis=False, textfont=dict(size=12))])
    fig.update_layout(barmode="group", xaxis_title="par campagne", margin={"r": 180},
                      legend=dict(orientation="h", y=-0.2, x=0))
    fig.update_yaxes(automargin=True, autorange="reversed")
    best = hyp.assign(rate=[per(c, v) for c, v in zip(hyp["clicks"], hyp["visits"])]
                      ).sort_values("rate", ascending=False).iloc[0]
    return {"fig": fig, "height": 420, "finding": (
        f"{len(hyp)} campagnes ; meilleure conversion : « {best['campaign_name']} » "
        f"({best['rate']:.0%})")}


def _integrated(out: Path) -> dict:
    return {"reason": "gardée par toi le 2026-09-28 — elle est maintenant DANS l'app : page "
                      "Meta Ads, « Ce que chaque vague de campagnes a rapporté en écoutes » "
                      "(R291), jugée par vague de campagnes"}


#: (id, title, the decision it serves, the data it reads, builder)
PROPOSALS = [
    ("campagnes", "P2 — Ce que chaque campagne a rapporté en écoutes, et le prix d'une écoute "
     "gagnée", "quelle campagne refaire, et combien payer une écoute", "R291", _integrated),
    ("courbe", "La courbe des écoutes autour de chaque vague de pub (remplace P1)",
     "combien de temps l'effet dure, donc quand juger une campagne et quand relancer — "
     "P1 disait « le lien est le plus fort à J+3 » en barres de corrélation ; ici on voit la "
     "courbe elle-même. Aucune figure de l'app ne la montre : la page Meta × Spotify (base "
     "100) suit UNE campagne choisie, pas toutes les vagues superposées",
     "v_meta_daily · v_s4a_song_daily · meta_impact.waves", _fig_curve),
    ("clics", "Combien de clics sur la pub font une écoute gagnée (nouvelle)",
     "si un clic payé se transforme en écoute — sinon, le coût par clic n'est pas le bon "
     "chiffre à optimiser", "v_meta_campaign_daily · v_s4a_song_daily · meta_impact",
     _fig_clicks),
    ("hypeddit", "P6 — Hypeddit par campagne : visites, clics vers les plateformes, et la pub "
     "Meta autour de chaque sortie", "le lien intelligent convertit-il, et la pub y amène-t-elle "
     "du monde", "v_hypeddit_daily · v_meta_daily", _fig_hypeddit),
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
