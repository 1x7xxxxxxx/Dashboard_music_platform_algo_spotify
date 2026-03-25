# Audit: Silent Success Anti-Pattern in Collectors

## What it is
A collector method catches an API error, logs it, then returns empty data (`None`, `[]`, `{}`).
The DAG task receives the empty result, upserts 0 rows, and exits `SUCCESS`.
No alert fires. The dashboard silently shows stale or missing data.

## How to detect

Search every `except` block in `src/collectors/` for these patterns:

```bash
grep -n "return None\|return \[\]\|return {}\|return tracks\|return stats\|return data" src/collectors/*.py
```

Also look for:
- `break` after a non-2xx status code check inside a loop (silently stops pagination)
- `except Exception` that wraps an inner `except ValueError: raise`, preventing re-raise of specific errors

## How to fix

### Rule 1 — always re-raise in collector methods
```python
# BAD
except Exception as e:
    logger.error(f"Error: {e}")
    return None          # silent success

# GOOD
except Exception as e:
    logger.error(f"Error: {e}")
    raise                # propagates → DAG task FAILED
```

### Rule 2 — raise on non-200, never break silently
```python
# BAD
if response.status_code != 200:
    print(f"Error {response.status_code}")
    break

# GOOD
if response.status_code == 401:
    raise ValueError("API 401 — token expired. Renew via Dashboard → Credentials.")
if response.status_code != 200:
    raise ValueError(f"API {response.status_code}: {response.text[:200]}")
```

### Rule 3 — specific exceptions must not be swallowed by outer except
```python
# BAD — ValueError raised inside is caught by outer except
try:
    if status == 401:
        raise ValueError("401")
except Exception as e:
    print(e)
    break               # ValueError silently eaten

# GOOD
except ValueError:
    raise
except Exception as e:
    raise RuntimeError(f"Fetch error: {e}") from e
```

### Rule 4 — zero-row guard in DAGs (defence in depth)
After processing all artists, check that at least one succeeded:
```python
if artists_with_creds > 0 and successful_fetches == 0:
    raise ValueError("All API calls returned 0 rows — possible credential/network failure.")
```

## Files audited and status (as of 2026-03-25)

| File | Status |
|---|---|
| `src/collectors/spotify_api.py` | ✅ Fixed — get_artist_info, get_artist_top_tracks now raise |
| `src/collectors/youtube_collector.py` | ✅ Fixed — get_channel_stats, get_channel_videos, get_video_stats now raise |
| `src/collectors/soundcloud_api_collector.py` | ✅ Fixed — non-200 raises ValueError; outer except re-raises ValueError |
| `src/collectors/instagram_api_collector.py` | ✅ Fixed — 401/400 raise ValueError; generic raises RuntimeError |
| `airflow/dags/youtube_daily.py` | ✅ Fixed — zero-row guard after artist loop |
| `airflow/dags/spotify_api_daily.py` | ✅ Fixed — zero-row guard in collect_spotify_artists + collect_spotify_top_tracks |
| `airflow/dags/instagram_daily.py` | ✅ Fixed — precheck task; ig_user_id bug fixed |
| `airflow/dags/soundcloud_daily.py` | ✅ Fixed — precheck task; user_id propagated |

## When to re-run this audit
Run after adding any new collector or DAG. Check every `except` block in `src/collectors/`.
