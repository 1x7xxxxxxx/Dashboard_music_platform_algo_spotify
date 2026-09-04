"""Keep an imported CSV for a fortnight, so a bad import can be re-read.

Type: Utility
Uses: pathlib, hashlib, datetime — no DB, no streamlit
Triggers: views/upload_csv.py
Persists in: data/uploads/<artist_id>/

Why this exists — 2026-09-04.

`upload_csv.py` reads the file into memory, parses it, upserts, and lets the bytes go.
So when an import lands wrong — a column renamed upstream, a separator misread, a
tenant's numbers that look off a week later — **the only copy of what was actually
sent is gone**. `csv_upload_log` records that a file called X produced N rows; it
cannot answer "what was in X".

That gap is what made the four `*_csv_watcher` DAGs feel necessary: they watched a
directory, so a file dropped there stayed on disk. But they polled directories that
have never held a file, cost 98,4 % of all Airflow task rows, and covered LESS than
the upload page (`parse_csv_file` builds no `songs_global` rows; the page does). The
useful half of a directory watcher was never the polling — it was that the file
survived. This keeps that half and drops the rest.

## The rules, and why each

* **Only after the rows landed.** An archive of files that failed to import would fill
  up with the uninteresting case; the interesting one is a file that imported
  *successfully* and still produced wrong numbers.
* **14 days.** Long enough to cover "the artist noticed last week"; short enough that
  this never becomes a data store with its own retention policy and GDPR surface.
* **The tenant owns the directory.** `data/uploads/<artist_id>/` — a flat directory
  would make one tenant's file readable by a path guess, and the deletion of one
  tenant's data would become a grep.
* **The filename is rebuilt, never trusted.** It arrives from a browser: `..%2F` and
  friends are one string away from writing outside the tree.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 14

# Anything outside this set is replaced. Built as an allowlist rather than a denylist
# of `../`: a denylist has to anticipate every encoding of the same idea, and this one
# arrives from a browser.
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def uploads_root() -> Path:
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "data" / "uploads"


def safe_name(filename: str) -> str:
    """A filename that cannot escape its directory, and still reads like the original."""
    stem = unicodedata.normalize("NFKD", filename or "sans-nom")
    stem = stem.encode("ascii", "ignore").decode("ascii")
    stem = _SAFE.sub("_", stem).strip("._-") or "sans-nom"
    # Les points consécutifs sont écrasés. Sans séparateur, un `..` restant dans le
    # nom ne traverse rien — `test_the_archived_path_stays_under_the_tenant_directory`
    # le prouve sur le chemin résolu. Mais `..%2F..%2Fx` donnait `2F.._2Fx`, un nom
    # qui CONTIENT `..` : suffisamment piégeux pour qu'un outil en aval le traite
    # comme un segment, et il ne coûte rien de le rendre impossible ici.
    stem = re.sub(r"\.{2,}", ".", stem).strip("._-") or "sans-nom"
    return stem[:120]


def archive_upload(artist_id: int, filename: str, data: bytes) -> Path | None:
    """Store one successfully-imported file. Returns its path, or None if it could not.

    Never raises. An archive is a convenience for a future diagnosis; failing the
    import because the copy could not be written would trade a working feature for a
    nice-to-have — and the row is already in the database by the time this runs.
    """
    if not data:
        return None
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_dir = uploads_root() / str(int(artist_id))
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{stamp}_{safe_name(filename)}"
        path.write_bytes(data)
        return path
    except (OSError, ValueError, TypeError):
        return None


def purge_expired(days: int = RETENTION_DAYS) -> int:
    """Delete archived uploads older than `days`. Returns how many were removed.

    Called opportunistically from the upload page rather than from a cron: the
    directory only grows when someone uploads, so the purge only needs to run then.
    One less scheduled thing to forget — and this repo has just spent a session on a
    restore drill that sat unscheduled since June.
    """
    root = uploads_root()
    if not root.is_dir():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def archived_for(artist_id: int) -> list[Path]:
    """What is currently kept for this tenant, newest first."""
    d = uploads_root() / str(int(artist_id))
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_file()),
                  key=lambda p: p.name, reverse=True)
