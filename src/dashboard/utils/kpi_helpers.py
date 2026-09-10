"""Fonctions KPI réutilisables par toutes les views du dashboard."""
import logging
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)

# Read-only metadata getters below are wrapped in @st.cache_data(ttl=60). The DB
# handle is passed as `_db` (leading underscore) so Streamlit excludes the
# unhashable connection from the cache key — entries are keyed on artist_id only.
# 60s TTL: pure read metadata, no behavioural change, saves repeat round-trips on
# re-render. kpi_helpers is imported only by Streamlit views (no Airflow caller).


# Seuils de fraîcheur (en heures)
_FRESH_H = 24
_WARN_H = 72

# Filtre ligne "Total" des CSV Spotify for Artists
ARTIST_NAME_FILTER = "1x7xxxxxxx"


# ─── Fraîcheur des sources ──────────────────────────────────────────────────

SOURCES_CONFIG = [
    {
        "label": "Spotify API",
        "icon": "🎸",
        "table": "artists",
        "col": "collected_at",
        "artist_col": None,
        # `artists` PK is the Spotify string id, not the saas artist_id. Scope per
        # tenant through the saas_artists.spotify_artist_id bridge so a fresh account
        # doesn't inherit another tenant's freshness (an unbridged tenant matches
        # nothing → "no data"). Trusted constant (no user input) — validated against
        # _ALLOWED_ARTIST_FILTERS before interpolation (CLAUDE.md rule #8).
        "artist_filter": "artist_id IN (SELECT spotify_artist_id FROM saas_artists WHERE id = %s)",
    },
    {
        "label": "Spotify S4A",
        "icon": "🎵",
        "table": "s4a_song_timeline",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "YouTube",
        "icon": "🎬",
        "table": "youtube_channel_history",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "SoundCloud",
        "icon": "☁️",
        "table": "soundcloud_tracks_daily",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Instagram",
        "icon": "📸",
        "table": "instagram_daily_stats",
        "col": "collected_at",  # DATE
        "artist_col": "artist_id",
    },
    {
        "label": "Apple Music",
        "icon": "🍎",
        "table": "apple_songs_performance",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "Meta Ads",
        "icon": "📱",
        "table": "meta_insights_performance_day",
        "col": "collected_at",
        "artist_col": "artist_id",
    },
    {
        "label": "iMusician",
        "icon": "💰",
        "table": "imusician_monthly_revenue",
        "col": "updated_at",
        "artist_col": "artist_id",
    },
]

# Allowlists — protect f-string identifier interpolation in get_source_freshness()
_ALLOWED_TABLES     = frozenset(s["table"]      for s in SOURCES_CONFIG)
_ALLOWED_COLS       = frozenset(s["col"]        for s in SOURCES_CONFIG)
_ALLOWED_ARTIST_COLS = frozenset(s["artist_col"] for s in SOURCES_CONFIG if s.get("artist_col"))
_ALLOWED_ARTIST_FILTERS = frozenset(s["artist_filter"] for s in SOURCES_CONFIG if s.get("artist_filter"))


@st.cache_data(ttl=60)
def get_source_freshness(_db, artist_id):
    """Return {label: {icon, last_dt}} for each source in a single UNION ALL query.

    Replaces 7 sequential SELECT MAX() calls with one round-trip.
    Identifiers are validated against allowlists before interpolation.
    """
    db = _db
    # Validate all identifiers against allowlists before building the query
    for src in SOURCES_CONFIG:
        if src["table"] not in _ALLOWED_TABLES:
            raise ValueError(f"Table not in allowlist: {src['table']}")
        if src["col"] not in _ALLOWED_COLS:
            raise ValueError(f"Column not in allowlist: {src['col']}")
        if (not src.get("skip_artist_filter") and not src.get("artist_filter")
                and src["artist_col"] not in _ALLOWED_ARTIST_COLS):
            raise ValueError(f"Artist column not in allowlist: {src['artist_col']}")
        if src.get("artist_filter") and src["artist_filter"] not in _ALLOWED_ARTIST_FILTERS:
            raise ValueError(f"Artist filter not in allowlist: {src['artist_filter']}")

    branches = []
    params = []
    for src in SOURCES_CONFIG:
        custom_filter = src.get("artist_filter")
        if artist_id is not None and custom_filter:
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']} WHERE {custom_filter}"
            )
            params.append(artist_id)
        elif artist_id is not None and not src.get("skip_artist_filter"):
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']} WHERE {src['artist_col']} = %s"
            )
            params.append(artist_id)
        else:
            branches.append(
                f"SELECT '{src['label']}' AS label, MAX({src['col']}) AS last_dt"
                f" FROM {src['table']}"
            )
    query = " UNION ALL ".join(branches)
    params = tuple(params)

    label_to_icon = {src["label"]: src["icon"] for src in SOURCES_CONFIG}
    result = {src["label"]: {"icon": src["icon"], "last_dt": None} for src in SOURCES_CONFIG}

    try:
        rows = db.fetch_query(query, params) if params else db.fetch_query(query)
        for label, val in rows:
            if val is not None and not isinstance(val, datetime):
                val = datetime(val.year, val.month, val.day, 0, 0, 0)
            result[label] = {"icon": label_to_icon.get(label, ""), "last_dt": val}
    except Exception:
        pass  # return defaults (all None) on failure

    return result


