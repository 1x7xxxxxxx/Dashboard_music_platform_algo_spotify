"""Cross-platform track tab — each platform's free-text titles scored against the
canonical track_release_reference; accept/reject → track_platform_link.

Type: Sub
Uses: track_mapping_suggest (rank_track_candidates, confidence_badge)
Persists in: track_platform_link (PostgreSQL spotify_etl)
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t
from src.utils.track_mapping_suggest import confidence_badge, rank_track_candidates

from ._common import _S4A_FILTER, _artist_noise, _mutex_checkboxes

# (platform_key, human label). platform_key is a fixed enum (never user input).
_PLATFORMS = [
    ('s4a', 'Spotify (S4A)'),
    ('spotify', 'Spotify (API)'),
    ('apple', 'Apple Music'),
    ('soundcloud', 'SoundCloud'),
    ('youtube', 'YouTube'),
    ('hypeddit', 'Hypeddit'),
]

# Short column headers for the coverage grid (compact, no long platform titles).
_PLATFORM_SHORT = {'s4a': 'S4A', 'spotify': 'Spotify', 'apple': 'Apple',
                   'soundcloud': 'SoundCloud', 'youtube': 'YouTube', 'hypeddit': 'Hypeddit'}


def _load_platform_titles(db, artist_id, platform):
    """[{title, ref_id, date}] of distinct platform-local titles. `date` = the platform's
    own upload/release date when the source exposes one (Spotify/SoundCloud/YouTube),
    else None (Apple, and S4A which IS the canonical source → near-exact title match)."""
    q = {
        's4a': ("SELECT DISTINCT song, NULL::text, NULL::date FROM s4a_song_timeline "
                "WHERE artist_id = %s AND song NOT ILIKE %s", (artist_id, _S4A_FILTER)),
        'spotify': ("SELECT track_name, MAX(track_id), MAX(release_date) FROM tracks "
                    "WHERE saas_artist_id = %s AND track_name IS NOT NULL "
                    "GROUP BY track_name", (artist_id,)),
        'apple': ("SELECT DISTINCT song_name, NULL::text, NULL::date "
                  "FROM apple_songs_performance "
                  "WHERE artist_id = %s AND song_name IS NOT NULL", (artist_id,)),
        'soundcloud': ("SELECT title, MAX(track_id), MAX(track_created_at) "
                       "FROM soundcloud_tracks_daily "
                       "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title",
                       (artist_id,)),
        'youtube': ("SELECT title, MAX(video_id), MAX(published_at) FROM youtube_videos "
                    "WHERE artist_id = %s AND title IS NOT NULL GROUP BY title", (artist_id,)),
        # Hypeddit promo campaigns are named after the track (no per-platform release date).
        'hypeddit': ("SELECT campaign_name, NULL::text, NULL::date FROM hypeddit_campaigns "
                     "WHERE artist_id = %s AND campaign_name IS NOT NULL", (artist_id,)),
    }.get(platform)
    if not q:
        return []
    try:
        rows = db.fetch_query(q[0], q[1])
    except Exception:
        return []
    return [{'title': r[0], 'ref_id': r[1], 'date': r[2]} for r in (rows or []) if r[0]]


def _load_links(db, artist_id):
    return db.fetch_df(
        "SELECT match_key, platform, platform_title, status, confidence "
        "FROM track_platform_link WHERE artist_id = %s",
        (artist_id,))


def _build_suggestions(db, artist_id, platform, canonical, links_df):
    """Per-platform unmapped titles → top candidate. `confidence` kept raw [0,1] for the
    DB; the displayed `Confiance` is ×100 so the ProgressColumn text reads a real %."""
    seen = set()
    if not links_df.empty:
        seen = {r.platform_title for r in
                links_df[links_df.platform == platform].itertuples()}
    confirmed_keys = (set(links_df[links_df.status == 'confirmed'].match_key)
                      if not links_df.empty else set())
    sugg, disp, orphans = [], [], []
    noise = _artist_noise(db, artist_id)
    for item in _load_platform_titles(db, artist_id, platform):
        if item['title'] in seen:
            continue  # already confirmed/rejected for this platform
        cands = rank_track_candidates(item['title'], canonical, confirmed_keys,
                                      top_n=1, platform_date=item.get('date'),
                                      noise_tokens=noise)
        if not cands:
            # UN TITRE SANS CANDIDAT DISPARAISSAIT EN SILENCE.
            #
            # « Patte Velours 1ère vitesse » existe sur Apple ET SoundCloud, et n'a
            # aucune entrée canonique — l'export S4A 12 mois ne le contient pas.
            # L'artiste ne voyait ni le titre ni la raison, donc il ne pouvait rien
            # faire. Et depuis que les marqueurs de version sont pris au sérieux,
            # un « (Radio Edit) » sans sortie correspondante tombe ici aussi : sans
            # cette liste, durcir l'algorithme reviendrait à cacher davantage.
            orphans.append({'title': item['title'],
                            'reason': _orphan_reason(item['title'], canonical)})
            continue
        c = cands[0]
        sugg.append({'platform_title': item['title'], 'ref_id': item['ref_id'],
                     'match_key': c.match_key, 'confidence': c.score, 'method': c.method})
        disp.append({'Fiab.': confidence_badge(c.score), 'Titre plateforme': item['title'],
                     'Suggestion (track)': c.title, 'Confiance': round(c.score * 100, 1),
                     'Accepter': c.score >= 0.8, 'Rejeter': False})
    return sugg, pd.DataFrame(disp), orphans


def _orphan_reason(platform_title: str, canonical) -> str:
    """Pourquoi ce titre n'a trouvé aucun morceau — la vraie raison, pas la générique.

    Trois causes, trois gestes différents : il n'y a pas de référence du tout, la
    version demandée n'existe pas dans les sorties, ou le titre ne ressemble à rien
    de connu. Les confondre revient à ne rien dire.
    """
    from src.utils.track_matching import split_version

    if not canonical:
        return t("track_mapping.orphan_no_reference",
                 "aucune sortie de référence — importe ton export S4A « 12 mois »")
    _base, tags = split_version(platform_title)
    if tags:
        known = set()
        for c in canonical:
            known |= split_version(c['title'])[1]
        missing = tags - known
        if missing:
            return t("track_mapping.orphan_version",
                     "version « {v} » : aucune de tes sorties ne porte ce marqueur"
                     ).format(v=", ".join(sorted(m.replace('_', ' ') for m in missing)))
    return t("track_mapping.orphan_no_match",
             "ne ressemble à aucune de tes sorties — sûrement un edit, un mix ou "
             "un morceau d'un autre artiste")


def _build_all_suggestions(db, artist_id, canonical, links_df):
    """All platforms' top suggestions in ONE list (no per-platform selector). Each
    display row carries a Plateforme column; each sugg dict carries its platform."""
    all_sugg, rows, orphan_rows = [], [], []
    cols = ['Fiab.', 'Titre plateforme', 'Suggestion (track)', 'Confiance', 'Accepter', 'Rejeter']
    for pkey, plabel in _PLATFORMS:
        sugg, disp, orphans = _build_suggestions(db, artist_id, pkey, canonical, links_df)
        for i, s in enumerate(sugg):
            s['platform'] = pkey
            all_sugg.append(s)
            r = disp.iloc[i]
            rows.append({'Plateforme': _PLATFORM_SHORT[pkey], **{c: r[c] for c in cols}})
        for o in orphans:
            orphan_rows.append({
                t("track_mapping.col_platform", "Plateforme"): _PLATFORM_SHORT[pkey],
                t("track_mapping.col_platform_title", "Titre sur la plateforme"): o['title'],
                t("track_mapping.col_why", "Pourquoi il n'est pas proposé"): o['reason'],
            })
    return all_sugg, pd.DataFrame(rows), pd.DataFrame(orphan_rows)


def _save_all_links(db, artist_id, all_sugg, edited):
    """One upsert across all platforms (track_platform_link carries the platform column)."""
    now = datetime.now(timezone.utc)
    data = []
    for i, row in edited.reset_index(drop=True).iterrows():
        if i >= len(all_sugg):
            continue
        status = 'confirmed' if row.get('Accepter') else 'rejected' if row.get('Rejeter') else None
        if status is None:
            continue
        s = all_sugg[i]
        data.append({'artist_id': artist_id, 'match_key': s['match_key'], 'platform': s['platform'],
                     'platform_title': s['platform_title'], 'platform_ref_id': s['ref_id'],
                     'status': status, 'confidence': s['confidence'], 'method': s['method'],
                     'updated_at': now})
    if data:
        db.upsert_many(
            'track_platform_link', data,
            conflict_columns=['artist_id', 'platform', 'platform_title', 'match_key'],
            update_columns=['status', 'confidence', 'method', 'updated_at'])
    return len(data)


def _render_orphans(orphans) -> None:
    """Les titres qu'aucune sortie ne réclame, avec la raison. Replié par défaut.

    Ce n'est pas une liste d'erreurs : un artiste qui héberge des edits sur
    SoundCloud en aura toujours. C'est la réponse à « pourquoi ce morceau
    n'apparaît-il nulle part ? », qui n'existait pas.
    """
    if orphans is None or orphans.empty:
        return
    with st.expander(t("track_mapping.orphans_header",
                       "🕳️ {n} titre(s) vus sur une plateforme et rattachés à aucune "
                       "de tes sorties").format(n=len(orphans)), expanded=False):
        st.caption(t("track_mapping.orphans_help",
                     "Rien à faire si ce sont des edits ou des mix. Si l'un d'eux "
                     "est bien une de tes sorties, c'est qu'elle manque à ton export "
                     "Spotify for Artists « 12 mois » — réimporte-le."))
        st.dataframe(orphans, hide_index=True, width='stretch')


def _render_track_suggestions(db, artist_id, canonical, links_df):
    """Suggestions to validate (all platforms, no selector). Green when nothing left."""
    st.subheader(t("track_mapping.suggest_header", "🔎 Suggestions à valider"))
    # Le verdict d'enregistrement passe par la session : `st.rerun()` efface tout ce
    # qui a été écrit avant lui (classe `message-written-before-a-rerun`).
    _saved = st.session_state.pop('_track_links_saved', None)
    if _saved is not None:
        st.success(t("track_mapping.links_saved",
                     "{n} lien(s) enregistré(s).").format(n=_saved))
    all_sugg, disp, orphans = _build_all_suggestions(db, artist_id, canonical, links_df)
    if disp.empty:
        st.success(t("track_mapping.nothing_to_map",
                     "✅ Rien à mapper (tout est déjà lié ou rejeté)."))
        _render_orphans(orphans)
        return
    st.caption(t("track_mapping.legend",
                 "Score = similarité du nom **+** proximité de date (si la plateforme "
                 "l'expose). Fiabilité : 🟢 ≥80 % · 🟡 50–80 % · 🔴 <50 %. Cochez "
                 "**Accepter** (ou **Rejeter** pour ne plus proposer), puis enregistrez."))
    edited = st.data_editor(
        disp, hide_index=True, width='stretch', key="ed_all_tracks",
        on_change=_mutex_checkboxes, args=("ed_all_tracks", "Accepter", "Rejeter"),
        column_config={
            'Plateforme': st.column_config.TextColumn("Plateforme", width="small"),
            'Fiab.': st.column_config.TextColumn("Fiab.", width="small"),
            'Titre plateforme': st.column_config.TextColumn("Titre plateforme", width="large"),
            'Suggestion (track)': st.column_config.TextColumn("Suggestion (track)", width="medium"),
            'Confiance': st.column_config.ProgressColumn(
                t("track_mapping.col_confidence", "Confiance"),
                min_value=0.0, max_value=100.0, format="%.0f%%", width="small"),
            'Accepter': st.column_config.CheckboxColumn(
                t("track_mapping.col_accept", "Accepter"), width="small"),
            'Rejeter': st.column_config.CheckboxColumn(
                t("track_mapping.col_reject", "Rejeter"), width="small"),
        },
        disabled=['Plateforme', 'Fiab.', 'Titre plateforme', 'Suggestion (track)', 'Confiance'])
    if st.button(t("track_mapping.save_links_button", "💾 Enregistrer les liens"),
                 type="primary"):
        n = _save_all_links(db, artist_id, all_sugg, edited)
        st.session_state['_track_links_saved'] = n
        st.rerun()
    # RENDUS DANS LES DEUX CAS. Ils ne l'étaient que sur la branche « rien à
    # mapper » : un artiste qui a encore des suggestions à valider est exactement
    # celui qui se demande où est passé son morceau manquant.
    _render_orphans(orphans)


def _render_coverage_grid(db, artist_id, canonical, links_df):
    """Le récap : ai-je le BON NOMBRE de titres sur chaque plateforme ?

    Trois changements le 2026-09-21, tous demandés en regardant l'écran.

    1. **Une ligne de comptes en tête.** La grille disait, titre par titre, si une
       plateforme était liée ; elle ne répondait pas à la question qu'on se pose
       en l'ouvrant — « est-ce que tout y est ? ». Il fallait compter les ✅ à
       l'œil sur onze lignes et six colonnes. Le compte est maintenant écrit, et
       comparé au nombre de titres canoniques.

    2. **Rouge pour ce qui manque.** Le « · » d'avant était neutre : une case vide
       et une case non liée se lisaient pareil. Une absence qui coûte quelque
       chose doit se voir.

    3. **Ce que la plateforme CONNAÎT entre dans le compte.** Un titre peut être
       vu par la plateforme sans être lié — c'est le cas qui produit un écart, et
       le seul que la grille ne montrait nulle part. La colonne « vus » vient du
       même chargeur que les suggestions, donc elle ne peut pas diverger d'elles.

    ⚠️ Hypeddit compte ses CAMPAGNES, pas ses titres : un titre sans campagne
    promo n'est pas une anomalie. Sa colonne de compte est donc informative et
    jamais rouge — l'écrire ici évite de « corriger » un écart qui n'en est pas un.
    """
    confirmed = links_df[links_df.status == 'confirmed'] if not links_df.empty else links_df
    st.subheader(t("track_mapping.coverage_header",
                   "🗺️ Couverture cross-plateforme — ai-je tout, partout ?"))

    n_canon = len(canonical)
    lies, vus = {}, {}
    for pkey, _ in _PLATFORMS:
        lies[pkey] = 0 if confirmed.empty else int(
            confirmed[confirmed.platform == pkey].match_key.nunique())
        vus[pkey] = len(_load_platform_titles(db, artist_id, pkey))

    # LA LIGNE DE COMPTES, une colonne par plateforme.
    cols = st.columns(len(_PLATFORMS))
    for col, (pkey, _) in zip(cols, _PLATFORMS):
        complet = lies[pkey] >= n_canon
        # ⚠️ `with col:` PUIS `st.metric`, jamais `col.metric(...)`. Les deux
        # rendent la même chose, mais le receveur `col` est une variable de
        # boucle : `tools/dev/gold_coverage.py` ne peut pas la résoudre et
        # classe la tuile « indéterminée · receveur-inconnu ». Le cliquet des
        # trous l'a attrapée le 2026-09-21 — `tiles.unknown 12 contre 11` — et
        # il a raison : une tuile qu'aucun outil ne sait rattacher à sa source
        # est un trou de la carte, pas un détail de style.
        #
        # `delta_color="off"` : ce n'est pas une évolution, c'est un écart. La
        # flèche verte/rouge de Streamlit raconterait une variation dans le temps.
        with col:
            st.metric(_PLATFORM_SHORT[pkey],
                      f"{lies[pkey]} / {n_canon}",
                      delta=t("track_mapping.seen_n", "{n} vu(s)").format(n=vus[pkey]),
                      delta_color="off",
                      help=(t("track_mapping.count_ok",
                              "Tous les titres canoniques sont liés sur cette plateforme.")
                            if complet else
                            t("track_mapping.count_missing",
                              "{k} titre(s) canonique(s) sans lien confirmé ici. "
                              "La plateforme en connaît {v} au total.")
                            .format(k=n_canon - lies[pkey], v=vus[pkey])))

    if pkey_manquants := [_PLATFORM_SHORT[k] for k, _ in _PLATFORMS
                          if k != 'hypeddit' and lies[k] < n_canon]:
        st.warning(t("track_mapping.coverage_gap",
                     "⚠️ Il manque des liens sur : **{p}**. Un titre non lié sort "
                     "des comparaisons cross-plateforme — c'est ce qui faisait "
                     "perdre 59 % des écoutes avant le rattachement par lien "
                     "confirmé.").format(p=", ".join(pkey_manquants)))
    else:
        st.success(t("track_mapping.coverage_full",
                     "✅ Les {n} titres canoniques sont liés sur toutes les "
                     "plateformes qui les portent.").format(n=n_canon))

    grid_rows = []
    for tr in canonical:
        row = {t("track_mapping.col_track", "Track"): tr['title'],
               t("track_mapping.col_release", "Sortie"): str(tr['release_date'] or '—')}
        for pkey, _ in _PLATFORMS:
            linked = (not confirmed.empty and not confirmed[
                (confirmed.match_key == tr['match_key']) & (confirmed.platform == pkey)].empty)
            row[_PLATFORM_SHORT[pkey]] = "✅" if linked else "❌"
        grid_rows.append(row)

    grid = pd.DataFrame(grid_rows)
    plat_cols = [_PLATFORM_SHORT[k] for k, _ in _PLATFORMS]

    def _cell(v):
        if v == "✅":
            return 'background-color: #1e7d3322; color: #1b8a3a; font-weight: 600'
        if v == "❌":
            return 'background-color: #c0392b22; color: #b03a2e; font-weight: 600'
        return ''

    st.dataframe(grid.style.map(_cell, subset=plat_cols), hide_index=True, width='stretch')
    st.caption(t("track_mapping.coverage_legend",
                 "✅ lié · ❌ non lié. Le compte du haut confronte les liens CONFIRMÉS "
                 "au nombre de titres canoniques ; « vu(s) » est ce que la plateforme "
                 "connaît, lié ou non. Hypeddit compte des CAMPAGNES promo, pas des "
                 "titres : y avoir moins n'est pas une anomalie. (Les campagnes Meta "
                 "sont dans l'onglet **📣 Campagnes Meta**.)"))


def render_overview_tab(db, artist_id, canonical):
    links_df = _load_links(db, artist_id)
    # Suggestions on top (green when nothing) …
    _render_track_suggestions(db, artist_id, canonical, links_df)
    st.markdown("---")
    # … cross-platform coverage recap just below.
    _render_coverage_grid(db, artist_id, canonical, links_df)
