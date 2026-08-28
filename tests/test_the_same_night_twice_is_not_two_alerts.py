"""Guard: an unchanged verdict is not re-mailed, and a changed one always is.

Type: Utility
Uses: src.utils.alert_repetition, tests/fixtures/alert_monitor_two_prod_nights.json
Triggers: pytest
Persists in: nothing

Error class `alert-repeats-an-unactionable-verdict`.

Measured 2026-08-28. `alert_monitor` mailed the same consolidated verdict on two
consecutive nights: Benken / Meta blocked on sharing `act_65390907`, GRiNCH /
SoundCloud with no public track, two stale CSV sources. Both gestures are human
actions in third-party interfaces, so neither mail could be acted on the evening it
arrived — and the second one carried nothing the first had not already said.

The fixture is the REAL XCom of the runs of 25 and 26 August, pulled from the
production metadata DB, not a shape invented by this test. That distinction is the
whole value of the file: the two nights differ by exactly `age_h` (1945.0 → 1969.0)
and `when`, and a rule written from memory would have digested both and suppressed
nothing. A threshold or a normalisation is calibrated on the real distribution or it
is calibrated on nothing.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.utils.alert_repetition import (
    FINDING_CATEGORIES,
    digest_input,
    findings_digest,
    repeat_window_days,
    suppression_reason,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "alert_monitor_two_prod_nights.json"
_NOW = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def nights():
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    runs = sorted(data)
    assert len(runs) == 2, runs
    return [data[r] for r in runs]


# ── The measurement this was written from ────────────────────────────────────

def test_the_two_real_production_nights_have_one_digest(nights):
    first, second = nights
    assert findings_digest(first) == findings_digest(second), (
        "the runs of 25 and 26 August carried the same findings and must digest "
        "equal — if this fails, a measurement field leaked into the identity"
    )


def test_the_two_nights_are_not_equal_before_stripping(nights):
    """The fixture must actually contain the volatile drift, or the test above is void.

    Without this, deleting `age_h` from the fixture would make the first test pass for
    the wrong reason: two identical inputs digest equal whatever the rule does.
    """
    first, second = nights
    assert first != second, "fixture no longer carries the nightly drift it was pinned for"
    dumped = json.dumps(nights, ensure_ascii=False)
    assert "1945.0" in dumped and "1969.0" in dumped, "the real age_h drift is gone"


def test_the_second_identical_night_is_suppressed(nights):
    digest = findings_digest(nights[1])
    why = suppression_reason(digest, findings_digest(nights[0]),
                             _NOW - timedelta(days=1), now=_NOW)
    assert why is not None and "inchangés" in why, why


# ── What it must never suppress ──────────────────────────────────────────────

def test_a_new_finding_is_mailed_the_same_night(nights):
    """A tenant that starts failing tonight cannot wait for the window to close."""
    changed = json.loads(json.dumps(nights[1]))
    changed["check_collection_outcomes.collection_failures"].append({
        "artist_id": 13, "artist_name": "GRiNCH", "platform": "soundcloud",
        "dag_id": "soundcloud_daily", "status": "failed", "reason": "HTTP 401",
        "when": "2026-08-28 07:00:00",
    })
    assert suppression_reason(findings_digest(changed), findings_digest(nights[0]),
                              _NOW - timedelta(days=1), now=_NOW) is None


def test_a_finding_that_disappears_is_mailed(nights):
    """A verdict getting SHORTER is news too — it is how a fix proves itself."""
    changed = json.loads(json.dumps(nights[1]))
    changed["check_collection_outcomes.collection_failures"] = []
    assert suppression_reason(findings_digest(changed), findings_digest(nights[0]),
                              _NOW - timedelta(days=1), now=_NOW) is None


def test_a_changed_reason_is_mailed(nights):
    """Same tenant, same platform, different cause — a different thing to do."""
    changed = json.loads(json.dumps(nights[1]))
    changed["check_collection_outcomes.collection_failures"][0]["reason"] = \
        "RuntimeError: token expired"
    assert suppression_reason(findings_digest(changed), findings_digest(nights[0]),
                              _NOW - timedelta(days=1), now=_NOW) is None


def test_an_escalation_is_mailed_even_though_the_counter_is_volatile():
    """`consecutive_days` moves nightly, but crossing into escalation is a finding."""
    calm = {"failing_dags": {"meta_ads_api_daily": {"consecutive_days": 0}}}
    day3 = {"failing_dags": {"meta_ads_api_daily": {"consecutive_days": 3}}}
    day4 = {"failing_dags": {"meta_ads_api_daily": {"consecutive_days": 4}}}
    assert findings_digest(calm) != findings_digest(day3), "escalation must be visible"
    assert findings_digest(day3) == findings_digest(day4), \
        "the counter ticking on is not a new finding"


def test_the_window_closes_and_the_verdict_comes_back(nights):
    """Silence is bounded. A permanent one is indistinguishable from a dead monitor."""
    digest = findings_digest(nights[1])
    stale_delivery = _NOW - timedelta(days=repeat_window_days())
    assert suppression_reason(digest, digest, stale_delivery, now=_NOW) is None


@pytest.mark.parametrize("last_digest,last_at", [
    (None, _NOW - timedelta(days=1)),        # nothing ever delivered
    ("abc", None),                           # ledger row without a timestamp
    ("abc", "not-a-date"),                   # unparseable timestamp
])
def test_anything_unknown_sends(last_digest, last_at, nights):
    """The module may only stay quiet on positive proof an identical mail went out."""
    assert suppression_reason(findings_digest(nights[1]), last_digest, last_at,
                              now=_NOW) is None


def test_a_naive_timestamp_does_not_raise(nights):
    """A naive datetime must not blow up mid-send; it is read as UTC."""
    digest = findings_digest(nights[1])
    assert suppression_reason(digest, digest, datetime(2026, 8, 27, 1, 0),
                              now=_NOW) is not None


def test_a_broken_window_variable_falls_back_instead_of_silencing(monkeypatch):
    """A typo in the env must not make the silence window infinite."""
    for bad in ("", "   ", "seven", "0", "-3"):
        monkeypatch.setenv("ALERT_REPEAT_SILENCE_DAYS", bad)
        assert repeat_window_days() == 7, bad

# ── Absent, vide : le même monde ────────────────────────────────────────────────

def test_an_absent_category_and_an_empty_one_digest_the_same(nights):
    """Zéro constat n'est pas un constat, quelle que soit la forme que prend le zéro.

    Mesuré le 2026-08-28 en PRÉDISANT la nuit suivante sur les données de production,
    pas en imaginant un cas. `check_credentials_all` était en panne : la catégorie était
    absente de la nuit stockée. Une fois la tâche réparée, elle valait `[]` — 11
    credentials manquants, **11 déjà dits** par « Inscrits sans rien connecter », donc
    zéro survivant, donc rien de neuf pour le lecteur. Les deux empreintes différaient
    quand même, et un mail serait reparti pour annoncer que rien n'avait bougé.

    C'est la forme la plus vicieuse de la classe : une vérification qui se RÉPARE
    déclenche une alerte, exactement au moment où l'on croit avoir supprimé le bruit.
    """
    base = json.loads(json.dumps(nights[1]))
    with_empty = dict(base, une_categorie_neuve=[])
    assert findings_digest(base) == findings_digest(with_empty)

    without = {k: v for k, v in base.items() if v not in ([], {}, None)}
    assert findings_digest(base) == findings_digest(without), (
        "removing the categories that hold nothing must not change the digest"
    )


def test_a_category_that_becomes_non_empty_still_changes_the_digest(nights):
    """La contrepartie : le retrait des vides ne doit pas rendre le garde aveugle."""
    base = json.loads(json.dumps(nights[1]))
    filled = dict(base, une_categorie_neuve=[{"artist_id": 99, "platform": "spotify"}])
    assert findings_digest(base) != findings_digest(filled)


# ── Un seul constructeur d'entrée ──────────────────────────────────────────────

def test_the_dag_and_the_module_agree_on_the_categories():
    """Le DAG doit passer exactement les catégories que le module déclare.

    Mesuré le 2026-08-28, et c'est le défaut que j'ai introduit moi-même : l'empreinte
    de référence rétro-remplie ce jour-là avait été calculée par un script qui
    reconstruisait le dictionnaire avec les clés BRUTES des XCom. Elle hachait une autre
    forme que la production, rien ne pouvait le dire, et la fenêtre de silence ne se
    serait jamais refermée — la comparaison aurait échoué chaque nuit.

    Lu par AST dans le DAG plutôt qu'en l'important : `alert_monitor.py` importe
    `airflow`, absent de certains environnements de test, et une porte de dépendance
    ferait sauter ce contrôle en silence.
    """
    import ast
    dag = Path(__file__).resolve().parents[1] / "airflow" / "dags" / "alert_monitor.py"
    tree = ast.parse(dag.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "digest_input"]
    assert len(calls) == 1, f"expected exactly one digest_input(...) call, found {len(calls)}"
    passed = {kw.arg for kw in calls[0].keywords if kw.arg}
    assert passed == set(FINDING_CATEGORIES), (
        f"the DAG passes {sorted(passed ^ set(FINDING_CATEGORIES))} differently from "
        "FINDING_CATEGORIES. A category the DAG computes but does not pass is invisible "
        "to suppression: a night where only it changes would stay silent."
    )


def test_an_unknown_category_is_refused_loudly():
    """Un contrôle neuf non déclaré doit casser au câblage, pas se taire une nuit."""
    with pytest.raises(KeyError, match="inconnue"):
        digest_input(failing_dags={}, un_controle_tout_neuf=[{"x": 1}])


def test_the_constructor_is_order_independent():
    """L'appelant nomme ses arguments ; l'ordre ne doit jamais changer l'empreinte."""
    a = digest_input(failing_dags={"d": 1}, sparks=[{"s": 2}])
    b = digest_input(sparks=[{"s": 2}], failing_dags={"d": 1})
    assert findings_digest(a) == findings_digest(b)
