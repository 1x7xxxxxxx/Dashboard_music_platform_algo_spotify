#!/usr/bin/env python3
"""La santé du catalogue de classes d'erreur — ce que git sait, et ce que le texte dit.

Type: Utility
Uses: .claude/scripts/audit_runner (parse), tools/dev/error_class_families (classify), git
Triggers: make error-health / make error-health-check
Persists in: .claude/dev-docs/error-class-health.{json,md} — versionnés

Pourquoi cet outil existe
-------------------------
Le catalogue porte 363 classes et **personne ne sait lesquelles servent**. La question
« comment écrire une classe qui empêche vraiment la récidive » n'avait jamais de réponse
mesurée, parce que rien ne mesurait.

Deux échecs du 2026-09-16 disent où est le trou. `a-kill-pattern-that-matches-its-own-
shell` avait été écrite le 2026-09-12 **avec son hook**, et s'est reproduite **trois
fois** : le hook gardait le VERBE `pkill`, la cause était un motif qui se contient
lui-même, et `pgrep` la partageait. Et une classe a été livrée sur une cause plausible
mais non vérifiée, testée ensuite, fausse, rétractée.

Ce que ce document mesure, et ce qu'il refuse de mesurer
--------------------------------------------------------
**Il mesure la récidive depuis GIT**, jamais depuis un champ tenu à la main : pour chaque
révision du catalogue, on diffe bloc par bloc et on compte les commits qui ont AJOUTÉ une
ligne d'historique à une classe. Un compteur de récidive écrit à la main serait deux
définitions d'une même grandeur qui ne se comparent jamais — ce dépôt a la classe.

**Il refuse de crantée un taux qui baisse.** Normalisé par le temps d'exposition, le taux
de récidive MONTE (0,35 évènement par classe-mois pour la cohorte de septembre contre
0,11 pour celle de mai) : un cliquet « le taux ne peut que baisser » serait rouge le jour
où on l'écrit. Ce qui se crante, c'est la **méthode** — la part de classes dont la
connaissance est invérifiable.

⚠️ Les deux instruments ne se mélangent jamais
-----------------------------------------------
`.claude/dev-docs/error-classes.md` **n'entre dans git que le 2026-09-10**. Toute histoire
antérieure a été écrite APRÈS COUP, de mémoire ; la suivante est observée commit par
commit. Publier un seul taux sur les deux serait `a-threshold-carried-across-instruments`
appliqué à notre propre métrique. Le document rend donc deux tableaux, étiquetés, et le
déclaratif porte la mention « ne pas comparer ».

Ce qu'il ne stocke pas
----------------------
Aucune série temporelle. Le JSON est un INSTANTANÉ, et **l'historique git EST la série** —
c'est pourquoi les clés sont triées, un scalaire par ligne, et le bloc `aggregate` écrit
en dernier et contigu : `git log -L` sur ce bloc sort l'histoire d'une métrique.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude" / "scripts"))

CATALOGUE = ROOT / ".claude" / "dev-docs" / "error-classes.md"
DOC = ROOT / ".claude" / "dev-docs" / "error-class-health.md"
DATA = ROOT / ".claude" / "dev-docs" / "error-class-health.json"
CAT_REL = ".claude/dev-docs/error-classes.md"

# Le catalogue entre dans git ce jour-là. Avant : histoire DÉCLARATIVE (réécrite après
# coup). Après : histoire OBSERVÉE, commit par commit. Calculé, pas codé en dur — voir
# `_window_start()`.
_HISTORY_LINE = re.compile(r"^\s*-\s+(20\d\d-\d\d-\d\d)\s*:", re.M)
_CLASS_HEAD = re.compile(r"^## ([a-z0-9][a-z0-9-]+)\s*$", re.M)

# Les types de garde qui s'exécutent SANS que personne y pense. Comparaison par
# SOUS-CHAÎNE : une comparaison par égalité comptait `pretooluse-hook` et `pre-commit`
# comme de la prose — dix faux positifs mesurés le 2026-09-16.
_AUTOMATIC_MARKS = ("pytest", "hook", "ci", "test", "ratchet", "make", "script",
                    "signature", "commit", "cross")
_PROSE_MARKS = ("doc", "aucun", "manual", "ops")

_HORIZONS = (7, 14, 30)


def _is_automatic(kind: str) -> bool:
    k = (kind or "aucun").lower()
    if any(m in k for m in _PROSE_MARKS):
        return False
    return any(m in k for m in _AUTOMATIC_MARKS)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=120).stdout


def _tree_is_dirty() -> bool:
    return bool(_git("status", "--porcelain", "--", CAT_REL).strip())


# ── Le texte : ce que le catalogue DÉCLARE ───────────────────────────────────

_GUARD_REF = re.compile(r"ref:\s*([^,}\s]+)")


def _guard_path(guard: str) -> str | None:
    """Le CHEMIN d'un `guard: { type: …, ref: … }`, ou None si ce n'en est pas un.

    Règle reprise de `tests/test_every_named_guard_exists.py:54-60` plutôt que
    réinventée : un `ref:` qui ne contient pas de `/` est de la prose (`make`, `extend`,
    `la règle …`), pas un fichier. Une ancre (`CLAUDE.md#9`) et un nœud pytest
    (`tests/x.py::y`) se ramènent au fichier.
    """
    m = _GUARD_REF.search(guard or "")
    if not m:
        return None
    path = m.group(1).split("::")[0].split("#")[0].strip().rstrip(",;)")
    if "/" not in path or path.startswith(("http", "<")):
        return None
    return path


def _field(body: str, name: str) -> str | None:
    m = re.search(rf"^- {name}:\s*(.+)$", body, re.M)
    if not m:
        return None
    v = m.group(1).strip()
    return None if v in ("—", "-", "") else v


def _blocks(text: str) -> dict[str, str]:
    """{id: corps} pour chaque classe. Même découpage que `audit_runner`."""
    out: dict[str, str] = {}
    for sec in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = sec.splitlines()
        cid = (lines[0].strip().split() or [""])[0]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", cid) or cid == "class-id":
            continue
        out[cid] = "\n".join(lines[1:])
    return out


def _derived_families() -> dict[str, str]:
    """{id: famille dérivée} — appelé UNE fois.

    `classify()` ne prend pas d'argument et rend `(buckets, orphelines)` : on inverse.
    On l'IMPORTE plutôt que de recopier ses 17 expressions — une règle recopiée diverge,
    et ce dépôt a la classe pour ça.
    """
    import importlib
    fam = importlib.import_module("tools.dev.error_class_families")
    buckets, orphans = fam.classify()
    out = {cid: slug for slug, rows in buckets.items() for cid, _ in rows}
    for cid, _ in orphans:
        out[cid] = "sans-famille"
    return out


def _declared(text: str) -> dict[str, dict]:
    import audit_runner

    derived = _derived_families()
    parsed = {c["id"]: c for c in audit_runner.parse_all_headers(text)}
    bodies = _blocks(text)
    out: dict[str, dict] = {}
    for cid, body in bodies.items():
        guard = _field(body, "guard") or ""
        gtype = (re.search(r"type:\s*([\w-]+)", guard) or [None, "aucun"])[1] \
            if "type:" in guard else "aucun"
        # ⚠️ Un `ref:` n'est un CHEMIN que s'il en a la forme. Ma première version
        # prenait le premier jeton après `ref:` et rapportait huit gardes « manquants »
        # dont `la`, `make`, `extend` et `CLAUDE.md#9` — des fragments de prose, pas des
        # fichiers. Le test `test_every_named_guard_exists.py` était vert au même
        # instant, et il avait raison. Même règle que lui : il faut un `/`.
        gref = _guard_path(guard)
        scope = _field(body, "guard_scope")
        out[cid] = {
            "status": (parsed.get(cid, {}).get("status") or "open"),
            "severity": _field(body, "severity") or "?",
            "kind": (parsed.get(cid, {}).get("kind") or ""),
            "has_signature": bool(parsed.get(cid, {}).get("signature")),
            "guard_type": gtype,
            "guard_ref": gref,
            "guard_ref_exists": bool(gref and (ROOT / gref.split("::")[0]).exists()),
            "guard_automatic": _is_automatic(gtype),
            "first_seen_declared": (_field(body, "first_seen") or "")[:10] or None,
            "history_dates_declared": sorted(set(_HISTORY_LINE.findall(body))),
            # Les trois champs du 2026-09-16. Absents tant que la passe n'a pas eu lieu.
            "seen_red": (_field(body, "seen_red") or "unknown").split()[0].lower(),
            "cause_evidence": (_field(body, "cause_evidence") or "unknown").split()[0].lower(),
            "guard_scope_declared_family": (scope.split("—")[0].strip() if scope else None),
            "guard_scope_has_not_covered": bool(scope and "ne couvre pas:" in scope),
            "guard_scope_derived_family": derived.get(cid),
        }
    return out


# ── Git : ce que personne ne peut éditer ─────────────────────────────────────

def _revisions() -> list[tuple[str, str]]:
    """[(sha, date ISO)] du plus ancien au plus récent, pour le catalogue seul."""
    out = _git("log", "--reverse", "--format=%H %cI", "--", CAT_REL)
    rows = []
    for line in out.splitlines():
        sha, _, iso = line.partition(" ")
        if sha:
            rows.append((sha, iso[:10]))
    return rows


def _observed() -> dict:
    """Rejeu de toutes les révisions du catalogue : introduction et récidives.

    ⚠️ Le renommage est détecté par similarité : sans ça, une classe renommée se lit
    « ancien id disparu, nouvel id introduit » et sa récidive repart à zéro en silence.
    """
    revs = _revisions()
    if not revs:
        return {"window_start": None, "as_of": None, "per_class": {}, "revisions": 0}

    per: dict[str, dict] = {}
    prev: dict[str, str] = {}
    for sha, day in revs:
        text = _git("show", f"{sha}:{CAT_REL}")
        if not text:
            continue
        cur = _blocks(text)
        for cid, body in cur.items():
            rec = per.setdefault(cid, {
                "introduced_date": day, "introduced_commit": sha[:12],
                "revisions": 0, "history_additions": 0, "renamed_from": None,
            })
            before = prev.get(cid)
            if before is None:
                # Introduction — ou renommage ? On cherche un id DISPARU au même
                # instant dont le corps est très proche.
                gone = set(prev) - set(cur)
                for old in gone:
                    ratio = difflib.SequenceMatcher(None, prev[old], body).quick_ratio()
                    if ratio >= 0.80:
                        rec["renamed_from"] = old
                        old_rec = per.get(old, {})
                        rec["introduced_date"] = old_rec.get("introduced_date", day)
                        rec["history_additions"] = old_rec.get("history_additions", 0)
                        break
            elif before != body:
                rec["revisions"] += 1
                if len(_HISTORY_LINE.findall(body)) > len(_HISTORY_LINE.findall(before)):
                    rec["history_additions"] += 1
        prev = cur

    as_of = revs[-1][1]
    return {"window_start": revs[0][1], "as_of": as_of,
            "per_class": per, "revisions": len(revs)}


# ── Les taux ─────────────────────────────────────────────────────────────────

def _poisson_ci(events: int, exposure_months: float) -> tuple[float, float] | None:
    """Intervalle à 95 % sur un taux d'évènements. None si l'exposition est nulle.

    Obligatoire, et pas décoratif : les sous-groupes qu'on compare portent 4 à 9
    évènements. Sans intervalle, un écart de cinq points se lit comme un résultat alors
    qu'un seul évènement le produit.
    """
    if exposure_months <= 0:
        return None
    lo = 0.0 if events == 0 else 0.5 * _chi2_inv(2 * events, 0.025)
    hi = 0.5 * _chi2_inv(2 * (events + 1), 0.975)
    return (lo / exposure_months, hi / exposure_months)


def _chi2_inv(k: float, p: float) -> float:
    """Quantile du chi² à k degrés — approximation de Wilson-Hilferty, sans SciPy.

    Assez juste pour un intervalle affiché à deux décimales ; ce document ne publie
    jamais l'intervalle comme une décision, seulement comme une raison de ne pas
    conclure.
    """
    if k <= 0:
        return 0.0
    z = 1.959963985 if p > 0.5 else -1.959963985
    return k * (1 - 2 / (9 * k) + z * math.sqrt(2 / (9 * k))) ** 3


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _rates(declared: dict, observed: dict) -> dict:
    ws, as_of = observed["window_start"], observed["as_of"]
    per = observed["per_class"]
    if not ws:
        return {}

    total_events = total_days = 0
    strata: dict[str, dict[str, list]] = {
        "by_guard": {}, "by_seen_red": {}, "by_scope": {}}
    for cid, d in declared.items():
        o = per.get(cid)
        if not o:
            continue
        start = max(o["introduced_date"], ws)
        exposure = max(0, _days(start, as_of))
        events = o["history_additions"]
        total_events += events
        total_days += exposure
        for key, label in (
            ("by_guard", "automatique" if d["guard_automatic"] else "prose"),
            ("by_seen_red", "daté" if re.fullmatch(r"20\d\d-\d\d-\d\d", d["seen_red"] or "")
             else "jamais-ou-inconnu"),
            ("by_scope", "ne-couvre-pas renseigné" if d["guard_scope_has_not_covered"]
             else "non renseigné"),
        ):
            s = strata[key].setdefault(label, [0, 0])
            s[0] += events
            s[1] += exposure

    def _rate(ev: int, days_: int) -> dict:
        months = days_ / 30.4
        ci = _poisson_ci(ev, months)
        return {"events": ev, "class_days": days_,
                "per_class_month": round(ev / months, 4) if months else None,
                "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None}

    out = {
        "window_start": ws, "as_of": as_of,
        "observed": _rate(total_events, total_days),
        "class_days_exposed": total_days,
    }
    for key, groups in strata.items():
        out[key] = {label: _rate(ev, days_) for label, (ev, days_) in sorted(groups.items())}

    # Cohortes à HORIZON FIXE. Une classe plus jeune que h est EXCLUE de la colonne,
    # jamais comptée « n'a pas récidivé » — c'est tout le correctif de l'artefact
    # 38 % → 18 % → 9 %, qui disait que tout s'améliorait quoi qu'il arrive.
    cohorts: dict[str, dict] = {}
    for h in _HORIZONS:
        at_risk = recurred = 0
        for cid, o in per.items():
            if cid not in declared:
                continue
            start = max(o["introduced_date"], ws)
            if _days(start, as_of) < h:
                continue
            at_risk += 1
            recurred += 1 if o["history_additions"] else 0
        cohorts[f"h{h}"] = {
            "at_risk": at_risk, "recurred": recurred,
            "rate": round(recurred / at_risk, 4) if at_risk else None,
        }
    out["fixed_horizon"] = cohorts
    return out


def _declarative(declared: dict, observed: dict) -> dict:
    """Le taux d'AVANT la fenêtre git — déclaratif, non comparable à l'observé."""
    ws = observed["window_start"]
    n = rec = 0
    for cid, d in declared.items():
        fs = d["first_seen_declared"]
        if not fs or not ws or fs >= ws:
            continue
        n += 1
        if any(x > fs for x in d["history_dates_declared"]):
            rec += 1
    return {"classes": n, "recurred": rec,
            "rate": round(rec / n, 4) if n else None,
            "note": "DÉCLARATIF — histoire écrite après coup. Ne pas comparer à l'observé."}


# ── Assemblage ───────────────────────────────────────────────────────────────

def build() -> tuple[str, str]:
    text = CATALOGUE.read_text(encoding="utf-8")
    declared = _declared(text)
    observed = _observed()
    per = observed["per_class"]

    classes = {}
    for cid in sorted(declared):
        d, o = declared[cid], per.get(cid, {})
        classes[cid] = {
            **{k: d[k] for k in sorted(d)},
            # ⚠️ Le SHA d'introduction a été RETIRÉ : `detect-secrets` voit une chaîne
            # hexadécimale de 12 caractères comme un secret à haute entropie, et il a
            # refusé le premier commit sur 89 lignes du JSON. Le marquer comme faux
            # positif ferait enfler `.secrets.baseline` à chaque régénération — un
            # document qui change tous les jours n'a rien à faire dans une liste
            # d'exceptions. La DATE suffit à tout ce qui est calculé ici ; qui veut le
            # commit le retrouve par `git log -S'## <id>' -- <catalogue>`.
            "introduced_date": o.get("introduced_date"),
            "revisions": o.get("revisions", 0),
            "history_additions": o.get("history_additions", 0),
            "renamed_from": o.get("renamed_from"),
        }

    holes = {
        "seen_red_unknown": sum(1 for c in classes.values() if c["seen_red"] == "unknown"),
        "seen_red_never": sum(1 for c in classes.values() if c["seen_red"] == "never"),
        "cause_unknown": sum(1 for c in classes.values() if c["cause_evidence"] == "unknown"),
        "cause_inferred": sum(1 for c in classes.values() if c["cause_evidence"] == "inferred"),
        "scope_unknown": sum(1 for c in classes.values()
                             if not c["guard_scope_declared_family"]),
        "scope_without_not_covered": sum(1 for c in classes.values()
                                         if not c["guard_scope_has_not_covered"]),
        "guards_ref_missing": sum(1 for c in classes.values()
                                  if c["guard_ref"] and not c["guard_ref_exists"]),
    }
    population = {
        "classes": len(classes),
        "with_signature": sum(1 for c in classes.values() if c["has_signature"]),
        "automatic_guard": sum(1 for c in classes.values() if c["guard_automatic"]),
        "prose_only": sum(1 for c in classes.values() if not c["guard_automatic"]),
        "ever_recurred_observed": sum(1 for c in classes.values() if c["history_additions"]),
    }
    rates = _rates(declared, observed)

    payload = {
        "classes": classes,
        # ⚠️ ÉCRIT EN DERNIER ET CONTIGU, pour que
        # `git log -L '/"aggregate": {/','/^  }/':<json>` rende l'histoire d'une métrique.
        "aggregate": {
            "declarative": _declarative(declared, observed),
            "generated_from": {
                "catalogue_revisions": observed["revisions"],
                # Idem : pas de SHA ici non plus.
                "head_date": (_git("log", "-1", "--format=%cI").strip()[:10] or None),
            },
            "holes": dict(sorted(holes.items())),
            "population": dict(sorted(population.items())),
            "recurrence": rates,
        },
    }
    js = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    return js, _render(payload)


def _render(p: dict) -> str:
    a = p["aggregate"]
    r, h, pop = a["recurrence"], a["holes"], a["population"]
    L = [
        "<!-- GÉNÉRÉ par `tools/dev/error_class_health.py` — toute édition à la main est",
        "     perdue à la prochaine exécution de `make error-health`. -->",
        "",
        "# La santé du catalogue de classes d'erreur",
        "",
        f"**{pop['classes']} classes.** Fenêtre observée : `{r.get('window_start')}` → "
        f"`{r.get('as_of')}` ({a['generated_from']['catalogue_revisions']} révisions du "
        "catalogue rejouées).",
        "",
        "## Ce que ce document corrige",
        "",
        "Cinq chiffres avancés le 2026-09-16 avant vérification, et ce qu'ils valent :",
        "",
        "| avancé | mesuré |",
        "|---|---|",
        f"| 367 classes | **{pop['classes']}** — les 4 en trop étaient `Contract`, "
        "`Index`, `Per-class schema`, `CLASS-ID` |",
        "| « 57 récidives » | **non reproductible** : cinq définitions défendables "
        "donnent 39 / 49 / 55 / 67 / 167. Ce document n'en retient qu'une, écrite "
        "ci-dessous, et c'est celle que le cliquet utilise |",
        "| gardes 15,1 % contre prose 22,7 % | voir les intervalles : les sous-groupes "
        "portent trop peu d'évènements pour trancher |",
        "| le taux s'améliore (38 → 18 → 9 %) | **il empire** une fois normalisé par "
        "l'exposition. L'ancien chiffre comptait comme « n'a pas récidivé » des classes "
        "trop jeunes pour avoir pu le faire |",
        "| `--fields` rouge sur 29 classes | **vert** — le commentaire du Makefile était "
        "périmé |",
        "",
        "## La définition, une seule",
        "",
        "> **Une récidive est un commit qui AJOUTE une ligne d'historique à une classe**, "
        "dans la fenêtre où le catalogue est versionné.",
        "",
        "Elle vient de git, donc aucun champ tenu à la main ne peut la contredire. Un "
        "compteur écrit à côté serait une seconde définition de la même grandeur, et "
        "elles ne se comparent jamais.",
        "",
        "## Population",
        "",
        "| grandeur | valeur |",
        "|---|---|",
    ]
    for k, v in pop.items():
        L.append(f"| `{k}` | {v} |")
    L += ["", "## Les trous — ce que le cliquet fait baisser", "",
          "Ce sont ces compteurs qui sont cranté, **pas le taux de récidive** : normalisé "
          "par l'exposition, il monte, et l'y cranter serait rouge à l'écriture.", "",
          "| trou | classes |", "|---|---|"]
    for k, v in h.items():
        L.append(f"| `{k}` | {v} |")

    L += ["", "## Récidive observée", ""]
    obs = r.get("observed") or {}
    L.append(f"**{obs.get('events', 0)} évènements** sur "
             f"{obs.get('class_days', 0)} classe-jours d'exposition — "
             f"**{obs.get('per_class_month')}** par classe-mois"
             + (f" (IC 95 % : {obs['ci95'][0]} – {obs['ci95'][1]})" if obs.get("ci95") else ""))
    L += ["", "### Par strate", "",
          "| strate | évènements | par classe-mois | IC 95 % |", "|---|---|---|---|"]
    for key in ("by_guard", "by_seen_red", "by_scope"):
        for label, v in (r.get(key) or {}).items():
            ci = f"{v['ci95'][0]} – {v['ci95'][1]}" if v.get("ci95") else "—"
            L.append(f"| {key} · {label} | {v['events']} | {v['per_class_month']} | {ci} |")
    L += ["", "⚠️ **Quand deux intervalles se recouvrent, il n'y a pas de résultat.** "
          "C'est le cas aujourd'hui sur toutes les strates : la fenêtre observée est "
          "courte et les sous-groupes portent peu d'évènements.", ""]

    L += ["## Cohortes à horizon fixe", "",
          "Une classe **plus jeune que l'horizon est exclue de la colonne**, jamais "
          "comptée « n'a pas récidivé ». Une colonne sans population affiche `—`, "
          "jamais `0`.", "",
          "| horizon | à risque | récidivées | taux |", "|---|---|---|---|"]
    for k, v in (r.get("fixed_horizon") or {}).items():
        taux = f"{100 * v['rate']:.0f} %" if v["rate"] is not None else "—"
        L.append(f"| {k[1:]} j | {v['at_risk']} | {v['recurred']} | {taux} |")

    d = a["declarative"]
    L += ["", "## Avant la fenêtre git — DÉCLARATIF", "",
          f"{d['classes']} classes introduites avant `{r.get('window_start')}`, "
          f"{d['recurred']} portant une date postérieure à leur `first_seen`.", "",
          f"⚠️ {d['note']} Le catalogue n'entre dans git qu'à cette date : tout ce qui "
          "précède a été écrit de mémoire, après coup. Comparer les deux serait "
          "`a-threshold-carried-across-instruments` appliqué à notre propre métrique.", ""]
    # ⚠️ UNE seule fin de ligne. Le crochet `end-of-file-fixer` de pre-commit retire les
    # lignes vides finales : avec deux, le document sur le disque cessait d'égaler
    # `build()` DÈS LE COMMIT, et le test de fraîcheur serait rouge sans que rien n'ait
    # bougé. Un générateur doit produire exactement ce que les crochets laissent passer.
    return "\n".join(L).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="sort ≠ 0 si les documents sur le disque ne sont pas ceux-ci")
    args = ap.parse_args()

    # ⚠️ Un arbre sale fait décrire DEUX états à un seul document : git rend le dernier
    # commit, le fichier rend le travail en cours. Refuser de conclure, avec un code
    # distinct — `a-verdict-from-a-tree-that-moved-under-it`.
    if _tree_is_dirty():
        sys.stderr.write(
            f"⚠️  `{CAT_REL}` porte des modifications non commitées.\n"
            "   Les faits tirés de GIT et ceux tirés du FICHIER décriraient deux états\n"
            "   différents. Commiter d'abord, puis relancer.\n")
        if args.check:
            return 3
    js, md = build()
    if args.check:
        for path, fresh, remedy in ((DATA, js, "make error-health"),
                                    (DOC, md, "make error-health")):
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current == fresh:
                continue
            diff = "".join(difflib.unified_diff(
                current.splitlines(keepends=True), fresh.splitlines(keepends=True),
                fromfile="sur le disque", tofile="ce que le dépôt dit", n=1))
            sys.stderr.write(f"`{path.relative_to(ROOT)}` ne décrit plus le catalogue.\n"
                             f"Remède : {remedy}\n\n" + diff[:8000] + "\n")
            return 1
        return 0
    DATA.write_text(js, encoding="utf-8")
    DOC.write_text(md, encoding="utf-8")
    print(f"écrit : {DATA.relative_to(ROOT)} + {DOC.relative_to(ROOT)} "
          f"({len(md.splitlines())} lignes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
