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



def _in_app_curve(out: Path) -> dict:
    return {"reason": "intégrée le 2026-09-28 sur ma reco (R301) — page Meta Ads, repliée sous "
                      "« Ce que chaque vague de campagnes a rapporté en écoutes » : voir sa fiche "
                      "dans ce dossier"}


def _in_app_hypeddit(out: Path) -> dict:
    return {"reason": "intégrée le 2026-09-28 sur ma reco (R301) — page Hypeddit : sous chaque "
                      "anneau de campagne, la pub Meta dépensée à ±14 jours de sa sortie. Les "
                      "visites, clics et taux par campagne y étaient déjà ; un second graphique "
                      "les aurait redits (R299)"}


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
     "v_meta_daily · v_s4a_song_daily · meta_impact.waves", _in_app_curve),
    ("clics", "Combien de clics sur la pub font une écoute gagnée (nouvelle)",
     "si un clic payé se transforme en écoute — sinon, le coût par clic n'est pas le bon "
     "chiffre à optimiser", "v_meta_campaign_daily · v_s4a_song_daily · meta_impact",
     _fig_clicks),
    ("hypeddit", "P6 — Hypeddit par campagne : visites, clics vers les plateformes, et la pub "
     "Meta autour de chaque sortie", "le lien intelligent convertit-il, et la pub y amène-t-elle "
     "du monde", "v_hypeddit_daily · v_meta_daily", _in_app_hypeddit),
]


#: My recommendation on each proposal (R298) — the owner decides, the PDF says what I would do.
RECO = {
    "campagnes": "déjà dans l'app (R291) : rien à décider.",
    "courbe": "gardée (R301) — la seule figure qui dit combien de temps l'effet dure. Une "
              "courbe qui monte AVANT le jour 0 est une sortie, pas la pub.",
    "clics": "ÉCARTÉE sur ma reco (R301) : tant que peu de vagues sortent du bruit, elle dit "
             "surtout « non concluant ». Dis-le en commentaire si « combien me coûte une écoute "
             "via Meta » est ta question — elle entre alors dans l'app.",
    "hypeddit": "gardée (R301), sous sa forme sans doublon : la pub autour de chaque sortie "
                "sous les anneaux existants de la page Hypeddit.",
}


def render(out: Path) -> list[dict]:
    """Draw every proposal; a proposal that cannot be drawn keeps its line with its reason."""
    figs = out / "proposals"
    figs.mkdir(exist_ok=True)
    done = []
    for pid, title, decision, data, build in PROPOSALS:
        entry = {"id": pid, "title": title, "decision": decision, "data": data,
                 "png": None, "reason": None, "finding": None, "reco": RECO.get(pid)}
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
