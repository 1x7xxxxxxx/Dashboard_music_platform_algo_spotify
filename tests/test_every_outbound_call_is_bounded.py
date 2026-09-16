"""Aucun appel sortant ne peut pendre sans fin.

Type: Test
Uses: pytest, ast
Depends on: src/**/*.py, airflow/**/*.py, tools/**/*.py
Persists in: nothing

Ce qui est en jeu, et pourquoi c'est une question de CONCURRENCE
---------------------------------------------------------------
Un appel HTTP sans délai d'attente ne coûte pas « une requête lente » : il coûte le
**thread**. Mesuré contre la production le 2026-09-16, N onglets cliquant ensemble :
p50 passe de 329 ms à un onglet à 3 488 ms à vingt-quatre, et **98 reruns se perdent**.
La dégradation est quasi linéaire dès quatre rendus simultanés — un processus, un GIL,
les rendus se sérialisent. Dans ce régime, un rendu qui ne rend jamais la main ne
ralentit pas la file : il la gèle.

Le dépôt a déjà payé une variante de cette classe : `timeout-bounds-the-socket-not-the-call`,
où YouTube passait par `httplib2` et ne levait aucune des exceptions de `requests`, donc
la politique de reprise ne voyait rien.

Ce que ce garde lit
-------------------
La STRUCTURE de l'appel, par `ast` : un `requests.post(...)`, un `session.get(...)`, un
`httpx.get(...)` porte-t-il un argument `timeout` ? Un commentaire qui parle de délai
d'attente n'en est pas un, et l'argument peut vivre dix lignes plus bas que le nom de la
fonction — deux raisons pour lesquelles une recherche de texte se trompe ici, dans les
deux sens.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_TREES = ("src", "airflow", "tools")

# Les fonctions qui ouvrent une socket et acceptent `timeout=`.
_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}

# Les noms qui désignent VRAIMENT un client HTTP. `s` et `client` en ont été retirés le
# 2026-09-16 après que le prédicat eut signalé trois sites justes : `s.get("artist_col")`
# sur un dict de `SOURCES_CONFIG` (`kpi_helpers.py:150`) et `s.get("std")` sur un dict de
# statistiques (`ml_inference.py:170`). `.get()` est la signature d'un dictionnaire autant
# que d'une session — un prédicat qui ne distingue pas les deux crie au loup, et un garde
# qui crie au loup finit ignoré.
_CLIENTS = {"requests", "httpx", "session", "_session"}

# Ce qui est exempté, et pourquoi. Une exemption sans raison est une dette muette.
_EXEMPT: dict[str, str] = {
    # rien aujourd'hui — et c'est le résultat, pas un point de départ
}


def _is_outbound_call(node: ast.Call) -> str | None:
    """`requests.post` → 'requests.post', sinon None. Structurel, pas textuel."""
    f = node.func
    if not isinstance(f, ast.Attribute) or f.attr not in _METHODS:
        return None
    if isinstance(f.value, ast.Name) and f.value.id in _CLIENTS:
        return f"{f.value.id}.{f.attr}"
    # `self.session.get(...)` / `self._session.post(...)`
    if isinstance(f.value, ast.Attribute) and f.value.attr in _CLIENTS:
        return f"{f.value.attr}.{f.attr}"
    return None


def unbounded_calls() -> list[str]:
    out = []
    for tree_name in _TREES:
        root = _ROOT / tree_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _is_outbound_call(node)
                if name is None:
                    continue
                if any(k.arg == "timeout" for k in node.keywords):
                    continue
                # `**kwargs` peut porter le timeout — on ne peut pas le savoir
                if any(k.arg is None for k in node.keywords):
                    continue
                rel = str(path.relative_to(_ROOT)).replace("\\", "/")
                site = f"{rel}:{node.lineno} → {name}(…)"
                if site.split(" →")[0] not in _EXEMPT:
                    out.append(site)
    return out


def test_no_outbound_call_can_hang_forever() -> None:
    bad = unbounded_calls()
    assert not bad, (
        "ces appels sortants n'ont aucun délai d'attente. Sans lui, la socket attend "
        "indéfiniment — et dans un rendu Streamlit, cela ne ralentit pas la file, cela "
        "la GÈLE : mesuré le 2026-09-16, un processus sérialise déjà les rendus dès "
        "quatre onglets simultanés.\n"
        "Remède : `timeout=…` sur l'appel. Une exemption se déclare dans `_EXEMPT` "
        "AVEC sa raison.\n  " + "\n  ".join(bad)
    )


def test_the_detector_sees_the_calls_it_claims_to_watch() -> None:
    """Non-vacuité : sans elle, un prédicat cassé rendrait ce fichier vert à vide."""
    seen = 0
    for tree_name in _TREES:
        root = _ROOT / tree_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            seen += sum(1 for n in ast.walk(tree)
                        if isinstance(n, ast.Call) and _is_outbound_call(n))
    assert seen >= 15, (
        f"seulement {seen} appel(s) sortant(s) reconnu(s) — le dépôt en compte plus de "
        "vingt. Le prédicat ne voit plus son sujet."
    )


def test_the_detector_reads_structure_not_text() -> None:
    """Un `timeout` dix lignes plus bas compte ; un commentaire qui en parle, non."""
    borne = ast.parse(
        "import requests\n"
        "requests.post(\n"
        "    'https://x',\n"
        "    data={'a': 1},\n"
        "    timeout=10,\n"
        ")\n")
    calls = [n for n in ast.walk(borne) if isinstance(n, ast.Call) and _is_outbound_call(n)]
    assert len(calls) == 1
    assert any(k.arg == "timeout" for k in calls[0].keywords), (
        "un `timeout` sur une ligne séparée n'est pas vu — le prédicat lit du texte"
    )

    nu = ast.parse("import requests\n# timeout=10 serait bien ici\nrequests.get('https://x')\n")
    calls = [n for n in ast.walk(nu) if isinstance(n, ast.Call) and _is_outbound_call(n)]
    assert len(calls) == 1
    assert not any(k.arg == "timeout" for k in calls[0].keywords), (
        "un commentaire qui PARLE du délai d'attente est pris pour un délai d'attente"
    )
