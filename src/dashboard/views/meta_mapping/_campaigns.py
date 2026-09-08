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

from ._common import _S4A_FILTER, _artist_noise, _mutex_checkboxes


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
    # Une campagne Meta porte souvent le nom de l'artiste en préfixe, comme les
    # titres SoundCloud : sans cette liste il compte comme un mot du titre.
    noise = _artist_noise(db, artist_id)
    for c in _load_unmapped_campaigns(db, artist_id):
        cands = rank_campaign_candidates(c['campaign'], c['start'], canonical, set(),
                                         top_n=1, noise_tokens=noise)
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


def _empty_campaigns_message(db, artist_id: int) -> tuple[str, str]:
    """(niveau, phrase) — POURQUOI la liste est vide, mesuré et non supposé.

    Le message d'origine disait « Connecte Meta Ads […] puis lance les collectes »
    quelle que soit la raison. Le 2026-09-06 il a été lu par un artiste dont Meta
    était branché, sondé vert, avec 224 lignes d'insights et une collecte réussie
    vingt minutes plus tôt : les deux gestes demandés étaient faits.

    Les trois faits ci-dessous sont déjà en base ; les lire coûte une requête.
    """
    from src.utils.meta_campaign_diagnosis import (
        CAMPAIGNS_ELSEWHERE, NEVER_RAN, NO_CAMPAIGN_AT_ALL, NO_IDENTITY,
        RUN_FAILED, SANDBOX_SHARES_ACCOUNT, diagnose_empty_campaigns,
    )

    row = db.fetch_query(
        "SELECT "
        "  (SELECT COUNT(*) FROM artist_credentials WHERE artist_id = %s "
        "     AND platform = 'meta' "
        "     AND btrim(COALESCE(extra_config->>'account_id', '')) <> ''), "
        "  (SELECT status FROM etl_run_log WHERE artist_id = %s AND platform = 'meta' "
        "     ORDER BY started_at DESC LIMIT 1), "
        "  (SELECT COUNT(*) FROM meta_insights_performance WHERE artist_id = %s), "
        # Le quatrième fait, ajouté le 2026-09-08 : sans lui, le seul locataire chez
        # qui « les campagnes sont ailleurs » peut ENCORE se produire lisait la
        # phrase écrite pour un cas qui, lui, ne se produit plus.
        "  (SELECT COALESCE(is_sandbox, FALSE) FROM saas_artists WHERE id = %s)",
        (artist_id, artist_id, artist_id, artist_id),
    )
    has_id, last_status, insights, is_sandbox = (row[0] if row else (0, None, 0, False))

    cause = diagnose_empty_campaigns(
        identity_present=bool(has_id),
        last_run_status=last_status,
        insight_rows=int(insights or 0),
        is_sandbox=bool(is_sandbox),
    )

    if cause == NO_IDENTITY:
        return "info", t(
            "meta_mapping.empty_no_identity",
            "Aucune campagne : ton compte publicitaire Meta n'est pas encore "
            "renseigné. Va dans **🔑 Credentials API → Meta Ads** et colle ton "
            "Ad Account ID.")
    if cause == NEVER_RAN:
        return "info", t(
            "meta_mapping.empty_never_ran",
            "Aucune campagne : la collecte Meta n'a encore jamais tourné pour toi. "
            "La collecte Meta tourne chaque matin à 5 h ; elle repart aussi dès que tu enregistres ton compte publicitaire.")
    if cause == RUN_FAILED:
        return "warning", t(
            "meta_mapping.empty_run_failed",
            "Aucune campagne : la dernière collecte Meta a échoué. Rien à faire de "
            "ton côté — on regarde.")
    if cause == NO_CAMPAIGN_AT_ALL:
        return "info", t(
            "meta_mapping.empty_no_campaign",
            "La collecte Meta fonctionne, et ton compte publicitaire ne contient "
            "aucune campagne. Il n'y a rien à mapper tant que tu n'as pas lancé de "
            "publicité — c'est normal, pas une erreur.")
    if cause == SANDBOX_SHARES_ACCOUNT:
        return "info", t(
            "meta_mapping.empty_sandbox",
            "Aucune campagne, et c'est **attendu ici** : ce profil est le bac à "
            "sable, il déclare le même compte publicitaire que ton profil "
            "principal. Une campagne appartient définitivement au premier profil "
            "qui l'a collectée — les tiennes sont donc toutes sur ton profil "
            "principal, avec leur mapping. Le bac à sable rejoue la mise en route, "
            "pas l'association des campagnes : pour celle-ci, connecte-toi avec "
            "ton compte principal.")
    assert cause == CAMPAIGNS_ELSEWHERE
    return "info", t(
        "meta_mapping.empty_elsewhere",
        "La collecte Meta fonctionne — tes chiffres de performance sont bien "
        "arrivés. En revanche aucune campagne n'est rattachée à **ce** profil : "
        "elles appartiennent au premier profil qui a déclaré ce compte "
        "publicitaire. C'est voulu — une campagne ne change jamais de "
        "propriétaire — et cela n'arrive que si deux profils partagent le même "
        "compte publicitaire. Rien à faire de ton côté.")


def render_campaign_tab(db, artist_id, canonical):
    # ── Suggestions to validate (top; green when nothing left) ──
    st.subheader(t("meta_mapping.auto_header", "🤖 Suggestions automatiques (campagne → titre)"))
    sugg, disp = _build_campaign_suggestions(db, artist_id, canonical)
    if disp.empty:
        # « Toutes les campagnes sont déjà traitées » sur ZÉRO campagne est un
        # succès pour un ensemble vide : rien n'a été traité, il n'y avait rien.
        # L'artiste du 2026-09-06 l'a lu juste au-dessus du message qui lui
        # demandait de connecter Meta — deux affirmations contradictoires sur le
        # même écran.
        if _load_campaigns(db, artist_id):
            st.success(t("meta_mapping.auto_done",
                         "✅ Toutes les campagnes Meta sont déjà traitées "
                         "(associées ou rejetées)."))
        else:
            _level, _msg = _empty_campaigns_message(db, artist_id)
            (st.warning if _level == "warning" else st.info)(_msg)
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
        _level, _msg = _empty_campaigns_message(db, artist_id)
        (st.warning if _level == "warning" else st.info)(_msg)
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
            # `meta_mapping.no_campaigns` portait DEUX phrases françaises
            # différentes, ici et dans le backlog. Une clé, deux sens : la
            # traduction anglaise n'en servait qu'un, et personne ne pouvait le
            # voir. Les deux surfaces posent la même question — on rend la même
            # réponse mesurée.
            #
            # Le texte d'origine nommait `meta_campaigns` et « le DAG Meta Ads » :
            # une table et un DAG que l'artiste ne peut ni ouvrir ni lancer.
            _level, _msg = _empty_campaigns_message(db, artist_id)
            (st.warning if _level == "warning" else st.info)(_msg)
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
