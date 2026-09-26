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
    from src.utils.freshness_monitor import _CSV_STALE_H, _MANUAL_STALE_H

    # ⚠️ Ce test épinglait la liste EXACTE `{"Spotify S4A", "Apple Music"}`, et le
    # 2026-09-22 il a rougi quand trois sources saisies à la main y sont entrées —
    # distributeur, SACEM, Hypeddit. Il avait raison de parler : une source CSV
    # ajoutée sans `fed_by` doit apparaître ici plutôt que dans un mail nocturne.
    #
    # Mais la propriété que sa propre phrase d'échec décrit n'est pas la liste, c'est
    # la CORRESPONDANCE : « une source a le seuil humain sans `fed_by: csv`, ou
    # l'inverse ». La liste était l'instantané de cette correspondance à un moment
    # donné. Les seuils humains sont désormais deux — sept jours pour un dépôt de
    # fichier, trente pour une saisie mensuelle — et la correspondance est intacte.
    _SEUILS_HUMAINS = {_CSV_STALE_H, _MANUAL_STALE_H}
    csv_fed = {t["source"] for t in MONITOR_TARGETS if t.get("fed_by") == "csv"}
    by_threshold = {t["source"] for t in MONITOR_TARGETS
                    if t["stale_h"] in _SEUILS_HUMAINS}
    assert len(csv_fed) >= 2, (
        f"only {len(csv_fed)} human-fed source(s) — this test would pin almost "
        "nothing. Non-vacuity, not a style rule.")
    assert csv_fed == by_threshold, (
        "a source has a human staleness threshold but not `fed_by: csv` (or the "
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
    lost = dropped_at_hop(
        (REPO / "src/utils/freshness_monitor.py").read_text(encoding="utf-8"),
        (REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8"))
    assert not lost, (
        f"field(s) produced by check_freshness and dropped at the xcom hop: {lost}. "
        "The email is the only reader; a dropped field is a sentence it cannot write.")


@pytest.mark.parametrize("fed_by, forbidden", [("csv", "relancer le DAG")])
def test_a_csv_source_is_never_told_to_relaunch_its_dag(fed_by, forbidden):
    """The branch exists and says something a human can actually do."""
    dag = (REPO / "airflow/dags/alert_monitor.py").read_text(encoding="utf-8")
    problems = csv_branch_problems(dag, forbidden)
    assert not problems, (
        f"{problems} — the stale-source action is one sentence for every source "
        "again, or its CSV branch tells a human to relaunch a watcher whose dropbox "
        "is empty")


def _dict_keys_marked_by(source: str, marker: str) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == marker for k in node.keys):
            keys |= {k.value for k in node.keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return keys


# `table`/`col`/`metric_col` are inputs to the query, never read by the mail.
_INTERNAL = frozenset({"table", "col", "metric_col", "tenant_table", "tenant_col",
                       "tenant_metric_col", "skip_artist_filter", "silence_expected"})


def dropped_at_hop(producer: str, hop: str) -> set[str]:
    """Fields the freshness row carries (dict marked by `stale_h`) that the xcom hop
    (dict marked by `measured_on`) does not copy, internal inputs aside. Pure.

    Raises when either dict is gone: a hop that moved leaves this guard blind.
    """
    produced = _dict_keys_marked_by(producer, "stale_h")
    carried = _dict_keys_marked_by(hop, "measured_on")
    assert "fed_by" in produced, "fixture lost: check_freshness no longer builds the row"
    assert carried, "the serialising hop moved — this guard is now blind"
    return produced - carried - _INTERNAL


def csv_branch_problems(dag: str, forbidden: str) -> list[str]:
    """What is wrong with the CSV branch of the stale-source action. Pure."""
    head = "if r.get('fed_by') == 'csv':"
    if head not in dag:
        return ["no-csv-branch"]
    branch = dag.split(head, 1)[1].split("else:", 1)[0]
    out = [] if "Déposer un export" in branch else ["no-human-gesture"]
    if forbidden in branch.replace("relancer son DAG ne collecte rien", ""):
        out.append("tells-to-relaunch")
    return out


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity, class `alert-names-an-action-its-source-cannot-take`: the hop that
    drops `fed_by` — the field the mail branches on — is named; so are one sentence
    for every source and a CSV branch that says to relaunch the DAG. The branch that
    names the human gesture passes."""
    producer = "row = {'source': s, 'stale_h': h, 'fed_by': f, 'table': t}\n"
    dropping = "x = {'source': r['source'], 'stale_h': r['stale_h'], 'measured_on': d}\n"
    assert dropped_at_hop(producer, dropping) == {"fed_by"}
    carrying = dropping.replace("'measured_on': d", "'measured_on': d, 'fed_by': r['fed_by']")
    assert dropped_at_hop(producer, carrying) == set()
    one_sentence = "action = 'relancer le DAG'\n"
    assert csv_branch_problems(one_sentence, "relancer le DAG") == ["no-csv-branch"]
    wrong = ("if r.get('fed_by') == 'csv':\n    a = 'relancer le DAG'\n"
             "else:\n    a = 'relancer le DAG'\n")
    assert csv_branch_problems(wrong, "relancer le DAG") == ["no-human-gesture",
                                                           "tells-to-relaunch"]
    right = ("if r.get('fed_by') == 'csv':\n    a = 'Déposer un export ; relancer son "
             "DAG ne collecte rien'\nelse:\n    a = 'relancer le DAG'\n")
    assert csv_branch_problems(right, "relancer le DAG") == []
