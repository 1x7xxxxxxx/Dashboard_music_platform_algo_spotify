"""La collecte par artiste — ce que le mail du soir dit, lisible sans le mail (R418).

Type: Sub
Uses: src.utils.collection_outcomes (collection_failures), src.utils.artist_readiness
      (readiness_many, red_platforms, stalled_platforms, is_stalled),
      src.dashboard.utils.status_matrix (read_failed_probes_many)
Triggers: views/admin.py (section « 🩺 Santé » → « 🔴 Collecte par artiste »)
Persists in: nothing — reads etl_run_log, saas_artists, artist_credentials,
             tenant_platform_probe and the freshness tables

The owner deletes the evening mail, so its « 🔴 NE COLLECTE PAS » section was read
nowhere. This screen reads the SAME functions the alert_monitor DAG calls — never a
second query that would drift — recomputed at render time: it says « now », not « at
23:00 ». Two differences with the mail, both stated on screen: no live API probe (the
remembered nightly verdicts are replayed instead), and the canary is not covered (it
has its own check, `check_canary_health`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t

logger = logging.getLogger(__name__)


def _human_tenants(db) -> list[tuple]:
    """Active non-canary, non-sandbox tenants — `get_active_artists(exclude_canaries=True)`
    on THIS render's connection (rule 9: one connection per render)."""
    from src.utils.tenant_kind import EXCLUDE_NON_HUMAN

    return db.fetch_query(
        "SELECT id, name, created_at FROM saas_artists WHERE active = TRUE"
        + EXCLUDE_NON_HUMAN + " ORDER BY id") or []


def _replayed(failed: dict) -> dict:
    """{aid: {platform: (ok, message)}} — the probe contract of `_matrix`, dated."""
    return {aid: {p: (False, f"{reason} (mesuré le {when:%d/%m %H:%M})" if when else reason)
                  for p, (_ok, reason, when) in plats.items()}
            for aid, plats in failed.items()}


def readiness_snapshot(db, now: datetime) -> dict:
    """{'red': [...], 'stalled': [...], 'unreadable': [...]} for every human tenant."""
    from src.dashboard.utils.status_matrix import read_failed_probes_many
    from src.utils.artist_readiness import (
        is_stalled, readiness_many, red_platforms, stalled_platforms)

    tenants = _human_tenants(db)
    ids = [r[0] for r in tenants]
    matrices = readiness_many(db, ids, probes=_replayed(read_failed_probes_many(db, ids)))
    out: dict = {"red": [], "stalled": [], "unreadable": []}
    for aid, name, created_at in tenants:
        matrix = matrices.get(aid)
        if matrix is None:
            # Named, never dropped: a tenant we could not read is not a tenant who is fine.
            out["unreadable"].append(f"{name} (#{aid})")
            continue
        out["red"] += [{"artist_id": aid, "artist_name": name, **m}
                       for m in red_platforms(matrix)]
        if is_stalled(created_at, now):
            todo = stalled_platforms(matrix)
            if todo:
                out["stalled"].append({"artist_id": aid, "artist_name": name,
                                       "platforms": [m["label"] for m in todo]})
    return out


def _render_failures(db) -> None:
    from src.utils.collection_outcomes import (
        WINDOW_H, collection_failures, describe_failure_age, split_by_age)

    st.markdown(t("admin.coll_fail_h", "#### ❌ Échecs de collecte (dernières {h} h)")
                .format(h=WINDOW_H))
    try:
        rows = collection_failures(db)
    except Exception as e:  # noqa: BLE001 — « illisible » ne se lit jamais « rien n'a échoué »
        logger.warning("collection_failures: %s", type(e).__name__)
        st.error(t("admin.coll_fail_err",
                   "❌ Le journal des collectes est illisible ({e}) — "
                   "ce n'est PAS « aucun échec ».").format(e=type(e).__name__))
        return
    if not rows:
        st.success(t("admin.coll_fail_none", "✅ Aucun échec de collecte."))
        return
    fresh, stuck = split_by_age(rows)
    st.caption(t("admin.coll_fail_count",
                 "{n} cette nuit · {m} bloqué(s) de longue date (geste humain attendu)")
               .format(n=len(fresh), m=len(stuck)))
    st.dataframe(pd.DataFrame([{
        t("admin.coll_col_artist", "Artiste"): f"{r['artist_name']} (#{r['artist_id']})",
        t("admin.coll_col_platform", "Plateforme"): r["platform"],
        t("admin.coll_col_since", "Depuis"): describe_failure_age(r),
        t("admin.coll_col_cause", "Cause"): r["reason"],
    } for r in rows]), hide_index=True, width="stretch")


def _render_readiness(db) -> None:
    try:
        snap = readiness_snapshot(db, datetime.now(timezone.utc))
    except Exception as e:  # noqa: BLE001 — same contract as the ledger above
        logger.warning("readiness_snapshot: %s", type(e).__name__)
        st.error(t("admin.coll_ready_err",
                   "❌ L'état des connexions est illisible ({e}).").format(e=type(e).__name__))
        return
    st.markdown(t("admin.coll_red_h", "#### 🔴 Connecté, mais rien n'arrive"))
    if snap["red"]:
        st.dataframe(pd.DataFrame([{
            t("admin.coll_col_artist", "Artiste"): f"{m['artist_name']} (#{m['artist_id']})",
            t("admin.coll_col_platform", "Plateforme"): m["label"],
            t("admin.coll_col_state", "État"): f"{m['icon']} {m['status_label']}",
            t("admin.coll_col_action", "Prochaine action"): m["next_action"],
        } for m in snap["red"]]), hide_index=True, width="stretch")
    else:
        st.success(t("admin.coll_red_none", "✅ Chaque plateforme connectée reçoit des données."))
    st.markdown(t("admin.coll_stalled_h", "#### ⚪ Inscrit depuis 7 jours ou plus, rien de connecté"))
    for s in snap["stalled"]:
        st.markdown(f"- **{s['artist_name']}** (#{s['artist_id']}) — "
                    + ", ".join(s["platforms"]))
    if not snap["stalled"]:
        st.caption(t("admin.coll_stalled_none", "Personne."))
    if snap["unreadable"]:
        st.warning(t("admin.coll_unreadable", "⚠️ Illisibles : {names}")
                   .format(names=", ".join(snap["unreadable"])))


def render(db) -> None:
    st.subheader(t("admin.coll_title", "🔴 Collecte par artiste"))
    st.caption(t("admin.coll_caption",
                 "État **maintenant**, recalculé à chaque affichage — le mail du soir dit la "
                 "même chose à 23 h. Les échecs couvrent tout locataire du journal de collecte ; "
                 "les connexions, les artistes actifs hors canari et bac à sable (le canari a "
                 "son propre contrôle). Aucun appel API ici : les causes affichées sont les "
                 "derniers verdicts mesurés la nuit."))
    _render_failures(db)
    _render_readiness(db)
