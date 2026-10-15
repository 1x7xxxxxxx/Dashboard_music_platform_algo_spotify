"""Upward arcs between src/ layers only shrink: they are exactly the baseline (R616).

Type: Hook
Uses: tools/dev/layer_arcs.py (ast over `git ls-files 'src/*.py' 'airflow/dags/*.py'`)
Persists in: tests/layer_arcs_baseline.json — `file::target module` → {level, reason}

Strict BOTH ways, like the dead-code ratchet: a new arc is red (import downward, or move
the module), and a baseline arc that is gone is red too (remove it — a stale key lets a
new arc hide behind a deleted one). Renaming a file reddens both lists: drop the old key
when adding the new one. An arc that moves from a function to module level is red — it
now runs at import (cost, cycle risk).

guard_scope: `import` / `from … import` nodes in tracked src/ files, at any depth
(`TYPE_CHECKING`, `try` included). NOT covered: `importlib.import_module` / `__import__`
with a string, `tools/` and `tests/`, imports between low layers. `airflow/dags/` is
scanned since R626, as the layer `dags`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
import layer_arcs  # noqa: E402


def test_the_upward_arcs_are_exactly_the_baseline() -> None:
    now, known = layer_arcs.current(), layer_arcs.load_baseline()
    new, gone = sorted(set(now) - set(known)), sorted(set(known) - set(now))
    assert not new, ("upward import arcs — import downward or move the module:\n  "
                     + "\n  ".join(new))
    assert not gone, ("no longer an arc — remove from tests/layer_arcs_baseline.json "
                      "(a renamed file: drop its old key):\n  " + "\n  ".join(gone))
    raised = sorted(k for k in now if now[k] == "module" and known[k]["level"] == "local")
    assert not raised, f"a lazy arc now runs at import time:\n  {raised}"


def test_every_arc_that_stays_says_why() -> None:
    """R626: the baseline is not a backlog — each arc left in it is a written decision."""
    for key, entry in layer_arcs.load_baseline().items():
        assert set(entry) == {"level", "reason"}, key
        assert entry["level"] in {"module", "local"}, key
        assert len(entry["reason"].split()) >= 8, f"{key}: a reason is a sentence, not a tag"


def test_a_dag_importing_an_app_is_an_arc(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    src = "def task():\n    from src.dashboard.utils import i18n\nimport src.utils.config_loader\n"
    assert layer_arcs.arcs_of("airflow/dags/d.py", src, root) == {
        "airflow/dags/d.py::src.dashboard.utils.i18n": "local"}
    assert layer_arcs.arcs_of("tools/dev/x.py", src, root) == {}


def _tree(tmp_path: Path) -> Path:
    for mod in ("src/dashboard/utils/i18n.py", "src/dashboard/utils/__init__.py",
                "src/dashboard/__init__.py", "src/api/security.py"):
        (tmp_path / mod).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / mod).write_text("")
    return tmp_path


def test_each_import_form_is_an_arc(tmp_path: Path) -> None:
    """False-negative direction: every spelling of an upward import is caught."""
    root = _tree(tmp_path)
    src = ("import src.dashboard.utils.i18n\n"
           "from src import dashboard\n"
           "def f():\n    from src.dashboard.utils import i18n, helper\n"
           "    from src.api.security import x\n")
    assert layer_arcs.arcs_of("src/utils/m.py", src, root) == {
        "src/utils/m.py::src.dashboard.utils.i18n": "module",
        "src/utils/m.py::src.dashboard": "module",
        "src/utils/m.py::src.dashboard.utils": "local",   # `helper` is a name, not a file
        "src/utils/m.py::src.api.security": "local",
    }


def test_an_app_importing_the_other_app_is_an_arc(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    assert layer_arcs.arcs_of("src/api/deps.py", "from src.dashboard import utils\n", root) \
        == {"src/api/deps.py::src.dashboard.utils": "module"}


def test_prose_and_downward_imports_are_not_arcs(tmp_path: Path) -> None:
    """False-positive direction: a docstring naming the dashboard, a downward import and
    an import inside the same layer are not arcs."""
    root = _tree(tmp_path)
    src = ('"""Uses: src.dashboard.utils.i18n"""\n'
           "import src.utils.config_loader\nfrom src.database import x\n"
           "s = 'from src.dashboard import utils'\n")
    assert layer_arcs.arcs_of("src/utils/m.py", src, root) == {}
    assert layer_arcs.arcs_of("src/dashboard/v.py", "from src.dashboard.utils import i18n\n",
                              root) == {}