def freshness_status(last_dt):
    """
    Retourne (emoji, color, label) selon l'âge de last_dt.
    """
    if last_dt is None:
        return "⚫", "#888888", "Pas de données"
    age_h = (datetime.now() - last_dt).total_seconds() / 3600
    if age_h < _FRESH_H:
        return "🟢", "#1DB954", f"Il y a {int(age_h)}h"
    elif age_h < _WARN_H:
        days = int(age_h / 24)
        return "🟠", "#FFA500", f"Il y a {days}j"
    else:
        days = int(age_h / 24)
        return "🔴", "#FF4444", f"Il y a {days}j"


# ─── KPI Streams ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_total_streams_s4a(_db, artist_id):
    """Total streams Spotify S4A (dédupliqué par MAX/jour/chanson)."""
    db = _db
    try:
        if artist_id is not None:
            q = """
                SELECT SUM(daily_max) FROM (
                    SELECT MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s AND artist_id = %s
                    GROUP BY date, song
                ) sub
            """
            row = db.fetch_query(q, (f"%{ARTIST_NAME_FILTER}%", artist_id))
        else:
            q = """
                SELECT SUM(daily_max) FROM (
                    SELECT MAX(streams) AS daily_max
                    FROM s4a_song_timeline
                    WHERE song NOT ILIKE %s
                    GROUP BY date, song
                ) sub
            """
            row = db.fetch_query(q, (f"%{ARTIST_NAME_FILTER}%",))
        return int(row[0][0] or 0)
    except Exception:
        return 0


@st.cache_data(ttl=60)
def get_total_views_youtube(_db, artist_id):
    """Total vues YouTube — la couche OR (`v_platform_totals`, ADR-019).

    Cette fonction lisait `youtube_channel_history.view_count`, le compteur de CHAÎNE,
    prouvé ~10× faux le 2026-09-08 : figé onze jours puis +360 attribués à une seule
    journée, quand YouTube Studio annonçait 64 vues sur la période. Il porte les vidéos
    privées, supprimées et des agrégats internes, et il avance par paliers.

    Elle alimente « Data Wrapped », qui affichait donc un total YouTube différent de
    celui de l'accueil et de l'API pour le même locataire au même instant. Mesuré le
    2026-09-10 sur l'artiste 1 : 120 627 ici contre 118 219 par la définition retenue.
    """
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT COALESCE(total, 0) FROM v_platform_totals "
                "WHERE artist_id = %s AND platform = 'youtube'", (artist_id,))
        else:
            row = db.fetch_query(
                "SELECT COALESCE(SUM(total), 0) FROM v_platform_totals "
                "WHERE platform = 'youtube'")
        return int(row[0][0] or 0) if row else 0
    except Exception as exc:      # noqa: BLE001
        logger.warning("YouTube total unreadable: %s", type(exc).__name__)
        return 0


@st.cache_data(ttl=60)
def get_total_plays_soundcloud(_db, artist_id):
    """Total plays SoundCloud (dernière snapshot disponible)."""
    db = _db
    try:
        if artist_id is not None:
            q = """
                SELECT SUM(playback_count) FROM (
                    SELECT DISTINCT ON (track_id) playback_count
                    FROM soundcloud_tracks_daily
                    WHERE artist_id = %s
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q, (artist_id,))
        else:
            q = """
                SELECT SUM(playback_count) FROM (
                    SELECT DISTINCT ON (track_id) playback_count
                    FROM soundcloud_tracks_daily
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q)
        return int(row[0][0] or 0)
    except Exception:
        return 0


