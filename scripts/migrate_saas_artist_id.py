#!/usr/bin/env python3
"""Migration script: Add artist_id to all data tables for SaaS multi-tenant support.

Idempotent — safe to re-run on existing databases.

Usage:
    python scripts/migrate_saas_artist_id.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_loader import config_loader
from src.database.postgres_handler import PostgresHandler


# ── Helpers ──────────────────────────────────────────────────────────────────

def table_exists(db: PostgresHandler, table_name: str) -> bool:
    result = db.fetch_query(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = %s",
        (table_name,)
    )
    return bool(result)


def column_exists(db: PostgresHandler, table_name: str, column_name: str) -> bool:
    result = db.fetch_query(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table_name, column_name)
    )
    return bool(result)


def constraint_exists(db: PostgresHandler, table_name: str, constraint_name: str) -> bool:
    result = db.fetch_query(
        "SELECT 1 FROM pg_constraint c "
        "JOIN pg_class t ON c.conrelid = t.oid "
        "WHERE t.relname = %s AND c.conname = %s",
        (table_name, constraint_name)
    )
    return bool(result)


def add_artist_id(db: PostgresHandler, table: str) -> None:
    """Add artist_id column (default 1) and backfill NULLs."""
    if not column_exists(db, table, 'artist_id'):
        print(f"    → Adding artist_id column...")
        db.execute_query(
            f"ALTER TABLE {table} ADD COLUMN artist_id INTEGER DEFAULT 1"
        )
    db.execute_query(
        f"UPDATE {table} SET artist_id = 1 WHERE artist_id IS NULL"
    )
    print(f"    ✓ artist_id present and backfilled")


def drop_constraint_if_exists(db: PostgresHandler, table: str, name: str, cascade: bool = False) -> None:
    if constraint_exists(db, table, name):
        print(f"    → Dropping old constraint {name}{'  CASCADE' if cascade else ''}...")
        suffix = " CASCADE" if cascade else ""
        db.execute_query(f"ALTER TABLE {table} DROP CONSTRAINT {name}{suffix}")


def add_unique_if_missing(db: PostgresHandler, table: str, name: str, cols: str) -> None:
    if not constraint_exists(db, table, name):
        print(f"    → Adding UNIQUE({cols}) as {name}...")
        db.execute_query(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE({cols})"
        )


def add_fk_if_missing(db: PostgresHandler, table: str) -> None:
    fk_name = f"fk_{table}_artist"
    if not constraint_exists(db, table, fk_name):
        print(f"    → Adding FK to saas_artists...")
        db.execute_query(
            f"ALTER TABLE {table} "
            f"ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY (artist_id) REFERENCES saas_artists(id)"
        )


def migrate_table_with_unique(
    db: PostgresHandler,
    table: str,
    old_constraint: str,
    new_constraint: str,
    new_cols: str,
    cascade: bool = False,
) -> None:
    if not table_exists(db, table):
        print(f"  ⚠  {table}: table not found — skipped (will include artist_id when created)")
        return
    print(f"  Table: {table}")
    add_artist_id(db, table)
    drop_constraint_if_exists(db, table, old_constraint, cascade=cascade)
    add_unique_if_missing(db, table, new_constraint, new_cols)
    add_fk_if_missing(db, table)


def migrate_table_no_unique(db: PostgresHandler, table: str) -> None:
    if not table_exists(db, table):
        print(f"  ⚠  {table}: table not found — skipped")
        return
    print(f"  Table: {table}")
    add_artist_id(db, table)
    add_fk_if_missing(db, table)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("MIGRATION — SaaS artist_id (Brick 1)")
    print("=" * 70)

    config = config_loader.load()
    db = PostgresHandler(**config['database'])

    try:
        # ── Step 1: saas_artists ──────────────────────────────────────────
        print("\n[1/9] saas_artists")
        if not table_exists(db, 'saas_artists'):
            print("  → Creating table...")
            db.execute_query("""
                CREATE TABLE saas_artists (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    tier VARCHAR(20) NOT NULL DEFAULT 'basic'
                        CHECK (tier IN ('basic', 'premium')),
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        print("  → Seeding default artist (id=1)...")
        db.execute_query("""
            INSERT INTO saas_artists (id, name, slug, tier, active)
            VALUES (1, 'Artist Default', 'default', 'premium', TRUE)
            ON CONFLICT (slug) DO NOTHING
        """)
        db.execute_query(
            "SELECT setval('saas_artists_id_seq', "
            "GREATEST(1, (SELECT MAX(id) FROM saas_artists)))"
        )
        print("  ✓ saas_artists ready")

        # ── Step 2: artist_credentials ────────────────────────────────────
        print("\n[2/9] artist_credentials")
        if not table_exists(db, 'artist_credentials'):
            print("  → Creating table...")
            db.execute_query("""
                CREATE TABLE artist_credentials (
                    id SERIAL PRIMARY KEY,
                    artist_id INTEGER NOT NULL
                        REFERENCES saas_artists(id) ON DELETE CASCADE,
                    platform VARCHAR(50) NOT NULL,
                    token_encrypted TEXT,
                    extra_config JSONB,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(artist_id, platform)
                )
            """)
        print("  ✓ artist_credentials ready")

        # ── Step 3: S4A tables ────────────────────────────────────────────
        print("\n[3/9] Spotify for Artists tables")
        migrate_table_with_unique(
            db, 's4a_songs_global',
            's4a_songs_global_song_key',
            's4a_songs_global_artist_id_song_key',
            'artist_id, song',
        )
        migrate_table_with_unique(
            db, 's4a_song_timeline',
            's4a_song_timeline_song_date_key',
            's4a_song_timeline_artist_id_song_date_key',
            'artist_id, song, date',
        )
        migrate_table_with_unique(
            db, 's4a_audience',
            's4a_audience_date_key',
            's4a_audience_artist_id_date_key',
            'artist_id, date',
        )

        # ── Step 4: Apple Music tables ────────────────────────────────────
        print("\n[4/9] Apple Music tables")
        migrate_table_with_unique(
            db, 'apple_songs_performance',
            'apple_songs_performance_song_name_key',
            'apple_songs_performance_artist_id_song_name_key',
            'artist_id, song_name',
        )
        migrate_table_with_unique(
            db, 'apple_daily_plays',
            'apple_daily_plays_song_name_date_key',
            'apple_daily_plays_artist_id_song_name_date_key',
            'artist_id, song_name, date',
        )
        migrate_table_with_unique(
            db, 'apple_listeners',
            'apple_listeners_date_key',
            'apple_listeners_artist_id_date_key',
            'artist_id, date',
        )

        # ── Step 5: Meta Ads tables ───────────────────────────────────────
        print("\n[5/9] Meta Ads tables")
        for t in ['meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights']:
            migrate_table_no_unique(db, t)

        # ── Step 6: Hypeddit tables ───────────────────────────────────────
        # Special handling: fk_hypeddit_campaign on daily_stats references
        # hypeddit_campaigns_campaign_name_key — must drop FK first (CASCADE),
        # then recreate as composite (artist_id, campaign_name) after both tables migrated.
        print("\n[6/9] Hypeddit tables")
        migrate_table_with_unique(
            db, 'hypeddit_campaigns',
            'hypeddit_campaigns_campaign_name_key',
            'hypeddit_campaigns_artist_id_campaign_name_key',
            'artist_id, campaign_name',
            cascade=True,  # drops dependent fk_hypeddit_campaign on daily_stats
        )
        migrate_table_with_unique(
            db, 'hypeddit_daily_stats',
            'hypeddit_daily_stats_campaign_name_date_key',
            'hypeddit_daily_stats_artist_id_campaign_name_date_key',
            'artist_id, campaign_name, date',
        )
        # Recreate cross-table FK as composite (artist_id, campaign_name)
        if (table_exists(db, 'hypeddit_campaigns')
                and table_exists(db, 'hypeddit_daily_stats')
                and not constraint_exists(db, 'hypeddit_daily_stats', 'fk_hypeddit_campaign')):
            print("  → Recreating fk_hypeddit_campaign as composite FK...")
            db.execute_query("""
                ALTER TABLE hypeddit_daily_stats
                ADD CONSTRAINT fk_hypeddit_campaign
                FOREIGN KEY (artist_id, campaign_name)
                REFERENCES hypeddit_campaigns(artist_id, campaign_name)
                ON DELETE CASCADE
            """)

        # ── Step 6b: Meta Insights tables (pre-existing, no schema file before) ──
        print("\n[6b/9] Meta Insights tables")
        for table, old_c, new_c, new_cols in [
            ('meta_insights_performance',
             'meta_insights_performance_campaign_name_date_start_key',
             'meta_insights_performance_artist_id_campaign_name_date_start_key',
             'artist_id, campaign_name, date_start'),
            ('meta_insights_performance_day',
             'meta_insights_performance_day_campaign_name_day_date_key',
             'meta_insights_performance_day_artist_id_campaign_name_day_date_key',
             'artist_id, campaign_name, day_date'),
            ('meta_insights_performance_age',
             'meta_insights_performance_age_campaign_name_age_range_key',
             'meta_insights_performance_age_artist_id_campaign_name_age_range_key',
             'artist_id, campaign_name, age_range'),
            ('meta_insights_performance_country',
             'meta_insights_performance_country_campaign_name_country_key',
             'meta_insights_performance_country_artist_id_campaign_name_country_key',
             'artist_id, campaign_name, country'),
            ('meta_insights_performance_placement',
             'meta_insights_performance_placement_campaign_name_platform_placement_key',
             'meta_insights_performance_placement_artist_id_campaign_name_platform_placement_key',
             'artist_id, campaign_name, platform, placement'),
            ('meta_insights_engagement',
             'meta_insights_engagement_campaign_name_date_start_key',
             'meta_insights_engagement_artist_id_campaign_name_date_start_key',
             'artist_id, campaign_name, date_start'),
            ('meta_insights_engagement_day',
             'meta_insights_engagement_day_campaign_name_day_date_key',
             'meta_insights_engagement_day_artist_id_campaign_name_day_date_key',
             'artist_id, campaign_name, day_date'),
            ('meta_insights_engagement_age',
             'meta_insights_engagement_age_campaign_name_age_range_key',
             'meta_insights_engagement_age_artist_id_campaign_name_age_range_key',
             'artist_id, campaign_name, age_range'),
            ('meta_insights_engagement_country',
             'meta_insights_engagement_country_campaign_name_country_key',
             'meta_insights_engagement_country_artist_id_campaign_name_country_key',
             'artist_id, campaign_name, country'),
            ('meta_insights_engagement_placement',
             'meta_insights_engagement_placement_campaign_name_platform_placement_key',
             'meta_insights_engagement_placement_artist_id_campaign_name_platform_placement_key',
             'artist_id, campaign_name, platform, placement'),
        ]:
            migrate_table_with_unique(db, table, old_c, new_c, new_cols)

        # ── Step 7: YouTube tables ────────────────────────────────────────
        print("\n[7/9] YouTube tables")
        for t in [
            'youtube_channels', 'youtube_channel_history', 'youtube_videos',
            'youtube_video_stats', 'youtube_playlists', 'youtube_comments',
        ]:
            migrate_table_no_unique(db, t)

        # ── Step 8: track_popularity_history ──────────────────────────────
        print("\n[8/9] track_popularity_history")
        migrate_table_with_unique(
            db, 'track_popularity_history',
            'track_popularity_history_track_id_date_key',
            'track_popularity_history_artist_id_track_id_date_key',
            'artist_id, track_id, date',
        )

        # ── Step 9: SoundCloud & Instagram ───────────────────────────────
        print("\n[9/9] SoundCloud & Instagram")

        if not table_exists(db, 'soundcloud_tracks_daily'):
            print("  soundcloud_tracks_daily: creating with artist_id...")
            db.execute_query("""
                CREATE TABLE soundcloud_tracks_daily (
                    id SERIAL PRIMARY KEY,
                    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
                    track_id VARCHAR(50) NOT NULL,
                    title VARCHAR(500),
                    permalink_url TEXT,
                    playback_count INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    reposts_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    collected_at DATE DEFAULT CURRENT_DATE,
                    UNIQUE(artist_id, track_id, collected_at)
                )
            """)
        else:
            print("  Table: soundcloud_tracks_daily")
            add_artist_id(db, 'soundcloud_tracks_daily')
            add_unique_if_missing(
                db, 'soundcloud_tracks_daily',
                'soundcloud_tracks_daily_artist_id_track_id_collected_at_key',
                'artist_id, track_id, collected_at',
            )
            add_fk_if_missing(db, 'soundcloud_tracks_daily')

        if not table_exists(db, 'instagram_daily_stats'):
            print("  instagram_daily_stats: creating with artist_id...")
            db.execute_query("""
                CREATE TABLE instagram_daily_stats (
                    id SERIAL PRIMARY KEY,
                    artist_id INTEGER DEFAULT 1 REFERENCES saas_artists(id),
                    ig_user_id VARCHAR(50) NOT NULL,
                    username VARCHAR(255),
                    followers_count INTEGER DEFAULT 0,
                    follows_count INTEGER DEFAULT 0,
                    media_count INTEGER DEFAULT 0,
                    collected_at DATE DEFAULT CURRENT_DATE,
                    UNIQUE(artist_id, ig_user_id, collected_at)
                )
            """)
        else:
            print("  Table: instagram_daily_stats")
            add_artist_id(db, 'instagram_daily_stats')
            add_unique_if_missing(
                db, 'instagram_daily_stats',
                'instagram_daily_stats_artist_id_ig_user_id_collected_at_key',
                'artist_id, ig_user_id, collected_at',
            )
            add_fk_if_missing(db, 'instagram_daily_stats')

        # ── Summary ───────────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)

        all_tables = [
            'saas_artists', 'artist_credentials',
            's4a_songs_global', 's4a_song_timeline', 's4a_audience',
            'apple_songs_performance', 'apple_daily_plays', 'apple_listeners',
            'meta_campaigns', 'meta_adsets', 'meta_ads', 'meta_insights',
            'meta_insights_performance', 'meta_insights_performance_day',
            'meta_insights_performance_age', 'meta_insights_performance_country',
            'meta_insights_performance_placement',
            'meta_insights_engagement', 'meta_insights_engagement_day',
            'meta_insights_engagement_age', 'meta_insights_engagement_country',
            'meta_insights_engagement_placement',
            'hypeddit_campaigns', 'hypeddit_daily_stats',
            'youtube_channels', 'youtube_channel_history', 'youtube_videos',
            'youtube_video_stats', 'youtube_playlists', 'youtube_comments',
            'track_popularity_history',
            'soundcloud_tracks_daily', 'instagram_daily_stats',
        ]

        ok = 0
        warn = 0
        for t in all_tables:
            if table_exists(db, t):
                has_aid = column_exists(db, t, 'artist_id') or t in ('saas_artists', 'artist_credentials')
                count = db.get_table_count(t)
                status = "✓" if has_aid else "⚠ NO artist_id"
                print(f"  {status}  {t:<45} {count:>6} rows")
                if has_aid:
                    ok += 1
                else:
                    warn += 1
            else:
                print(f"  ✗  {t:<45} MISSING")
                warn += 1

        print(f"\n  {ok} OK  |  {warn} warnings")
        print("\n✅ Migration complete")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
