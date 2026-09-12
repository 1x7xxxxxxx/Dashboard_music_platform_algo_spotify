"""Valider ce qu'on CALCULE, pas seulement ce qu'on collecte.

Type: Utility
Uses: nothing (stdlib only — must be importable without Airflow)
Triggers: alert_monitor.check_metric_bounds, tools/metric_check.py
Depends on: —
Persists in: nothing

Le trou que ce module ferme
---------------------------
Ce dépôt valide la SOURCE avec soin. Quatre des cinq piliers de Moses/Gavish/Vorwerck
(*Data Quality Fundamentals*, p. 144) sont instrumentés — fraîcheur, volume,
distribution, schéma ; le lignage est écarté par ADR-012. Tous regardent les tables
brutes.

**Aucun ne regarde les nombres que le produit calcule.** Densmore le nomme
(*Data Pipelines Pocket Reference*, p. 218) :

    « Even if the source data passed validation earlier in a pipeline, it's always good
      practice to run validation on the data models that are built at the end of a
      pipeline. Three things to check: a metric within lower and upper bounds,
      row-count growth or reduction, and […] »

Mesuré le 2026-09-10 : la figure de l'accueil dessinait **23 251** écoutes là où la
fenêtre en contenait **8 490** — ×2,7. C'est exactement une métrique hors bornes, et
aucun contrôle ne pouvait la voir parce qu'aucun contrôle ne regarde de ce côté.

Ce que ce module vérifie, et pourquoi CELUI-LÀ
-----------------------------------------------
L'invariant le plus fort qu'on puisse écrire sans seuil arbitraire, donc sans calibrage
qui vieillit :

    pour une source QUOTIDIENNE, le compteur « depuis le début » DOIT égaler la somme
    de sa série quotidienne.

Les deux se lisent dans la même table, par deux chemins différents
(`_SQL_LIFETIME_SPOTIFY` et `_SQL_SPOTIFY` de `platform_timeseries`). Mesuré le
2026-09-10 sur l'artiste 1 : 163 088 des deux côtés, écart 0. Le jour où ils divergent,
l'un des deux chemins a changé de sens — et c'est exactement la classe de défaut que la
séance a trouvée trois fois.

Pour un compteur CUMULÉ (SoundCloud, YouTube), l'égalité est fausse par construction :
le compteur porte tout ce qui précède notre première collecte. On n'y vérifie donc que
le sens : la somme mesurée ne peut pas DÉPASSER le compteur.
"""
from __future__ import annotations

# Ce que chaque source rend comme valeur. La règle de contrôle en découle : elle n'est
# pas un réglage, c'est la nature de la donnée.
DAILY = "daily"                 # une quantité du jour (Spotify for Artists)
CUMULATIVE = "cumulative"       # un compteur qui ne redescend pas (SoundCloud, YouTube)

KINDS = {"spotify": DAILY, "soundcloud": CUMULATIVE, "youtube": CUMULATIVE}

# Une source quotidienne doit s'équilibrer À L'EURO PRÈS ; on tolère l'erreur de
# représentation flottante, rien de plus. Un écart relatif, ici, masquerait le défaut.
_EXACT_TOLERANCE = 1e-6


def disagreement(platform: str, lifetime, measured_sum) -> str | None:
    """Le désaccord entre les deux chemins, ou `None` s'il n'y en a pas.

    `None` en entrée veut dire « pas mesuré » et ne déclenche rien : on ne juge pas ce
    qu'on n'a pas lu — c'est la règle que le reste de la séance applique partout.
    """
    if lifetime is None or measured_sum is None:
        return None
    kind = KINDS.get(platform)
    if kind is None:
        return None

    if kind == DAILY:
        if abs(float(lifetime) - float(measured_sum)) > _EXACT_TOLERANCE:
            return (f"{platform} : le compteur « depuis le début » annonce "
                    f"{lifetime:,.0f} et la somme de la série quotidienne "
                    f"{measured_sum:,.0f}. Les deux lisent la même table : l'un des "
                    f"deux chemins a changé de sens.")
        return None

    # Cumulé : la somme des écarts mesurés ne peut pas dépasser le compteur, qui porte
    # en plus tout ce qui précède notre première collecte.
    if float(measured_sum) > float(lifetime) + _EXACT_TOLERANCE:
        return (f"{platform} : la somme des écarts mesurés ({measured_sum:,.0f}) "
                f"dépasse le compteur de la plateforme ({lifetime:,.0f}). Un cumul ne "
                f"redescend pas : la conversion cumul → quotidien invente du volume.")
    return None


def report(rows) -> list[str]:
    """`rows = [(platform, lifetime, measured_sum), …]` → les désaccords, nommés.

    Rendu tel quel à l'alerte : ADR-011 veut qu'une alerte nomme un symptôme et une
    action, jamais un code.
    """
    out = []
    for platform, lifetime, measured in rows or []:
        msg = disagreement(platform, lifetime, measured)
        if msg:
            out.append(msg)
    return out


def run(db) -> tuple[list[str], int]:
    """`(constats, locataires examinés)` — le contrôle entier, hors d'Airflow.

    Sorti de `alert_monitor.check_metric_bounds` le 2026-09-12, pour la raison que
    son voisin `gold_invariants.run` documente : un contrôle enfermé dans un DAG
    n'est exerçable que par Airflow. Le prédicat vivait déjà ici ; seule la boucle
    qui lit la base restait de l'autre côté, et c'est elle qui portait la question
    « sur quels locataires ? ».
    """
    from src.dashboard.utils.platform_timeseries import (
        daily_streams_by_platform, platform_totals,
    )

    tenants = [r[0] for r in db.fetch_query(
        "SELECT DISTINCT artist_id FROM s4a_song_timeline WHERE artist_id IS NOT NULL "
        "UNION SELECT DISTINCT artist_id FROM soundcloud_tracks_daily "
        "WHERE artist_id IS NOT NULL "
        "UNION SELECT DISTINCT artist_id FROM youtube_video_stats "
        "WHERE artist_id IS NOT NULL"
    ) or []]
    findings: list[str] = []
    for aid in tenants:
        lifetime = platform_totals(db, aid)
        series = daily_streams_by_platform(db, aid)
        rows = [(k, lifetime.get(k), sum(v for _, v in series.get(k, []) or []) or None)
                for k in KINDS]
        findings += [f"artiste {aid} — {msg}" for msg in report(rows)]
    return findings, len(tenants)
