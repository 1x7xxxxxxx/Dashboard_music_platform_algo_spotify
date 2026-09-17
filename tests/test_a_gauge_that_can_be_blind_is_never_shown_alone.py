"""Une jauge qui peut etre aveugle n'est jamais affichee seule.

Type: Sub
Uses: json, pathlib
Triggers: pytest
Depends on: deploy/grafana/dashboards/streamlytics-ops.json
Persists in: —

Error class `a-gauge-that-reports-zero-when-it-cannot-read`.

Le raisonnement
---------------
`streamlytics_open_defects` est lue depuis `app_error_log`. Par construction, elle
n'emet AUCUN echantillon quand la lecture echoue — c'est ce qui l'empeche de rendre un
zero invente pendant une panne de base.

Mais un panneau Grafana affichant cette seule serie reproduirait exactement le mensonge
qu'on vient d'eviter, une couche plus haut : un graphe vide se lit « aucun defaut »,
pas « je ne sais pas ». La desambiguisation vit dans
`streamlytics_open_defects_read_ok`, et elle doit etre SOUS LES YEUX de qui lit le
premier panneau — pas dans une alerte qu'on decouvre trois jours plus tard.

La propriete tenue : tout tableau qui trace `streamlytics_open_defects` trace aussi
`..._read_ok`, dans le meme tableau de bord.

Mutation record — 2026-09-17, deux mutations EXECUTEES et vues rouges :
  1. le panneau « … et SAIT-ON ? » supprime du JSON -> rouge ;
  2. sa requete `read_ok` remplacee par une autre metrique -> rouge.
0 apres remise en etat.
"""
from __future__ import annotations

import json
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DASH = _ROOT / "deploy" / "grafana" / "dashboards"


def _dashboards() -> list[tuple[str, dict]]:
    out = []
    for path in sorted(_DASH.glob("*.json")):
        out.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    assert out, (
        "Aucun tableau de bord versionne. Ce garde porte sur leur contenu ; si le "
        "provisioning a demenage, pointer ce test sur le nouvel emplacement plutot "
        "que de le laisser vert sur un ensemble vide."
    )
    return out


def _exprs(dashboard: dict) -> list[str]:
    return [t.get("expr", "")
            for panel in dashboard.get("panels", [])
            for t in panel.get("targets", [])]


def test_the_defect_gauge_is_never_charted_without_its_read_ok():
    for name, dashboard in _dashboards():
        exprs = _exprs(dashboard)
        charts_gauge = any("streamlytics_open_defects" in e
                           and "read_ok" not in e
                           and "last_success" not in e
                           for e in exprs)
        if not charts_gauge:
            continue
        assert any("streamlytics_open_defects_read_ok" in e for e in exprs), (
            f"{name} trace `streamlytics_open_defects` sans tracer `..._read_ok`. "
            f"La jauge n'emet rien quand la base est injoignable — un graphe vide se "
            f"lira donc « aucun defaut ouvert » au lieu de « je ne sais pas ». C'est "
            f"exactement le mensonge que la conception de cette jauge evite, "
            f"reintroduit une couche plus haut."
        )


def test_the_route_label_is_never_charted_as_a_raw_url():
    """Un panneau qui grouperait par URL brute trahirait la borne de cardinalite."""
    for name, dashboard in _dashboards():
        for expr in _exprs(dashboard):
            if "streamlytics_http_" not in expr:
                continue
            assert "by (path)" not in expr and "by (url)" not in expr, (
                f"{name} agrege les metriques HTTP par `path`/`url`. Le seul label "
                f"borne est `route`, qui porte le PATRON de route."
            )
