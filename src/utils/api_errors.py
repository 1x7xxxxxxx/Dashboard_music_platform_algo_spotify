"""Read what an upstream API error actually MEANS — from its structure, never its text.

Type: Utility
Uses: nothing (stdlib only — must import without the vendor SDKs installed)
Triggers: any `except` that has to tell "a valid empty state" from "a real failure"
Persists in: nothing

Why this module exists, and why it is not inside the collector — measured 2026-08-23.

`youtube_collector` already had an empty-channel branch, and it was UNREACHABLE:

    if ... and 'playlistNotFound' in safe_error(he):   # never true

`safe_error()` truncates at 300 characters for LOG HYGIENE. In a real googleapiclient
repr the URL alone is ~170 characters, and the token `playlistNotFound` sits at index
455 of 531. So a decision about control flow was being made on a string that had been
shortened for DISPLAY. Every night `youtube_daily` retried 3x and raised for a tenant
whose channel simply had no videos, losing the channel snapshot already fetched, while
the DAG stayed SUCCESS.

Two rules follow, and they are why this file is separate:

1. **Decide on structure, not on text.** `HttpError.error_details` is a list of dicts
   carrying a machine-readable `reason`. Read that.
2. **A guard must be runnable where it is tested.** Keeping this next to
   `from googleapiclient.discovery import build` made its test uncollectable on any
   machine without the Google SDK — and a guard that silently does not run is the
   defect this repo keeps rediscovering. Nothing here imports a vendor SDK.
"""
from __future__ import annotations


def is_empty_uploads_playlist(exc: BaseException) -> bool:
    """True when a 404 means "this channel has no uploads playlist", i.e. zero videos.

    A YouTube channel with no public uploads has no uploads playlist, so asking for its
    items answers 404 `playlistNotFound`. That is a valid state for a brand-new artist,
    not a failure.

    A 404 on the CHANNEL itself is a different thing and is not matched here — it stays
    an error, and the collector still raises (project rule #6).
    """
    resp = getattr(exc, "resp", None)
    if resp is None or getattr(resp, "status", None) != 404:
        return False
    # `error_details` defaults to "" (a str) in googleapiclient; iterating that would
    # yield characters, so the dict check is load-bearing, not defensive noise.
    for detail in getattr(exc, "error_details", None) or []:
        if isinstance(detail, dict) and detail.get("reason") == "playlistNotFound":
            return True
    return False
