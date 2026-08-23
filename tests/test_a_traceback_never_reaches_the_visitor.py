"""
Guard — an unhandled exception must not render its traceback in a visitor's browser.

Type: Sub
Uses: tomllib, pathlib
Triggers: pytest
Depends on: .streamlit/config.toml
Persists in: nothing

Error class: traceback-rendered-to-the-visitor.

Mesuré en production le 2026-08-23. `client.showErrorDetails` n'était pas configuré, et
son défaut Streamlit est `full` : toute exception non rattrapée rendait sa traceback
complète dans le navigateur — chemins de fichiers, lignes de code, et le message de
l'exception. Ce dépôt sait ce que ce message peut contenir : Meta et YouTube passent leur
credential en QUERY STRING, et c'est toute la raison d'être de
`secret-in-an-exception-message` et de `safe_error()`. Le travail fait pour empêcher un
credential d'atteindre un LOG était donc contourné par la surface la plus exposée de
toutes, le navigateur d'un visiteur non authentifié.

`register.py` avait déjà reçu `public_error_ref()` pour cette raison exacte (R23 : la
page d'inscription rendait un message psycopg2 nommant contrainte et colonnes). Ce
réglage est la même décision, prise une fois pour toute l'application.
"""

import tomllib
from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
_SAFE = {"none", "type"}


def test_the_config_exists():
    assert _CONFIG.is_file(), f"{_CONFIG} manquant — le réglage ne serait pas embarqué"


def test_a_visitor_never_sees_a_traceback():
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    value = cfg.get("client", {}).get("showErrorDetails")
    assert value is not None, (
        "client.showErrorDetails n'est pas configuré. Le DÉFAUT de Streamlit est "
        "`full` : une exception non rattrapée rend sa traceback complète dans le "
        "navigateur du visiteur. Ne pas régler cette option n'est pas neutre."
    )
    assert value in _SAFE, (
        f"client.showErrorDetails = {value!r}. Un visiteur verrait la traceback, donc "
        f"les chemins, le code et le message de l'exception — que Meta et YouTube "
        f"peuvent remplir avec le credential qu'ils passent en query string. "
        f"Valeurs acceptées ici : {sorted(_SAFE)}."
    )


def test_the_upload_cap_is_still_there():
    """Voisinage : le même fichier porte le plafond d'upload (DoS)."""
    cfg = tomllib.loads(_CONFIG.read_text(encoding="utf-8"))
    size = cfg.get("server", {}).get("maxUploadSize")
    assert size and size <= 200, f"maxUploadSize={size} — plafond absent ou trop haut"
