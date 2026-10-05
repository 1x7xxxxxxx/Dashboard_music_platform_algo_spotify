"""Age brackets — CPR and efficiency per bracket, and the finding they support. Pure.

Type: Utility
Uses: pandas, src.dashboard.utils.ratios
Triggers: views/meta_cpr_optimizer.py (age affinity in the score),
  views/meta_breakdowns.py (the age finding, free tier)
Depends on: rows of meta_insights_performance_*age (age_range, spend, results)
Persists in: nothing

R409 (owner, 2026-10-05): « la tranche d'âge va dans la vue croisée free, ce sont des
données déjà accessibles sur Meta Ads ». The finding moved from the Premium CPR
Optimizer to the free breakdowns; the affinity stays in the Premium score. Both read
THIS computation, so the bracket the free page calls cheapest is the one the score
rewards.
"""
from __future__ import annotations

import pandas as pd


def brackets(rows: pd.DataFrame) -> pd.DataFrame:
    """Per `age_range`: spend, results, cpr and `efficacite` (median CPR ÷ CPR).

    A bracket needs spend AND results to have a CPR: « Unknown » carries 0 € and 7
    results, and a zero cost is an absence of cost, not a low one. `efficacite` is
    absent when no median CPR can be computed.
    """
    from src.dashboard.utils.ratios import per_series      # R258 — one definition

    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows.copy()
    rows['spend'] = pd.to_numeric(rows['spend'], errors='coerce').fillna(0.0)
    rows['results'] = pd.to_numeric(rows['results'], errors='coerce').fillna(0)
    par = rows.groupby('age_range', as_index=False)[['spend', 'results']].sum()
    par['cpr'] = per_series(par['spend'].where(par['spend'] > 0), par['results'])
    mediane = par['cpr'].median()
    if pd.isna(mediane) or mediane <= 0:
        return par
    par['efficacite'] = mediane / par['cpr']
    return par


def finding(par: pd.DataFrame) -> dict | None:
    """Cheapest and dearest bracket, how much cheaper, and the spend share on brackets
    worse than the median — None under two measured brackets."""
    if par is None or par.empty or 'efficacite' not in par:
        return None
    d = par.dropna(subset=['cpr'])
    d = d[d['cpr'] > 0].sort_values('cpr')
    if len(d) < 2:
        return None
    best, worst = d.iloc[0], d.iloc[-1]
    total = d['spend'].sum()
    return {"best": best['age_range'], "cb": float(best['cpr']),
            "worst": worst['age_range'], "cw": float(worst['cpr']),
            "ratio": (1 - best['cpr'] / worst['cpr']) * 100,
            "part": float(d[d['efficacite'] < 1]['spend'].sum() / total * 100) if total else 0.0}
