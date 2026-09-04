"""Give a defect a stable identity, so two occurrences of it are one row.

Type: Utility
Uses: hashlib, traceback
Triggers: dashboard.utils.error_alert, tools/error_inbox.py
Depends on: nothing
Persists in: nothing (pure)

The whole point is what the fingerprint LEAVES OUT.

* **the line number** — it moves at the first commit that touches anything above the
  frame, and a counter that restarts at 1 on every deploy measures nothing;
* **the message** — it usually carries a value (an id, a key, a URL) that differs on
  every occurrence, so keeping it would give one row per occurrence, which is what an
  inbox already is;
* **third-party frames** — `site-packages/streamlit/...` describes Streamlit's
  machinery, not our defect. The last frame of the real traceback is almost always in
  a library; the frame that identifies the bug is the deepest one WE own.

What it keeps: the exception class, and `path:function` of that first frame of ours,
repo-relative so a local run and a container agree.

Measured on the real case that prompted this (2026-09-04): the same
`StreamlitAPIException` arrived with its last frame in
`streamlit/runtime/state/session_state.py`, three different line numbers across two
days, and a message naming a different `_nav_<section>` key each time. Fingerprinted on
the raw traceback it is three unrelated defects; fingerprinted here it is one, called
`utils/navigation.py:goto`.
"""
from __future__ import annotations

import hashlib
import traceback
from typing import Optional

# A frame is "ours" when its path is inside the repo and not a dependency. Kept as a
# suffix test rather than an absolute prefix: the same code runs from /app in the
# container, /opt/airflow in the scheduler and /mnt/c/... on the dev box.
_OURS = ("/src/", "/airflow/dags/", "/tools/", "\\src\\", "\\airflow\\dags\\")
_THEIRS = ("site-packages", "dist-packages", "/usr/lib/python", "lib/python3")


def _repo_relative(path: str) -> str:
    """`…/Dashboard_music…/src/dashboard/x.py` → `src/dashboard/x.py`."""
    norm = path.replace("\\", "/")
    for anchor in ("/src/", "/airflow/dags/", "/tools/"):
        idx = norm.rfind(anchor)
        if idx != -1:
            return norm[idx + 1:]
    return norm.rsplit("/", 1)[-1]


def origin_frame(exc: BaseException) -> Optional[str]:
    """`src/dashboard/utils/navigation.py:goto` — the deepest frame we own, or None."""
    try:
        frames = traceback.extract_tb(exc.__traceback__)
    except Exception:      # noqa: BLE001 — fingerprinting must never raise
        return None
    ours = [f for f in frames
            if any(a in f.filename.replace("\\", "/") or a in f.filename for a in _OURS)
            and not any(t in f.filename.replace("\\", "/") for t in _THEIRS)]
    if not ours:
        return None
    frame = ours[-1]       # deepest of ours = where our code actually went wrong
    return f"{_repo_relative(frame.filename)}:{frame.name}"


def fingerprint(exc: BaseException) -> str:
    """Stable 40-char id for this DEFECT — not for this occurrence."""
    origin = origin_frame(exc) or "unknown"
    raw = f"{type(exc).__name__}|{origin}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
