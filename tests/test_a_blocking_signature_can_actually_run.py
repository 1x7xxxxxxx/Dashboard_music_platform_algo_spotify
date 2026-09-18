"""Une porte bloquante ne peut pas être rouge à cause de sa propre syntaxe.

Type: Test
Uses: ast, .claude/scripts/audit_runner.py
Depends on: .claude/dev-docs/error-classes.md
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
La CI de ce dépôt a rendu **1 succès sur 60 exécutions** en une journée. La cause
n'était aucun défaut du produit : la signature de
`a-backtick-in-a-shell-string-is-executed` était un GABARIT —

    `! grep -nE '^\\s*echo .*`[a-z]' <script>` — heuristique, report-only.

Trois accents graves (donc une capture tronquée au mauvais endroit), une quote simple
laissée ouverte, et un `<script>` à remplacer à la main. `/bin/sh` rendait
« Syntax error: Unterminated quoted string » et un code 2 ; `run_signature` lisait
`returncode != 0` comme « la classe est touchée » ; et le message imprimé sous la liste
disait *« these are real, fix or re-triage the signature »*.

La classe se déclarait par ailleurs `deterministic` — donc bloquante — alors que son
propre texte disait « heuristique, report-only » depuis le premier jour.

Trois défauts distincts, un seul symptôme :

1. une signature non exécutable pouvait exister (→ `--lint`, gardé ici) ;
2. un code de sortie « je n'ai pas su répondre » était compté comme un verdict
   (→ `run_signature` à trois états, gardé ici) ;
3. `kind` était DÉCLARÉ et non dérivé, donc une classe pouvait s'attribuer un pouvoir
   bloquant que sa signature ne justifiait pas.

Ce que ce fichier tient
-----------------------
Que `--lint` VOIT les trois formes qui l'ont produit, et que `run_signature` sépare
« propre », « touche » et « cassée ». Les deux moitiés sont fabriquées ici : ni l'une ni
l'autre ne dépend de l'état du catalogue, donc le garde ne peut pas devenir vert parce
que le dépôt s'est nettoyé.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_RUNNER = ROOT / ".claude" / "scripts" / "audit_runner.py"


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location("audit_runner", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_catalogue_carries_no_signature_that_cannot_run(runner) -> None:
    """Le cliquet : zéro, et il ne peut pas remonter sans qu'on le voie."""
    headers = runner.parse_all_headers(
        runner._CATALOGUE.read_text(encoding="utf-8"))
    assert headers, "aucune classe lue — le parseur est cassé, pas le catalogue"
    code = runner._lint(headers)
    assert code == 0, (
        "au moins une signature ne peut pas rendre de verdict (voir la sortie "
        "ci-dessus). Tant qu'elle existe, `audit_runner --static` peut rougir sur "
        "elle-même et le message annoncera que la touche est réelle.")


def test_the_lint_sees_the_three_shapes_that_produced_it(tmp_path, runner) -> None:
    """Non-vacuité : les trois formes fautives sont FABRIQUÉES, et la saine aussi.

    Sans cette moitié, `test_the_catalogue_carries_no_signature_that_cannot_run` reste
    vert mot pour mot sur un `_lint()` qui rendrait toujours 0.
    """
    sain = [{"id": "une-classe-saine",
             "signature": "! grep -rn 'motif' src/",
             "signature_raw": "- signature: `! grep -rn 'motif' src/`"}]
    assert runner._lint(sain) == 0, (
        "le lint refuse une signature parfaitement exécutable : il ferait rougir la CI "
        "sur du catalogue correct, et la seule issue serait de le désarmer.")

    # (1) la syntaxe que `sh` ne sait pas lire — le cas exact du 2026-09-18
    casse = [{"id": "x", "signature": "! grep -nE '^echo .*[a-z]' fichier",
              "signature_raw": "- signature: `…`"}]
    casse[0]["signature"] = "grep -nE 'motif non fermé src/"
    assert runner._lint(casse) == 2, "une signature que `sh -n` refuse passe le lint"

    # (2) le gabarit : exécutable en apparence, impossible en pratique
    gabarit = [{"id": "y", "signature": "docker exec <pg> psql -c 'SELECT 1'",
                "signature_raw": "- signature: `docker exec <pg> psql -c 'SELECT 1'`"}]
    assert runner._lint(gabarit) == 2, (
        "un `<placeholder>` passe le lint — or une commande qu'un humain doit compléter "
        "n'est jamais lancée par un automate, quelle que soit sa prose")

    # (3) l'accent grave IMPAIR, qui tronque la capture du parseur en silence.
    #     C'est la forme d'origine : trois accents graves sur la ligne.
    impair = [{"id": "z", "signature": "grep -n motif src/",
               "signature_raw": "- signature: `! grep -nE 'echo .*`[a-z]' fichier`"}]
    assert runner._lint(impair) == 2, (
        "une ligne `- signature:` à nombre IMPAIR d'accents graves passe le lint. La "
        "capture du parseur s'arrête au premier accent fermant, donc la commande "
        "obtenue est tronquée — et elle peut avoir l'air complète.")


def test_a_signature_that_cannot_answer_is_not_a_hit(runner) -> None:
    """`run_signature` sépare « propre », « touche » et « cassée ».

    C'est la cause racine, et elle dépasse le cas du 2026-09-18 : une signature qui
    pointe un test supprimé rend `pytest` 5 (« no tests collected »), une commande
    absente du poste rend 127. Les compter comme des touches envoie chercher un défaut
    du produit là où c'est l'outillage qui est en panne.
    """
    assert runner.run_signature("true")[0] == runner.CLEAN
    assert runner.run_signature("false")[0] == runner.HIT
    assert runner.run_signature("exit 2")[0] == runner.BROKEN, (
        "un code 2 — ce que rend `sh` sur une syntaxe invalide, et `grep` sur un "
        "fichier illisible — est compté comme une touche")
    assert runner.run_signature("exit 127")[0] == runner.BROKEN, (
        "une commande ABSENTE du poste est comptée comme un défaut du produit")
    assert runner.run_signature("exit 5")[0] == runner.BROKEN, (
        "`pytest` 5 veut dire « aucun test collecté » — une signature qui pointe un "
        "test renommé annoncerait donc un défaut à chaque exécution")


def test_every_code_declared_broken_is_actually_handled(runner) -> None:
    """Chaque membre de `_BROKEN_CODES` se comporte comme tel — pas « est documenté ».

    ⚠️ La première version de ce test lisait le SOURCE d'`audit_runner.py` et cherchait
    `rc=<n>` dans ses commentaires. `test_a_guard_reads_structure_not_text.py` l'a
    refusée dans l'heure, et elle avait raison : un nombre présent dans un commentaire
    ne dit rien de ce que le code en fait, et c'est très exactement
    `guard-satisfied-by-its-own-comment` — la classe écrite ce matin même. Un ensemble
    de codes se vérifie en les EXÉCUTANT.
    """
    assert runner._BROKEN_CODES, "l'ensemble est vide : plus rien n'est traité comme cassé"
    for code in sorted(runner._BROKEN_CODES):
        verdict, _ = runner.run_signature(f"exit {code}")
        assert verdict == runner.BROKEN, (
            f"le code {code} est déclaré dans `_BROKEN_CODES` mais `run_signature` le "
            f"rend `{verdict}` — un code déclaré et non traité est une couverture qu'on "
            "croit avoir.")
