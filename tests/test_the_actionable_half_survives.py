"""A diagnosis has two halves. The automatic surfaces kept only the first one.

Measured 2026-08-26 on the nightly PRODUCTION alert — both red rows of the
"🔴 À regarder" section, which is every red row there was:

    Benken / Meta        shown   "act_65390907 inaccessible … (#200) … for details"
                         dropped "→ le compte n'a pas été partagé avec l'app
                                  (Business Manager → … → permission Annonceur)"
    GRiNCH / SoundCloud  shown   "… aucun titre public … Deux cas :"
                         dropped the two cases.

`platform_probes.probe` returned `str(message).splitlines()[0][:300]`. The probes
author their diagnosis as SYMPTOM, blank line, GESTURE — so the first line is
reliably the half nobody can act on. Benken's dropped half is the exact instruction
that unblocks the ad account this repo has been waiting on since June.

Why nothing caught it: `test_readiness_carries_the_live_diagnosis` pins a
hand-copied `_GRINCH_TRUTH` that itself stops before "Deux cas :". A guard that
compares production to a copy of production tests the copy. So every assertion here
drives the REAL probe function with the network stubbed, and reads the real string.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.utils.diagnosis_text import as_console, as_html, as_markdown, clamp

REPO = pathlib.Path(__file__).resolve().parents[1]


# ── the real messages, network stubbed ───────────────────────────────────────

class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.fixture()
def grinch_diagnosis(monkeypatch):
    """The exact string `_test_soundcloud` returns for a reachable, empty profile."""
    from src.dashboard.views.credentials import _platform_soundcloud as mod

    monkeypatch.setattr(mod.requests, "post",
                        lambda *a, **k: _Resp(200, {"access_token": "tok"}))
    monkeypatch.setattr(mod.requests, "get",
                        lambda *a, **k: _Resp(200, {"collection": []}))
    # No `_artist_id`: `_claimed_count` returns 0 without touching a database, which
    # is the GRiNCH state — an empty profile with nothing declared elsewhere.
    ok, message = mod._test_soundcloud(
        {"user_id": "72854583", "client_id": "cid", "client_secret": "sec"})
    assert ok is False, "fixture did not reproduce the red"
    return message


@pytest.fixture()
def benken_diagnosis(monkeypatch):
    """The exact string `_probe_ad_account` returns for an unshared ad account."""
    from src.dashboard.views.credentials import _platform_meta as mod

    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: _Resp(400, {"error": {
        "message": "(#200) Ad account owner has NOT grant ads_management or "
                   "ads_read permission"}}))
    ok, message = mod._probe_ad_account("act_65390907", "tok")
    assert ok is False, "fixture did not reproduce the red"
    return message


def test_the_soundcloud_diagnosis_announces_two_cases_and_carries_them(grinch_diagnosis):
    """The half that made the sentence a lie: it promised an enumeration."""
    assert "Deux cas" in grinch_diagnosis, "fixture drifted from the authored text"
    assert "Mes titres hébergés sur d'autres comptes" in grinch_diagnosis
    assert "en **public**" in grinch_diagnosis


def test_the_meta_diagnosis_carries_the_sharing_instruction(benken_diagnosis):
    assert "ETL_DASHBOARD_SPOTIFY" in benken_diagnosis
    assert "Business Assets" in benken_diagnosis


@pytest.mark.parametrize("fixture_name, tail", [
    ("grinch_diagnosis", "en **public**"),
    ("benken_diagnosis", "Business Assets"),
])
def test_the_probe_seam_keeps_the_gesture(request, monkeypatch, fixture_name, tail):
    """`platform_probes.probe` is the seam every automatic surface reads through.

    This is the assertion that was false in production: the gesture must come out
    the other side. Mutation-verified by restoring `.splitlines()[0][:300]`.
    """
    message = request.getfixturevalue(fixture_name)
    from src.utils import platform_probes as pp

    monkeypatch.setattr(
        "src.dashboard.views.credentials._registry.CONNECTION_TESTS",
        {"soundcloud": lambda fields: (False, message)})
    monkeypatch.setattr(pp, "_identity_fields", lambda *a, **k: {})

    ok, out = pp.probe(object(), 13, "soundcloud")
    assert ok is False
    assert tail in out, (
        f"the probe seam dropped the actionable half:\n{out!r}")


# ── each surface renders what it can show ────────────────────────────────────

def test_the_email_turns_line_breaks_into_breaks_and_emphasis_into_bold(grinch_diagnosis):
    """An HTML `<td>` collapses `\\n` and shows `**` as asterisks — both were visible
    in the 2026-08-26 mail, which read `**aucun titre public**` literally."""
    html = as_html(grinch_diagnosis)
    assert "<br>" in html
    assert "<b>aucun titre public</b>" in html
    assert "**" not in html


def test_the_email_escapes_the_platforms_own_words_before_emphasising_ours():
    """The tail of these strings is an API's answer. Escape first, or a `<` from Meta
    closes our cell."""
    out = as_html("Compte **act_1** : <script>alert(1)</script> & co")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "<b>act_1</b>" in out


def test_the_console_keeps_every_line_and_drops_the_markers(grinch_diagnosis):
    out = as_console(grinch_diagnosis)
    assert "en public" in out, "the gesture must reach the operator's terminal"
    assert "**" not in out
    assert out.count("\n") >= 2, "continuation lines must stay on their own lines"


def test_the_matrix_gets_hard_breaks(grinch_diagnosis):
    """A single `\\n` is not a break in markdown: the two bullets would run into one."""
    out = as_markdown(grinch_diagnosis)
    assert "  \n" in out


def test_a_cap_that_fires_says_so():
    """A cut landing mid-sentence reads as a whole sentence — the exact shape of the
    defect this file exists for."""
    assert clamp("x" * 10, limit=5).endswith("…")
    assert clamp("short", limit=100) == "short"


# ── structural: nobody may re-flatten ────────────────────────────────────────

_CONSUMERS = [
    "src/utils/platform_probes.py",
    "src/dashboard/utils/status_matrix.py",
    "tools/artist_preflight.py",
    "airflow/dags/alert_monitor.py",
]


def test_no_consumer_keeps_only_the_first_line():
    """Reads the AST, not the text: a comment naming `splitlines()[0]` must not fail
    the guard, and a rewrite that spells it differently must not pass it.

    This is the class, not the instance — `message-flattened-for-the-narrowest-renderer`.
    Any surface that takes a diagnosis and keeps `[0]` of its lines re-opens it.
    """
    offenders = []
    for rel in _CONSUMERS:
        tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            call = node.value
            if (isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "splitlines"
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == 0):
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "a diagnosis is flattened to its first line again — the half that says what "
        f"to DO is the half being dropped: {offenders}")


# Asserting that `as_html` is CORRECT says nothing about it being CALLED — three
# layers in this repo were correct and unreached in the fortnight before this one.
#
# The predicate below asks the QUESTION ("does a diagnosis reach a markup cell
# unrendered?"), not the symptom ("does the name appear in an f-string"). The first
# draft asked the symptom and flagged a `logger.warning` line, where none of this
# matters. A guard whose scope is wider than its question gets narrowed until it is
# silent, and then it guards nothing.
_CARRIERS = {"next_action", "reason"}


def _names_in(node) -> set:
    """Every identifier and string subscript key inside an expression."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.add(sub.id)
        elif isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
            if isinstance(sub.slice.value, str):
                found.add(sub.slice.value)
    return found


