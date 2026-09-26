"""Une chaîne qui DÉCRIT un geste ne doit pas l'exécuter.

Type: Test
Uses: re
Depends on: tools/**/*.sh, .claude/**/*.sh, Makefile
Persists in: nothing

En Bash, l'accent grave est une SUBSTITUTION DE COMMANDE — y compris à l'intérieur d'une
chaîne entre guillemets doubles. Or ce dépôt écrit sa prose en français et y cite des
commandes en continu, avec la convention Markdown : l'accent grave cite du code.

Les deux conventions se rencontrent dans un `echo`, et le shell gagne.

Mesuré le 2026-09-18, vécu et non simulé : un `echo` de description contenant une
commande entre accents graves l'a RÉELLEMENT exécutée. Elle a désinstallé 22 paquets de
développement (pytest, ruff, pre-commit, detect-secrets, pytest-xdist…), et les quatre
commandes suivantes ont rendu « No module named pytest » — ce qui ressemblait à un dépôt
cassé et n'était qu'un environnement vidé.

Ce qu'il couvre, et ce qu'il NE PEUT PAS couvrir
-------------------------------------------------
Il lit les scripts VERSIONNÉS du dépôt. L'incident, lui, a eu lieu dans une commande
ÉPHÉMÈRE — une ligne tapée dans un terminal, qui n'existe dans aucun fichier. **Aucun
test ne peut l'atteindre**, et c'est la raison pour laquelle la classe reste `reported`
plutôt que `guarded` : ce garde protège le dépôt, pas la séance.

Le dire est le point. Un garde qui laisserait croire que la classe est couverte serait
pire que pas de garde, parce qu'il ferait cesser de faire attention là où l'attention
est la seule protection.

Mutation record — 2026-09-18 : en ajoutant `echo "voir `pwd` pour le chemin"` dans un
script de `tools/`, ce garde le nomme ; retiré, il passe.

---
rex: []
---
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCANNED = ("tools", ".claude", "deploy")

# Un `echo` (ou `printf`) dont l'argument porte un accent grave suivi d'une lettre :
# c'est la forme qui s'exécute. Un accent grave isolé, ou suivi d'une ponctuation, ne
# forme pas une substitution plausible.
_RISQUE = re.compile(r"^\s*(echo|printf)\b[^\n]*`[A-Za-z_./$]")
# L'apostrophe simple supprime toute substitution : `echo '…`x…'` est SÛR.
_SIMPLE = re.compile(r"^\s*(echo|printf)\s+'[^']*'\s*$")


def _shell_files() -> list[Path]:
    out: list[Path] = []
    for base in _SCANNED:
        d = _ROOT / base
        if not d.is_dir():
            continue
        out += [p for p in d.rglob("*.sh") if "__pycache__" not in p.parts]
    mk = _ROOT / "Makefile"
    if mk.is_file():
        out.append(mk)
    return sorted(out)


def test_the_scan_sees_shell_files() -> None:
    """Anti-vacuité : sans script à lire, ce garde est vert sur rien."""
    files = _shell_files()
    assert len(files) >= 5, (
        f"seulement {len(files)} script(s) shell trouvé(s) sous {_SCANNED} — il y en "
        "avait 14 le 2026-09-18. Le balayage est cassé, ou les scripts ont déménagé.")


def _executes(line: str) -> bool:
    """An `echo`/`printf` whose text Bash would run: a backtick outside single quotes."""
    return bool(_RISQUE.search(line)) and not _SIMPLE.search(line)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """The exact shape of 2026-09-18 (a description quoting a command between backticks,
    in double quotes — Bash ran it), and the single-quoted correction."""
    assert _executes('echo "▶ nettoyage : `make clean` puis relance"')
    assert _executes("printf \"voir `.env`\\n\"")
    assert not _executes("echo '▶ nettoyage : `make clean` puis relance'")
    assert not _executes('echo "rien à exécuter ici"')


def test_no_description_string_can_execute() -> None:
    fautifs = []
    for path in _shell_files():
        for n, line in enumerate(path.read_text(encoding="utf-8",
                                                errors="replace").splitlines(), 1):
            if _executes(line):
                rel = str(path.relative_to(_ROOT)).replace("\\", "/")
                fautifs.append(f"{rel}:{n}  {line.strip()[:100]}")
    assert not fautifs, (
        f"{len(fautifs)} ligne(s) affichent un texte dont le shell EXÉCUTERA une "
        "partie.\nEn Bash l'accent grave est une substitution de commande, même entre "
        "guillemets doubles — et ce dépôt cite ses commandes entre accents graves par "
        "convention Markdown.\nMesuré le 2026-09-18 : un tel `echo` a réellement lancé "
        "la commande qu'il décrivait et vidé l'environnement de développement.\n"
        "Remède : l'apostrophe simple, qui supprime toute substitution.\n  "
        + "\n  ".join(fautifs[:12]))
