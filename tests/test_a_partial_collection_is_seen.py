"""
Guard — a collection that arrives but arrives SHORT must be seen (R39).

Type: Sub
Uses: pytest, alert_monitor
Triggers: pytest
Depends on: airflow/dags/alert_monitor.py
Persists in: nothing

Error class: partial-collection-invisible.

`check_row_anomalies` watches the spike direction only, and its docstring delegates the
other one to freshness — "freshness already covers the opposite (no recent data)". True
of ZERO rows, false of TOO FEW: a recent partial collection trips neither, because
freshness sees rows from today and the spike check sees no spike. streaMLytics has lived
that hole twice (SoundCloud "✅ on 0 titles" at the GRiNCH test, Benken's empty YouTube
channel), found by a human both times.

Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p.144: **Volume — "Has all the data
arrived?"** is a pillar distinct from Freshness.

The thresholds asserted here are the MEASURED ones. Real prod volumes per tenant on
2026-08-23 are 1498/day (canary), 19/day (admin) and **7/day (Benken)** — so the floor of
30 first written would have blinded the detector to two tenants out of three, including
the one with a live collection failure. That is why `test_the_floor_does_not_blind_a_real_tenant`
exists: it pins the calibration to reality, not to a round number.
"""

import ast
from pathlib import Path

from src.utils.volume_monitor import (
    DIP_RATIO,
    MIN_BASELINE_ROWS,
    dip_finding,
    is_partial_collection,
)

_ROOT = Path(__file__).resolve().parents[1]
_DAG = _ROOT / "airflow" / "dags" / "alert_monitor.py"


def test_a_tenant_collecting_a_fraction_of_its_usual_volume_is_flagged():
    # 2 lignes là où 19 arrivent d'habitude : ni la fraîcheur ni le pic ne le voient.
    assert is_partial_collection(2.0, 19.0)


def test_zero_rows_is_left_to_freshness():
    # Zéro n'appartient PAS à ce détecteur : la fraîcheur couvre déjà la source muette,
    # et le signaler ici doublerait chaque alerte de source morte.
    assert not is_partial_collection(0.0, 19.0)


def test_a_normal_day_is_silent():
    assert not is_partial_collection(18.0, 19.0)


def test_a_spike_is_not_a_dip():
    assert not is_partial_collection(200.0, 19.0)


def test_a_missing_baseline_is_not_an_alert():
    # Un locataire dont on n'a qu'un jour d'historique n'a pas de référence.
    assert not is_partial_collection(1498.0, None)
    assert not is_partial_collection(None, 19.0)


def test_the_floor_does_not_blind_a_real_tenant():
    """Benken collecte 7 lignes/jour en prod. Un plancher trop haut l'exclut."""
    assert is_partial_collection(1.0, 7.0), (
        "un locataire à 7 lignes/jour tombant à 1 doit être vu. Les volumes réels par "
        "locataire mesurés en prod le 2026-08-23 sont 1498, 19 et 7 par jour : un "
        "plancher au-dessus de 7 rend le détecteur aveugle à deux locataires sur trois."
    )
    assert MIN_BASELINE_ROWS <= 7.0, (
        f"MIN_BASELINE_ROWS={MIN_BASELINE_ROWS} exclurait Benken (7 lignes/jour en prod)"
    )
    assert DIP_RATIO >= 2.0, "un ratio trop petit ferait du bruit sur la variation normale"


def test_the_finding_carries_its_tenant():
    f = dip_finding("soundcloud_tracks_daily", 12, 2.0, 19.0, "2026-08-22")
    assert f["tenant"] == 12 and f["recent"] == 2 and f["baseline"] == 19.0
    assert f["table"] == "soundcloud_tracks_daily"


def test_the_dag_delegates_instead_of_restating_the_threshold():
    """Un seuil recopié dans le DAG dérive de celui qui est testé.

    Le DAG n'est importable dans AUCUN test de ce dépôt (l'Airflow installé refuse
    `schedule_interval`), donc rien ne peut vérifier son comportement à l'exécution :
    la seule garantie possible est structurelle — il appelle le prédicat, il ne le
    réécrit pas.
    """
    tree = ast.parse(_DAG.read_text(encoding="utf-8"))
    called = {
        n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert "is_partial_collection" in called, (
        "check_row_dips doit appeler src.utils.volume_monitor.is_partial_collection ; "
        "un seuil réécrit sur place n'est plus celui que les tests ci-dessus pinnent"
    )
