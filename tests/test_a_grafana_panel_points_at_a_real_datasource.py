"""Un panneau qui vise une source inexistante rend « No data », pas une erreur.

Type: Test
Uses: json, yaml, pathlib
Depends on: deploy/grafana/**
Persists in: nothing

Ce qui a été mesuré
-------------------
2026-09-16, trouvé par l'utilisateur en OUVRANT Grafana — pas par un test. Les neuf
panneaux référencent `datasource: {type: prometheus, uid: PROM}` ; le fichier de
provisionnement de la source ne déclarait **aucun `uid`**, donc Grafana en génère un
aléatoire au premier démarrage. Les panneaux visaient une source qui n'existe pas.

Le symptôme est ce qui rend la classe coûteuse : **« No data » sur tous les panneaux,
sans aucune erreur**. Grafana ne dit pas « source introuvable », il rend un graphe vide.
Et un graphe vide se lit « rien ne se passe » — la lecture exactement inverse de la
vérité. Tout le reste était juste : Prometheus répondait, les cinq cibles étaient `up`,
les requêtes PromQL étaient correctes. Rien ne reliait les deux moitiés.

Classe : `du-code-correct-que-rien-n-atteint`.

Ce que ce test assert
---------------------
Chaque `uid` de source cité par un panneau (ou par une de ses cibles) est déclaré par un
fichier de provisionnement. Et symétriquement : le provisionnement déclare bien un `uid`,
car l'omettre est exactement le défaut d'origine.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_DASHBOARDS = _ROOT / "deploy" / "grafana" / "dashboards"
_DATASOURCES = _ROOT / "deploy" / "grafana" / "provisioning" / "datasources"


def _provisioned_uids() -> set[str]:
    uids = set()
    for path in sorted(_DATASOURCES.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for ds in doc.get("datasources") or []:
            assert ds.get("uid"), (
                f"{path.name} : la source « {ds.get('name')} » ne déclare pas d'`uid`. "
                "Grafana en générera un aléatoire, et tout panneau qui en cite un fixe "
                "visera une source inexistante — « No data » partout, sans erreur.")
            uids.add(ds["uid"])
    return uids


def _referenced_uids() -> dict[str, list[str]]:
    """{uid: [où il est cité]} sur tous les tableaux versionnés."""
    refs: dict[str, list[str]] = {}

    def note(ds, where: str) -> None:
        if isinstance(ds, dict) and isinstance(ds.get("uid"), str):
            uid = ds["uid"]
            # `${DS_…}` et `-- Grafana --` sont des sources spéciales, pas des UID.
            if uid.startswith("$") or uid.startswith("--"):
                return
            refs.setdefault(uid, []).append(where)

    for path in sorted(_DASHBOARDS.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        note(doc.get("datasource"), f"{path.name} (tableau)")
        for panel in doc.get("panels") or []:
            label = f"{path.name} panneau {panel.get('id')} « {panel.get('title')} »"
            note(panel.get("datasource"), label)
            for target in panel.get("targets") or []:
                note(target.get("datasource"), f"{label} (cible)")
    return refs


def test_every_panel_points_at_a_provisioned_datasource() -> None:
    provisioned = _provisioned_uids()
    referenced = _referenced_uids()

    assert referenced, (
        "aucun panneau ne référence de source — la lecture est cassée, ou les tableaux "
        "ont changé de forme. Le garde serait vert à vide.")

    orphans = {uid: where for uid, where in referenced.items()
               if uid not in provisioned}
    assert not orphans, (
        "panneau(x) visant une source NON provisionnée — Grafana rendra « No data » "
        "sans aucune erreur, et un graphe vide se lit « rien ne se passe » :\n  "
        + "\n  ".join(f"uid `{uid}` → {', '.join(w)}" for uid, w in orphans.items())
        + f"\n\nUID provisionnés : {sorted(provisioned)}. Déclarer l'`uid` dans "
          "`deploy/grafana/provisioning/datasources/`, ne pas le laisser générer.")


def test_the_detector_would_see_the_original_defect() -> None:
    """Non-vacuité, sur le défaut EXACT du 2026-09-16.

    Sans elle, une lecture cassée des tableaux rendrait le test ci-dessus vert à vide —
    ce qui est très précisément la façon dont le défaut a vécu : tout avait l'air juste.
    """
    referenced = _referenced_uids()
    assert "PROM" in referenced, (
        "les panneaux ne citent plus `PROM` : le garde ne décrit plus le déploiement")

    # Le défaut d'origine : la source provisionnée sans `uid`.
    orphans = {uid for uid in referenced if uid not in set()}
    assert orphans, "un ensemble de sources VIDE doit rendre tous les uid orphelins"
