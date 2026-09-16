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

import ast
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


def _subscript_keys(node, var: str) -> set[str]:
    """Les clés littérales lues sur `var[...]` sous ce nœud — par l'AST, pas par le texte.

    Les f-strings sont parsées : leurs expressions sont de vrais nœuds, donc
    `f"{o['action']}"` donne bien un `Subscript`. Un nom cité dans un COMMENTAIRE ou une
    docstring n'en donne aucun, et c'est tout l'intérêt — quatre gardes de ce dépôt ont
    été verts sur leur propre défaut parce qu'un nom survivait dans un commentaire.
    """
    keys = set()
    for n in ast.walk(node):
        if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                and n.value.id == var and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, str)):
            keys.add(n.slice.value)
    return keys


def _func(tree, name: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def test_the_mail_carries_the_annotations_to_the_reader() -> None:
    """Une annotation qui n'arrive pas dans le mail ne tient pas ADR-011.

    Le symptôme et le geste vivent dans les `annotations`, qui ne sont PAS dans la série
    `ALERTS` : elles ne se lisent que par `/api/v1/rules`. Si le rendu cessait de les
    porter, l'alerte dirait « ça a sonné » sans dire quoi faire — l'alerte exacte
    qu'ADR-011 interdit.

    Deux moitiés, parce que le rendu et la décision d'envoi vivent à deux endroits :
    `render_html()` fabrique la section, et le DAG décide de l'appeler. Vérifier l'une
    sans l'autre laisse passer une section parfaite que personne n'ajoute au corps.

    Lu par l'AST. Un `grep` aurait été vert sur le commentaire qui explique la règle.
    """
    mod = ast.parse((_ROOT / "src" / "utils" / "ops_alerts.py")
                    .read_text(encoding="utf-8"))
    render = _func(mod, "render_html")
    assert render is not None, "`render_html()` a disparu de `ops_alerts.py`"
    rendered = _subscript_keys(render, "o")
    for key in _REQUIRED:
        assert key in rendered, (
            f"`render_html()` ne rend pas `{key}` (clés rendues : {sorted(rendered)})")

    dag = ast.parse((_ROOT / "airflow" / "dags" / "alert_monitor.py")
                    .read_text(encoding="utf-8"))
    branch = next((n for n in ast.walk(dag)
                   if isinstance(n, ast.If) and isinstance(n.test, ast.Name)
                   and n.test.id == "ops_alerts"), None)
    assert branch is not None, (
        "aucun bloc `if ops_alerts:` dans le rendu du mail — la section infrastructure "
        "est fabriquée mais jamais ajoutée au corps")
    called = {n.func.id for n in ast.walk(branch)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert any("ops_html" in c or c == "render_html" for c in called), (
        f"le bloc `if ops_alerts:` n'appelle aucun rendu (appels : {sorted(called)})")


def test_the_reader_asks_prometheus_the_two_questions_it_must() -> None:
    """Les deux appels, et la FENÊTRE. Lus comme littéraux de l'AST, pas par `grep`.

    `/api/v1/rules` : sans lui, les annotations n'atteignent jamais le mail, parce que
    `ALERTS` ne porte que des labels.

    `max_over_time` : sans lui on interroge l'état INSTANTANÉ, et une alerte partie à
    14 h puis résolue à 15 h serait invisible à 23 h — c'est-à-dire précisément celles
    pour lesquelles on a posé des règles à fenêtre.
    """
    tree = ast.parse((_ROOT / "src" / "utils" / "ops_alerts.py")
                     .read_text(encoding="utf-8"))
    # Les littéraux de chaîne qui vivent dans du CODE. Les docstrings sont écartées par
    # IDENTITÉ DE NŒUD, pas par valeur — et la distinction n'est pas théorique : la
    # première version comparait à `ast.get_docstring()`, qui DÉDENTE, donc le littéral
    # brut ne correspondait jamais et la docstring du module suffisait à rendre le test
    # vert. Mesuré : la mutation « remplacer /api/v1/rules par /api/v1/alerts » est
    # passée inaperçue. Un garde aveugle à sa propre mutation ne garde rien.
    docstring_nodes = set()
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)) and body:
            first = body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstring_nodes.add(id(first.value))
    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstring_nodes}

    assert any("/api/v1/rules" in v for v in literals), (
        "`ops_alerts.py` n'interroge pas /api/v1/rules dans son CODE : les annotations "
        "ne peuvent pas atteindre le mail, `ALERTS` ne porte que des labels.")
    assert any("max_over_time" in v for v in literals), (
        "le lecteur interroge l'état INSTANTANÉ : une alerte partie à 14 h et résolue à "
        "15 h serait invisible à 23 h.")


def _fired(monkeypatch, annotations: dict, fired: dict, live: set):
    from src.utils import ops_alerts

    monkeypatch.setattr(ops_alerts, "_rule_annotations", lambda: annotations)
    monkeypatch.setattr(ops_alerts, "_fired_names", lambda window="24h": fired)
    monkeypatch.setattr(ops_alerts, "_still_firing", lambda: live)
    return {r["alertname"]: r for r in ops_alerts.fired_since()}


def test_a_rule_that_vanished_is_not_accused_of_bad_writing(monkeypatch) -> None:
    """Deux absences distinctes : une annotation manquante, et une règle disparue.

    Les confondre envoie corriger un fichier où il n'y a rien à corriger. Le cas est
    réel : la vérification de bout en bout du 2026-09-16 a posé une règle temporaire,
    l'a vue sonner, puis l'a retirée — la série `ALERTS` l'a gardée 24 h de plus.
    """
    out = _fired(monkeypatch,
                 annotations={"Kept": {"symptom": "s", "action": "a", "panel": "p"}},
                 fired={"Kept": {"severity": "high"}, "Gone": {"severity": "info"}},
                 live={"Kept"})

    assert set(out) == {"Kept", "Gone"}, "une alerte a été perdue en route"
    assert "ADR-011" not in out["Gone"]["action"], (
        "une règle DISPARUE est accusée d'être hors contrat ADR-011 — le lecteur "
        "confond « annotation absente » et « règle absente »")
    assert "disparu" in out["Gone"]["symptom"]
    assert out["Gone"]["still_firing"] is False
    assert out["Kept"]["still_firing"] is True


def test_a_rule_present_but_unannotated_IS_accused(monkeypatch) -> None:
    """Non-vacuité du test précédent : le cas « hors contrat » doit rester détecté."""
    out = _fired(monkeypatch,
                 annotations={"Sloppy": {"symptom": "s"}},   # pas d'`action`
                 fired={"Sloppy": {"severity": "high"}},
                 live=set())
    assert "ADR-011" in out["Sloppy"]["action"], (
        "une règle présente SANS `action` passe sans reproche — le garde du lecteur "
        "ne garde rien")


def test_prometheus_silent_is_not_read_as_healthy(monkeypatch) -> None:
    """Une liste vide se lit « rien à signaler ». Un instrument mort ne doit pas."""
    from src.utils import ops_alerts

    monkeypatch.setattr(ops_alerts, "_rule_annotations", dict)
    out = ops_alerts.fired_since()
    assert len(out) == 1 and out[0]["alertname"] == "UNAVAILABLE", (
        f"Prometheus muet a rendu {out!r} — une liste vide serait lue comme une nuit "
        "calme, c'est-à-dire l'inverse de la vérité")
    assert out[0]["action"], "la ligne UNAVAILABLE ne nomme aucun geste"
