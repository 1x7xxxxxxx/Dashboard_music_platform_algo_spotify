"""Meta Ads collector — throttle-aware retry helpers (leaf, imports no siblings).

Type: Sub
Uses: facebook_business.exceptions.FacebookRequestError (lazy, in-function)
Depends on: nothing (leaf module to avoid circular imports)

Pure module functions, already unit-tested. Retry any Meta throttle code with
exponential backoff; materialise list cursors inside the retry loop.
"""
import logging
import time

logger = logging.getLogger(__name__)

# Meta throttling error codes (all transient, safe to retry with backoff):
#   17    — user-level rate limit
#   4     — app-level request limit ("Application request limit reached")
#   80004 — ads-management business-use-case throttle ("too many calls to this ad-account")
#   32    — page-level rate limit
# A backfill that includes archived ads multiplies call volume, so the run must
# back off on ALL of these — handling only code 17 made the placement-insights call
# hard-fail on code 4.
_META_THROTTLE_CODES = frozenset({4, 17, 32, 80004})
_META_RATE_LIMIT_WAIT = 60  # base seconds; multiplied per attempt (exponential)


def _meta_retry(callable_fn, *args, max_retries: int = 4, **kwargs):
    """Call a facebook_business SDK method, retrying any throttle code with exponential backoff.

    Works for both list edges (get_insights, get_ads…) and single-object reads
    (AdCreative.api_get). Returns the callable's raw result.
    """
    from facebook_business.exceptions import FacebookRequestError
    for attempt in range(1, max_retries + 1):
        try:
            return callable_fn(*args, **kwargs)
        except FacebookRequestError as exc:
            if exc.api_error_code() in _META_THROTTLE_CODES and attempt < max_retries:
                wait = _META_RATE_LIMIT_WAIT * (2 ** (attempt - 1))  # 60s, 120s, 240s
                logger.warning(
                    f"Meta throttle (code {exc.api_error_code()}) — attempt "
                    f"{attempt}/{max_retries}. Waiting {wait}s before retry..."
                )
                time.sleep(wait)
            else:
                raise


def _meta_list(callable_fn, *args, **kwargs) -> list:
    """Throttle-aware list call — materialises the cursor INSIDE the retry loop.

    The SDK raises during cursor iteration (load_next_page), so list() must run
    within _meta_retry or a paging throttle would escape un-retried.
    """
    return _meta_retry(lambda: list(callable_fn(*args, **kwargs)))
