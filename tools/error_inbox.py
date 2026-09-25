#!/usr/bin/env python3
"""Render `app_error_log` into a document, and link it from the roadmap.

Type: Utility
Uses: PostgresHandler, error-classes.md (for the link, never for the truth)
Triggers: `make error-inbox`, `make error-resolve`, alert_monitor (read-only)
Depends on: app_error_log (migration 083)
Persists in: .claude/dev-docs/error-inbox.md, .claude/dev-docs/roadmap/checklist.md
    (ONE anchored line, never a task)

Why this writes a document and NOT roadmap items
------------------------------------------------
Asked on 2026-09-04: « un process automatisé qui intègre en roadmap ou dans un document
qu'on relie automatiquement ». Both were on the table; only one of them is safe.

The roadmap here is curated prose under two invariants a machine cannot honour: items
MOVE between `checklist.md` and `archive.md` and are never deleted
(`tests/test_roadmap_two_files.py`), and the top index is « ce qu'on peut commencer
maintenant » — a judgement. A writer that appends a row per exception would break the
first and destroy the second: forty machine rows would bury the two real tasks, and the
percentage would move without anything being delivered.

So the machine owns a document it generates in full, and touches the roadmap through
exactly ONE anchored line — a pointer with a count. Same shape as the reprise anchor:
a claim in prose that a test can compare against the data.

The list is by DEFECT, not by occurrence: the fingerprint (src/utils/error_fingerprint)
folds the same bug seen twenty times into one entry with a counter.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.env_files import load_project_env  # noqa: E402

# ⚠️ Lancé d'un shell nu, cet outil lirait un environnement DIFFÉRENT de celui du
# dashboard et des DAG — donc une autre base — et rapporterait sur une configuration
# que personne n'exécute. Trouvé le 2026-09-17 par
# `tests/test_operator_tools_read_the_apps_env.py`, au moment où `--check` a été
# ajouté : c'est précisément un contrôle de FRAÎCHEUR qui ne doit pas se tromper de
# base, sans quoi il rend un verdict sur un registre qui n'est pas celui qu'on lit.
load_project_env()

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude" / "dev-docs" / "error-inbox.md"
CHECKLIST = ROOT / ".claude" / "dev-docs" / "roadmap" / "checklist.md"
CLASSES = ROOT / ".claude" / "dev-docs" / "error-classes.md"

_ANCHOR_RE = re.compile(r"<!-- error-inbox: open=\d+ -->")
_LINK_LINE = (
    "📥 **Erreurs applicatives non triées : {n}** — "
    "`.claude/dev-docs/error-inbox.md`, régénéré par `make error-inbox`. "
    "Ce fichier est écrit par une machine ; aucune tâche n'en sort toute seule.\n"
    "<!-- error-inbox: open={n} -->"
)


def _db():
    from src.database.postgres_handler import PostgresHandler
    return PostgresHandler.from_env_or_config()


def _known_classes() -> set[str]:
    """Catalogued class names, so an entry can point at the lesson already written."""
    try:
        text = CLASSES.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"^## ([a-z0-9-]+)$", text, re.M))


def _fetch(db, include_resolved: bool):
    where = "" if include_resolved else "WHERE resolved_at IS NULL"
    return db.fetch_query(
        f"""
        SELECT fingerprint, exc_type, message, page, origin, environment,
               occurrences, first_seen, last_seen, error_class, resolved_at,
               resolved_note
        FROM app_error_log
        {where}
        ORDER BY resolved_at IS NULL DESC, last_seen DESC
        """
    )


def _age(dt) -> str:
    if dt is None:
        return "—"
    delta = datetime.now(timezone.utc) - dt
    hours = delta.total_seconds() / 3600
    if hours < 48:
        return f"{hours:.0f} h"
    return f"{hours / 24:.0f} j"


def render(rows, known: set[str]) -> tuple[str, int]:
    open_rows = [r for r in rows if r[10] is None]
    lines = [
        "# Registre des erreurs applicatives",
        "",
        "<!-- GÉNÉRÉ par `tools/error_inbox.py` — toute édition à la main est perdue "
        "à la prochaine exécution. -->",
        "",
        "Une ligne par **défaut**, pas par occurrence : l'empreinte "
        "(`src/utils/error_fingerprint.py`) est la classe d'exception plus le premier "
        "cadre de pile qui nous appartient, **sans numéro de ligne**. Le même bug vu "
        "vingt fois, avant et après un déploiement, reste une seule ligne avec un "
        "compteur.",
        "",
        "⚠️ **Instantané de la base LOCALE, régénéré à la main** (`make error-inbox`). Les "
        "défauts de PRODUCTION n'ont pas besoin de ce fichier : ils arrivent chaque soir "
        "dans le mail de 23 h (`check_app_errors`, DAG `alert_monitor`). Décision R171 du "
        "2026-09-25 — le fichier était resté 7 jours sans régénération, avec pour seul "
        "défaut ouvert un artefact de test.",
        "",
        f"Régénéré le {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC · "
        f"**{len(open_rows)} ouverte(s)** sur {len(rows)} au total.",
        "",
        "Fermer une entrée : `make error-resolve FP=<12 premiers caractères> "
        'NOTE="ce qui a été corrigé"`. Une **nouvelle** occurrence la rouvre '
        "automatiquement — c'est le signal le plus utile du registre.",
        "",
    ]

    if not open_rows:
        lines += ["## ✅ Rien d'ouvert", "",
                  "Aucune erreur applicative non triée.", ""]
    else:
        lines += ["## Ouvertes", "",
                  "| Empreinte | Exception | Où | Page | Env | # | Vue il y a | Classe |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in open_rows:
            (fp, exc_type, _msg, page, origin, env, occ, _first, last,
             err_class, _res, _note) = r
            klass = (f"[`{err_class}`](error-classes.md#{err_class})"
                     if err_class and err_class in known else "—")
            lines.append(
                f"| `{fp[:12]}` | `{exc_type}` | `{origin}` | {page or '—'} | "
                f"{env} | {occ} | {_age(last)} | {klass} |")
        lines.append("")
        lines.append("### Le détail")
        lines.append("")
        for r in open_rows:
            (fp, exc_type, msg, page, origin, env, occ, first, last,
             err_class, _res, _note) = r
            lines += [
                f"#### `{fp[:12]}` — {exc_type} dans `{origin}`",
                "",
                f"- **Message** : {msg or '—'}",
                f"- **Page** : {page or '—'} · **environnement** : {env}",
                f"- **{occ} occurrence(s)**, première il y a {_age(first)}, "
                f"dernière il y a {_age(last)}",
                (f"- **Classe** : `{err_class}`" if err_class
                 else "- **Classe** : non rattachée — si elle se reproduit, "
                      "`/capitalise` en écrit une"),
                "",
            ]

    resolved = [r for r in rows if r[10] is not None]
    if resolved:
        lines += ["## Fermées", "",
                  "| Empreinte | Exception | Fermée il y a | Note |",
                  "|---|---|---|---|"]
        for r in resolved[:25]:
            fp, exc_type = r[0], r[1]
            lines.append(f"| `{fp[:12]}` | `{exc_type}` | {_age(r[10])} | "
                         f"{(r[11] or '—')[:90]} |")
        lines.append("")

    # Exactement UNE fin de ligne finale : le hook `end-of-file-fixer` réécrivait
    # le fichier généré à chaque commit, donc le commit échouait sur un fichier
    # que personne n'avait édité.
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n", len(open_rows)


def _update_checklist(n_open: int) -> bool:
    """Replace the single anchored line in the roadmap. Never adds a task."""
    try:
        text = CHECKLIST.read_text(encoding="utf-8")
    except OSError:
        return False
    block = _LINK_LINE.format(n=n_open)
    if _ANCHOR_RE.search(text):
        # Rewrite the pointer line and its anchor, together — they are one claim.
        start = text.rindex("📥 **Erreurs applicatives non triées")
        end = text.index("-->", _ANCHOR_RE.search(text).start()) + 3
        new = text[:start] + block + text[end:]
    else:
        marker = "## 🙋 En attente de toi"
        idx = text.index(marker)
        new = text[:idx] + block + "\n\n" + text[idx:]
    if new == text:
        return False
    CHECKLIST.write_text(new, encoding="utf-8")
    return True


def _check() -> int:
    """Le document décrit-il encore la base ? Trois issues, jamais deux.

    ⚠️ Ce contrôle est le seul des quatre générateurs de documents qui dépende d'une
    ressource EXTERNE. Ses trois pairs (`gold_coverage`, `error_class_families`,
    `error_class_health`) dérivent du dépôt : ils peuvent comparer disque et rendu
    n'importe où, y compris en CI. Celui-ci a besoin de `app_error_log`.

    D'où le code de sortie **2**, et il est le point de cette fonction. Un contrôle qui
    rendrait 0 parce qu'il n'a pas pu se connecter ressemblerait à un contrôle qui a
    vérifié quelque chose — c'est la classe `a-check-that-can-never-pass`, et le dépôt
    l'a déjà payée sur un `gh api … || echo true` qui déclarait succès sur une panne
    réseau. Ici, « je n'ai rien pu vérifier » a son propre code et son propre message.
    """
    try:
        db = _db()
    except Exception as exc:                                   # noqa: BLE001
        print(f"⚠️  base injoignable ({type(exc).__name__}) — ce contrôle n'a RIEN "
              f"vérifié. Le document peut être à jour comme périmé ; il est impossible "
              f"de le dire d'ici. Lancer sur une machine qui voit `app_error_log`.",
              file=sys.stderr)
        return 2
    try:
        rows = _fetch(db, include_resolved=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"⚠️  `app_error_log` illisible ({type(exc).__name__}) — RIEN vérifié.",
              file=sys.stderr)
        return 2
    finally:
        try:
            db.close()
        except Exception:                                      # noqa: BLE001
            pass

    fresh, n_open = render(rows, _known_classes())
    try:
        current = DOC.read_text(encoding="utf-8")
    except OSError:
        print(f"❌ {DOC.relative_to(ROOT)} est absent. Remède : make error-inbox",
              file=sys.stderr)
        return 1

    # L'horodatage de régénération change à chaque exécution : le comparer ferait
    # rougir un document parfaitement à jour. On compare tout le reste, ligne à ligne.
    def _body(text: str) -> list[str]:
        return [ln for ln in text.splitlines() if not ln.startswith("Régénéré le ")]

    if _body(current) == _body(fresh):
        print(f"✅ {DOC.relative_to(ROOT)} décrit la base — {n_open} ouverte(s) sur "
              f"{len(rows)}")
        return 0
    print(f"❌ {DOC.relative_to(ROOT)} ne décrit plus `app_error_log` : la base porte "
          f"{n_open} entrée(s) ouverte(s) sur {len(rows)}. Remède : make error-inbox\n"
          f"\nUn document généré qui affirme un état périmé est pire qu'un document "
          f"absent : il se lit comme une mesure.", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resolve", metavar="FP",
                    help="ferme l'entrée dont l'empreinte commence par FP")
    ap.add_argument("--note", default="", help="pourquoi elle est fermée")
    ap.add_argument("--all", action="store_true", help="inclure les fermées")
    ap.add_argument("--check", action="store_true",
                    help="n'écrit rien : dit si le document décrit encore la base. "
                         "0 = à jour · 1 = périmé · 2 = LA BASE EST INJOIGNABLE, "
                         "donc RIEN n'a été vérifié")
    args = ap.parse_args()

    if args.check:
        return _check()

    db = _db()
    try:
        if args.resolve:
            if not args.note.strip():
                print("❌ --note est obligatoire : une entrée fermée sans raison est "
                      "une entrée perdue.", file=sys.stderr)
                return 1
            rows = db.fetch_query(
                "UPDATE app_error_log SET resolved_at = NOW(), resolved_note = %s "
                "WHERE fingerprint LIKE %s AND resolved_at IS NULL RETURNING fingerprint",
                (args.note.strip(), args.resolve + "%"))
            if not rows:
                print(f"❌ aucune entrée OUVERTE dont l'empreinte commence par "
                      f"{args.resolve!r}", file=sys.stderr)
                return 1
            print(f"✅ {len(rows)} entrée(s) fermée(s)")

        rows = _fetch(db, include_resolved=True)
    finally:
        try:
            db.close()
        except Exception:      # noqa: BLE001
            pass

    body, n_open = render(rows, _known_classes())
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(body, encoding="utf-8")
    print(f"✅ {DOC.relative_to(ROOT)} — {n_open} ouverte(s) sur {len(rows)}")
    if _update_checklist(n_open):
        print("✅ roadmap : la ligne de renvoi a été mise à jour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
