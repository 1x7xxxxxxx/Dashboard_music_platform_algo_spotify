"""A schema module never indexes `config.yaml` directly.

Type: Sub
Uses: src/database/*_schema.py (read as AST)
Depends on: nothing
Persists in: nothing

Class `config-not-env`: `config.yaml` exists in development and not in production, so
`config['x']` is correct where the code is written and a `KeyError` where it runs. The
class signature was a `grep` for `config[`; this file asks the AST, so a comment or a
docstring showing the forbidden form does not trip it, and the form through
`config_loader.load()[...]` is seen too.
"""
from __future__ import annotations

import ast
from pathlib import Path

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "database"


def config_subscripts(source: str) -> list[int]:
    """Lines that subscript `config` or `<x>.load()` — reading the YAML by key. Pure."""
    out = []
    for n in ast.walk(ast.parse(source)):
        if not isinstance(n, ast.Subscript):
            continue
        v = n.value
        if isinstance(v, ast.Name) and v.id == "config":
            out.append(n.lineno)
        elif isinstance(v, ast.Call) and getattr(v.func, "attr", None) == "load":
            out.append(n.lineno)
    return sorted(out)


def test_no_schema_module_indexes_the_config_file() -> None:
    files = sorted(_SCHEMAS.glob("*_schema.py"))
    assert files, "no *_schema.py under src/database — the scan sees nothing"
    offenders = [f"{p.name}:{line}" for p in files
                 for line in config_subscripts(p.read_text(encoding="utf-8-sig"))]
    assert not offenders, (
        f"{offenders} : lecture de `config.yaml` par clé dans un module de schéma. Le "
        "fichier n'existe pas en production : `KeyError` là où le code tourne. Résoudre "
        "par l'environnement d'abord, `config.yaml` en repli local (forme `_smtp_config`).")


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity: `config['database']` and `config_loader.load()['smtp']` are named; a
    `config.get(...)` fallback after the environment, and a comment or a docstring
    showing the forbidden form, are not."""
    bad = ("host = config['database']['host']\n"
           "smtp = config_loader.load()['smtp']\n")
    assert config_subscripts(bad) == [1, 2]
    good = ('"""Never config[\'x\'] here."""\n'
            "# config['database'] was the defect\n"
            "host = os.getenv('DB_HOST') or config.get('database', {}).get('host')\n")
    assert config_subscripts(good) == []
