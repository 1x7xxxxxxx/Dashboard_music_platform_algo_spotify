"""The API image ships what the API imports, and the claim stays testable.

Type: Test
Uses: ast, importlib
Depends on: requirements-api.txt, Dockerfile.api, src/api/**
Persists in: nothing

The defect
----------
One `requirements.txt` was installed into every image. Measured in production on
2026-08-30, the FastAPI image — which serves JSON — carried 454 MB of CUDA
libraries, xgboost, plotly, llvmlite, numba, scikit-image, matplotlib,
googleapiclient and weasyprint. None of it reachable from `src.api.main`.

That was verified rather than assumed: `src.api.main` was imported inside the
running production container with every one of those packages blocked by a
`sys.meta_path` hook, and it imported clean. This file is that proof, kept
runnable.

Why a blocked-import proof and not a requirements diff
------------------------------------------------------
A diff of two files says what someone WROTE. It cannot see a lazy `import shap`
inside a request handler, which is exactly the shape that would ship a green test
and a 500 in production. Blocking the module and importing the app asks the
question the image actually poses: *can this run without those bytes?*
"""
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_API_REQ = _ROOT / "requirements-api.txt"
_FULL_REQ = _ROOT / "requirements.txt"
_DOCKERFILE = _ROOT / "Dockerfile.api"

# Packages deliberately left OUT of the API image. Each was measured in the
# production image on 2026-08-30; the sizes are in requirements-api.txt's header.
EXCLUDED_MODULES = [
    "xgboost", "shap", "lime", "sklearn", "numba", "llvmlite", "skimage",
    "matplotlib", "plotly", "weasyprint", "googleapiclient", "facebook_business",
    "spotipy",
]


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        name = line.split("[")[0].split("==")[0].split(">=")[0].split("<")[0].strip()
        if name:
            names.add(name.lower().replace("_", "-"))
    return names


def test_the_dockerfile_installs_the_api_manifest():
    body = _DOCKERFILE.read_text(encoding="utf-8")
    assert "requirements-api.txt" in body, (
        "Dockerfile.api no longer installs requirements-api.txt — the split is undone "
        "and the image is back to carrying the full ML stack."
    )
    assert "-r requirements.txt" not in body, (
        "Dockerfile.api installs the project-wide manifest again."
    )


def test_the_api_manifest_is_a_strict_subset_of_the_project_manifest():
    """No package may enter the API image without also being a project dependency.

    Otherwise the two manifests drift into two different resolutions of the same
    application, and only one of them is ever tested anywhere else.
    """
    extra = _requirement_names(_API_REQ) - _requirement_names(_FULL_REQ)
    assert not extra, (
        f"{sorted(extra)} are in requirements-api.txt but not requirements.txt. "
        "Add them to the project manifest first, or drop them here."
    )


def test_the_excluded_packages_really_are_excluded():
    """The guard watches something: each name must still be absent from the manifest."""
    declared = _requirement_names(_API_REQ)
    leaked = sorted(m for m in ("xgboost", "shap", "lime", "plotly", "weasyprint")
                    if m in declared)
    assert not leaked, (
        f"{leaked} came back into requirements-api.txt. If the API now genuinely needs "
        "one, say so in the file header and re-measure the image."
    )


def test_the_api_imports_with_the_excluded_packages_blocked():
    """The load-bearing assertion: import the app with those modules unavailable.

    Runs in a subprocess so the block cannot leak into the rest of the suite.
    """
    for mod in ("fastapi", "streamlit"):
        if importlib.util.find_spec(mod) is None:
            pytest.skip(f"{mod} not importable in this interpreter — "
                        "run with `make sync` to prove the API's import closure")

    script = textwrap.dedent(f"""
        import sys
        BLOCKED = {EXCLUDED_MODULES!r}

        class Blocker:
            def find_module(self, name, path=None):
                return self if name.split(".")[0] in BLOCKED else None
            def load_module(self, name):
                raise ImportError("BLOCKED:" + name)

        sys.meta_path.insert(0, Blocker())
        sys.path.insert(0, {str(_ROOT)!r})
        import src.api.main   # noqa: F401
        print("OK")
    """)
    proc = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=300, cwd=_ROOT)
    assert "OK" in proc.stdout, (
        "src.api.main cannot be imported without the packages the API image no "
        "longer ships:\n" + (proc.stderr or proc.stdout)[-3000:]
    )


def test_no_api_module_imports_an_excluded_package_at_any_scope():
    """Lexical backstop for the shape a runtime import test can still miss.

    The subprocess above only exercises import time. A handler that does
    `import shap` on the first request would pass it and 500 in production, so the
    tree is read as well — an import statement anywhere under src/api naming an
    excluded package is a defect regardless of when it would execute.
    """
    offenders = []
    for path in sorted((_ROOT / "src" / "api").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            for n in names:
                if n in EXCLUDED_MODULES:
                    offenders.append(f"{path.relative_to(_ROOT)}:{node.lineno} -> {n}")
    assert not offenders, (
        "These API modules import a package the API image no longer ships:\n  "
        + "\n  ".join(offenders)
    )


def test_the_lexical_backstop_goes_red_on_a_lazy_import(tmp_path):
    """Mutation: the shape the runtime proof cannot see must still be caught."""
    mutant = tmp_path / "handler.py"
    mutant.write_text(
        "def endpoint():\n"
        "    import shap\n"
        "    return shap\n", encoding="utf-8")
    tree = ast.parse(mutant.read_text(encoding="utf-8"))
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.Import)
            and any(a.name.split(".")[0] in EXCLUDED_MODULES for a in n.names)]
    assert hits, "the lexical rule does not see a function-scope import"
