"""Un message de commit ne se donne pas par l'entrée standard.

Type: Test
Uses: pytest, ast, shlex
Depends on: .claude/, tools/, scripts/, .github/
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

Pourquoi ce garde PARSE au lieu de chercher une chaîne
------------------------------------------------------
Sa première version cherchait `git\\s+commit.*-F\\s+-` par expression régulière
sur des lignes de texte, et `test_a_guard_reads_structure_not_text` l'a refusée
le jour même. Elle avait raison deux fois :

  * elle voyait le geste dans un COMMENTAIRE ou un docstring qui le décrit —
    exactement ce que ce fichier-ci fait quatre lignes plus haut ;
  * et elle ratait `--file=-`, un `git` préfixé d'une affectation d'environnement,
    ou une commande construite autrement.

La question structurelle est : dans un segment de shell, `git` est-il la
**commande** (jamais un mot dans un argument), et `-F -` / `--file -` /
`--file=-` sont-ils parmi ses arguments ? Le Python est lu par `ast`, et seules
les chaînes littérales sont examinées — un docstring n'en est pas une ici, il est
retiré explicitement.

La parade
---------
Un message de commit passe par un **fichier** (`-F <chemin>`) ou par `-m`. Les
deux formes sont observables et rejouables ; l'entrée standard ne l'est pas, et
son échec est SILENCIEUX.
"""
from __future__ import annotations

import ast
import shlex
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_ROOTS = (".claude", "tools", "scripts", ".github")
_PY = ".py"
_SHELLISH = (".sh", ".yml", ".yaml")

_SEPARATEURS = {";", "&&", "||", "|", "&", "\n", "(", ")"}


def _segments(commande: str) -> list[list[str]]:
    """Découpe une ligne de shell en segments, chacun rendu comme ses jetons."""
    lex = shlex.shlex(commande, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    segments: list[list[str]] = []
    courant: list[str] = []
    try:
        for jeton in lex:
            if jeton in _SEPARATEURS or (jeton and set(jeton) <= {";", "&", "|"}):
                if courant:
                    segments.append(courant)
                    courant = []
            else:
                courant.append(jeton)
    except ValueError:
        # Guillemet non fermé : ce n'est pas une commande de shell valide.
        return segments
    if courant:
        segments.append(courant)
    return segments


def _lit_stdin(jetons: list[str]) -> bool:
    """`git` est-il la COMMANDE de ce segment, avec un message lu sur stdin ?"""
    i = 0
    # Les affectations d'environnement qui precedent la commande (`GIT_DIR=… git …`).
    while i < len(jetons) and "=" in jetons[i] and not jetons[i].startswith("-"):
        i += 1
    if i >= len(jetons) or Path(jetons[i]).name not in {"git", "git.exe"}:
        return False
    args = jetons[i + 1:]
    if "commit" not in args:
        return False
    for j, a in enumerate(args):
        if a == "--file=-":
            return True
        if a in {"-F", "--file"} and j + 1 < len(args) and args[j + 1] == "-":
            return True
    return False


def _chaines_python(source: str) -> list[str]:
    """Les chaînes littérales d'un module, docstrings EXCLUS."""
    arbre = ast.parse(source)
    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef,
                              ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = getattr(noeud, "body", None)
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [n.value for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def _fichiers() -> list[Path]:
    vus: list[Path] = []
    for racine in _ROOTS:
        base = REPO / racine
        if not base.exists():
            continue
        for chemin in sorted(base.rglob("*")):
            if chemin.is_file() and chemin.suffix in (_PY, *_SHELLISH):
                vus.append(chemin)
    return vus


def _sites() -> list[str]:
    trouves = []
    for chemin in _fichiers():
        try:
            texte = chemin.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if chemin.suffix == _PY:
            try:
                commandes = _chaines_python(texte)
            except SyntaxError:
                continue
        else:
            commandes = texte.splitlines()
        for commande in commandes:
            if "git" not in commande:
                continue
            for segment in _segments(commande):
                if _lit_stdin(segment):
                    trouves.append(str(chemin.relative_to(REPO)))
                    break
    return sorted(set(trouves))


def test_no_automation_feeds_a_commit_message_through_stdin() -> None:
    sites = _sites()
    assert not sites, (
        "message de commit lu sur l'entrée standard : " + ", ".join(sites)
        + "\nSi le shell qui exécute la commande reformate ou avale stdin, le "
        "message arrive VIDE, `git commit` abandonne, et le `git push` suivant "
        "rend `ok` en poussant une branche inchangée. Mesuré le 2026-09-13 : "
        "24 fichiers non commités pendant que le rapport disait l'inverse. "
        "Passer par `-F <fichier>` ou `-m`.")


def test_the_predicate_sees_the_forms_it_forbids() -> None:
    """Un prédicat qu'on n'a jamais vu reconnaître son motif ne garde rien."""
    for interdit in ('git commit -F - ',
                     'git commit --file - ',
                     'git commit --file=- ',
                     '/usr/bin/git commit -F -',
                     'GIT_AUTHOR_NAME=x git commit -F -',
                     'cd /tmp && git commit -F -'):
        assert any(_lit_stdin(s) for s in _segments(interdit)), interdit


def test_the_predicate_does_not_bite_the_correct_forms() -> None:
    """Et il ne mord pas sur ce qui est licite -- ni sur la prose qui en parle."""
    for permis in ('git commit -F /tmp/msg.txt',
                   'git commit -m "un message"',
                   'git log --format=- ',
                   'echo "git commit -F -"',          # une CHAINE, pas la commande
                   'grep "git commit -F -" fichier'):  # le geste en ARGUMENT
        assert not any(_lit_stdin(s) for s in _segments(permis)), permis


def test_a_docstring_describing_the_gesture_is_not_a_site() -> None:
    """Ce fichier decrit le geste interdit : le lire par le TEXTE le rendrait rouge."""
    module = '"""On interdit git commit -F - ici."""\nx = 1\n'
    assert _chaines_python(module) == []


def test_the_scan_reaches_a_real_corpus() -> None:
    """Le balayage lit-il encore quelque chose ? Un garde sur zéro fichier est vert."""
    vus = len(_fichiers())
    assert vus >= 50, (
        f"seulement {vus} fichier(s) balayé(s) : la portée ne lit plus "
        "l'automatisation du dépôt, et l'assertion négative ci-dessus est verte "
        "sur du vide.")
