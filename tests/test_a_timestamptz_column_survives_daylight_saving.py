"""A `timestamptz` column read into pandas must survive a daylight-saving change.

Type: Test
Uses: ast
Depends on: src/**/*.py, src/dashboard/utils/tz.py
Persists in: nothing

The defect
----------
`pd.to_datetime(series)` raises when the values carry different UTC offsets:

    ValueError: Tz-aware datetime.datetime cannot be converted to datetime64
                unless utc=True, at position 2

Every `timestamptz` column read through psycopg2 comes back bearing the offset in
force at that instant, so a table holding rows from March and June holds `+01:00`
and `+02:00` side by side. Measured on production `saas_users.created_at` on
2026-08-30: ids 1–2 at `+01`, id 10 onward at `+02` — "position 2" exactly.

`views/admin.py` crashed on this **in production**, on the user list. Four more
sites had the identical shape and had simply never been handed a window spanning a
DST change. **The trigger is a date on the calendar, not a code path** — which is
why a render-smoke on today's data cannot be the guard, and this must read the tree.

Why the check is an intersection, not a blanket ban
---------------------------------------------------
49 call sites pass a Series to `pd.to_datetime` without `utc=`. Only the ones whose
column is genuinely `timestamptz` can ever hold mixed offsets; `date`, `week`,
`day`, `prediction_date` are DATE columns and are safe. Forbidding all 49 would be a
large diff that changes rendering (`utc=True` alone shifts the displayed hour, and
near midnight the displayed DATE) in exchange for nothing on 44 of them.

So TZ_COLUMNS is the list read from the production schema, and it is asserted
non-empty — a guard that silently narrows to zero columns watches nothing.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

# `SELECT DISTINCT column_name FROM information_schema.columns
#   WHERE data_type = 'timestamp with time zone' AND table_schema = 'public'`
# run against production on 2026-08-30.
TZ_COLUMNS = {
    "applied_at", "changed_at", "collected_at", "created_at", "executed_at",
    "expires_at", "imported_at", "last_attempt_at", "last_heartbeat",
    "locked_until", "marketing_consent_at", "onboarding_report_sent_at",
    "probed_at", "promo_plan_expires_at", "run_at", "terms_accepted_at", "ts",
    "updated_at", "verification_token_created_at", "window_start",
}

# The helpers that make mixed offsets legal AND keep the rendered value unchanged.
SAFE_CALLS = {"to_local_datetime", "to_local_naive"}


def _tz_column_of(node: ast.AST) -> str | None:
    """The timestamptz column an expression reads, or None.

    Recognises the two shapes the code actually uses: `x['created_at']` and
    `x.get('created_at')`.
    """
    if (isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
            and node.slice.value in TZ_COLUMNS):
        return node.slice.value
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value in TZ_COLUMNS):
        return node.args[0].value
    return None


def _enclosing_function(tree: ast.Module, target: ast.AST):
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(n is target for n in ast.walk(fn)):
                return fn
    return None


def unsafe_timestamptz_parses(paths: list[Path]) -> list[str]:
    """`file:line` for every `pd.to_datetime(<timestamptz value>)` with no `utc=`.

    The rule is deliberately UNIFORM over anything that reads a timestamptz column,
    and that was not the first draft. The first draft exempted scalars —
    `pd.to_datetime(row['created_at'])` genuinely cannot carry two offsets — and then
    the guard flagged `account.py:133` anyway, because **the AST cannot tell
    `df['col']` from `row['col']`**: both are a Subscript with a string slice, and
    only a type checker knows which.

    Weakening the rule to silence that would have meant guessing, per call site, at
    something the tree does not say. Widening it costs one call to a helper measured
    to render a scalar identically in both DST regimes.

    It also follows ONE assignment hop, and that was not academic either: the first
    version read only the call's own argument and therefore missed
    `account.py:72`, where the value is bound to a local (`joined = user.get(...)`)
    one line above the parse. A defect one variable away is still the defect.
    """
    bad: list[str] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "to_datetime"):
                continue
            if any(kw.arg == "utc" for kw in node.keywords) or not node.args:
                continue
            arg = node.args[0]
            col = _tz_column_of(arg)
            if col is None and isinstance(arg, ast.Name):
                fn = _enclosing_function(tree, node)
                if fn is not None:
                    for sub in ast.walk(fn):
                        if isinstance(sub, ast.Assign) and any(
                                isinstance(tgt, ast.Name) and tgt.id == arg.id
                                for tgt in sub.targets):
                            col = col or _tz_column_of(sub.value)
            if col is None:
                continue
            try:
                rel = path.relative_to(_ROOT)
            except ValueError:
                rel = path
            bad.append(f"{rel}:{node.lineno} -> {col}")
    return sorted(set(bad))


def _sources() -> list[Path]:
    return sorted(_SRC.rglob("*.py"))


def test_no_timestamptz_series_is_parsed_without_utc():
    offenders = unsafe_timestamptz_parses(_sources())
    assert not offenders, (
        "These parse a `timestamptz` column into pandas without `utc=`. They work "
        "until the rows span a daylight-saving change, then raise "
        "'Tz-aware datetime.datetime cannot be converted to datetime64':\n  "
        + "\n  ".join(offenders)
        + "\n\nUse to_local_datetime / to_local_naive from src/dashboard/utils/tz.py — "
          "they normalise to UTC and convert back, so the rendered value is unchanged."
    )


def test_the_guard_goes_red_on_the_defect_it_was_written_for(tmp_path):
    """Mutation: the exact line that crashed production must be seen."""
    mutant = tmp_path / "mutant_view.py"
    mutant.write_text(
        "import pandas as pd\n"
        "def show(df_display):\n"
        "    df_display['created_at'] = pd.to_datetime(df_display['created_at'])"
        ".dt.strftime('%d/%m/%Y')\n", encoding="utf-8")
    assert unsafe_timestamptz_parses([mutant]), (
        "the guard does not see the shape that crashed views/admin.py in production"
    )


def test_the_guard_stays_quiet_on_the_shapes_that_cannot_break(tmp_path):
    """DATE columns and an explicit `utc=` are safe — those must not be flagged.

    A scalar is deliberately NOT in this list: see the docstring of
    `unsafe_timestamptz_parses` for why the rule does not try to recognise one.
    """
    ok = tmp_path / "ok_view.py"
    ok.write_text(
        "import pandas as pd\n"
        "def show(df):\n"
        "    df['date'] = pd.to_datetime(df['date'])            # DATE column\n"
        "    df['week'] = pd.to_datetime(df['week'])            # DATE column\n"
        "    df['day'] = pd.to_datetime(df['day'])              # DATE column\n"
        "    b = pd.to_datetime(df['created_at'], utc=True)     # already explicit\n",
        encoding="utf-8")
    assert unsafe_timestamptz_parses([ok]) == []


def test_the_column_list_is_not_empty_and_still_matches_the_code():
    """A guard that narrows to zero columns watches nothing.

    `check_stale_deliverables` reports that failure mode by name; this is the same
    hazard one level down — the intersection could quietly become empty if the
    schema list were lost, and every call site would then pass.
    """
    assert len(TZ_COLUMNS) >= 15, (
        f"TZ_COLUMNS has shrunk to {len(TZ_COLUMNS)} — re-read it from the schema "
        "rather than trimming it."
    )
    text = "\n".join(p.read_text(encoding="utf-8") for p in _sources())
    seen = {c for c in TZ_COLUMNS if f"'{c}'" in text or f'"{c}"' in text}
    assert len(seen) >= 5, (
        f"Only {sorted(seen)} of the timestamptz columns appear in src/. Either the "
        "list is stale or the data layer moved — re-derive it against the schema."
    )


def test_the_helpers_exist_and_normalise_before_converting():
    """The fix is two steps in one order; assert the module still does both."""
    tz = (_SRC / "dashboard" / "utils" / "tz.py").read_text(encoding="utf-8")
    tree = ast.parse(tz)
    names = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    assert SAFE_CALLS <= names, f"utils/tz.py no longer defines {SAFE_CALLS - names}"
    assert "utc=True" in tz, (
        "utils/tz.py no longer passes utc=True — mixed offsets raise again."
    )
    assert "tz_convert" in tz, (
        "utils/tz.py no longer converts back to the display timezone; `utc=True` "
        "alone shifts the rendered hour, and near midnight the rendered DATE."
    )


def test_the_guard_follows_one_assignment_hop(tmp_path):
    """Mutation: the shape that the first version of this guard missed.

    `account.py:72` bound the value to a local before parsing it. Reading only the
    call's own argument left it invisible.
    """
    mutant = tmp_path / "hop.py"
    mutant.write_text(
        "import pandas as pd\n"
        "def show(user):\n"
        "    joined = user.get('created_at')\n"
        "    return pd.to_datetime(joined).strftime('%d %B %Y')\n", encoding="utf-8")
    assert unsafe_timestamptz_parses([mutant]), (
        "the guard does not follow a value bound to a local before being parsed"
    )
