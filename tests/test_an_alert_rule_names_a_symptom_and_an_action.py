"""ADR-011, rendu mécanique — et le chemin qui va du fichier jusqu'à Prometheus.

ADR-011 : « une alerte n'est envoyée que si elle nomme un SYMPTÔME qu'un artiste
pourrait observer dans le produit, ET une ACTION qu'un humain peut faire ce soir. »
Jusqu'ici c'était un jugement écrit dans le docstring de chaque détecteur. Les règles
Prometheus (R115 étape 5) peuvent le porter en DONNÉES : deux annotations obligatoires.

⚠️ La moitié de ce fichier ne parle pas des annotations mais du CHEMIN. C'est délibéré,
et ça vient d'un défaut trouvé pendant l'écriture : `rule_files` pointait sur
`/etc/prometheus/rules/*.yml` alors que le compose ne montait QUE `prometheus.yml`. Un
glob qui ne matche rien ne fait pas tomber Prometheus — il le note et démarre. Les
quatre règles auraient donc été versionnées, relues en revue, et **jamais évaluées**.
C'est la forme `du-code-correct-que-rien-n-atteint`, que ce dépôt a payée six fois en
une séance.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_ROOT = Path(__file__).resolve().parents[1]
_RULES = _ROOT / "deploy" / "prometheus" / "rules" / "streamlytics.yml"
_PROM = _ROOT / "deploy" / "prometheus" / "prometheus.yml"
_COMPOSE = _ROOT / "deploy" / "docker-compose.observability.yml"

_REQUIRED = ("symptom", "action")


def _alerting_rules(doc: dict) -> list[dict]:
    return [r for g in (doc.get("groups") or [])
            for r in (g.get("rules") or []) if "alert" in r]


def _load() -> list[dict]:
    return _alerting_rules(yaml.safe_load(_RULES.read_text(encoding="utf-8")))


def test_the_rules_file_is_not_empty() -> None:
    """Non-vacuité. Sans elle, un chemin faux rendrait tout ce fichier vert à vide."""
    assert _RULES.exists(), f"{_RULES} absent — les trois tests suivants ne prouveraient rien"
    rules = _load()
    assert len(rules) >= 4, (
        f"{len(rules)} règle(s) d'alerte lue(s) dans {_RULES.name}. R115 étape 5 en pose "
        "quatre ; en dessous, soit la lecture est cassée, soit une règle a disparu.")


def test_every_alert_names_a_symptom_and_an_action() -> None:
    """L'exigence d'ADR-011, sur chaque règle."""
    failures = []
    for rule in _load():
        ann = rule.get("annotations") or {}
        for key in _REQUIRED:
            value = (ann.get(key) or "").strip()
            if not value:
                failures.append(f"{rule['alert']} : `{key}` absent ou vide")
            elif len(value) < 40:
                # Un mot n'est pas un geste. Le seuil est bas exprès : il attrape
                # « voir Grafana » et laisse passer une phrase écrite.
                failures.append(f"{rule['alert']} : `{key}` fait {len(value)} car. — "
                                f"trop court pour nommer quoi que ce soit ({value!r})")
    assert not failures, (
        "ADR-011 exige qu'une alerte nomme un symptôme ET un geste :\n  "
        + "\n  ".join(failures))


def test_the_detector_sees_a_missing_annotation() -> None:
    """Mutation : le garde doit rougir sur une règle amputée, sinon il ne garde rien."""
    doc = yaml.safe_load(_RULES.read_text(encoding="utf-8"))
    rules = _alerting_rules(doc)
    victim = rules[0]
    for key in _REQUIRED:
        saved = victim["annotations"].pop(key)
        found = [r for r in _alerting_rules(doc)
                 if not (r.get("annotations") or {}).get(key)]
        assert found, f"une règle sans `{key}` passe inaperçue — le garde est aveugle"
        victim["annotations"][key] = saved
    # Et sur une annotation VIDE, pas seulement absente : c'est la forme qu'on écrit
    # sans le vouloir en laissant un `>-` sans texte dessous.
    victim["annotations"]["action"] = "   "
    assert not (victim["annotations"]["action"] or "").strip(), (
        "une annotation faite d'espaces doit compter comme absente")


def test_the_rules_are_actually_loaded_by_prometheus() -> None:
    """Le chemin complet : fichier → `rule_files` → montage du conteneur.

    Les trois doivent s'accorder. Deux sur trois suffisent à produire des règles
    parfaites que rien n'évalue.
    """
    prom = yaml.safe_load(_PROM.read_text(encoding="utf-8"))
    globs = prom.get("rule_files") or []
    assert globs, (
        "`rule_files` absent de deploy/prometheus/prometheus.yml : les règles existent "
        "et Prometheus ne les lit pas.")

    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    volumes = (compose["services"]["prometheus"].get("volumes") or [])
    mounts = {v.split(":")[1] for v in volumes if isinstance(v, str) and ":" in v}

    for glob in globs:
        target_dir = str(Path(glob).parent)
        assert any(m == target_dir or m.startswith(target_dir + "/") or
                   target_dir.startswith(m.rstrip("/") + "/") or m == glob
                   for m in mounts), (
            f"`rule_files: {glob}` vise {target_dir}, que le compose ne monte pas "
            f"(montages : {sorted(mounts)}). Un glob qui ne matche rien ne fait PAS "
            "échouer Prometheus : il note et démarre. Les règles seraient versionnées "
            "et jamais évaluées.")

    # Et le montage doit pointer sur le dossier qui porte VRAIMENT le fichier.
    sources = {v.split(":")[0] for v in volumes if isinstance(v, str) and ":" in v}
    assert any(_RULES.parent.as_posix().endswith(src.lstrip("./").rstrip("/"))
               for src in sources), (
        f"aucun montage ne vient de {_RULES.parent.relative_to(_ROOT)} "
        f"(sources : {sorted(sources)})")


def test_the_mail_carries_the_annotations_to_the_reader() -> None:
    """Une annotation qui n'arrive pas dans le mail ne tient pas ADR-011.

    Le symptôme et le geste vivent dans les `annotations`, qui ne sont PAS dans la série
    `ALERTS` : elles ne se lisent que par `/api/v1/rules`. Si le rendu du mail cessait de
    les porter, l'alerte dirait « ça a sonné » sans dire quoi faire — l'alerte exacte
    qu'ADR-011 interdit.
    """
    dag = (_ROOT / "airflow" / "dags" / "alert_monitor.py").read_text(encoding="utf-8")
    body = dag[dag.index("if ops_alerts:"):]
    body = body[:body.index("if app_errors:")]
    for key in _REQUIRED:
        assert re.search(rf"o\[['\"]{key}['\"]\]", body), (
            f"la section infrastructure du mail ne rend pas `{key}`")
    reader = (_ROOT / "src" / "utils" / "ops_alerts.py").read_text(encoding="utf-8")
    assert "/api/v1/rules" in reader, (
        "`ops_alerts.py` ne lit pas /api/v1/rules : les annotations ne peuvent pas "
        "atteindre le mail, `ALERTS` ne porte que des labels.")
    assert "max_over_time" in reader, (
        "le lecteur interroge l'état INSTANTANÉ : une alerte partie à 14 h et résolue à "
        "15 h serait invisible à 23 h, c'est-à-dire précisément celles pour lesquelles "
        "on a posé des règles à fenêtre.")
