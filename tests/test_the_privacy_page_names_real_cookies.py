"""Garde : un cookie nommé par la politique de confidentialité existe vraiment.

Type: Utility
Uses: ast, pathlib, streamlit (package installé)
Triggers: pytest
Persists in: nothing

Ce qui a été mesuré le 2026-09-23
----------------------------------
La page de confidentialité ET l'avis de l'écran de connexion annonçaient « un seul
cookie de session (`music_dashboard`) ». Ce cookie était celui de
`streamlit-authenticator`, retiré le 2026-03-25 (commit `16d6264`) : **plus aucune
ligne ne le posait depuis six mois**. Les cookies réels — `_streamlit_xsrf`, et
`_streamlit_user` depuis la connexion Google — n'étaient nommés nulle part. Une
information RGPD (Art. 13) décrivait donc un mécanisme qui n'existait plus.

Ce garde couvre : chaque nom en `code` des sections Cookies (FR et EN) et de l'avis
de connexion doit apparaître comme une chaîne littérale dans le package Streamlit
installé ou dans `src/`. Il NE couvre PAS : un cookie posé par un proxy (Caddy,
Cloudflare `__cf_bm`), ni la DURÉE annoncée — elle a été lue dans
`streamlit/web/server/starlette/starlette_server_config.py` le même jour, pour la
version épinglée 1.63.0, et une montée de version peut la changer.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

import streamlit

_ROOT = Path(__file__).resolve().parents[1]
_FR = _ROOT / "src" / "dashboard" / "views" / "privacy.py"
_EN = _ROOT / "src" / "dashboard" / "utils" / "i18n_catalog" / "privacy.py"
_NOTICES = (_ROOT / "src" / "dashboard" / "app.py",
            _ROOT / "src" / "dashboard" / "utils" / "i18n_catalog" / "app_shell.py")


def _strings(path: Path) -> list[str]:
    """The string literals of a module, read from its syntax tree — never its text,
    so a comment or a docstring cannot vouch for a cookie."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    doc_nodes = {id(n.body[0].value) for n in ast.walk(tree)
                 if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                 and n.body and isinstance(n.body[0], ast.Expr)}
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in doc_nodes]


@lru_cache(maxsize=1)
def _literals_of_the_code_that_sets_cookies() -> frozenset[str]:
    out: set[str] = set()
    for root in (Path(streamlit.__file__).parent, _ROOT / "src"):
        for py in root.rglob("*.py"):
            if "i18n_catalog" in py.parts or py.name == "privacy.py":
                continue  # the page itself proves nothing about the cookie
            try:
                out.update(_strings(py))
            except SyntaxError:
                continue
    return frozenset(out)


def _cookie_names(texts: list[str], anchor: str) -> set[str]:
    names: set[str] = set()
    for s in texts:
        if anchor in s:
            section = s.split(anchor, 1)[1].split("\n## ", 1)[0]
            names |= set(re.findall(r"`([A-Za-z_][\w-]*)`", section))
    return names


def _named_cookies() -> set[str]:
    return _cookie_names(_strings(_FR) + _strings(_EN), ". Cookies\n")


def test_the_cookie_section_names_cookies_at_all() -> None:
    assert len(_named_cookies()) >= 2, f"non-vacuité : {_named_cookies()}"


def test_every_cookie_the_privacy_page_names_is_set_by_something() -> None:
    known = _literals_of_the_code_that_sets_cookies()
    ghosts = sorted(n for n in _named_cookies() if n not in known)
    assert not ghosts, (
        f"{ghosts} : la politique de confidentialité nomme un cookie qu'aucun code ne "
        "pose — ni Streamlit, ni `src/`. C'est la forme de `music_dashboard`, annoncé "
        "six mois après que plus rien ne le posait.")


def test_the_login_notice_does_not_name_a_ghost_cookie() -> None:
    known = _literals_of_the_code_that_sets_cookies()
    notices = [s for f in _NOTICES for s in _strings(f) if "🍪" in s]
    assert len(notices) >= 2, f"non-vacuité : {len(notices)} avis de cookie trouvé(s)"
    for s in notices:
        for name in re.findall(r"`([A-Za-z_][\w-]*)`", s):
            assert name in known, f"l'avis de connexion nomme `{name}`, que rien ne pose."
