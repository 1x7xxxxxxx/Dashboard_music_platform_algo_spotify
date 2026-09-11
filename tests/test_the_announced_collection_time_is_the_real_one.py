"""The hour the home page promises is the hour the DAG actually runs.

Type: Test
Uses: ast, re
Depends on: src/dashboard/utils/kpi_helpers.py, airflow/dags/*.py
Persists in: nothing

Why this exists
---------------
Asked on 2026-09-11: group the freshness tiles into APIs and CSVs, and say
underneath at what time the data arrives. Saying it means copying the DAG
schedules into `SOURCES_CONFIG` — a duplication, and duplications drift.

The drift here is worse than cosmetic. A tenant who reads "chaque jour à 08:00"
and sees nothing new at 09:00 concludes the product is broken; if the DAG had
been moved to 11:00 and nobody updated the tile, the product is fine and the
sentence is the defect. The repository has a name for this shape — a promise the
code no longer keeps — and the cheap way out is to not promise. The better way
is to promise and pin it.

So: every source declared `kind="api"` must name an hour, that hour must match
its DAG's `schedule`, and every `kind="csv"` source must name none — a CSV
arrives when someone drops it, and inventing a time for it would be the same
defect in the other direction.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_ROOT = _repo_root()
_DAGS = _ROOT / "airflow" / "dags"

# source label -> the DAG file that feeds it. Only API sources appear: a CSV has
# no DAG, which is exactly what makes it a CSV.
_DAG_FOR = {
    "Spotify API": "spotify_api_daily.py",
    "YouTube": "youtube_daily.py",
    "SoundCloud": "soundcloud_daily.py",
    "Instagram": "instagram_daily.py",
    "Meta Ads": "meta_ads_api_daily.py",
}

_CRON = re.compile(r"""['"]0\s+(\d{1,2})\s+\*\s+\*\s+\*['"]""")


def _sources() -> list[dict]:
    from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG
    return list(SOURCES_CONFIG)


def _dag_hour(filename: str) -> int | None:
    """The hour in the DAG's daily schedule, or None if it is not a daily cron."""
    path = _DAGS / filename
    if not path.exists():
        return None
    hours = {int(m.group(1)) for m in _CRON.finditer(path.read_text(encoding="utf-8"))}
    return hours.pop() if len(hours) == 1 else None


def test_every_source_declares_whether_it_is_collected_or_uploaded() -> None:
    missing = [s["label"] for s in _sources() if s.get("kind") not in ("api", "csv")]
    assert not missing, (
        f"source(s) without a `kind`: {missing}. The home page groups the freshness "
        "tiles by it; an unclassified source silently disappears from both groups."
    )


def test_an_api_source_announces_the_hour_its_dag_actually_runs() -> None:
    wrong = []
    for src in _sources():
        if src.get("kind") != "api":
            continue
        label, announced = src["label"], src.get("at")
        if not announced:
            wrong.append(f"{label}: announces no hour while collected automatically")
            continue
        dag = _DAG_FOR.get(label)
        if dag is None:
            wrong.append(f"{label}: no DAG mapped in this test — add it or mark it csv")
            continue
        real = _dag_hour(dag)
        if real is None:
            wrong.append(f"{label}: {dag} has no single daily cron to compare against")
            continue
        if int(announced.split(":")[0]) != real:
            wrong.append(
                f"{label}: the page promises {announced}, {dag} runs at {real:02d}:00"
            )
    assert not wrong, (
        "The home page announces a collection time that the DAG does not keep. A "
        "tenant reading it concludes the product is broken while it is working.\n\n"
        + "\n".join(wrong)
    )


def test_a_csv_source_promises_no_hour() -> None:
    """A file arrives when someone drops it. Naming a time would invent one."""
    wrong = [s["label"] for s in _sources() if s.get("kind") == "csv" and s.get("at")]
    assert not wrong, (
        f"CSV source(s) announcing a collection time: {wrong}. Nothing collects them "
        "on a schedule — the tile would promise an arrival that never happens."
    )


def test_the_dag_map_still_points_at_files_that_exist() -> None:
    """A renamed DAG must not turn this guard into a no-op."""
    gone = [f"{label} -> {dag}" for label, dag in _DAG_FOR.items()
            if not (_DAGS / dag).exists()]
    assert not gone, (
        f"DAG file(s) named here no longer exist: {gone}. Until fixed, the hours they "
        "were meant to verify are unchecked."
    )


def test_the_home_page_reads_kind_and_at_rather_than_restating_them() -> None:
    """The grouping must come from the declaration, not from a second hard-coded list.

    The version this replaced described the split in a caption — one sentence
    listing which sources were automatic. That sentence is a third place to keep
    in sync, and the one nobody updates.
    """
    home = (_ROOT / "src" / "dashboard" / "views" / "home.py").read_text(encoding="utf-8")
    fn = next(
        n for n in ast.walk(ast.parse(home))
        if isinstance(n, ast.FunctionDef) and n.name == "_section_freshness"
    )
    body = ast.unparse(fn)
    assert '"kind"' in body or "'kind'" in body, (
        "_section_freshness no longer reads `kind` — the grouping has been hard-coded "
        "somewhere else, and SOURCES_CONFIG is no longer the single declaration."
    )
    assert '"at"' in body or "'at'" in body, (
        "_section_freshness no longer reads `at` — the announced hour is hard-coded."
    )
