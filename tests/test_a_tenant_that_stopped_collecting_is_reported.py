"""
Guard — "it collected, then stopped" reaches somebody.

Type: Sub
Uses: ast, src.utils.artist_readiness
Triggers: pytest
Depends on: src/utils/artist_readiness.py, airflow/dags/alert_monitor.py
Persists in: nothing (read-only assertions)

Error classes: broken-probe-rendered-as-user-fault (one layer up),
`stale` excluded from the flags that alert.

Measured in production 2026-08-23. Benken (tenant 12) had YouTube declared, a working
credential (the channel answered, 15 subscribers), and no fresh row for two nights.
Nothing said so, through three independent doors:

  1. `youtube_daily` isolates failures per tenant, so the task stayed SUCCESS and
     `check_dag_failures` saw no FAILED run;
  2. freshness turned the tenant STALE — and `readiness_red_flags` returned only
     NO_DATA + BROKEN, dropping STALE on the floor;
  3. the freshness xcom did not carry `error`, so a probe that FAILED rendered in the
     nightly email as "🟡 stale · Airflow UI → relancer le DAG".

Door 3 matters twice: `check_freshness` computes `error` precisely so a dead probe can
be told apart from an empty table, and `artist_readiness` reads it (→ BROKEN, "rien à
faire de ton côté"). Losing it at the xcom hop rebuilt, at the email layer, the exact
class the BROKEN status was introduced to kill.
"""

import ast
from pathlib import Path

from src.utils.artist_readiness import (
    BROKEN,
    NO_DATA,
    OK,
    QUIET,
    STALE,
    TODO,
    next_action,
)

ROOT = Path(__file__).resolve().parent.parent
ALERT_MONITOR = ROOT / "airflow" / "dags" / "alert_monitor.py"
READINESS = ROOT / "src" / "utils" / "artist_readiness.py"

_PLATFORM = {"key": "youtube", "label": "🎬 YouTube",
             "id_hint": "ton Channel ID (UC…)", "nodata_hint": "vérifie le Channel ID"}


def _red_flag_statuses() -> set[str]:
    """The status set `readiness_red_flags` filters on, read off the AST."""
    tree = ast.parse(READINESS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "readiness_red_flags":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Compare) and isinstance(sub.ops[0], ast.In):
                    comp = sub.comparators[0]
                    if isinstance(comp, ast.Tuple):
                        return {e.id for e in comp.elts if isinstance(e, ast.Name)}
    raise AssertionError("could not read the status filter of readiness_red_flags")


def test_stale_is_one_of_the_statuses_that_alert() -> None:
    statuses = _red_flag_statuses()
    assert "STALE" in statuses, (
        "readiness_red_flags drops STALE. 'Collected, then stopped' is the only shape a "
        "WORKING credential can take when it breaks — excluding it is what let Benken's "
        f"YouTube go two nights unreported. Current filter: {sorted(statuses)}"
    )
    # The others must stay: widening must not quietly narrow.
    assert {"NO_DATA", "BROKEN"} <= statuses, f"a status was lost: {sorted(statuses)}"


def test_a_stale_platform_never_tells_the_artist_to_check_a_dag() -> None:
    """The artist has no Airflow login. Cooper, About Face p.311."""
    msg = next_action(_PLATFORM, STALE)
    lowered = msg.lower()
    assert "dag" not in lowered and "airflow" not in lowered, (
        f"the STALE message sent to the artist is {msg!r} — it asks them to fix "
        "something they cannot reach. The operator gets the DAG name through "
        "etl_run_log and the nightly email instead."
    )
    assert msg.strip(), "a STALE platform must still say something"


def test_a_live_reason_still_wins_over_the_generic_sentence() -> None:
    """A measurement beats a template, for STALE as it already did for NO_DATA."""
    measured = "le compte a été mis en privé"
    assert next_action(_PLATFORM, STALE, live_reason=measured) == measured


def test_the_other_statuses_keep_their_contract() -> None:
    assert next_action(_PLATFORM, OK) == ""
    assert "Rien à faire" in next_action(_PLATFORM, QUIET, expected_silence="aucune pub")
    assert "de ton côté" in next_action(_PLATFORM, BROKEN)
    assert _PLATFORM["id_hint"] in next_action(_PLATFORM, TODO)
    assert next_action(_PLATFORM, NO_DATA) == _PLATFORM["nodata_hint"]


def _freshness_xcom_keys() -> set[str]:
    """Keys the freshness task serialises — read off the AST, not off a comment."""
    tree = ast.parse(ALERT_MONITOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "check_data_freshness":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Dict):
                    keys = {k.value for k in sub.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                    if "source" in keys:
                        return keys
    raise AssertionError("could not find the serialised freshness dict")


def test_the_freshness_xcom_carries_the_error() -> None:
    keys = _freshness_xcom_keys()
    assert "error" in keys, (
        "check_data_freshness drops `error` before the email. check_freshness computes "
        "it so a FAILED probe can be told apart from an empty table; without it the "
        "email tells the reader to relaunch a DAG for a check that never ran. "
        f"Serialised keys: {sorted(keys)}"
    )
    assert "measured_on" in keys, (
        "`measured_on` distinguishes 'written this morning' from 'describes a recent "
        "day'. Confusing the two is what hid Meta Ads for months."
    )
