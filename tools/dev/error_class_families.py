#!/usr/bin/env python3
"""Regrouper les 287 classes d'erreur en familles, sans toucher à une seule entrée.

Type: Utility
Uses: re — rien d'autre. Pas de base, pas d'import de `src/`.
Triggers: `make error-families`, CI step 8
Depends on: .claude/dev-docs/error-classes.md
Persists in: .claude/dev-docs/error-class-families.md

Why this exists
---------------
287 classes, zéro famille. À ce volume le catalogue cesse d'être consultable : on
n'y cherche plus « ai-je déjà vu cette forme ? », on y cherche un nom qu'on a en
tête. Un défaut de la même famille se re-découvre donc de zéro — c'est arrivé le
2026-09-12 avec `two-generations-of-rows-in-one-fact-table`, dont la leçon était
écrite depuis des semaines dans un commentaire et dans une classe voisine.

Une famille n'est PAS un mot-clef
---------------------------------
Chaque famille porte une **question** — celle qu'on se pose devant du code, pas
celle qui décrit le bug après coup. C'est la question qui a de la valeur : elle se
pose avant que le défaut existe. Le classement se fait par une règle explicite,
écrite à côté de la famille, et **la règle est publiée dans le document** pour
qu'un lecteur puisse contester un rattachement sans lire ce script.

Ce que ce document ne fait pas
-------------------------------
Il ne modifie aucune des 287 entrées. Pas de champ `family:`, pas de
réécriture — le catalogue est append-only et le restera. Si cette taxonomie tient
six semaines, la question d'un champ se posera ; pas avant.

Une classe qui ne tombe dans aucune famille est **listée et comptée**, et ce
compte est un cliquet : il ne peut que baisser. Une taxonomie qui laisse un tiers
du catalogue dehors décrit une opinion, pas le catalogue.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".claude" / "dev-docs" / "error-classes.md"
DOC = ROOT / ".claude" / "dev-docs" / "error-class-families.md"

# (slug, la QUESTION qu'on se pose devant le code, motif sur l'id + le symptôme)
#
# L'ORDRE COMPTE : une classe rejoint la PREMIÈRE famille qui la retient, et les
# familles les plus spécifiques viennent d'abord. Sans ça « deux surfaces, deux
# nombres » avalerait la moitié du catalogue.
FAMILIES: list[tuple[str, str, str]] = [
    ("le-locataire",
     "Cette lecture, cette écriture, cette jointure nomment-elles leur locataire — "
     "toutes, et pas seulement la première ?",
     # ⚠️ PAS le mot « locataire » nu. C'est le mot que ce dépôt emploie pour dire
     # « client », et il apparaît dans la moitié des symptômes — la famille en
     # capturait 37 et volait leurs membres aux suivantes. Le cas qui l'a montré :
     # `two-definitions-that-must-coincide-are-never-compared` atterrissait ici
     # parce que son symptôme dit « pour le même locataire », alors que son sujet
     # est deux définitions qui divergent.
     #
     # On garde donc les formes qui parlent VRAIMENT de tenance : un identifiant,
     # ou une tournure où le locataire est le sujet du défaut.
     r"tenant|artist[_-]id|saas_artist|multitenant|fleet|canary|sandbox|"
     r"deux locataires|par locataire|du locataire|son locataire|le locataire|"
     r"d'un locataire|leur locataire|chaque locataire|un locataire|"
     r"locataires? multi|aux locataires"),

    ("un-cumul-pris-pour-un-quotidien",
     "Cette colonne est-elle une quantité du jour ou un compteur qui ne redescend "
     "pas ? Et si c'est un compteur, la fenêtre est-elle `niveau(fin) − niveau(début)` ?",
     r"cumulative|counter|compteur|delta|lifetime|two-generations|snapshot"),

    ("un-travail-qui-n-arrive-nulle-part",
     "Ce résultat atteint-il quelqu'un ? Ce code est-il appelé par quelque chose "
     "qu'un humain peut déclencher ?",
     r"never-sent|not-alerted|never-read|nothing-happens|nothing-routes|"
     r"nobody-call|never-hit|not-when-it-is-needed|nobody-writes|"
     r"rebuilt-per-rerun|unwired|debranch|not-reached|orphan"),

    ("un-nombre-affirmé-qui-n-a-pas-été-mesuré",
     "Ce chiffre a-t-il été mesuré, ou construit ? Le lecteur peut-il distinguer "
     "« zéro » de « on ne sait pas » ?",
     r"unmeasured|claimed-not-measured|outranks-the-measurement|nan-written|"
     r"rendered-as-health|sums-the-display|discarded-in-silence|"
     r"erases-every-other|past-the-end-of-its-evidence|renders-nothing|"
     r"named-like-a-final-one|imput|estimat"),

    ("le-message-parle-au-mauvais-lecteur",
     "Cette phrase s'adresse-t-elle à qui la lira — et nomme-t-elle un geste que "
     "ce lecteur-là peut faire ?",
     r"assumes-a-shell|assumes-visibility|by-direction-not-by-name|"
     r"wrong-advice|blames-the-most-common|names-an-action|"
     r"flattened-for-the-narrowest|without-naming-the-reason|leaves-no-trace|"
     # `becomes-the-word-` est entré le 2026-09-12 : `title=None` fait écrire
     # « undefined » en toutes lettres au-dessus de la figure. Un mot de moteur de
     # rendu montré à un artiste est exactement la question de cette famille — à
     # qui cette phrase s'adresse-t-elle, et nomme-t-elle un geste ? — même si
     # personne ne l'a écrite volontairement.
     r"announces-a-field|instruction-|-instruction|speaks-its-own-plumbing|"
     r"addressed-to|reader|becomes-the-word-|undefined"),

    ("un-état-qui-déborde-de-sa-portée",
     "Cet état vit-il exactement le temps de ce qui l'a créé — ni plus, ni pour "
     "quelqu'un d'autre ?",
     r"outlives-the-visit|written-after-instantiation|per-worker|"
     r"namespaced-by-another|connection|closes-a-connection|"
     r"only-inside-a-session|loses-the-race|first-row|session|cache|"
     r"state-file|leak"),

    ("deux-surfaces-deux-nombres",
     "Ce nombre a-t-il une seule définition, ou chaque surface refait-elle le calcul ?",
     r"metric-computed-outside|outside-the-metrics|two-|divergen|recopi|restated|"
     r"duplicat|escapes-every-sql-guard|drift|desync|hand-synced"),

    ("une-erreur-avalée-devient-une-absence",
     "Ce `except` distingue-t-il « rien à lire » de « on n'a pas pu lire » — et "
     "l'utilisateur voit-il la différence ?",
     r"silent|swallow|avalée|absence|silencieu|renders?-as-a-measurement|"
     r"empty-bracket|no-op|returns-none|degrade|logged-as-success|"
     # `read-that-failed`, ajouté le 2026-09-12 : la classe atterrissait dans
     # « une configuration qui diverge de la prod » à cause du mot `prod` dans son
     # symptôme. Un motif qui ne nomme pas la forme la laisse au premier venu.
     r"outside-its-condition|read-that-failed|failed-read|except.*number"),

    ("un-garde-qui-ne-garde-pas",
     "Ce garde a-t-il déjà été VU rouge sur le défaut qu'il vise — et sa portée "
     "contient-elle ce défaut ?",
     r"guard|cliquet|ratchet|signature|probe|predicate|vacuous|mutation|"
     r"test-|suite|assert|blind"),

    ("un-document-qui-affirme-un-état-périmé",
     "Ce qui est écrit là est-il régénéré, ou recopié une fois puis oublié ?",
     r"stale|périmé|obsolete|doc|readme|roadmap|comment|caption|note|prose|"
     r"generated|index|diagram|map|guide|runbook|lags-its-source|"
     r"hand-written-list"),

    ("un-contrôle-qui-ne-peut-jamais-passer",
     "Où ce contrôle s'exécute-t-il — la machine où il tourne a-t-elle ce qu'il "
     "lui faut pour réussir un jour ?",
     r"never-pass|env-independent|host-env|container|reachab|unreachable|"
     r"not-wired|orphan|dead-code|no-caller|unrun|install|"
     r"shares-the-fate|unstated-import-path|below-detection"),

    ("un-coût-payé-sans-contrepartie",
     "Ce travail est-il payé par quelqu'un — temps de CI, premier écran, attention "
     "du lecteur — et lui rend-il quelque chose ?",
     # `drags-a-view-behind-it` est entré le 2026-09-12 : un module partagé qui
     # importe une vue fait payer un chargement de page entière à tous ses
     # appelants pour ce qu'un seul y lit. C'est exactement la question de la
     # famille — qui paie, et pour quoi — et le motif ne la voyait pas parce qu'il
     # ne nommait que des coûts de CI. Un coût de PREMIER ÉCRAN est le même sujet.
     r"runs-twice|concurrency-group|overload|competing-for-one-decision|"
     r"costs-more-than|waste|duplicate-run|too-many|drags-a-.*-behind|"
     r"paid-by|first-render"),

    ("un-seuil-écrit-d-instinct",
     "Ce seuil vient-il de la distribution réelle, ou d'une intuition ? Le test "
     "épingle-t-il la réalité ou la constante ?",
     r"threshold|seuil|min[_-]|floor|ceiling|limit|budget|quota|window|"
     r"magic-number|hardcoded"),

    ("une-écriture-qui-écrase",
     "Cette écriture peut-elle détruire ce qu'un autre vient d'écrire — et le "
     "saurait-on ?",
     r"overwrit|écrase|clobber|upsert|conflict|restore|delete|drop|purge|"
     r"lost|data-loss|resurrect|rotation"),

    ("le-temps-et-l-horloge",
     "Cette date est-elle celle de l'événement ou celle de la collecte ? Et dans "
     "quel fuseau ?",
     r"date|time|clock|tz|utc|timezone|fresh|schedule|cron|window-applied|"
     r"day|month|period"),

    ("la-frontière-avec-le-dehors",
     "Ce que ce code envoie dehors — un mail, une requête, un paiement, un "
     "secret — est-il ce qu'on croit, et vers qui ?",
     r"secret|token|credential|auth|jwt|mail|smtp|http|webhook|stripe|payment|"
     r"url|cors|redact|external|api-|fstring-identifier|string-substitution|"
     r"untrusted|privileged|access-gate|is-not-an-identity|"
     r"rendered-to-the-visitor|bare-except|containment"),

    ("une-configuration-qui-diverge-de-la-prod",
     "Ce que le dépôt déclare est-il ce que la production exécute ?",
     r"prod|deploy|schema-drift|migration|image|docker|compose|pin|lock|"
     r"requirements|manifest|ddl|init_db|version"),
]

_ID = re.compile(r"^## ([a-z0-9][a-z0-9-]+)$", re.M)


def _entries() -> list[tuple[str, str]]:
    """(class-id, texte de l'entrée) dans l'ordre du catalogue."""
    text = SOURCE.read_text(encoding="utf-8")
    marks = [(m.group(1), m.start(), m.end()) for m in _ID.finditer(text)]
    out = []
    for i, (cid, _, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out.append((cid, text[end:stop]))
    return out


def _cell(text: str) -> str:
    """Un symptôme rendu sûr pour une cellule de tableau Markdown.

    Écrit hors f-string : ruff cible Python 3.11 ici, où un backslash dans une
    f-string est une erreur de syntaxe.
    """
    return text[:150].replace("|", "\\|")


def _one_line(body: str, field: str) -> str:
    m = re.search(rf"^- {field}: (.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def classify() -> tuple[dict[str, list[tuple[str, str]]], list[tuple[str, str]]]:
    buckets: dict[str, list[tuple[str, str]]] = {slug: [] for slug, _, _ in FAMILIES}
    orphans: list[tuple[str, str]] = []
    for cid, body in _entries():
        # Le SYMPTÔME entre dans le texte classé, pas la cause : la cause nomme
        # des fichiers, et un chemin ferait tomber toute une famille dans une
        # autre le jour d'un renommage.
        hay = f"{cid} {_one_line(body, 'symptom')}".lower()
        for slug, _, pattern in FAMILIES:
            if re.search(pattern, hay):
                buckets[slug].append((cid, _one_line(body, "symptom")))
                break
        else:
            orphans.append((cid, _one_line(body, "symptom")))
    return buckets, orphans


def render() -> str:
    buckets, orphans = classify()
    total = sum(len(v) for v in buckets.values()) + len(orphans)
    lines = [
        "# Familles de classes d'erreur",
        "",
        "<!-- GÉNÉRÉ par `tools/dev/error_class_families.py` — toute édition à la "
        "main est perdue à la prochaine exécution. `make error-families` -->",
        "",
        f"**{total} classes**, regroupées en **{len(FAMILIES)} familles** par une règle "
        "explicite, écrite sous chaque titre. Aucune entrée de "
        "`.claude/dev-docs/error-classes.md` n'est modifiée : le catalogue est "
        "append-only, cette taxonomie vit à côté.",
        "",
        "Une famille porte une **question**, pas un mot-clef. La question est ce qui "
        "a de la valeur : elle se pose devant du code, avant que le défaut existe. "
        "Une classe rejoint la **première** famille qui la retient — l'ordre va du "
        "plus spécifique au plus général, sinon « deux surfaces, deux nombres » "
        "avalerait la moitié du catalogue.",
        "",
        "Le rattachement est mécanique et donc parfois discutable. La règle est "
        "publiée pour qu'on puisse le contester sans lire le script : si une classe "
        "est mal rangée, c'est le motif qu'on corrige, jamais l'entrée.",
        "",
        "| famille | classes | la question |",
        "|---|---|---|",
    ]
    for slug, question, _ in FAMILIES:
        lines.append(f"| [{slug}](#{slug}) | {len(buckets[slug])} | {question} |")
    lines += [f"| _sans famille_ | {len(orphans)} | — |", ""]

    for slug, question, pattern in FAMILIES:
        members = buckets[slug]
        lines += [
            f"## {slug}", "",
            f"**{question}**", "",
            f"Règle de rattachement : `{pattern}` sur l'identifiant et le symptôme. "
            f"{len(members)} classe(s).", "",
        ]
        if members:
            lines += ["| classe | symptôme |", "|---|---|"]
            lines += [f"| [`{c}`](error-classes.md#{c}) | {_cell(sym)} |"
                      for c, sym in members]
        else:
            lines.append("_Aucune classe. Une famille vide est un motif trop étroit, "
                         "pas une absence de défauts._")
        lines.append("")

    lines += [
        "## Sans famille", "",
        "Ces classes ne tombent dans aucun motif. **Ce compte est un cliquet : il ne "
        "peut que baisser.** Une taxonomie qui laisse un tiers du catalogue dehors "
        "décrit une opinion, pas le catalogue — et chaque classe qu'on range est une "
        "question qu'on a su formuler.", "",
    ]
    if orphans:
        lines += ["| classe | symptôme |", "|---|---|"]
        lines += [f"| [`{c}`](error-classes.md#{c}) | {_cell(sym)} |"
                  for c, sym in orphans]
    else:
        lines.append("_Aucune._")
    lines += [
        "",
        "## Les chiffres gelés", "",
        f"<!-- error-class-families: total={total} families={len(FAMILIES)} "
        f"orphans={len(orphans)} -->",
        "",
    ]
    body = "\n".join(lines).rstrip("\n") + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body + f"\n<!-- error-class-families: sha256={digest} -->\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = render()
    if args.check:
        current = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
        if current == fresh:
            return 0
        diff = "".join(difflib.unified_diff(
            current.splitlines(keepends=True), fresh.splitlines(keepends=True),
            fromfile="sur le disque", tofile="ce que le catalogue dit", n=1))
        sys.stderr.write("`.claude/dev-docs/error-class-families.md` est périmé.\n"
                         "Remède : make error-families\n\n" + diff[:4000] + "\n")
        return 1
    DOC.write_text(fresh, encoding="utf-8")
    print(f"écrit : {DOC.relative_to(ROOT)} ({len(fresh.splitlines())} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
