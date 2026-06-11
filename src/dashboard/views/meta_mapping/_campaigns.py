"""Meta campaigns tab — auto-suggestions (title + campaign-start proximity), backlog,
manual add → campaign_track_mapping (+ campaign_mapping_rejected tombstone).

Type: Sub
Uses: track_mapping_suggest (rank_campaign_candidates, confidence_badge),
      track_matching (canonical_song)
Persists in: campaign_track_mapping, campaign_mapping_rejected (PostgreSQL spotify_etl)
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.utils.track_matching import canonical_song
from src.utils.track_mapping_suggest import confidence_badge, rank_campaign_candidates

from ._common import _S4A_FILTER, _mutex_checkboxes


def _load_unmapped_campaigns(db, artist_id: int):
    # Pending = neither already mapped (campaign_track_mapping) nor rejected
    # (campaign_mapping_rejected tombstone).
    rows = db.fetch_query(
        "SELECT campaign_name, MAX(start_time) FROM meta_campaigns mc "
        "WHERE mc.artist_id = %s AND NOT EXISTS ("
        "  SELECT 1 FROM campaign_track_mapping ctm "
        "  WHERE ctm.artist_id = mc.artist_id AND ctm.campaign_name = mc.campaign_name) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM campaign_mapping_rejected cmr "
        "  WHERE cmr.artist_id = mc.artist_id AND cmr.campaign_name = mc.campaign_name) "
        "GROUP BY campaign_name ORDER BY MAX(start_time) DESC NULLS LAST",
        (artist_id,))
    return [{'campaign': r[0], 'start': r[1]} for r in (rows or []) if r[0]]


def _load_campaign_context(db, artist_id: int) -> dict:
    """{campaign_name: {'adsets', 'ads', 'period'}} — adset & ad names help recognise
    which release a campaign was for; period = active window across the campaign + its
    adsets (epoch-1970 placeholder dates dropped) to compare against the track release."""
    rows = db.fetch_query(
        "SELECT c.campaign_name, "
        "  string_agg(DISTINCT s.adset_name, ' · '), string_agg(DISTINCT a.ad_name, ' · '), "
        "  LEAST(MIN(NULLIF(c.start_time::date, DATE '1970-01-01')), "
        "        MIN(NULLIF(s.start_time::date, DATE '1970-01-01'))), "
        "  GREATEST(MAX(NULLIF(c.end_time::date, DATE '1970-01-01')), "
        "           MAX(NULLIF(s.end_time::date, DATE '1970-01-01'))) "
        "FROM meta_campaigns c "
        "LEFT JOIN meta_adsets s ON s.campaign_id = c.campaign_id AND s.artist_id = c.artist_id "
        "LEFT JOIN meta_ads a ON a.campaign_id = c.campaign_id AND a.artist_id = c.artist_id "
        "WHERE c.artist_id = %s GROUP BY c.campaign_name",
        (artist_id,))
    out = {}
    for name, adsets, ads, pstart, pend in (rows or []):
        period = f"{pstart} → {pend}" if pstart and pend else (str(pstart) if pstart else "—")
        out[name] = {'adsets': adsets or '', 'ads': ads or '', 'period': period, 'spend': 0.0}
    # Spend per campaign over its active period (meta_insights_performance is a lifetime
    # aggregate keyed by campaign_name) — shown left of the campaign for context.
    spend_rows = db.fetch_query(
        "SELECT campaign_name, COALESCE(SUM(spend), 0) FROM meta_insights_performance "
        "WHERE artist_id = %s GROUP BY campaign_name", (artist_id,))
    for cn, sp in (spend_rows or []):
        if cn in out:
            out[cn]['spend'] = float(sp or 0)
    return out


def _trunc(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _build_campaign_suggestions(db, artist_id: int, canonical):
    """Unmapped campaign → best track via title-sim + release-date proximity. `confidence`
    kept raw [0,1]; displayed `Confiance` ×100. Adset/ad names add release context."""
    ctx = _load_campaign_context(db, artist_id)
    rel_by_key = {c['match_key']: c['release_date'] for c in canonical}
    sugg, disp = [], []
    for c in _load_unmapped_campaigns(db, artist_id):
        cands = rank_campaign_candidates(c['campaign'], c['start'], canonical, set(), top_n=1)
        if not cands:
            continue
        cand = cands[0]
        cc = ctx.get(c['campaign'], {})
        # A campaign with 0 € spent never ran a real promo for a release → propose to
        # reject it by default (and don't pre-tick Associer).
        spent = round(cc.get('spend', 0.0), 2)
        no_spend = spent == 0
        # track_name in `_`-form to match s4a_song_timeline.song (the meta_x_spotify join key).
        sugg.append({'campaign': c['campaign'], 'track_name': canonical_song(cand.title),
                     'confidence': cand.score, 'method': cand.method})
        disp.append({'Fiab.': confidence_badge(cand.score),
                     'Dépensé (€)': spent, 'Campagne': c['campaign'],
                     'Adsets': _trunc(cc.get('adsets', '')), 'Ads': _trunc(cc.get('ads', '')),
                     'Période camp.': cc.get('period', '—'),
                     'Suggestion (track)': cand.title,
                     'Sortie track': str(rel_by_key.get(cand.match_key) or '—'),
                     'Confiance': round(cand.score * 100, 1),
                     'Associer': cand.score >= 0.6 and not no_spend,
                     'Rejeter': no_spend})
    return sugg, pd.DataFrame(disp)


def _save_campaign_links(db, artist_id: int, sugg, edited):
    """Associer → campaign_track_mapping (real mapping). Rejeter → tombstone (stop
    suggesting). Returns (n_associated, n_rejected)."""
    now = datetime.now(timezone.utc)
    assoc, rejected = [], []
    for i, row in edited.reset_index(drop=True).iterrows():
        if i >= len(sugg):
            continue
        s = sugg[i]
        if row.get('Associer'):
            assoc.append({'artist_id': artist_id, 'campaign_name': s['campaign'],
                          'track_name': s['track_name'], 'confidence': s['confidence'],
                          'method': s['method'] or 'auto', 'auto_suggested': True,
                          'created_at': now})
        elif row.get('Rejeter'):
            rejected.append({'artist_id': artist_id, 'campaign_name': s['campaign'],
                             'created_at': now})
    if assoc:
        db.upsert_many(
            'campaign_track_mapping', assoc,
            conflict_columns=['artist_id', 'campaign_name', 'track_name'],
            update_columns=['confidence', 'method', 'auto_suggested'])
    if rejected:
        db.upsert_many(
            'campaign_mapping_rejected', rejected,
            conflict_columns=['artist_id', 'campaign_name'], update_columns=['created_at'])
    return len(assoc), len(rejected)


def _load_campaign_backlog(db, artist_id: int):
    """All Meta campaigns with their mapping state: ✅ associé / 🔴 rejeté / ⏳ à traiter."""
    return db.fetch_df(
        "SELECT mc.campaign_name, MAX(mc.start_time)::date AS debut, "
        "  string_agg(DISTINCT ctm.track_name, ' · ') AS track, "
        "  bool_or(cmr.campaign_name IS NOT NULL) AS rejected "
        "FROM meta_campaigns mc "
        "LEFT JOIN campaign_track_mapping ctm "
        "  ON ctm.artist_id = mc.artist_id AND ctm.campaign_name = mc.campaign_name "
        "LEFT JOIN campaign_mapping_rejected cmr "
        "  ON cmr.artist_id = mc.artist_id AND cmr.campaign_name = mc.campaign_name "
        "WHERE mc.artist_id = %s "
        "GROUP BY mc.campaign_name ORDER BY MAX(mc.start_time) DESC NULLS LAST",
        (artist_id,))


def _load_campaigns(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT campaign_name FROM meta_campaigns WHERE artist_id = %s GROUP BY campaign_name "
        "ORDER BY MAX(start_time) DESC NULLS LAST, campaign_name", (artist_id,))
    return [r[0] for r in rows]


def _load_tracks(db, artist_id: int) -> list[str]:
    rows = db.fetch_query(
        "SELECT DISTINCT song FROM s4a_song_timeline "
        "WHERE artist_id = %s AND song NOT ILIKE %s ORDER BY song",
        (artist_id, _S4A_FILTER))
    return [r[0] for r in rows]


def _load_mappings(db, artist_id: int):
    return db.fetch_df(
        "SELECT id, campaign_name, track_name, created_at FROM campaign_track_mapping "
        "WHERE artist_id = %s ORDER BY created_at DESC", (artist_id,))


def render_campaign_tab(db, artist_id, canonical):
    # ── Suggestions to validate (top; green when nothing left) ──
    st.subheader(t("meta_mapping.auto_header", "🤖 Suggestions automatiques (campagne → titre)"))
    sugg, disp = _build_campaign_suggestions(db, artist_id, canonical)
    if disp.empty:
        st.success(t("meta_mapping.auto_done",
                     "✅ Toutes les campagnes Meta sont déjà traitées (associées ou rejetées)."))
    else:
        st.caption(t("meta_mapping.auto_legend",
                     "Score = similarité du nom **et** proximité avec la date de sortie. "
                     "**Dépensé (€)** + **Adsets / Ads** donnent le contexte. Fiabilité : "
                     "🟢 ≥ 80 % · 🟡 50–80 % · 🔴 < 50 %. Les campagnes à **0 € dépensé** "
                     "sont pré-cochées **Rejeter** (jamais une vraie promo de release). "
                     "Cochez **Associer** ou **Rejeter**, puis enregistrez."))
        edited = st.data_editor(
            disp, hide_index=True, width="stretch", key="ed_auto_camp",
            on_change=_mutex_checkboxes, args=("ed_auto_camp", "Associer", "Rejeter"),
            column_config={
                'Fiab.': st.column_config.TextColumn("Fiab.", width="small"),
                'Dépensé (€)': st.column_config.NumberColumn("Dépensé (€)", format="%.0f €",
                                                             width="small"),
                'Campagne': st.column_config.TextColumn("Campagne", width="medium"),
                'Adsets': st.column_config.TextColumn("Adsets", width="medium"),
                'Ads': st.column_config.TextColumn("Ads", width="medium"),
                'Période camp.': st.column_config.TextColumn("Période camp.", width="small"),
                'Suggestion (track)': st.column_config.TextColumn("Suggestion (track)", width="medium"),
                'Sortie track': st.column_config.TextColumn("Sortie track", width="small"),
                'Confiance': st.column_config.ProgressColumn(
                    t("meta_mapping.col_confidence", "Confiance"),
                    min_value=0.0, max_value=100.0, format="%.0f%%", width="small"),
                'Associer': st.column_config.CheckboxColumn(
                    t("meta_mapping.col_associate", "Associer"), width="small"),
                'Rejeter': st.column_config.CheckboxColumn(
                    t("track_mapping.col_reject", "Rejeter"), width="small"),
            },
            disabled=['Fiab.', 'Dépensé (€)', 'Campagne', 'Adsets', 'Ads', 'Période camp.',
                      'Suggestion (track)', 'Sortie track', 'Confiance'])
        if st.button(t("meta_mapping.associate_button", "💾 Enregistrer (associer / rejeter)"),
                     type="primary"):
            n_a, n_r = _save_campaign_links(db, artist_id, sugg, edited)
            st.success(t("meta_mapping.campaigns_saved",
                         "{a} associée(s), {r} rejetée(s).").format(a=n_a, r=n_r))
            st.rerun()

    st.markdown("---")
    # ── Backlog (full recap) below ──
    st.subheader(t("meta_mapping.backlog_header", "📋 Backlog des campagnes (récap)"))
    bl = _load_campaign_backlog(db, artist_id)
    if bl.empty:
        st.info(t("meta_mapping.no_campaigns",
                  "Aucune campagne trouvée dans `meta_campaigns`. Lancez d'abord le DAG Meta Ads."))
    else:
        def _status(r):
            return ("🔴 Rejeté" if r['rejected'] else "✅ Associé" if r['track'] else "⏳ À traiter")
        view = pd.DataFrame({
            t("meta_mapping.bl_campaign", "Campagne"): bl['campaign_name'],
            t("meta_mapping.bl_status", "Statut"): bl.apply(_status, axis=1),
            t("meta_mapping.bl_track", "Titre associé"): bl['track'].fillna("—"),
            t("meta_mapping.bl_start", "Début"): bl['debut'].astype(str),
        })
        st.dataframe(view, hide_index=True, width="stretch")
        n_assoc = int(bl['track'].notna().sum())
        n_rej = int(bl['rejected'].sum())
        st.caption(t("meta_mapping.bl_counts",
                     "✅ {a} associée(s) · 🔴 {r} rejetée(s) · ⏳ {p} à traiter").format(
                         a=n_assoc, r=n_rej, p=len(bl) - n_assoc - n_rej))

    st.markdown("---")
    # ── Existing + manual ──
    sub_existing, sub_add = st.tabs([
        t("meta_mapping.tab_existing", "Mappings existants"),
        t("meta_mapping.tab_add", "Ajout manuel"),
    ])
    with sub_existing:
        df = _load_mappings(db, artist_id)
        if df.empty:
            st.info(t("meta_mapping.no_mappings",
                      "Aucun mapping pour le moment. Utilisez les suggestions ci-dessus ou "
                      "l'onglet **Ajout manuel**."))
        else:
            st.dataframe(df[["campaign_name", "track_name"]],
                         width="stretch", hide_index=True)
            st.markdown("---")
            st.subheader(t("meta_mapping.delete_title", "Supprimer un mapping"))
            options = {f"{r['campaign_name']} → {r['track_name']}": r["id"]
                       for _, r in df.iterrows()}
            sel = st.selectbox(
                t("meta_mapping.select_delete", "Sélectionnez le mapping à supprimer"),
                list(options.keys()))
            if st.button(t("common.delete", "🗑️ Supprimer"), type="secondary"):
                db.execute_query(
                    "DELETE FROM campaign_track_mapping WHERE id = %s AND artist_id = %s",
                    (options[sel], artist_id))
                st.success(t("meta_mapping.deleted", "Supprimé : {label}").format(label=sel))
                st.rerun()
    with sub_add:
        campaigns = _load_campaigns(db, artist_id)
        tracks = _load_tracks(db, artist_id)
        if not campaigns:
            st.warning(t("meta_mapping.no_campaigns",
                         "Aucune campagne trouvée dans `meta_campaigns`. "
                         "Lancez d'abord le DAG Meta Ads."))
            return
        if not tracks:
            st.warning(t("meta_mapping.no_tracks",
                         "Aucun titre trouvé. Importez d'abord vos CSV S4A."))
            return
        with st.form("add_mapping_form"):
            campaign = st.selectbox(t("meta_mapping.meta_campaign", "Campagne Meta"), campaigns)
            track = st.selectbox(t("meta_mapping.spotify_track", "Titre Spotify"), tracks)
            submitted = st.form_submit_button(
                t("meta_mapping.add_btn", "➕ Ajouter le mapping"), type="primary")
        if submitted:
            db.execute_query(
                "INSERT INTO campaign_track_mapping (artist_id, campaign_name, track_name) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (artist_id, campaign_name, track_name) DO NOTHING",
                (artist_id, campaign, track))
            st.success(t("meta_mapping.mapped", "Associé : **{campaign}** → **{track}**")
                       .format(campaign=campaign, track=track))
            st.rerun()
