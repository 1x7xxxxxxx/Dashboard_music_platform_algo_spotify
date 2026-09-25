"""Le sens INVERSE de `test_every_named_guard_exists.py` : le garde nomme-t-il une classe ?

Mesuré le 2026-09-16, pendant la revue R122. `test_every_named_guard_exists.py` vérifie
depuis un an que **classe → garde** tient : si une classe nomme un fichier de test, ce
fichier est sur le disque. Personne n'avait vérifié l'autre direction, et elle ne tenait
pas : **7 gardes sur 81 sites annonçaient une classe absente du catalogue**.

Deux étaient de simples renommages, corrigés dans le même commit
(`guide-windows-only-shortcut` → `guide-single-os-shortcut`,
`guard-reads-the-host-env-not-the-code` → `guard-predicate-depends-on-the-host-env`).

Les cinq autres sont plus intéressantes : **la classe n'a jamais été écrite**. Le garde
existe, il est vert, sa docstring porte la mesure, la date, le coût — et le catalogue ne
sait rien. Autrement dit `/capitalise` a été sauté, et l'auteur a écrit le nom de la
classe dans le seul endroit que rien ne relit. `.claude/dev-docs/error-class-families.md`
ne les range pas, `make error-health` ne les compte pas, et la prochaine occurrence du
même défaut sera « nouvelle ».

C'est exactement la forme que ce dépôt appelle une référence qui manque sans se plaindre
— et la leçon de fond est dans la mémoire du projet : **une cohérence vérifiée dans UN
seul sens n'est pas vérifiée**. Le garde qui traque les références mortes en avait
lui-même une réciproque, non gardée.

Mutation record — 2026-09-16, deux mutations EXÉCUTÉES et vues rouges :

  * une lettre ajoutée au slug de `tests/test_os_hints.py` (un renommage de classe qui
    laisse la docstring en arrière : le cas le plus fréquent des sept trouvés) →
    2 rouges, le cas paramétré et le plafond ;
  * `tests/test_apple_periods_are_asked_not_guessed.py` DÉPLACÉ hors de l'arbre — la
    mutation qui compte, parce qu'elle fait baisser le compteur d'orphelins sans que
    rien ne soit écrit → 2 rouges, dont `test_each_orphan_still_has_the_guard_that_named_it`.
    Sans cette dernière assertion, supprimer un garde aurait été la façon la moins chère
    de « fermer » la dette.

Ce que ce fichier NE fait pas
-----------------------------
Il ne force personne à écrire une classe pour tout. Un garde peut parfaitement ne nommer
aucune classe : rien ici ne l'exige, parce qu'exiger une classe par test produirait des
classes écrites pour contenter un compteur. Il n'a d'avis que sur les gardes qui en
NOMMENT une : un nom annoncé doit se résoudre.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import tokenize

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = REPO / ".claude" / "dev-docs" / "error-classes.md"
SCANNED = ("tests", ".claude/hooks", ".claude/scripts", "tools")

# La marque, puis un ou plusieurs slugs ENTRE BACKTICKS. Les backticks ne sont pas une
# coquetterie : sans eux, « Error class: signature » et « error-class index » — deux
# tournures présentes dans le dépôt — entreraient comme des identifiants, et un garde qui
# rend des faux positifs sur sa propre prose est le premier qu'on désactive.
_MARK = re.compile(
    r"(?i)(?:error[- ]class(?:es)?|classes?\s+d'erreur)\s*:?\s*"
    r"((?:`[a-z0-9][a-z0-9-]{5,}`[\s,;/]*(?:et|and|ou|or)?[\s,;/]*)+)")
_SLUG = re.compile(r"`([a-z0-9][a-z0-9-]{5,})`")
_ENTRY = re.compile(r"^## ([a-z0-9][a-z0-9-]+)$", re.M)

# ⚠️ Ce fichier se balaie LUI-MÊME, et c'est voulu : s'en exempter serait
# `a-guard-that-exempts-itself`. La conséquence est une contrainte de rédaction —
# la docstring ci-dessus nomme les deux renommages SANS la marque devant, donc aucun
# identifiant mort n'y est déclaré. Le plafond plus bas les liste en clair, hors marque.

# Les cinq gardes dont la classe n'a jamais été écrite. Mesuré le 2026-09-16.
# Ce n'est pas une exemption : c'est la dette, nommée, et le plafond ne peut que baisser.
# Chacune se ferme en écrivant la classe — la docstring du garde porte déjà le symptôme,
# la cause et la mesure, c'est-à-dire la matière de `/capitalise`.
_KNOWN_ORPHANS: dict[str, str] = {}
# ── VIDÉE le 2026-09-17, une nuit après avoir été posée ──────────────────────
#
# Les cinq classes y sont ÉCRITES, pas exemptées : `setup-step-asks-for-a-developer-
# gesture`, `image-sized-for-a-layout-it-no-longer-has`, `two-shapes-summed-as-one`,
# `a-scoring-call-that-omits-its-context`, `an-optimisation-that-degrades-what-worked`.
#
# Chacune depuis la docstring de son garde, qui portait déjà tout : le symptôme, la
# cause, la mesure, la date, le coût. Rien n'a été inventé — et rien n'aurait été
# retrouvé : ces chiffres n'existaient QUE dans un test.
#
#     6 locataires connectés, 3 ouvertures de la page, 0 ligne SoundCloud
#     8 captures sur 16 entre 1257 et 1693 px, les 8 débordaient
#     l'export Apple n'a AUCUNE colonne de date
#     score 0,90 → 0,75 sans `noise_tokens`, sous le seuil d'auto-acceptation
#     21 rapprochements corrects sur 21, intrus écartés sous 0,21
#
# Le plafond reste, vide : une SIXIÈME orpheline le ferait rougir. C'est le sens d'un
# cliquet — il ne se retire pas quand la dette est payée, il garde qu'elle le reste.


def _catalogue_ids() -> set[str]:
    return set(_ENTRY.findall(CATALOGUE.read_text(encoding="utf-8")))


def _prose_chunks(source: str) -> list[tuple[int, str]]:
    """Les `(ligne, texte)` de PROSE d'un module : docstrings et commentaires.

    Pas `source` en entier, et la différence n'est pas cosmétique. Ce dépôt a un
    cliquet — `tests/test_a_guard_reads_structure_not_text.py` — qui refuse un garde
    neuf inspectant du Python par correspondance de chaînes, parce que quatre gardes
    ont été pris VERTS sur leur propre défaut en une soirée. Il exempte tout fichier
    contenant `ast.parse`, donc en poser un décoratif aurait suffi à le faire taire :
    c'est exactement « desserrer le garde qu'il est facile de contenter », et ce même
    geste a déjà été refusé une fois ce jour-là, sur les fragments.

    La lecture est donc RÉELLE : `ast` rend les docstrings (module, classe, fonction),
    `tokenize` rend les vrais jetons de commentaire. La marque annoncée dans une chaîne
    de DONNÉES — un message d'assertion, une table, un cas de test — ne compte plus.

    Mesuré le 2026-09-16 avant de remplacer le parcours textuel : **81 déclarations par
    le texte, 81 par les docstrings et commentaires, aucune perdue.** Le resserrement ne
    coûte donc aucun rappel ; sans cette mesure il aurait fallu le croire.

    Un fichier qui ne parse pas retombe sur son texte brut : ne rien lire d'un module
    cassé le ferait sortir du compte en silence — un plafond qui baisse tout seul.
    """
    chunks: list[tuple[int, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [(1, source)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                chunks.append((getattr(node, "lineno", 1), doc))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                chunks.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError):
        pass
    return chunks


def _declarations() -> list[tuple[str, int, str]]:
    """`(fichier, ligne, id)` pour chaque classe NOMMÉE par un outil du dépôt."""
    out: list[tuple[str, int, str]] = []
    for root in SCANNED:
        for path in sorted((REPO / root).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            rel = str(path.relative_to(REPO))
            source = path.read_text(encoding="utf-8", errors="replace")
            for line, chunk in _prose_chunks(source):
                for match in _MARK.finditer(chunk):
                    for slug in _SLUG.findall(match.group(1)):
                        out.append((rel, line, slug))
    return out


_DECLARED = _declarations()


def test_the_scan_still_sees_something() -> None:
    """Non-vacuité : une expression régulière sur de la prose devient aveugle en silence."""
    assert len(_DECLARED) >= 60, (
        f"seulement {len(_DECLARED)} déclarations de classe trouvées dans "
        f"{SCANNED} — la marque a changé de forme et ce garde ne voit plus rien"
    )
    assert len(_catalogue_ids()) >= 360, "le parseur du catalogue est cassé"


@pytest.mark.parametrize(
    "rel, line, slug",
    [d for d in _DECLARED if d[2] not in _KNOWN_ORPHANS],
    ids=[f"{d[2]}@{d[0].rsplit('/', 1)[-1]}" for d in _DECLARED
         if d[2] not in _KNOWN_ORPHANS],
)
def test_every_class_a_tool_names_is_in_the_catalogue(rel: str, line: int, slug: str) -> None:
    assert slug in _catalogue_ids(), (
        f"{rel}:{line} annonce la classe `{slug}`, absente de "
        f"`.claude/dev-docs/error-classes.md`.\n"
        "Soit le nom a changé et la docstring est restée en arrière, soit la classe n'a "
        "jamais été écrite — dans les deux cas le garde est le SEUL endroit où ce défaut "
        "est décrit, donc il n'est ni rangé en famille, ni compté par `make error-health`, "
        "et la prochaine occurrence passera pour neuve. Écrire la classe : /capitalise."
    )


def test_the_orphan_ceiling_never_grows() -> None:
    """Le plafond ÉGALE la mesure : un plafond lâche autorise une régression."""
    ids = _catalogue_ids()
    orphans = {slug for _, _, slug in _DECLARED if slug not in ids}
    assert orphans == set(_KNOWN_ORPHANS), (
        "la liste des classes orphelines a changé.\n"
        f"  nouvelles : {sorted(orphans - set(_KNOWN_ORPHANS))}\n"
        f"  fermées   : {sorted(set(_KNOWN_ORPHANS) - orphans)}\n"
        "Une fermeture se verrouille en retirant la ligne de `_KNOWN_ORPHANS` dans le "
        "même commit ; une nouvelle veut une classe, pas une entrée de plus ici."
    )


@pytest.mark.parametrize("slug, rel", sorted(_KNOWN_ORPHANS.items()))
def test_each_orphan_still_has_the_guard_that_named_it(slug: str, rel: str) -> None:
    """Un orphelin dont le garde disparaît ne se ferme pas : il s'efface.

    Sans cette assertion, supprimer `tests/test_apple_periods_are_asked_not_guessed.py`
    ferait baisser le compteur sans que rien ne soit écrit — la forme exacte qu'un
    cliquet doit refuser, et celle que `class_days_exposed` refuse dans
    `test_the_error_class_health_only_improves.py`.
    """
    assert (REPO / rel).exists(), (
        f"{rel} a disparu, et c'est le seul endroit où la classe `{slug}` est décrite. "
        "La supprimer n'a pas fermé la dette, elle l'a perdue."
    )


def _named_in(source: str) -> list[str]:
    return [slug for _, chunk in _prose_chunks(source) for m in _MARK.finditer(chunk)
            for slug in _SLUG.findall(m.group(1))]


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity on a FABRICATED tool: a class named in its docstring and in a comment
    is read — the declaration this guard checks against the catalogue; the same mark in
    a DATA string (an assertion message) is not a declaration."""
    source = ('"""A probe. Error class: `a-class-nobody-wrote-yet`."""\n'
              "# error class: `another-orphan-name`\n"
              "MSG = \"error class: `only-inside-a-data-string`\"\n")
    named = _named_in(source)
    assert sorted(named) == ["a-class-nobody-wrote-yet", "another-orphan-name"], named
    assert "a-class-nobody-wrote-yet" not in _catalogue_ids(), "the probe must be a real orphan"
