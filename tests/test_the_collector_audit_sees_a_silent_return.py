"""The collector audit sees `except …: return None` — rule 6, « collectors must raise ».

Type: Sub
Uses: .claude/scripts/audit_collectors_ast.py (scan)
Depends on: nothing — fabricated collector code under tmp_path

`collector-silent-success` is guarded by that script, run by audit_runner in CI. Nothing
proved the script could still SEE the shape: a scan that always returns [] keeps CI green.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "audit_collectors_ast", Path(__file__).resolve().parents[1] / ".claude/scripts/audit_collectors_ast.py")
aca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aca)


def _scan(tmp_path: Path, source: str) -> list[int]:
    f = tmp_path / "fake_collector.py"
    f.write_text(source, encoding="utf-8")
    return aca.scan(f)


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path) -> None:
    defect = ("def fetch():\n"
              "    try:\n"
              "        return call()\n"
              "    except Exception:\n"
              "        return None\n")
    assert _scan(tmp_path, defect) == [5], "a silent `return None` in an except is the defect"
    assert _scan(tmp_path, defect.replace("return None", "return []")) == [5]
    fixed = defect.replace("        return None\n", "        logger.error('x')\n        raise\n")
    assert _scan(tmp_path, fixed) == [], "a handler that re-raises is the correction"
    status = defect.replace("return None", "return False")
    assert _scan(tmp_path, status) == [], "a bool status helper is the documented exemption"
