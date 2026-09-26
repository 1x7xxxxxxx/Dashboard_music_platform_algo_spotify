"""Une classe d'erreur neuve doit dire pourquoi elle mérite d'exister.

Type: Test
Uses: .claude/scripts/audit_runner.py
Depends on: .claude/dev-docs/error-classes.md
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
Le catalogue a gagné **365 classes en sept semaines** — 131 en août, **234 en
septembre**, soit ~10 par jour. Chacune coûte 15 champs tenus à la main, et la mesure
dit que **91 % ne récidivent jamais** (37 sur 402). On paie l'écriture d'une classe
pour un évènement qui n'arrivera pas.

Le billet d'admission, étalonné rétroactivement sur ces 402 classes :

    récidivé au moins une fois   37  (9 %)
    balayage à ≥ 1 site          38  (9 %)
    balayage à ≥ 2 sites         21  (5 %)
    ADMISES (récidive OU ≥ 2)    52  (13 %)  → ~1,3 classe/jour au lieu de ~10

⚠️ **Le seuil n'est PAS justifié par une corrélation, et il faut le dire.** Le verdict
de balayage sépare fortement dans les données — 0,505 récidive/classe-mois à ≥ 1 site
contre 0,112 à 0 site, intervalles DISJOINTS, la seule séparation nette du jeu. C'est
un leurre : sur les 37 classes concernées, le balayage précède la récidive **0 fois**,
la suit 2 fois, et tombe **le même jour 12 fois**. C'est la signature de « ça a
récidivé, j'ai balayé, j'ai écrit les deux lignes dans le même commit ». Rétrospectif,
donc inutilisable comme prédicteur.

Le seuil tient sur un argument de DÉCISION, pas de statistique : **un défaut présent à
deux endroits n'est pas un cas isolé, par définition.**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_RUNNER = ROOT / ".claude" / "scripts" / "audit_runner.py"


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location("audit_runner", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_switch_date_is_posted_in_the_catalogue(runner) -> None:
    """Sans date de bascule, la porte ne peut rien exiger — et elle sort 0 en silence."""
    since = runner._admission_since()
    assert since, (
        "aucune date de bascule dans le catalogue : `--admission` n'exige alors rien "
        "de personne et sort 0. Une porte qui ne peut jamais rougir n'est pas une "
        "porte. Poser `<!-- admission-since: AAAA-MM-JJ -->`.")


def test_every_class_written_since_the_switch_carries_a_ticket(runner) -> None:
    """Le cliquet. Les classes antérieures sont acquises, les neuves se justifient."""
    headers = runner.parse_all_headers(
        runner._CATALOGUE.read_text(encoding="utf-8"))
    assert runner._admission(headers) == 0, (
        "au moins une classe écrite depuis la bascule n'a pas de billet (voir la "
        "sortie ci-dessus). Un défaut corrigé produit un TEST par défaut ; une classe "
        "est l'index des gardes, pas le journal des défauts.")


def test_the_three_tickets_are_accepted_and_the_near_misses_refused(runner) -> None:
    """Non-vacuité : les formes valides ET les refus, tous FABRIQUÉS ici.

    Sans cette moitié, `_admission_verdict` pourrait rendre `None` pour tout et le
    cliquet ci-dessus resterait vert — la forme d'aveuglement que ce dépôt a mesurée
    neuf fois.
    """
    for billet in ("recurrence:2026-09-01,2026-09-14", "sites:2", "sites:7",
                   "p1:la collecte de trois locataires s'est arrêtée"):
        assert runner._admission_verdict(billet) is None, (
            f"le billet valide {billet!r} est refusé : écrire une classe légitime "
            "deviendrait impossible sans désarmer la porte.")

    assert runner._admission_verdict(None), "l'absence de billet est acceptée"
    assert runner._admission_verdict(""), "un billet vide est accepté"
    assert runner._admission_verdict("sites:1"), (
        "`sites:1` passe — or un seul site est un cas isolé, pas une classe. C'est "
        "tout le seuil : un défaut présent à DEUX endroits n'est pas unique par "
        "définition.")
    assert runner._admission_verdict("sites:0"), "`sites:0` passe"
    assert runner._admission_verdict("recurrence:2026-09-01"), (
        "une SEULE date passe comme récidive — or une fois est un accident. C'est la "
        "deuxième occurrence qui fait la classe.")
    assert runner._admission_verdict("parce que c'est important"), (
        "un billet en prose libre passe : la porte redevient un jugement, et tout "
        "défaut peut se justifier après coup.")


def test_the_gate_refuses_a_fabricated_class_without_a_ticket(runner) -> None:
    """Le bout en bout : une classe neuve sans billet fait sortir 2.

    Les assertions précédentes portent sur le PRÉDICAT ; celle-ci sur la PORTE — un
    prédicat juste câblé au mauvais endroit est la forme que ce dépôt a payée six fois.
    """
    since = runner._admission_since()
    neuve = {"id": "une-classe-neuve", "first_seen": since, "admitted": None,
             "family": "le-locataire",
             "kind": "deterministic", "status": "open", "signature": None}
    assert runner._admission([neuve]) == 2, (
        "une classe datée du jour de la bascule, sans billet, passe la porte.")

    ancienne = {**neuve, "id": "une-classe-ancienne", "first_seen": "2026-01-01"}
    assert runner._admission([ancienne]) == 0, (
        "une classe ANTÉRIEURE à la bascule est refusée : la porte réécrit "
        "l'histoire au lieu d'arrêter la production. Les 402 classes existantes "
        "deviendraient une dette impossible à solder.")


def test_the_detector_sees_a_class_without_a_declared_family(runner) -> None:
    """Non-vacuity, R180: a class with no `family:`, and one naming something that is not
    a family, are refused; a declared real family passes."""
    slugs = frozenset({"le-locataire", "un-garde-qui-ne-garde-pas"})
    headers = [{"id": "a", "family": ""}, {"id": "b", "family": "not-a-family"},
               {"id": "c", "family": "le-locataire"}]
    assert [cid for cid, _ in runner.undeclared_families(headers, slugs)] == ["a", "b"]


def test_every_class_declares_one_of_the_families(runner) -> None:
    """The real catalogue: every entry names a family (R180)."""
    catalogue = runner._CATALOGUE.read_text(encoding="utf-8")
    missing = runner.undeclared_families(runner.parse_all_headers(catalogue), runner._family_slugs())
    assert not missing, (f"{len(missing)} classe(s) sans famille déclarée : "
                         f"{[cid for cid, _ in missing[:10]]}")


# R185 (2026-09-26) — the proofs a NEW class carries, refused per class and not through a
# ceiling: two of the hole counters that refused them were already full, so raising a
# number would have re-opened the door in silence.
_COMPLETE = {
    "id": "fabricated",
    "siblings": "swept:2026-09-26 — `sibling-sweeper` : 9 candidates → **2 sites vivants**",
    "root_cause": "the loader reads the stored copy before the environment, whatever its app",
    "cause_evidence": "read (src/utils/credential_loader.py — central_app_wins, 2026-09-26)",
    "seen_red": "self-proving (tests/test_x.py::test_the_detector_sees_the_defect_it_is_written_for)",
}


def test_the_detector_sees_a_new_class_without_its_proofs(runner) -> None:
    """Each missing proof is named; the complete class passes; honest terminal states
    (`inferred` citing a file, `never` with a reason) pass — rule 15 allows them."""
    exists = lambda p: p.startswith("src/")  # noqa: E731
    assert runner.proof_gaps(dict(_COMPLETE), exists) == []
    broken = {
        "siblings": "not-swept",
        "root_cause": "it broke",
        "cause_evidence": "unknown",
        "seen_red": "never",
    }
    for key, bad in broken.items():
        gaps = runner.proof_gaps({**_COMPLETE, key: bad}, exists)
        assert len(gaps) == 1, (key, gaps)
    assert runner.proof_gaps({**_COMPLETE, "siblings": "swept:2026-09-26 — looked"}, exists)
    assert runner.proof_gaps({**_COMPLETE, "cause_evidence": "measured"}, exists)
    assert runner.proof_gaps({**_COMPLETE, "cause_evidence": "read (the code, trust me, really)"},
                             exists)
    honest = {**_COMPLETE, "cause_evidence": "inferred (from src/a.py — not reproduced yet)",
              "seen_red": "never — no fixture can reach the branch yet"}
    assert runner.proof_gaps(honest, exists) == []
