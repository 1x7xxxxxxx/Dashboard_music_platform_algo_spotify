"""A stale CSV source was told to relaunch a DAG that cannot collect anything.

Measured 2026-08-26 on the nightly PRODUCTION alert. Both stale rows — every stale
row there was — named the same action:

    Spotify S4A   1921h   168h   Airflow UI → relancer le DAG correspondant
    Apple Music   1709h   168h   Airflow UI → relancer le DAG correspondant

Both are fed by a human dropping an export. `s4a_csv_watcher` over an empty dropbox
upserts nothing, exits SUCCESS, and the next night's mail says the same sentence. The
staleness is TRUE — R46 established S4A has been silent for ~80 days because only the
admin ever uploaded — so suppressing the line would be wrong. Naming an action that
cannot work is the separate defect, and it is the one ADR-011 exists to forbid.

The second half of this file guards the hop that made the class possible. Its own
comments record two fields — `error` and `measured_on` — dropped at the xcom
boundary, each costing a wrong instruction in the mail. `fed_by` is the third. A hop
that silently narrows its payload will keep doing it, so the assertion is on the hop
itself, not on today's field list.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.utils.freshness_monitor import MONITOR_TARGETS

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_the_csv_fed_sources_are_exactly_the_ones_that_wait_on_a_human():
    """Derived from the registry, not restated: `_CSV_STALE_H` already marked them.

    Pinning the REALITY (which sources these are) rather than the constant, so a new
    CSV source added without `fed_by` shows up here instead of in a nightly mail.
    """
    csv_fed = {t["source"] for t in MONITOR_TARGETS if t.get("fed_by") == "csv"}
    by_threshold = {t["source"] for t in MONITOR_TARGETS if t["stale_h"] == 7 * 24}
    assert csv_fed == {"Spotify S4A", "Apple Music"}
    assert csv_fed == by_threshold, (
        "a source has the CSV staleness threshold but not `fed_by: csv` (or the "
        f"reverse): {csv_fed ^ by_threshold}. The alert would name a DAG relaunch "
        "for a source nothing can relaunch.")


def test_check_freshness_reports_how_each_source_is_fed():
    """Non-vacuity for the branch below: the field must actually be produced."""
    src = (REPO / "src/utils/freshness_monitor.py").read_text(encoding="utf-8")
    assert '"fed_by": t.get("fed_by", "dag")' in src, (
        "check_freshness no longer reports fed_by — the email cannot branch on it")


def test_the_xcom_hop_carries_every_field_the_email_may_read():
    """The hop that has already dropped two fields, guarded as a hop.

    `check_freshness` builds a dict; `_serialize`-style code in the DAG rebuilds it
    for xcom. Any key produced there and not copied here is invisible to the mail,
    and the mail is the only reader. Mutation-verified by deleting the `fed_by` line.
    """
    produced = set()
    tree = ast.parse((REPO / "src/utils/freshness_monitor.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == "stale_h" for k in node.keys):
            produced |= {k.value for k in node.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert "fed_by" in produced, "fixture lost: check_freshness no longer builds the row"

    dag = (REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    tree = ast.parse(dag)
    carried = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == "measured_on"
                for k in node.keys):
            carried |= {k.value for k in node.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert carried, "the serialising hop moved — this guard is now blind"

    # `table`/`col`/`metric_col` are inputs to the query, never read by the mail.
    internal = {"table", "col", "metric_col", "tenant_table", "tenant_col",
                "tenant_metric_col", "skip_artist_filter", "silence_expected"}
    lost = produced - carried - internal
    assert not lost, (
        f"field(s) produced by check_freshness and dropped at the xcom hop: {lost}. "
        "The email is the only reader; a dropped field is a sentence it cannot write.")


@pytest.mark.parametrize("fed_by, forbidden", [("csv", "relancer le DAG")])
def test_a_csv_source_is_never_told_to_relaunch_its_dag(fed_by, forbidden):
    """The branch exists and says something a human can actually do."""
    dag = (REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    assert "if r.get('fed_by') == 'csv':" in dag, (
        "the stale-source action is one sentence for every source again — a CSV "
        "source is told to relaunch a watcher whose dropbox is empty")
    branch = dag.split("if r.get('fed_by') == 'csv':", 1)[1].split("else:", 1)[0]
    assert "Déposer un export" in branch
    assert forbidden not in branch.replace("relancer son DAG ne collecte rien", "")
