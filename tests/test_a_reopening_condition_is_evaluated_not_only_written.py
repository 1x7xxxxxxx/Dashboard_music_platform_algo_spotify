"""Une condition de reouverture ecrite est une condition EVALUEE.

Type: Sub
Uses: ast, pathlib, re
Triggers: pytest
Depends on: tools/dev/reopen_check.py, .claude/dev-docs/roadmap/*.md
Persists in: —

Error class `a-reopening-condition-nothing-ever-evaluates`.

Le defaut mesure le 2026-09-17
-------------------------------
Huit taches closes portent une « condition de reouverture, calculable » ecrite noir sur
blanc. **Aucune n'etait evaluee par quoi que ce soit.**

Le cas qui l'a revele : R122 s'est close en se donnant « rouvrir si
`ever_recurred_observed` repasse au-dessus de 47 ». Le compteur valait **48** avant la
seance du 2026-09-17, puis **49**. La condition etait remplie depuis des heures, et
personne ne l'a su — parce qu'ecrire un declencheur et le VERIFIER sont deux gestes, et
que seul le premier avait ete fait.

⚠️ Ce n'est PAS un defaut du cliquet des classes d'erreur : lui verifie que les trous ne
grandissent pas, ce qu'il fait. Il ne lui a jamais ete demande de dire si une tache close
doit rouvrir. C'est une question que personne ne posait.

Les deux proprietes tenues
---------------------------
1. **Chaque tache du registre a soit une evaluation, soit un aveu.** Une condition qu'on
   ne sait pas trancher rend `INDÉCIDABLE`, jamais « en attente » — sans quoi
   l'ignorance se lirait comme du calme.
2. **Une panne d'evaluation ne rend pas « en attente ».** C'est la meme discipline que
   `_read_ok` pour la jauge des defauts : un instrument muet ne doit jamais ressembler
   a un instrument qui rassure.

Mutation record — 2026-09-17, trois mutations EXECUTEES et vues rouges :
  1. le seuil de R122 porte de 47 a 100 (la condition cesse d'etre remplie) -> rouge ;
  2. le `except` de `Trigger.run` rendant `NOT_MET` au lieu de `UNKNOWN` -> rouge ;
  3. le registre `TRIGGERS` vide -> rouge.
0 apres remise en etat.
"""
from __future__ import annotations

import ast
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TOOL = _ROOT / "tools" / "dev" / "reopen_check.py"
_ROADMAP = _ROOT / ".claude" / "dev-docs" / "roadmap"

_WRITTEN = re.compile(
    r"(?:déclencheur|condition)\s+(?:de\s+réouverture|d[’']attente)", re.I)


def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("reopen_check", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_registry_is_not_empty():
    """Un registre vide rendrait « 0 à rouvrir » et serait vert pour rien."""
    mod = _module()
    assert len(mod.TRIGGERS) >= 4, (
        f"Le registre ne porte que {len(mod.TRIGGERS)} condition(s). Il en existe au "
        f"moins six d'écrites dans la roadmap ; un registre qui se vide rend « rien à "
        f"rouvrir » sans avoir rien regardé."
    )


def test_an_unevaluable_condition_is_declared_undecidable_not_waiting():
    """L'ignorance ne se déguise pas en calme."""
    mod = _module()

    def _boom():
        raise RuntimeError("la base ne répond pas")

    t = mod.Trigger("RX", "peu importe", "nulle part", _boom)
    verdict, detail = t.run()
    assert verdict == mod.UNKNOWN, (
        f"Une évaluation qui LÈVE rend {verdict!r}. Si ce n'est pas `INDÉCIDABLE`, une "
        f"panne d'accès à la base se lirait « condition non remplie », c'est-à-dire "
        f"« rien à faire » — le contraire de la vérité."
    )
    assert "la base ne répond pas" in detail, (
        "Le détail n'expose pas la cause : on ne saura pas quoi réparer."
    )


def test_a_trigger_without_an_evaluator_is_undecidable():
    mod = _module()
    verdict, _ = mod.Trigger("RX", "à la main", "nulle part", None).run()
    assert verdict == mod.UNKNOWN


def _written_sites(text: str) -> int:
    """Lines that WRITE a reopening condition — one per line, however often it matches."""
    return sum(1 for line in text.splitlines() if _WRITTEN.search(line))


def test_the_detector_sees_the_defect_it_is_written_for():
    """Both spellings the roadmap uses are counted, a line matching twice counts once
    (the over-count that would have forced the threshold up), prose about something
    else counts zero."""
    text = ("- R122 : condition de réouverture — le compteur dépasse 48\n"
            "- R131 : Condition d'attente, déclencheur de réouverture calculable\n"
            "- R140 : livrée, rien à rouvrir\n")
    assert _written_sites(text) == 2


def test_every_task_that_writes_a_condition_is_in_the_registry():
    """Ce que la roadmap ÉCRIT et ce que l'outil ÉVALUE ne divergent pas en silence.

    Le garde compte plutôt qu'il n'apparie : les conditions sont rédigées en français
    sous des formes variées, et un appariement par texte se tromperait. Ce qu'il refuse,
    c'est que la roadmap se mette à porter beaucoup plus de conditions que le registre
    n'en connaît — le début exact de la dérive de 2026-09-17.
    """
    # Par SITE (une ligne qui porte une condition), pas par occurrence de motif : la
    # tournure « Condition d'attente, déclencheur calculable » matche DEUX fois et
    # comptait une condition pour deux. Un garde qui sur-compte crie pour rien, puis on
    # relève son seuil, et il cesse de garder.
    written = sum(_written_sites(path.read_text(encoding="utf-8"))
                  for path in sorted(_ROADMAP.glob("*.md")))
    known = len(_module().TRIGGERS)
    assert written <= known + 2, (
        f"La roadmap écrit {written} conditions de réouverture, le registre de "
        f"`tools/dev/reopen_check.py` en connaît {known}. L'écart grandit : des "
        f"conditions s'écrivent sans que rien ne les évalue, ce qui est exactement le "
        f"défaut du 2026-09-17 — R122 était à rouvrir depuis des heures, sans lecteur."
    )


def test_the_tool_exits_non_zero_when_something_must_reopen():
    """Le code de sortie porte le verdict, sinon aucun automate ne peut s'en servir."""
    src = _TOOL.read_text(encoding="utf-8")
    tree = ast.parse(src)
    returns = [n for n in ast.walk(tree)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.IfExp)]
    assert returns, (
        "`main()` ne rend plus un code conditionnel : `make reopen-check` serait vert "
        "même avec une tâche à rouvrir, et ne pourrait bloquer nulle part."
    )


def test_a_workstation_condition_is_undecidable_on_a_runner(monkeypatch) -> None:
    """The first nightly (2026-09-25) said ROUVRIR on « 3ᵉ worker » from the RUNNER's
    14 667 Mo — a machine the condition does not describe. A condition that cannot see
    its subject must say so, never answer for another machine."""
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location(
        "reopen_check_ci", pathlib.Path(__file__).resolve().parents[1] / "tools/dev/reopen_check.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(RuntimeError, match="runner"):
        rc._pytest_third_worker()
    monkeypatch.delenv("CI")
    state, _ = rc._pytest_third_worker()
    assert state in (rc.MET, rc.NOT_MET), "on a workstation it measures"