def _is_markup(joined: ast.JoinedStr) -> bool:
    """Does this f-string build HTML? Only those cells owe the diagnosis a render."""
    literal = "".join(p.value for p in joined.values
                      if isinstance(p, ast.Constant) and isinstance(p.value, str))
    return "<" in literal and ">" in literal


def test_every_markup_cell_that_shows_a_diagnosis_renders_it():
    """The wiring, not the renderer. Mutation-verified by unwrapping one call site."""
    rel = "airflow/dags/alert_monitor.py"
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    bare, wrapped = [], 0
    for joined in ast.walk(tree):
        if not isinstance(joined, ast.JoinedStr) or not _is_markup(joined):
            continue
        for node in joined.values:
            if not isinstance(node, ast.FormattedValue):
                continue
            if not (_names_in(node.value) & _CARRIERS):
                continue
            call = node.value
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "as_html"):
                wrapped += 1
            else:
                bare.append(f"{rel}:{node.lineno}")
    assert not bare, (
        "a diagnosis reaches an HTML cell without as_html() — its line breaks and "
        f"emphasis are dropped, and a platform's own `<` goes in raw: {bare}")
    # Non-vacuity. A scope that matches nothing passes forever, which is how the
    # `status_matrix` half of the first draft of this guard asserted nothing at all.
    assert wrapped >= 6, f"guard matched only {wrapped} cells — has the shape moved?"


def test_the_matrix_and_the_cli_route_their_diagnosis_too():
    """Neither surface builds an f-string of markup, so the check above cannot see
    them. They are named here explicitly rather than left silently uncovered."""
    matrix = (REPO / "src/dashboard/utils/status_matrix.py").read_text(encoding="utf-8")
    calls = [ast.unparse(n) for n in ast.walk(ast.parse(matrix))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "caption"]
    assert calls, "the matrix no longer captions its next step — scope moved"
    assert any("as_markdown" in c for c in calls), (
        f"the artist's own matrix shows the diagnosis unrendered: {calls}")

    cli = (REPO / "tools/artist_preflight.py").read_text(encoding="utf-8")
    prints = [ast.unparse(n) for n in ast.walk(ast.parse(cli))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
              and n.func.id == "print" and "message" in ast.unparse(n)]
    assert prints, "the preflight no longer prints its probe message — scope moved"
    assert all("as_console" in p for p in prints), (
        f"the operator's terminal drops the gesture again: {prints}")
