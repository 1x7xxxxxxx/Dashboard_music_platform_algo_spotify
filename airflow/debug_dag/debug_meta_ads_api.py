"""Debug script for meta_ads_api_daily DAG.

Steps:
  1. Credential check — verify access_token, app_id, app_secret, account_id in DB.
  2. API connectivity — call /me endpoint with the access token.
  3. Dry-run — fetch campaigns (no DB write), print count + first 3 names.
  4. Full run — only with --write flag; persists to DB.

Usage:
  python airflow/debug_dag/debug_meta_ads_api.py                         # steps 1-3 only
  python airflow/debug_dag/debug_meta_ads_api.py --write                 # step 4, last 90 days
  python airflow/debug_dag/debug_meta_ads_api.py --write --full-history  # step 4, full history
  python airflow/debug_dag/debug_meta_ads_api.py --artist 2              # specific artist
"""
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env.local', override=True)
load_dotenv(project_root / '.env')


def main():
    parser = argparse.ArgumentParser(description='Debug Meta Ads API collector')
    parser.add_argument('--write', action='store_true', help='Persist results to DB (step 4)')
    parser.add_argument('--full-history', action='store_true',
                        help='Fetch all historical data (monthly chunks from earliest campaign start)')
    parser.add_argument('--insights-only', action='store_true',
                        help='Skip campaigns/adsets/ads fetch (already in DB); only run insight calls')
    parser.add_argument('--skip-creatives', action='store_true',
                        help='Skip per-creative content fetch (title/body/CTA) — the dominant '
                             'rate-limit driver on full-history; not needed for the Créatives view')
    parser.add_argument('--artist', type=int, default=1, help='artist_id to test (default: 1)')
    args = parser.parse_args()
    artist_id = args.artist

    mode = "FULL HISTORY" if args.full_history else "last 90 days"
    print(f"\n{'='*60}")
    print(f"Debug meta_ads_api_daily — artist_id={artist_id} [{mode}]")
    print(f"{'='*60}")

    # ── Step 1: Credential check ──────────────────────────────────
    print("\n[1/4] Credential check...")
    from src.utils.credential_loader import load_platform_credentials
    creds = load_platform_credentials(artist_id, 'meta')
    required = ['access_token', 'app_id', 'app_secret', 'account_id']
    missing = [k for k in required if not creds.get(k)]
    if missing:
        print(f"  ❌ Missing: {missing}")
        print("  → Configure via Dashboard → Credentials → Meta")
        sys.exit(1)
    raw_id = creds['account_id']
    ad_account_id = raw_id if raw_id.startswith('act_') else f"act_{raw_id}"
    print(f"  ✅ access_token  : {'*' * 12}{creds['access_token'][-6:]}")
    print(f"  ✅ app_id         : {creds['app_id']}")
    print(f"  ✅ ad_account_id  : {ad_account_id}")

    # ── Step 2: API connectivity ──────────────────────────────────
    print("\n[2/4] API connectivity test...")
    try:
        import requests
        resp = requests.get(
            'https://graph.facebook.com/v24.0/me',
            params={'access_token': creds['access_token'], 'fields': 'id,name'},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"  ✅ Connected as: {data.get('name')} (id={data.get('id')})")
    except Exception as e:
        print(f"  ❌ Connectivity failed: {e}")
        sys.exit(1)

    # ── Step 3: Dry-run campaigns fetch ───────────────────────────
    print("\n[3/4] Dry-run — fetching campaigns (no DB write)...")
    try:
        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.campaign import Campaign

        FacebookAdsApi.init(
            app_id=creds['app_id'],
            app_secret=creds['app_secret'],
            access_token=creds['access_token'],
            api_version='v24.0',
        )
        ad_account = AdAccount(ad_account_id)
        # Route through the collector's throttle-aware retry so a transient 80004/4
        # on the probe doesn't hard-fail before the real run even starts.
        from src.collectors.meta_ads_api_collector import _meta_list
        campaigns = _meta_list(
            ad_account.get_campaigns,
            fields=[Campaign.Field.id, Campaign.Field.name, Campaign.Field.status],
            params={'limit': 100, 'effective_status': ['ACTIVE', 'PAUSED']},
        )
        print(f"  ✅ {len(campaigns)} campaigns found (ACTIVE/PAUSED)")
        for c in campaigns[:3]:
            print(f"     - {c['name']} [{c['status']}]")
        if len(campaigns) > 3:
            print(f"     ... and {len(campaigns) - 3} more")
    except Exception as e:
        print(f"  ❌ Dry-run failed: {e}")
        sys.exit(1)

    # ── Step 4: Full run (--write only) ───────────────────────────
    if not args.write:
        print("\n[4/4] Full run — skipped (use --write to persist to DB)")
        print("\nTip: add --full-history to fetch all data from earliest campaign start.")
        print("\n✅ Dry-run complete.")
        return

    mode_parts = []
    if args.full_history:
        mode_parts.append("FULL HISTORY")
    if args.insights_only:
        mode_parts.append("insights only")
    if args.skip_creatives:
        mode_parts.append("no creatives")
    hist_label = f" ({', '.join(mode_parts)})" if mode_parts else " (last 90 days)"
    print(f"\n[4/4] Full run — writing to DB{hist_label}...")
    try:
        from src.collectors.meta_ads_api_collector import MetaAdsApiCollector
        collector = MetaAdsApiCollector(artist_id=artist_id)
        collector.run(full_history=args.full_history, insights_only=args.insights_only,
                      fetch_creatives=not args.skip_creatives)
        print("  ✅ Full collection complete.")
        print("\n  DB row counts (check these):")
        for tbl in [
            'meta_campaigns', 'meta_adsets', 'meta_ads',
            'meta_insights_performance', 'meta_insights_performance_day',
            'meta_insights_performance_age', 'meta_insights_performance_country',
            'meta_insights_performance_placement',
            'meta_insights_engagement', 'meta_insights_engagement_day',
            'meta_insights_engagement_age', 'meta_insights_engagement_country',
            'meta_insights_engagement_placement',
        ]:
            try:
                rows = collector.db.fetch_query(
                    f"SELECT COUNT(*) FROM {tbl} WHERE artist_id = %s",
                    (artist_id,),
                )
                count = rows[0][0] if rows else '?'
                print(f"    {tbl:<45} {count:>6} rows")
            except Exception as count_err:
                print(f"    {tbl:<45} ERROR: {count_err}")
    except Exception as e:
        print(f"  ❌ Full run failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Done.")


if __name__ == '__main__':
    main()