@st.cache_data(ttl=60)
def get_total_plays_apple(_db, artist_id):
    """Total plays Apple Music, SANS compter deux fois.

    `SUM(plays)` sur toute la table était juste tant qu'un artiste n'avait qu'un seul
    relevé — ce que la clé lui imposait avant la migration 093. Depuis qu'il peut
    déposer plusieurs exports (« depuis le début », puis un par année, migration 094),
    la somme brute additionne un cumul ET les années qu'il contient déjà : les mêmes
    écoutes deux fois.

    La règle est donc « le dernier cumul s'il existe, sinon la somme des périodes
    bornées » — elle vit dans `platform_timeseries.apple_lifetime_plays`, et les trois
    lecteurs (accueil, Data Wrapped, export PDF) passent par ici.
    """
    if artist_id is not None:
        from src.dashboard.utils.platform_timeseries import apple_lifetime_plays
        return apple_lifetime_plays(_db, artist_id)
    try:
        # Vue flotte (admin) : pas de locataire, donc pas de notion de « son » cumul.
        row = _db.fetch_query(
            "SELECT COALESCE(SUM(plays), 0) FROM apple_songs_performance "
            "WHERE period_start IS NULL")
        return int(row[0][0] or 0)
    except Exception:      # noqa: BLE001
        return 0


# ─── KPI ML ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_spotify_popularity(_db, artist_id):
    """Score de popularité Spotify (dernier enregistrement)."""
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history WHERE artist_id = %s ORDER BY date DESC LIMIT 1",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT popularity, track_name FROM track_popularity_history ORDER BY date DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'score': int(row[0][0]), 'track': row[0][1]}
    except Exception:
        pass
    return None


@st.cache_data(ttl=60)
def get_instagram_followers(_db, artist_id):
    """Nombre d'abonnés Instagram (dernier snapshot)."""
    db = _db
    try:
        if artist_id is not None:
            row = db.fetch_query(
                """SELECT followers_count, collected_at FROM instagram_daily_stats
                   WHERE artist_id = %s ORDER BY collected_at DESC LIMIT 1""",
                (artist_id,)
            )
        else:
            row = db.fetch_query(
                "SELECT followers_count, collected_at FROM instagram_daily_stats ORDER BY collected_at DESC LIMIT 1"
            )
        if row and row[0][0] is not None:
            return {'followers': int(row[0][0]), 'date': row[0][1]}
    except Exception:
        pass
    return None


