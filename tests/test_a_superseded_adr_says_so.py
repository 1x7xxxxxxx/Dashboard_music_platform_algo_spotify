"""Un ADR contredit par la pratique le DIT dans son statut.

Type: Test
Uses: pytest, re
Depends on: docs/adr/*.md, CLAUDE.md
Persists in: nothing

Le défaut, payé deux fois
-------------------------
`ADR-002` refuse sept motifs. Deux de ses refus ont été **dépassés par la pratique sans
que l'ADR le dise** :

* **§7 (reprise après sinistre)** — rejeté au motif que « backup/restore is
  operator-driven ». La ré-évaluation du 2026-08-21 a constaté : *« dépassé par les
  faits : cron `pg_dump` actif en production, 17 sauvegardes sur disque, plus
  `make backup-test`. **L'ADR n'avait pas été mis à jour.** »*
* **§4 (observabilité)** — rejeté, puis `R115` ouverte dans la roadmap active, puis
  Prometheus et Grafana adoptés le 2026-09-16 (ADR-026). Entre les deux, `CLAUDE.md`
  a continué d'afficher « Rejected msdr patterns (… observability) » — l'état du
  2026-05-14 — et c'est la seule ligne que la plupart des lectures voient.

Ce que ce test tient
--------------------
Un ADR dont un paragraphe est superseded doit le déclarer **dans son statut**, avec le
numéro de l'ADR qui le remplace. Ce n'est pas de la bureaucratie : un refus qu'on cite
alors qu'il a été renversé fait prendre la mauvaise décision, et c'est arrivé ici — une
skill cherchait QuestDB et des révisions Alembic « qu'ADR-002 rejette », longtemps après.

⚠️ Ce test ne dit PAS qu'un ADR doit être superseded. Il dit que **si** une ADR nomme
une autre comme superseded, la cible doit le porter dans son statut. La relation se lit
dans les deux sens ou elle ne se lit pas.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ADR_DIR = _ROOT / "docs" / "adr"

# La DIRECTION compte, et une seule expression ne la porte pas : « supersede ADR-002 »
# et « SUPERSEDED par ADR-002 » disent l'inverse l'un de l'autre avec les mêmes mots.
# Une première version les confondait, et ADR-002 — qui déclare « §4 SUPERSEDED par
# ADR-026 » — se lisait comme superseding ADR-026. Le marqueur du passif est la
# préposition : `par` / `by`.
_ACTIVE = re.compile(r"supersede[sd]?\s+(ADR-\d{3})", re.I)        # X supersede Y
_PASSIVE = re.compile(r"supersede[sd]?\s+(?:par|by)\s+(ADR-\d{3})", re.I)  # X l'EST par Y


def _adrs() -> dict[str, Path]:
    return {p.name.split("-")[1]: p for p in sorted(_ADR_DIR.glob("ADR-*.md"))
            if p.name != "ADR-TEMPLATE.md"}


def _status(path: Path) -> str:
    """Le bloc de statut : de `- **Status:**` jusqu'à la ligne `## `."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^- \*\*Status:\*\*(.*?)(?=^##\s)", text, re.M | re.S)
    return m.group(1) if m else ""


def test_there_are_adrs_to_check() -> None:
    """Non-vacuité : un glob vide rendrait tout ce qui suit vrai de rien."""
    assert len(_adrs()) >= 20, f"{len(_adrs())} ADR trouvées — le chemin a changé ?"


def test_every_superseding_adr_is_declared_by_its_target() -> None:
    """Si A supersede B, le STATUT de B doit nommer A.

    Sans cette réciprocité, un lecteur qui ouvre B — et c'est le cas fréquent, B étant
    l'ancienne décision qu'on cite — n'apprend jamais qu'elle a été renversée.
    """
    adrs = _adrs()
    broken: list[str] = []
    for num, path in adrs.items():
        header = path.read_text(encoding="utf-8")[:2000]
        actives = set(_ACTIVE.findall(header)) - set(_PASSIVE.findall(header))
        for target in actives:
            tnum = target.split("-")[1]
            if tnum == num:
                continue                      # une ADR qui se cite elle-même
            tpath = adrs.get(tnum)
            if tpath is None:
                broken.append(f"{path.name} supersede {target}, qui n'existe pas")
                continue
            # La RELATION, pas le numéro. Une version antérieure testait
            # `f"ADR-{num}" in status` : elle restait verte sur un statut qui
            # mentionnait l'ADR en passant (« Lire ADR-026 avant de citer §4 »), donc
            # sur un ADR dont la supersession avait été effacée. Mutée, elle n'a pas
            # mordu. Le prédicat doit exiger la tournure PASSIVE nommant le superseder.
            declared = {m.split("-")[1] for m in _PASSIVE.findall(_status(tpath))}
            if num not in declared:
                broken.append(
                    f"{path.name} supersede {target}, mais le STATUT de {tpath.name} "
                    f"ne déclare pas « superseded par ADR-{num} » "
                    f"(déclaré : {sorted(declared) or 'rien'})")
    assert not broken, (
        "relation de supersession à sens unique :\n  " + "\n  ".join(broken)
        + "\n\nUn refus qu'on cite alors qu'il a été renversé fait prendre la mauvaise "
        "décision. C'est arrivé deux fois sur ADR-002 (§7 reprise après sinistre, §4 "
        "observabilité) — la seconde alors qu'une skill cherchait encore QuestDB et "
        "Alembic « qu'ADR-002 rejette »."
    )


def test_the_index_of_adrs_in_claude_md_is_not_stale() -> None:
    """Un ADR superseded ne peut pas être décrit dans `CLAUDE.md` sans le dire.

    `CLAUDE.md` est la surface que la plupart des lectures voient ; elle a affiché
    « Rejected msdr patterns (… observability) » pendant que R115 était ouverte.
    """
    claude = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    adrs = _adrs()

    # Les ADR qui SUBISSENT une supersession — la relation, pas le mot. Une première
    # version testait `"supersed" in status`, ce qui attrapait aussi celle qui
    # SUPERSEDE : ADR-026 s'est signalée elle-même comme périmée le jour de sa
    # naissance. Un prédicat qui ne distingue pas l'actif du passif ne lit pas une
    # relation, il lit un vocabulaire.
    superseded: set[str] = set()
    for num, path in adrs.items():
        header = path.read_text(encoding="utf-8")[:2000]
        # A dit « je supersede B »  ->  B est superseded
        for target in set(_ACTIVE.findall(header)) - set(_PASSIVE.findall(header)):
            if target.split("-")[1] != num:
                superseded.add(target.split("-")[1])
        # B dit « je suis superseded par A »  ->  B l'est
        if _PASSIVE.search(header):
            superseded.add(num)

    stale: list[str] = []
    for num in sorted(superseded):
        path = adrs[num]
        line = next((ln for ln in claude.splitlines()
                     if f"ADR-{num}-" in ln and ln.lstrip().startswith("|")), None)
        if line is None:
            continue                          # non indexée : rien à périmer
        if "supersed" not in line.lower():
            stale.append(f"ADR-{num} ({path.name}) est superseded, et CLAUDE.md la "
                         f"décrit sans le dire :\n      {line.strip()}")
    assert not stale, (
        "index périmé dans `CLAUDE.md` :\n  " + "\n  ".join(stale)
        + "\n\nC'est la ligne que la plupart des lectures voient. Elle a affiché "
        "« Rejected … observability » pendant que la roadmap portait R115."
    )
