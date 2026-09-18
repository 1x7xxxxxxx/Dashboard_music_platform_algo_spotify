#!/usr/bin/env python3
"""Valider les nombres que le produit CALCULE, à la main.

Type: Utility
Uses: src.utils.metric_bounds, src.dashboard.utils.platform_timeseries
Triggers: `make metric-check`
Persists in: nothing

Le jumeau manuel de `alert_monitor.check_metric_bounds`. Il lit les DEUX chemins que le
tableau de bord emploie réellement et les confronte : pour une source quotidienne, le
compteur « depuis le début » doit égaler la somme de sa série ; pour un compteur cumulé,
la somme mesurée ne peut pas le dépasser.

Sortie ≠ 0 dès qu'un désaccord existe, pour pouvoir servir de signature.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dashboard.utils.platform_timeseries import (  # noqa: E402
    daily_streams_by_platform, platform_totals,
)
from src.database.postgres_handler import PostgresHandler  # noqa: E402
from src.utils.metric_bounds import KINDS, report  # noqa: E402


def main() -> int:
    db = PostgresHandler.from_env_or_config()
    if db is None:
        print("❌ base injoignable. Lancer : make up")
        return 2

    tenants = [r[0] for r in db.fetch_query(
        "SELECT DISTINCT artist_id FROM s4a_song_timeline WHERE artist_id IS NOT NULL "
        "UNION SELECT DISTINCT artist_id FROM soundcloud_tracks_daily WHERE artist_id IS NOT NULL "
        "UNION SELECT DISTINCT artist_id FROM youtube_video_stats WHERE artist_id IS NOT NULL"
    ) or []]

    findings = []
    for aid in sorted(tenants):
        # ISOLEMENT PAR LOCATAIRE — ajouté le 2026-09-18 (R132). Le jumeau en ligne de
        # commande de `src/utils/metric_bounds.py`, corrigé le même jour pour la même
        # cause. Ici un plantage est VISIBLE (l'outil se lance à la main), mais il
        # arrête le contrôle au premier locataire illisible : les suivants ne sont pas
        # examinés, et l'opérateur lit un rapport partiel comme un rapport complet.
        try:
            lifetime = platform_totals(db, aid)
            series = daily_streams_by_platform(db, aid)
        except Exception as exc:      # noqa: BLE001 — isolement par locataire
            findings.append(
                f"artiste {aid} — lecture impossible ({type(exc).__name__}) : ce "
                "locataire n'a pas pu être contrôlé, les autres l'ont été")
            print(f"  artiste {aid:>4}  ❌ illisible ({type(exc).__name__})")
            continue
        rows = [(k, lifetime.get(k), sum(v for _, v in series.get(k, []) or []) or None)
                for k in KINDS]
        for msg in report(rows):
            findings.append(f"artiste {aid} — {msg}")
        for k in KINDS:
            lt = lifetime.get(k)
            ms = sum(v for _, v in series.get(k, []) or []) or None
            print(f"  artiste {aid:>4}  {k:11} compteur={_f(lt):>12}  mesuré={_f(ms):>12}")

    print()
    if findings:
        print(f"❌ {len(findings)} désaccord(s) :")
        for f in findings:
            print("   -", f)
        return 1
    print(f"✅ {len(tenants)} locataire(s) — les deux chemins de calcul s'accordent.")
    return 0


def _f(v) -> str:
    return "—" if v is None else f"{v:,.0f}"


if __name__ == "__main__":
    sys.exit(main())
