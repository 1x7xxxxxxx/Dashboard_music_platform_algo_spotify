"""Un message de commit ne se donne pas par l'entrée standard.

Type: Test
Uses: pytest
Depends on: .claude/, tools/, scripts/
Persists in: nothing

Le défaut, mesuré le 2026-09-13
--------------------------------
`git commit -F -` alimenté par un heredoc n'a **jamais reçu son message** : la
couche qui exécute les commandes du shell a mangé l'entrée standard. Le commit a
été abandonné, son message d'abandon avalé, et le `git push` qui suivait a rendu
`ok` en poussant une branche inchangée. **24 fichiers sont restés non commités
pendant que le rapport annonçait le contraire.**

C'est la moitié MÉCANISABLE de la classe
`a-verification-read-through-a-filtering-wrapper`. L'autre moitié — une commande
de vérification dont la sortie est reformatée — vit dans le comportement de
l'agent et n'a pas de site dans le dépôt ; elle reste `manual`.

La parade
---------
Un message de commit passe par un **fichier** (`-F <chemin>`) ou par `-m`. Les
deux formes sont observables et rejouables ; l'entrée standard ne l'est pas, et
son échec est SILENCIEUX.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# `git commit … -F -` ou `--file -` : le tiret seul veut dire « lis stdin ».
_STDIN_MSG = re.compile(r"git\s+commit\b[^\n]*?(?:-F|--file)\s+-(?:\s|$|\"|')")

_ROOTS = (".claude", "tools", "scripts", ".github")
_SUFFIXES = {".py", ".sh", ".yml", ".yaml"}


def _sites() -> list[str]:
    hits = []
    for root in _ROOTS:
        base = REPO / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in _SUFFIXES or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                # La PROSE qui décrit le défaut ne doit pas déclencher le garde :
                # ce dépôt s'est fait prendre trois fois le 2026-09-04 par un garde
                # rouge sur le commentaire de son propre correctif.
                stripped = line.lstrip()
                if stripped.startswith(("#", "--", "//", "*")):
                    continue
                if _STDIN_MSG.search(line):
                    hits.append(f"{path.relative_to(REPO)}:{i}")
    return hits


def test_no_automation_feeds_a_commit_message_through_stdin() -> None:
    hits = _sites()
    assert not hits, (
        "message de commit lu sur l'entrée standard : " + ", ".join(hits)
        + "\nSi le shell qui exécute la commande reformate ou avale stdin, le "
        "message arrive VIDE, `git commit` abandonne, et le `git push` suivant "
        "rend `ok` en poussant une branche inchangée. Mesuré le 2026-09-13 : "
        "24 fichiers non commités pendant que le rapport disait l'inverse. "
        "Passer par `-F <fichier>` ou `-m`.")


def test_the_predicate_sees_the_form_it_forbids() -> None:
    """Un prédicat qu'on n'a jamais vu reconnaître son motif ne garde rien."""
    assert _STDIN_MSG.search('git commit -F - <<"MSG"')
    assert _STDIN_MSG.search("git commit --file - ")
    # Et il ne doit PAS mordre sur la forme correcte.
    assert not _STDIN_MSG.search("git commit -F /tmp/msg.txt")
    assert not _STDIN_MSG.search('git commit -m "un message"')


def test_the_scan_reaches_a_real_corpus() -> None:
    """Le balayage lit-il encore quelque chose ? Un garde sur zéro fichier est vert."""
    seen = sum(1 for root in _ROOTS
               for p in (REPO / root).rglob("*")
               if (REPO / root).exists() and p.suffix in _SUFFIXES and p.is_file())
    assert seen >= 50, (
        f"seulement {seen} fichier(s) balayé(s) : la portée ne lit plus "
        "l'automatisation du dépôt, et l'assertion négative ci-dessus est verte "
        "sur du vide.")
