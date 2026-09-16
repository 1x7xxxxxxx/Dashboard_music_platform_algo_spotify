#!/usr/bin/env python3
"""Rétro-porte les trois preuves sur les classes existantes — mécaniquement, une fois.

Type: Utility
Uses: tools/dev/error_class_families (familles dérivées), audit_runner (signatures)
Triggers: à la main, une seule fois (puis `/capitalise` écrit les champs à la source)
Persists in: .claude/dev-docs/error-classes.md — insertion seule

Ce qu'il fait, et surtout ce qu'il REFUSE de faire
---------------------------------------------------
Il insère trois lignes par classe, jamais une de plus, et **n'invente aucune date**.

* `cause_evidence` — `read` quand `root_cause` nomme un chemin qui EXISTE sur le disque
  (la provenance est écrite dans la valeur), sinon `unknown` ;
* `guard_scope` — la famille **dérivée** par `error_class_families.classify()`, avec la
  mention explicite qu'elle est dérivée et que « couvre / ne couvre pas » reste à écrire.
  Une famille dérivée n'est pas une portée : c'est un point de départ honnête ;
* `seen_red` — `n-a` quand la classe n'a pas de signature (mécaniquement connu),
  `unknown` partout ailleurs. **Jamais une date**, même quand la prose en raconte une :
  43 % des entrées mentionnent une vérification rouge, et le document de santé calcule
  la récidive PAR STRATE sur ce champ. Une date lue dans une phrase et promue en fait
  calculerait la réponse sur des strates fabriquées.

Pourquoi l'insertion seule
---------------------------
Aucune ligne n'est supprimée, aucun `## Index` touché : le diff se relit comme
`3 × N ajouts` et rien d'autre. Un rétro-portage qui réécrit est un rétro-portage qu'on
ne peut pas relire, donc qu'on approuve sans lire.

⚠️ Idempotent : une classe qui porte déjà l'un des trois champs n'est pas touchée. Le
relancer après une revue humaine n'écrase rien.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))

CATALOGUE = ROOT / ".claude" / "dev-docs" / "error-classes.md"
_TODAY = date.today().isoformat()

# Un chemin dans une prose : au moins un `/` et une extension connue. Volontairement
# étroit — un faux `read` est pire qu'un `unknown`, parce qu'il se lit comme une preuve.
_PATH = re.compile(r"`?([A-Za-z0-9_./\-]+/[A-Za-z0-9_.\-]+\.(?:py|md|sql|yml|yaml|sh|toml|json))`?")


def _existing_path(root_cause: str | None) -> str | None:
    if not root_cause:
        return None
    for m in _PATH.finditer(root_cause):
        cand = m.group(1)
        if (ROOT / cand).exists():
            return cand
    return None


def _insert_after(body_lines: list[str], anchor: str, new_line: str) -> bool:
    """Insère `new_line` juste après la ligne `- <anchor>:`. Rend True si posé."""
    for i, line in enumerate(body_lines):
        if line.startswith(f"- {anchor}:"):
            body_lines.insert(i + 1, new_line)
            return True
    return False


_MUTATION = re.compile(r"Mutation record\s*[—-]\s*(20\d\d-\d\d-\d\d)")
_PYTEST_FILE = re.compile(r"(tests/[A-Za-z0-9_/]+\.py)")


def _mutation_date(signature: str | None) -> tuple[str, str] | None:
    """(date, fichier) si la signature vise un test qui PORTE une trace de mutation.

    ⚠️ Ce que cette date prouve, exactement : l'auteur du garde a joué des mutations et
    les a vues rouges, et il l'a consigné dans le docstring du test. Pour une classe dont
    la SIGNATURE EST ce test, c'est bien la preuve que `seen_red` demande — le même
    prédicat, vu tomber sur le défaut remis.

    Ce que ça ne prouve PAS, et qui reste à la revue humaine : que la mutation portait
    sur le défaut de CETTE classe quand un test garde plusieurs propriétés. La valeur
    écrite nomme donc sa source, pour qu'on puisse la contester.
    """
    if not signature:
        return None
    m = _PYTEST_FILE.search(signature)
    if not m:
        return None
    path = ROOT / m.group(1)
    if not path.exists():
        return None
    try:
        head = path.read_text(encoding="utf-8")[:4000]
    except OSError:
        return None
    d = _MUTATION.search(head)
    return (d.group(1), m.group(1)) if d else None


def phase_b() -> int:
    """Remonte `seen_red: unknown` → la date lue dans la trace de mutation du test."""
    import audit_runner

    text = CATALOGUE.read_text(encoding="utf-8")
    parsed = {c["id"]: c for c in audit_runner.parse_all_headers(text)}
    parts = re.split(r"(?m)^(## )", text)
    out: list[str] = [parts[0]]
    promoted = 0
    for i in range(1, len(parts), 2):
        head, sec = parts[i], parts[i + 1]
        cid = (sec.split("\n", 1)[0].strip().split() or [""])[0]
        got = _mutation_date(parsed.get(cid, {}).get("signature")) if cid in parsed else None
        if not got:
            out += [head, sec]
            continue
        lines = sec.split("\n")
        for j, ln in enumerate(lines):
            if ln.startswith("- seen_red: unknown"):
                date_, f = got
                lines[j] = (f"- seen_red: {date_} (via la trace de mutation de `{f}`, "
                            "consignée par l'auteur du garde)")
                promoted += 1
                break
        out += [head, "\n".join(lines)]
    CATALOGUE.write_text("".join(out), encoding="utf-8")
    print(f"✅ phase B : {promoted} `seen_red` remontées depuis une trace de mutation")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="compter sans écrire")
    ap.add_argument("--phase-b", action="store_true",
                    help="remonter seen_red depuis les traces de mutation existantes")
    args = ap.parse_args()
    if args.phase_b:
        return phase_b()

    import audit_runner
    import importlib
    fam = importlib.import_module("tools.dev.error_class_families")
    buckets, orphans = fam.classify()
    derived = {cid: slug for slug, rows in buckets.items() for cid, _ in rows}
    for cid, _ in orphans:
        derived[cid] = "sans-famille"

    text = CATALOGUE.read_text(encoding="utf-8")
    parsed = {c["id"]: c for c in audit_runner.parse_all_headers(text)}

    parts = re.split(r"(?m)^(## )", text)
    out: list[str] = [parts[0]]
    stats = {"touchées": 0, "déjà": 0, "cause_read": 0, "cause_unknown": 0,
             "seen_na": 0, "seen_unknown": 0}

    for i in range(1, len(parts), 2):
        head, sec = parts[i], parts[i + 1]
        cid = (sec.split("\n", 1)[0].strip().split() or [""])[0]
        if cid not in parsed:
            out += [head, sec]
            continue
        lines = sec.split("\n")
        if any(ln.startswith(("- seen_red:", "- cause_evidence:", "- guard_scope:"))
               for ln in lines):
            stats["déjà"] += 1
            out += [head, sec]
            continue

        rc = next((ln.split(":", 1)[1].strip() for ln in lines
                   if ln.startswith("- root_cause:")), None)
        path = _existing_path(rc)
        if path:
            cause = f"- cause_evidence: read ({path}, rétro-portage mécanique {_TODAY})"
            stats["cause_read"] += 1
        else:
            cause = (f"- cause_evidence: unknown (rétro-portage mécanique {_TODAY} — "
                     "aucun chemin vérifiable dans `root_cause`)")
            stats["cause_unknown"] += 1

        if parsed[cid].get("signature"):
            seen = (f"- seen_red: unknown (rétro-portage mécanique {_TODAY} — "
                    "aucune date ne sera inventée)")
            stats["seen_unknown"] += 1
        else:
            seen = f"- seen_red: n-a (pas de signature ; rétro-portage {_TODAY})"
            stats["seen_na"] += 1

        scope = (f"- guard_scope: {derived.get(cid, 'sans-famille')} — (famille DÉRIVÉE "
                 f"mécaniquement {_TODAY} ; couvre / ne couvre pas restent à écrire)")

        _insert_after(lines, "signature", seen) or _insert_after(lines, "symptom", seen)
        _insert_after(lines, "root_cause", cause)
        _insert_after(lines, "guard", scope) or lines.insert(len(lines) - 1, scope)
        stats["touchées"] += 1
        out += [head, "\n".join(lines)]

    fresh = "".join(out)
    if args.dry_run:
        print("  (dry-run)", stats)
        return 0
    CATALOGUE.write_text(fresh, encoding="utf-8")
    print(f"✅ {stats['touchées']} classe(s) rétro-portées, {stats['déjà']} déjà pourvues")
    print(f"   cause_evidence : read={stats['cause_read']} unknown={stats['cause_unknown']}")
    print(f"   seen_red       : n-a={stats['seen_na']} unknown={stats['seen_unknown']}")
    print("   Puis : make error-health && make error-families")
    return 0


if __name__ == "__main__":
    sys.exit(main())