@st.cache_data(ttl=60)
def get_soundcloud_likes(_db, artist_id):
    """Total likes SoundCloud (dernière snapshot)."""
    db = _db
    try:
        if artist_id is not None:
            q = """
                SELECT SUM(likes_count) FROM (
                    SELECT DISTINCT ON (track_id) likes_count
                    FROM soundcloud_tracks_daily
                    WHERE artist_id = %s
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q, (artist_id,))
        else:
            q = """
                SELECT SUM(likes_count) FROM (
                    SELECT DISTINCT ON (track_id) likes_count
                    FROM soundcloud_tracks_daily
                    ORDER BY track_id, collected_at DESC
                ) latest
            """
            row = db.fetch_query(q)
        return int(row[0][0] or 0)
    except Exception:
        return 0


# ─── ROI Breakheaven ─────────────────────────────────────────────────────────

def month_window(from_date, to_date):
    """Les bornes JOUR des mois que la fenêtre demandée chevauche.

    `v_artist_monthly_revenue` n'a pas de grain jour : ses colonnes sont `year` et
    `month`. Il n'existe donc AUCUNE fenêtre exacte côté revenu — le mois est le grain
    natif, pas une approximation qu'on choisit.

    On élargit aux mois entiers plutôt que de restreindre aux mois pleinement contenus,
    parce que restreindre rendrait vide toute fenêtre courte, et qu'un revenu vide est
    indiscernable à l'écran d'un revenu absent. L'élargissement est rendu à l'appelant
    (`effective_from` / `effective_to`) pour qu'il puisse le DIRE — un réglage qu'on ne
    peut pas honorer se dit, il ne se tait pas.

    Le défaut que ce helper retire, lu le 2026-09-10 : le revenu était filtré sur
    `make_date(year, month, 1) BETWEEN from AND to` pendant que la dépense Meta l'était
    sur `day_date`. Une fenêtre 15 janvier → 10 septembre excluait janvier en entier et
    comptait tout septembre — numérateur et dénominateur du ROI sur deux périodes
    différentes.
    """
    import calendar
    import datetime as _dt

    def _as_date(d):
        return d.date() if isinstance(d, _dt.datetime) else d

    lo, hi = _as_date(from_date), _as_date(to_date)
    eff_from = lo.replace(day=1)
    eff_to = hi.replace(day=calendar.monthrange(hi.year, hi.month)[1])
    return eff_from, eff_to


def fmt_eur(val, digits: int = 2) -> str:
    """Un montant, ou « — ». Jamais « 0,00 € » pour une valeur qu'on n'a pas pu lire."""
    if val is None:
        return "—"
    return f"{val:,.{digits}f} €"


@st.cache_data(ttl=60)
def get_roi_data(_db, artist_id, from_date, to_date):
    """
    Calcule le ROI iMusician / Meta Ads pour une période donnée.
    Retourne revenue_eur, meta_spend, roi_pct, profitable.
    roi_pct = VRAI ROI = (revenus − dépenses) / dépenses × 100
    (0 % = équilibre, négatif = perte). Pas un ratio revenus/dépenses.
    """
    eff_from, eff_to = month_window(from_date, to_date)
    result = {
        # `None` et non `0.0` : une lecture qui échoue ne se déguise pas en « rien
        # gagné ». `profitable=False` par défaut faisait produire un VERDICT métier
        # par une panne de base (règle .claude/rules/python.md § Erreurs et absences).
        'revenue_eur': None,
        'meta_spend': None,
        'total_spend': None,
        'roi_pct': None,
        'profitable': None,
        # La fenêtre RÉELLEMENT couverte, pour que l'appelant l'affiche.
        'effective_from': eff_from,
        'effective_to': eff_to,
        # LE TROISIÈME ÉTAT. « Rien mesuré » et « on n'a pas pu lire » rendent tous
        # deux None ; sans cette liste l'appelant les confond, et affiche « aucune
        # dépense promo » sur une panne de base.
        'unreadable': [],
    }

    # Revenus distributeurs (iMusician + DistroKid, aggregation sur year+month)
    try:
        if artist_id is not None:
            row = _db.fetch_query(
                """SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue
                   WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s""",
                (artist_id, eff_from, eff_to)
            )
        else:
            row = _db.fetch_query(
                """SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue
                   WHERE make_date(year, month, 1) BETWEEN %s AND %s""",
                (eff_from, eff_to)
            )
        raw = row[0][0] if row else None
        result['revenue_eur'] = float(raw) if raw is not None else None
    except Exception as exc:      # noqa: BLE001 — une tuile ne fait pas tomber la page
        logger.warning("ROI revenue unreadable: %s", type(exc).__name__)
        result['unreadable'].append('revenue')

    # Dépenses Meta Ads
    try:
        if artist_id is not None:
            row = _db.fetch_query(
                """SELECT SUM(spend) FROM meta_insights_performance_day
                   WHERE artist_id = %s AND day_date BETWEEN %s AND %s""",
                (artist_id, eff_from, eff_to)
            )
        else:
            row = _db.fetch_query(
                """SELECT SUM(spend) FROM meta_insights_performance_day
                   WHERE day_date BETWEEN %s AND %s""",
                (eff_from, eff_to)
            )
        raw = row[0][0] if row else None
        result['meta_spend'] = float(raw) if raw is not None else None
    except Exception as exc:      # noqa: BLE001
        logger.warning("ROI spend unreadable: %s", type(exc).__name__)
        result['unreadable'].append('spend')

    # Promo spend = Meta Ads only (the Hypeddit "budget" the user enters is in fact the
    # Meta-ad budget, not a separate Hypeddit spend — so it must not be double-counted).
    result['total_spend'] = result['meta_spend']
    # Un ROI ne se calcule QUE si les deux côtés sont connus. Un côté inconnu rend le
    # verdict inconnu — il ne le rend pas « déficitaire ».
    known = result['revenue_eur'] is not None and result['total_spend'] is not None
    if known and result['total_spend'] > 0:
        result['roi_pct'] = (
            (result['revenue_eur'] - result['total_spend']) / result['total_spend']) * 100
        result['profitable'] = result['revenue_eur'] >= result['total_spend']

    return result


@st.cache_data(ttl=60)
def get_monthly_roi_series(_db, artist_id, from_date, to_date):
    """Monthly revenue vs Meta spend for the period.
    Columns: period_date, distributor_revenue, sacem_revenue, revenue_eur (= the two
    summed), meta_spend. SACEM is kept distinct so the chart can stack it. No Hypeddit
    (the entered Hypeddit budget is in fact the Meta-ad budget — not a real spend)."""
    import pandas as pd

    # LES DEUX SÉRIES SUR LES MÊMES BORNES. Le revenu est mensuel, la dépense
    # quotidienne ; les borner différemment faisait comparer deux périodes.
    eff_from, eff_to = month_window(from_date, to_date)

    def _q(sql_artist, sql_all, cols):
        try:
            if artist_id is not None:
                return _db.fetch_df(sql_artist, (artist_id, eff_from, eff_to))
            return _db.fetch_df(sql_all, (eff_from, eff_to))
        except Exception as exc:      # noqa: BLE001 — une courbe absente ne tue pas la page
            logger.warning("ROI series unreadable (%s): %s", cols[1], type(exc).__name__)
            return pd.DataFrame(columns=cols)

    # Revenue per month — distributor (iMusician + DistroKid) and SACEM split in ONE
    # scan of the revenue view via conditional aggregation (was two separate scans).
    df_rev = _q(
        """SELECT make_date(year, month, 1) AS period_date,
                  SUM(revenue_eur) FILTER (WHERE source IN ('imusician', 'distrokid'))
                      AS distributor_revenue,
                  SUM(revenue_eur) FILTER (WHERE source = 'sacem') AS sacem_revenue
           FROM v_artist_monthly_revenue
           WHERE artist_id = %s AND make_date(year, month, 1) BETWEEN %s AND %s
           GROUP BY year, month ORDER BY year, month""",
        """SELECT make_date(year, month, 1) AS period_date,
                  SUM(revenue_eur) FILTER (WHERE source IN ('imusician', 'distrokid'))
                      AS distributor_revenue,
                  SUM(revenue_eur) FILTER (WHERE source = 'sacem') AS sacem_revenue
           FROM v_artist_monthly_revenue
           WHERE make_date(year, month, 1) BETWEEN %s AND %s
           GROUP BY year, month ORDER BY year, month""",
        ['period_date', 'distributor_revenue', 'sacem_revenue'])

    # Meta spend per month
    df_spend = _q(
        """SELECT DATE_TRUNC('month', day_date)::date AS period_date, SUM(spend) AS meta_spend
           FROM meta_insights_performance_day
           WHERE artist_id = %s AND day_date BETWEEN %s AND %s
           GROUP BY 1 ORDER BY 1""",
        """SELECT DATE_TRUNC('month', day_date)::date AS period_date, SUM(spend) AS meta_spend
           FROM meta_insights_performance_day WHERE day_date BETWEEN %s AND %s
           GROUP BY 1 ORDER BY 1""",
        ['period_date', 'meta_spend'])

    if df_rev.empty and df_spend.empty:
        return pd.DataFrame()

    if df_rev.empty:
        df_rev = pd.DataFrame(columns=['period_date', 'distributor_revenue', 'sacem_revenue'])
    if df_spend.empty:
        df_spend = pd.DataFrame(columns=['period_date', 'meta_spend'])

    # PAS de `.fillna(0)` : un mois présent côté revenu et absent côté Meta n'a pas
    # « 0 € dépensé », il n'a pas de mesure. Les deux appelants pandas
    # (`revenue_forecast.py`, `_tab_budget_roi.py`) étaient DÉJÀ écrits pour l'absence
    # — `.sum()` saute les NaN et l'un fait même un `dropna` explicite ; c'est le
    # helper qui la leur cachait.
    df = pd.merge(df_rev, df_spend, on='period_date', how='outer')
    # LE TYPE, pas seulement la valeur. `.fillna(0)` coerçait accessoirement ces
    # colonnes en float64 ; en le retirant, psycopg2 les laisse en `object` porteuses
    # de `decimal.Decimal`, et le premier `float - Decimal` d'un appelant lève
    # (`revenue_forecast.py:453`, vu rouge le 2026-09-10). C'est la classe
    # `object-dtype-numeric-op` du catalogue. `errors='coerce'` garde les NaN NaN :
    # on convertit le type, on ne remplit pas l'absence.
    for _col in ('distributor_revenue', 'sacem_revenue', 'meta_spend'):
        if _col in df.columns:
            df[_col] = pd.to_numeric(df[_col], errors='coerce')
    df['revenue_eur'] = df['distributor_revenue'] + df['sacem_revenue']
    df['period_date'] = pd.to_datetime(df['period_date'])
    return df.sort_values('period_date')
