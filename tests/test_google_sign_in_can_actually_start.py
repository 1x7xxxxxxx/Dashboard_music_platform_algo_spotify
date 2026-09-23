"""Garde : la connexion Google peut réellement DÉMARRER là où elle est offerte.

Type: Utility
Uses: pytest, packaging, src.dashboard.utils.google_auth, streamlit.auth_util
Triggers: pytest
Persists in: nothing

Ce qui a été mesuré le 2026-09-23
----------------------------------
Les secrets OAuth posés en production, le bouton « Se connecter avec Google »
s'affichait — et un clic levait `StreamlitMissingAuthlibError` : `st.login()` a besoin
d'Authlib, que streamlit **n'installe pas** (c'est l'extra `streamlit[auth]`). Il
n'était déclaré ni dans `pyproject.toml`, ni dans `requirements.txt`, ni présent dans
le venv local. Trouvé en tentant de fabriquer un jeton de fournisseur DANS le
conteneur de production, pas par un test.

Pourquoi les tests existants étaient verts : ils simulent `st.user` — ce qui SUIT le
retour de Google. Aucun ne passait par `st.login()`, le seul endroit qui a besoin de
la bibliothèque. C'est la forme de `a test that mocks what it verifies`.

Ce que ce garde couvre : (1) le fichier que l'image Docker installe déclare Authlib ;
(2) l'environnement de test peut réellement fabriquer un jeton de fournisseur, le
premier geste de `/auth/login` ; (3) `configure()` masque le bouton si la bibliothèque
manque malgré les secrets. Ce qu'il NE couvre PAS : l'aller-retour réel avec Google
(il ne se prouve qu'en vrai — runbook §23, vérification 3), ni une autre dépendance
optionnelle d'une autre fonction de Streamlit.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

_ROOT = Path(__file__).resolve().parents[1]
_MINIMUM = Version("1.3.2")  # streamlit/auth_util.py: "Authentication requires Authlib>=1.3.2"


def _declared(path: Path) -> dict[str, Requirement]:
    out: dict[str, Requirement] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            req = Requirement(line)
            out[req.name.lower()] = req
    return out


def test_the_image_installs_authlib() -> None:
    """`Dockerfile` runs `pip install -r requirements.txt`: that file is the image."""
    req = _declared(_ROOT / "requirements.txt").get("authlib")
    assert req is not None, (
        "requirements.txt ne déclare pas `authlib` : l'image de production n'aura pas "
        "la bibliothèque, et le bouton Google lèvera au premier clic.")
    assert req.specifier.contains(_MINIMUM, prereleases=False) or all(
        Version(s.version) >= _MINIMUM for s in req.specifier), (
        f"`{req}` peut installer une version sous {_MINIMUM}, que Streamlit refuse.")


def test_a_provider_token_can_really_be_made(monkeypatch) -> None:
    """Le premier geste de `/auth/login` — celui qui a levé en production."""
    from streamlit import auth_util

    # Only the signing secret is faked — the library path under test is real.
    monkeypatch.setattr(auth_util, "get_signing_secret", lambda: "x" * 48)
    token = auth_util.encode_provider_token("default")
    assert isinstance(token, str) and token, "aucun jeton de fournisseur fabriqué"


def test_the_button_hides_when_the_library_is_missing(monkeypatch) -> None:
    import importlib.util

    from src.dashboard.utils import google_auth as ga

    monkeypatch.setattr(ga.st, "secrets", {"auth": {
        "client_id": "x.apps.googleusercontent.com",
        "redirect_uri": "http://localhost:8501/oauth2callback"}}, raising=False)
    assert ga.configure() is True, "non-vacuité : avec secrets et bibliothèque, le bouton doit s'afficher"

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "authlib" else real(name, *a, **k))
    assert ga.configure() is False, (
        "secrets posés, Authlib absent : `configure()` affiche encore le bouton, et le "
        "premier clic lèvera StreamlitMissingAuthlibError.")


@pytest.mark.parametrize("manifest", ["pyproject.toml", "uv.lock"])
def test_the_dependency_is_declared_where_the_lock_is_built(manifest: str) -> None:
    text = (_ROOT / manifest).read_text(encoding="utf-8").lower()
    assert '"authlib' in text or 'name = "authlib"' in text, (
        f"{manifest} ne porte pas authlib — `make sync` rendrait un venv sans lui, et "
        "les tests de la connexion Google redeviendraient verts sur du vide.")
