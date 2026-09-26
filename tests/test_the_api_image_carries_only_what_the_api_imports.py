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

from tests.code_text import code_of

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
    body = code_of(_DOCKERFILE)
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


def excluded_imports(source: str) -> list[tuple[int, str]]:
    """(line, package) of every import of an excluded package, at ANY scope. Pure."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        else:
            continue
        out += [(node.lineno, n) for n in names if n in EXCLUDED_MODULES]
    return out


def test_no_api_module_imports_an_excluded_package_at_any_scope():
    """Lexical backstop for the shape a runtime import test can still miss.

    The subprocess above only exercises import time. A handler that does
    `import shap` on the first request would pass it and 500 in production, so the
    tree is read as well — an import statement anywhere under src/api naming an
    excluded package is a defect regardless of when it would execute.
    """
    offenders = [f"{path.relative_to(_ROOT)}:{line} -> {n}"
                 for path in sorted((_ROOT / "src" / "api").rglob("*.py"))
                 for line, n in excluded_imports(path.read_text(encoding="utf-8"))]
    assert not offenders, (
        "These API modules import a package the API image no longer ships:\n  "
        + "\n  ".join(offenders)
    )


def test_the_lexical_backstop_goes_red_on_a_lazy_import(tmp_path):
    """Mutation: the shape the runtime proof cannot see must still be caught."""
    # The guard's OWN predicate, not a copy of it: until 2026-09-26 this proof rebuilt
    # the rule inline, so breaking `excluded_imports` would have left it green
    # (class `a-proof-that-tests-a-copy-of-its-detector`).
    pkg = sorted(EXCLUDED_MODULES)[0]
    lazy = f"def endpoint():\n    import {pkg}\n    return {pkg}\n"
    assert excluded_imports(lazy) == [(2, pkg)], "a function-scope import is not seen"
    assert excluded_imports(f"def endpoint():\n    from {pkg}.x import y\n") == [(2, pkg)]
    assert excluded_imports("import json\n") == []


# ── Les CONTRAINTES, pas seulement les NOMS — 2026-09-18 ─────────────────────
#
# `_requirement_names()` ci-dessus decoupe sur `==`, `>=` et `<` pour ne garder que le
# NOM. C'est ce qu'il lui faut pour sa question — « l'image API porte-t-elle un paquet
# que l'API n'importe pas ? ». Mais il rend les deux manifestes identiques meme quand
# ils installent des VERSIONS differentes, et ces deux manifestes construisent deux
# images qui tournent cote a cote en production.
#
# Mesure du 2026-09-18 : sur 20 paquets communs, **un seul diverge** — et c'est
# `bcrypt`, la bibliotheque qui hache les mots de passe, dans deux images qui
# authentifient toutes les deux.
#
#     requirements.txt:40      bcrypt>=4.0,<5.1     (releve par 0b83522, avec le lock)
#     requirements-api.txt:52  bcrypt>=4.0,<4.1     (fige par 283ff46, anterieur)
#     pyproject.toml:50        bcrypt>=4.0,<5.1
#
# `uv.lock` resout 4.0.1, qui satisfait les DEUX — donc l'environnement verrouille ne
# montre rien. Les images Docker, elles, installent depuis les `requirements*.txt`
# (CLAUDE.md : « Legacy install path — kept parallel for the existing Dockerfile »),
# donc `pip` peut resoudre deux majeures differentes de part et d'autre. bcrypt 4.1+
# REFUSE un mot de passe de plus de 72 octets la ou 4.0 le tronque : la meme
# inscription peut passer d'un cote et echouer de l'autre.
#
# ⚠️ **TRANCHEE LE 2026-09-20** (R140 §16.8), et l'ensemble est VIDE — ce test refuse
# desormais qu'elle revienne, comme la version precedente de ce commentaire l'annoncait.
#
# La direction a ete donnee par la MESURE, pas par un arbitrage : `uv.lock` resout
# **4.0.1**, et les TROIS fichiers portaient le meme commentaire disant « Pin
# bcrypt<4.1 » — deux d'entre eux sous une contrainte `<5.1` qui le contredit. Le
# commentaire et le lock designaient donc la meme borne ; seules deux contraintes
# s'en ecartaient.
#
# Verifie le 2026-09-20 sur l'environnement reel : bcrypt 4.0.1 + passlib 1.7.4,
# hachage et verification corrects, et un mot de passe de 100 octets ACCEPTE (tronque)
# — le comportement que 4.1+ remplace par une `ValueError`.
#
# Aligner vers `<5.1` aurait ete aligner sur le cote NON verifie : personne n'a mesure
# que passlib 1.7.4 survit a bcrypt 4.1+, et son propre commentaire dit le contraire.
_DIVERGENCES_CONNUES: set[str] = set()


def _requirement_constraints(path: Path) -> dict[str, str]:
    """`{nom: contrainte}` — la contrainte de version, telle qu'ecrite."""
    import re
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(.*)$", line)
        if m:
            out[m.group(1).lower().replace("_", "-")] = (m.group(3) or "").strip()
    return out


def test_the_two_images_pin_the_same_versions():
    plein = _requirement_constraints(_ROOT / "requirements.txt")
    api = _requirement_constraints(_ROOT / "requirements-api.txt")
    communs = sorted(set(plein) & set(api))
    assert len(communs) > 10, (
        f"seulement {len(communs)} paquets communs aux deux manifestes — la lecture a "
        "rate sa cible, et le test ci-dessous est vert pour une raison qui n'a rien a "
        "voir avec la propriete.")
    divergents = {k for k in communs if plein[k] != api[k]}
    neuves = divergents - _DIVERGENCES_CONNUES
    assert not neuves, (
        "".join(f"\n  {k}: requirements.txt={plein[k]!r} vs requirements-api.txt={api[k]!r}"
                for k in sorted(neuves)) +
        "\n\nCes paquets sont contraints DIFFEREMMENT dans deux manifestes qui "
        "construisent deux images tournant cote a cote. `pip` peut y resoudre deux "
        "versions differentes — le lock ne protege que l'environnement de "
        "developpement. Aligner les deux, ou inscrire la divergence dans "
        "`_DIVERGENCES_CONNUES` AVEC sa raison et sa ligne de roadmap.")


def test_the_frozen_divergences_are_still_real():
    """Un cliquet qui gele une divergence disparue est un mensonge qui dure.

    Il s'annonce comme une dette et n'en est plus une ; pire, il autorise a la
    reintroduire. Ce test force le vidage le jour ou elle est tranchee.
    """
    plein = _requirement_constraints(_ROOT / "requirements.txt")
    api = _requirement_constraints(_ROOT / "requirements-api.txt")
    fantomes = {k for k in _DIVERGENCES_CONNUES
                if k not in plein or k not in api or plein[k] == api[k]}
    assert not fantomes, (
        f"{sorted(fantomes)} sont geles dans `_DIVERGENCES_CONNUES` alors qu'ils ne "
        "divergent plus (ou ne sont plus dans les deux manifestes). Les retirer : un "
        "cliquet qui garde une dette reglee autorise a la recreer.")
