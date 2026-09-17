"""Aucune leçon REX ne vit hors du périmètre de son validateur.

Type: Test
Uses: yaml
Depends on: .claude/scripts/validate_rex.py, .claude/skills/
Persists in: nothing

Le défaut
---------
**60 entrées REX — les plus riches du dépôt — vivaient dans `.claude/skills/.migrated/`**,
hors du périmètre de `validate_rex.py`. `_SCAN_DIRS` porte `("skills", "*.md")`, un glob à
UN niveau qui n'atteint pas un sous-répertoire. Elles n'étaient ni validées, ni comptées,
ni lisibles par aucun outil.

Pire : le mécanisme de remplacement ÉTAIT annoncé. `validate_rex.py:160-172` écrit qu'une
skill range son histoire dans « a colocated `<name>.rex.md` archive, which `_iter_archives`
already validates ». Or `find .claude -name '*.rex.md'` rendait **vide**, et
`_iter_archives()` validait un ensemble **vide**. La promesse était écrite, l'implémentation
absente — et rien ne signalait l'écart.

Famille : `un-garde-qui-ne-garde-pas`. Un validateur qui parcourt zéro fichier sort 0.

Ce que ce garde couvre, et ce qu'il ne couvre pas
------------------------------------------------
Il compare l'ensemble des fichiers PORTANT un bloc `rex:` sous `.claude/` à l'ensemble de
ceux que le validateur VISITE. Tout écart est un REX invisible.

⚠️ Il ne vérifie pas que les entrées sont JUSTES — seulement qu'elles sont vues. Une leçon
fausse mais validée passe.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_CLAUDE = Path(__file__).resolve().parents[1] / ".claude"
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.S)


class _Unparseable(Exception):
    """Le frontmatter n'est pas du YAML — on ne sait pas s'il porte un `rex:`."""


def _carries_rex(path: Path) -> bool:
    """Ce fichier porte-t-il des leçons ? LÈVE si son frontmatter est illisible.

    ⚠️ La première version avalait `YAMLError` et rendait `False` — donc un
    frontmatter cassé se lisait comme « pas de REX », et le fichier sortait du
    périmètre en silence. C'est exactement ce qui est arrivé :
    `skills/response-protocol/SKILL.md` portait `ALL code:` non échappé dans sa
    `description`, son YAML était invalide, il portait UNE leçon, et ni
    `validate_rex.py` ni ce garde ne le signalaient.
    `une-erreur-avalée-devient-une-absence`, dans le garde des absences.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    m = _FRONTMATTER.match(text)
    if not m:
        return False
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise _Unparseable(f"{path}: {str(exc).splitlines()[0]}") from exc
    return isinstance(fm, dict) and bool(fm.get("rex"))


def test_no_frontmatter_is_unparseable() -> None:
    """Un frontmatter illisible sort du périmètre SANS que personne ne le sache."""
    broken = []
    for p in _CLAUDE.rglob("*.md"):
        if ".retired" in p.parts:
            continue
        try:
            _carries_rex(p)
        except _Unparseable as exc:
            broken.append(str(exc))
    assert not broken, (
        "frontmatter YAML invalide — ces fichiers sont invisibles à tout outil qui "
        "les parse strictement :\n  " + "\n  ".join(broken) + "\n\n"
        "`response-protocol/SKILL.md` a vécu ainsi : `ALL code:` non échappé dans sa "
        "`description`. Le harnais le tolérait, `validate_rex.py` le sautait en "
        "silence, et la leçon qu'il portait n'était comptée nulle part. "
        "Remède : guillemeter la valeur.")


def _visited() -> set[Path]:
    """Les fichiers que `validate_rex.py` parcourt réellement, d'après ses globs."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_vrex", _CLAUDE / "scripts" / "validate_rex.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen = set(mod._iter_files(_CLAUDE)) | set(mod._iter_archives(_CLAUDE))
    return {p.resolve() for p in seen}


def test_the_validator_visits_something() -> None:
    """Non-vacuité : un validateur qui ne parcourt rien sort 0 et ne prouve rien."""
    assert len(_visited()) > 20, (
        "`validate_rex.py` ne parcourt presque aucun fichier — ce test, et le "
        "validateur lui-même, ne démontrent plus rien")


def test_every_rex_bearing_markdown_is_visited() -> None:
    """Un fichier qui porte des leçons et que personne ne lit est un cimetière."""
    visited = _visited()
    orphans = sorted(
        str(p.relative_to(_CLAUDE.parent))
        for p in _CLAUDE.rglob("*.md")
        # `.retired/` est un cimetière DÉLIBÉRÉ : on y range ce qu'on a cessé
        # d'utiliser, et son histoire n'a plus d'outil à instruire. `.migrated/`
        # n'en était pas un — c'était une étape de migration qu'on a oubliée en
        # route, et 60 leçons vivantes y dormaient.
        if ".retired" not in p.parts
        and _carries_rex(p) and p.resolve() not in visited
    )
    assert not orphans, (
        "ces fichiers portent des entrées `rex:` que `validate_rex.py` ne visite "
        "jamais :\n  " + "\n  ".join(orphans) + "\n\n"
        "60 leçons ont vécu ainsi dans `.claude/skills/.migrated/` — ni validées, ni "
        "comptées, ni lues. `_SCAN_DIRS` globe à UN niveau ; un sous-répertoire y "
        "échappe. Remède : une archive `<nom>.rex.md` à plat dans le répertoire de "
        "l'outil, ce que `_iter_archives` visite déjà.")


def test_an_archive_is_not_an_injectable_tool() -> None:
    """Une `.rex.md` ne porte pas `keywords:` — sinon elle se lit comme un outil."""
    offenders = []
    for archive in _CLAUDE.rglob("*.rex.md"):
        m = _FRONTMATTER.match(archive.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        if isinstance(fm, dict) and "keywords" in fm:
            offenders.append(str(archive.relative_to(_CLAUDE.parent)))
    assert not offenders, (
        "ces archives portent `keywords:` : " + ", ".join(offenders) + ".\n"
        "`_iter_files` les exclut du dénominateur des outils — leur laisser des "
        "mots-clefs les fait ressembler à quelque chose d'injectable, qu'elles ne "
        "sont pas.")
