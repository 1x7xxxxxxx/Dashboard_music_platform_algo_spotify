#!/usr/bin/env python3
"""A PDF the owner must validate comes out twice, numbered, marked A_VALIDER, and on the Desktop (R646).

Type: Utility
Uses: the PDF bytes and a `key` — the text of the SOURCES the owner validates (for the charts dossier:
      tools/dev/charts_dossier/review.yaml), never the PDF itself: a re-capture of the same grades is
      not a new revision
Triggers: tools/dev/charts_dossier/main.py build() ; `python3 tools/dev/validation_pdf.py [validate <stem>]`
Persists in: <folder>/A_VALIDER_<stem>_revNN_<date>.pdf + the same on the Desktop ;
             revue/pdf-revisions.json (gitignored, like the copies: machine artefacts)

Port of the master's tools/dev/validation_pdf.py (baseline REQ-GOV-20 / REQ-PARC-133, owner 2026-10-22:
« tous les pdf qui sont générés et qui nécessitent des validations de ma part doivent être générés en
double dans le dossier avec bon n° de révision et un indice de A_VALIDER + sur le bureau »). So:
  - the revision goes up when the key's hash changes, and only then;
  - the previous A_VALIDER copies this module wrote are removed (only those it recorded: a file it did not
    write is never touched), so the Desktop shows only what is CURRENTLY to validate;
  - the name starts with its status, then the revision and the day that revision was cut —
    `A_VALIDER_dossier-graphiques_rev01_2026-10-23.pdf`;
  - `validate <stem>` renames the folder copy to VALIDE_… and takes the Desktop copy away; a validated
    revision is not proposed again until its sources change;
  - a Desktop copy locked by a PDF viewer (Windows) is reported, never a crash;
  - what waits on the owner comes FIRST (baseline REQ-GOV-23): publish refuses an HTML whose first <h2>
    is not marked `data-owner-first`.

    python3 tools/dev/validation_pdf.py                              # what waits for validation
    python3 tools/dev/validation_pdf.py validate dossier-graphiques

guard_scope: tests/test_a_pdf_to_validate_comes_out_twice.py — revision bumps on key only, both copies
written, old copy removed, validate renames and clears the Desktop, a locked file is reported, an HTML
that does not open on the owner's decisions is refused, the charts dossier publishes only when it waits.
NOT covered: the Desktop path on another machine (DESKTOP is this workstation's).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "revue" / "pdf-revisions.json"
DESKTOP = Path("/mnt/c/Users/timot/Desktop")
TODO, DONE = "A_VALIDER", "VALIDE"


def name(stem: str, rev: int, mark: str = TODO, day: str = "") -> str:
    return f"{mark}_{stem}_rev{rev:02d}" + (f"_{day}" if day else "") + ".pdf"


def _load(state: Path) -> dict:
    try:
        return json.loads(state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(state: Path, d: dict) -> None:
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(d, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _drop(paths: list[str], keep: set[str]) -> list[str]:
    """Remove the copies this module wrote before, except `keep`; returns those it could not remove."""
    stuck = []
    for f in paths:
        p = Path(f)
        if f in keep or not p.exists():
            continue
        try:
            p.unlink()
        except OSError:
            stuck.append(f)
    return stuck


OWNER_FIRST = "data-owner-first"


def owner_first_error(html: str) -> str | None:
    """None when the document's first <h2> is the owner's section; else why not. Pure."""
    i = html.find("<h2")
    if i == -1:
        return "aucune section <h2> : rien ne dit ce qui attend le propriétaire"
    tag = html[i:html.find(">", i) + 1]
    return None if OWNER_FIRST in tag else f"la première section n'est pas « à valider » ({OWNER_FIRST} absent de {tag})"


def publish(pdf: bytes, folder: Path, stem: str, key: str, desktop: Path | None = DESKTOP,
            state: Path = STATE, *, html: str) -> str:
    """Write the A_VALIDER copies of `stem` (folder + Desktop) at the right revision. Returns the line to print.
    Raises ValueError when `html` (the document the PDF was printed from) does not open on the owner's section."""
    err = owner_first_error(html)
    if err:
        raise ValueError(f"{stem} : publication refusée — {err} (REQ-GOV-23)")
    d = _load(state)
    e = d.get(stem) or {"rev": 0, "sha": None, "files": [], "valide": None}
    sha = hashlib.sha256(key.encode("utf-8")).hexdigest()
    if sha != e["sha"]:
        e["rev"], e["sha"], e["date"] = e["rev"] + 1, sha, date.today().isoformat()
    e.setdefault("date", date.today().isoformat())   # a revision cut before T311 gets the day it is next written
    if e.get("valide") == e["rev"]:
        d[stem] = e
        _save(state, d)
        return f"{stem} rev{e['rev']:02d} déjà validée — rien à valider"
    fname = name(stem, e["rev"], TODO, e.get("date", ""))
    targets = [folder / fname]
    if desktop is not None and desktop.is_dir():
        targets.append(desktop / fname)
    written, locked = [], []
    for t in targets:
        try:
            t.write_bytes(pdf)
            written.append(str(t))
        except OSError:
            locked.append(str(t))   # a viewer holds it open on Windows: say so, keep going
    stuck = _drop(e.get("files", []), set(written))
    e["files"] = written + [f for f in stuck if f not in written]
    d[stem] = e
    _save(state, d)
    out = f"{stem} rev{e['rev']:02d} à valider : " + " ; ".join(written)
    if locked or stuck:
        out += " ⚠️ verrouillé (fermer le lecteur PDF) : " + " ; ".join(locked + stuck)
    return out


def validate(stem: str, state: Path = STATE) -> str:
    """The owner validated `stem`: A_VALIDER → VALIDE in its folder, the Desktop copy taken away."""
    d = _load(state)
    e = d.get(stem)
    if not e or not e.get("files"):
        return f"{stem} : rien à valider"
    kept = []
    for f in e["files"]:
        p = Path(f)
        if not p.exists():
            continue
        if p.parent == DESKTOP:
            p.unlink()
        else:
            done = p.with_name(name(stem, e["rev"], DONE, e.get("date", "")))
            p.rename(done)
            kept.append(str(done))
    e["valide"], e["files"] = e["rev"], []
    d[stem] = e
    _save(state, d)
    return f"{stem} rev{e['rev']:02d} validée : " + (" ; ".join(kept) or "(aucune copie dans le dossier)")


def supersede(stem: str, state: Path = STATE) -> str:
    """A new version replaces `stem` (T327: MASTER-v6 over MASTER-v3): its A_VALIDER copies are removed —
    only those this module recorded — and it no longer waits. Returns the line to print, "" if nothing."""
    d = _load(state)
    e = d.get(stem)
    if not e or not e.get("files"):
        return ""
    stuck = _drop(e["files"], set())
    e["files"], e["remplacé"] = stuck, True
    d[stem] = e
    _save(state, d)
    return f"{stem} remplacé : copies A_VALIDER retirées" + (f" ⚠️ verrouillé : {' ; '.join(stuck)}" if stuck else "")


def pending(state: Path = STATE) -> list[str]:
    return [f"{s} rev{e['rev']:02d} : " + " ; ".join(e["files"])
            for s, e in sorted(_load(state).items())
            if e.get("files") and e.get("valide") != e["rev"] and not e.get("remplacé")]


def main(argv: list[str]) -> int:
    if argv[:1] == ["validate"] and len(argv) == 2:
        print(validate(argv[1]))
        return 0
    if argv:
        print(__doc__)
        return 2
    print("\n".join(pending()) or "rien à valider")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
