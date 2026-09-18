"""Garde : le panneau qu'une alerte nomme existe dans le tableau Grafana.

Type: Utility
Uses: json, re, pathlib
Triggers: pytest
Persists in: nothing

Classe `an-identifier-that-is-referenced-but-never-declared`, sur la surface qui envoie
quelqu'un quelque part à 23 h.

Ce qui a été mesuré le 2026-09-18
----------------------------------
`deploy/prometheus/rules/streamlytics.yml` porte **8 annotations `panel:`**.
`src/utils/ops_alerts.py:177` les lit et `:228` les rend dans le **mail unique du soir**.

**Quatre pointaient vers un chemin qui n'existe pas** — `Grafana → VPS → Disque`,
`Grafana → VPS → RAM`, `Grafana → Application → p95 par phase`,
`Grafana → Application → Pool`. Il n'y a ni tableau « VPS » ni tableau « Application » :
tout vit dans `streaMLytics — sante et rendu`, et les panneaux réels s'appellent
`VPS — CPU, RAM, disque`, `Latence de rendu — CHROME vs VUE (p95)` et
`Pool Postgres — et le repli SILENCIEUX`.

**Le signe qui trahit, et qui est la leçon** : les quatre cassées utilisaient un FORMAT
différent des quatre valides — `Grafana → X → Y` contre `<tableau> / <panneau>`. Une
seconde convention d'écriture, née une fois, jamais confrontée à la première. Personne ne
résout ces chaînes à l'exécution : elles sont recopiées dans un mail, donc rien ne pouvait
les contredire avant qu'un humain ne clique.

Ce que ce fichier ne tient pas
------------------------------
Il ne vérifie pas que le panneau nommé soit le BON — seulement qu'il existe. Dire à
quelqu'un d'aller voir la RAM quand l'alerte parle du disque resterait vert ici ; les deux
sont dans le même panneau `VPS — CPU, RAM, disque`, et c'est pour cette raison que les
deux alertes le nomment.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_REGLES = _ROOT / "deploy" / "prometheus" / "rules" / "streamlytics.yml"
_TABLEAU = _ROOT / "deploy" / "grafana" / "dashboards" / "streamlytics-ops.json"
_PANEL = re.compile(r"^\s*panel:\s*(\S.*?)\s*$", re.M)


def _pointeurs() -> list[str]:
    if not _REGLES.exists():
        return []
    return _PANEL.findall(_REGLES.read_text(encoding="utf-8"))


def _titres() -> tuple[str, set[str]]:
    d = json.loads(_TABLEAU.read_text(encoding="utf-8"))
    return d.get("title", ""), {p.get("title", "") for p in d.get("panels", [])}


def test_the_pointers_were_really_found() -> None:
    """Non-vacuité : un fichier de règles illisible rendrait tout le reste vert."""
    if not _REGLES.exists():
        pytest.skip("pas de règles Prometheus dans cet arbre")
    assert len(_pointeurs()) >= 5, (
        f"seulement {len(_pointeurs())} annotation(s) `panel:` extraite(s) — "
        "l'extraction a raté sa cible et le test ci-dessous n'affirme rien.")
    _, titres = _titres()
    assert len(titres) >= 5, f"seulement {len(titres)} panneau(x) lu(s) dans le tableau"


@pytest.mark.parametrize("pointeur", _pointeurs() or ["(aucun)"])
def test_an_alert_names_a_panel_that_exists(pointeur: str) -> None:
    if pointeur == "(aucun)":
        pytest.skip("pas de règles Prometheus dans cet arbre")
    tableau, titres = _titres()
    tab, _, pan = pointeur.partition(" / ")
    assert tab == tableau, (
        f"`{pointeur}` nomme le tableau « {tab} », qui n'existe pas. Le seul tableau est "
        f"« {tableau} ». Cette chaîne part dans le mail du soir : personne ne la résout, "
        "donc rien ne la contredit avant qu'un humain ne clique. Format attendu : "
        "`<tableau> / <panneau>` — les quatre pointeurs morts du 2026-09-18 utilisaient "
        "une SECONDE convention, `Grafana → X → Y`, qui n'a jamais rien désigné.")
    if pan:
        assert any(t.lower().startswith(pan.lower()) for t in titres), (
            f"`{pointeur}` nomme le panneau « {pan} », absent du tableau.\n"
            f"Panneaux réels : {sorted(titres)}")
