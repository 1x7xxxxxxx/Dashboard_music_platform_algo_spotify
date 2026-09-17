"""L'écran de reprise lit TOUTE la roadmap, et un filtre de hook vise un vrai chemin.

Type: Test
Uses: ast, tools.dev.night_run
Depends on: tools/dev/night_run.py, .claude/hooks/check_roadmap_update.py
Persists in: nothing

Les deux défauts
----------------
**`night-status` ne lisait qu'une des deux tables d'index.** Le 2026-09-17, R124 a été
déplacée vers `## 🙋 En attente de toi` — sa place légitime — et l'écran a annoncé
« 0 tâche(s) ouverte(s) » sur un dépôt qui en avait une. Le total a été rapporté au
propriétaire comme vrai. C'est l'écran qu'on lit EN PREMIER après chaque compaction.

**`check_roadmap_update.py` filtrait sur `src/Application`**, un répertoire qui n'existe
pas ici. Le hook sortait 0 sur CHAQUE édition Python, depuis toujours.

Ce qu'ils ont en commun, et c'est le sujet
------------------------------------------
Les deux sont des correctifs qui **se sont arrêtés au fichier où le défaut a été vu** :
le découpage non ancré a été corrigé dans `test_roadmap_index_is_honest.py:60` et jamais
propagé à `night_run.py` ; le tracker du hook a été corrigé en 2026-08-03 et son filtre
d'entrée laissé mort. Classe `a-fix-that-stops-at-the-file-where-it-was-seen`.

⚠️ Ce garde ne vérifie pas que le hook DÉCLENCHE — sa fraîcheur dépend d'un `mtime`, donc
d'une horloge. Il vérifie que son filtre désigne un chemin qui EXISTE, ce qui est la
propriété qui a manqué.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_NIGHT = _REPO / "tools" / "dev" / "night_run.py"
_HOOK = _REPO / ".claude" / "hooks" / "check_roadmap_update.py"
_ROADMAP = _REPO / ".claude" / "dev-docs" / "roadmap" / "checklist.md"


def _night_run():
    spec = importlib.util.spec_from_file_location("_night_run_probe", _NIGHT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_status_screen_counts_both_index_tables() -> None:
    """Les deux titres d'index doivent être lus, pas seulement le premier."""
    mod = _night_run()
    sections = getattr(mod, "_INDEX_SECTIONS", None)
    assert sections is not None, (
        "`_INDEX_SECTIONS` a disparu : `night-status` est probablement revenu à une "
        "seule table, et il annoncera un total faux dès qu'une tâche attendra un humain")
    assert "## 📋 Tâches ouvertes" in sections and "## 🙋 En attente de toi" in sections, (
        f"les deux tables d'index de la roadmap doivent être lues, vu : {sections}")


def test_the_count_matches_what_the_roadmap_carries() -> None:
    """L'EFFET, pas la présence d'une constante : le compte doit être le bon.

    C'est la forme qui aurait attrapé le défaut. Compter les lignes d'index des deux
    sections à la main, et exiger que l'écran en trouve autant.
    """
    import re

    mod = _night_run()
    text = _ROADMAP.read_text(encoding="utf-8")
    expected: set[str] = set()
    for title in mod._INDEX_SECTIONS:
        expected |= {row[0] for row in mod._INDEX_ROW.findall(mod._section(text, title))}
    got = {row[0] for row in mod._open_tasks()}
    assert got == expected, (
        f"`night-status` rend {sorted(got)} alors que la roadmap porte "
        f"{sorted(expected)} dans ses deux tables d'index")


def test_the_section_slice_is_anchored_at_a_line_start() -> None:
    """Un titre cité dans la prose ne doit pas servir de borne."""
    mod = _night_run()
    piege = ("blabla ## 📋 Tâches ouvertes citée dans une phrase\n"
             "## 📋 Tâches ouvertes\n"
             "| R42 | vraie ligne | P1 | mesurée |\n"
             "## suite\n")
    ids = [row[0] for row in mod._INDEX_ROW.findall(mod._section(piege, "## 📋 Tâches ouvertes"))]
    assert ids == ["R42"], (
        f"le découpage suit la première OCCURRENCE et non le titre en début de ligne "
        f"(vu {ids}) — c'est `a-document-slice-bounded-by-the-wrong-heading-level`")


def test_a_closing_entry_only_closes_its_own_task() -> None:
    """`start R1` puis `done R2` laisse R1 ouverte."""
    mod = _night_run()
    journal = [{"kind": "start", "task": "R1", "what": "en cours"},
               {"kind": "done", "task": "R2", "what": "autre tache"}]
    unit = mod._current_unit(journal)
    assert unit is not None and unit["task"] == "R1", (
        "un `done` sur une AUTRE tâche referme l'unité ouverte : l'invariant des 3 h "
        f"de `night-check` ne la voit plus (vu {unit})")


def test_git_unavailable_is_not_a_clean_tree() -> None:
    """`_git` doit LEVER, jamais rendre une chaîne vide qui se lit comme « propre »."""
    mod = _night_run()
    assert hasattr(mod, "GitUnavailable"), (
        "`GitUnavailable` a disparu : `_git` avale probablement de nouveau son échec, "
        "et `night-check` redeviendra VERT sur une machine où git ne répond pas")
    src = ast.parse(_NIGHT.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(src)
               if isinstance(n, ast.FunctionDef) and n.name == "_git"), None)
    assert fn is not None, "`_git` a disparu"
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    assert raises, "`_git` ne lève plus : son échec redevient indistinguable d'un succès vide"


def test_the_roadmap_hook_filters_on_a_path_that_exists() -> None:
    """Un filtre d'entrée qui vise un répertoire absent est un hook mort."""
    tree = ast.parse(_HOOK.read_text(encoding="utf-8"))
    include = None
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and node.targets):
            continue
        tgt = node.targets[0]
        if isinstance(tgt, ast.Name) and tgt.id == "_INCLUDE":
            call = node.value
            if isinstance(call, ast.Call):
                include = [a.value for a in call.args if isinstance(a, ast.Constant)]
    assert include is not None, "`_INCLUDE` a disparu de check_roadmap_update.py"
    # ⚠️ La première version ne testait que `include[0]` — donc `src`, qui existe.
    # Muter le filtre en `src/Application` la laissait VERTE : elle gardait le préfixe,
    # pas le chemin. C'est le défaut du hook, commis dans le garde du hook.
    # On teste le chemin JOINT, celui que le hook compare vraiment.
    joined = Path(*[c for c in include if c])
    assert (_REPO / joined).is_dir(), (
        f"le hook filtre sur `{joined}` qui n'est pas un répertoire de ce dépôt — "
        f"il sortira 0 sur chaque édition, comme `src/Application` l'a fait "
        f"jusqu'au 2026-09-17")


# ── Trois défauts de plus, fermés le 2026-09-17 après l'audit REX ─────────────


def test_an_index_row_without_a_priority_is_still_seen() -> None:
    """Un champ accessoire manquant ne fait pas disparaître une tâche de l'écran.

    `_INDEX_ROW` exigeait `(P\\d)`. Une ligne dont la priorité vaut `—`, `?` ou rien
    disparaissait de `night-status` SANS erreur : la tâche existait dans la roadmap et
    n'existait pas à l'écran.
    """
    mod = _night_run()
    piege = ("## 📋 Tâches ouvertes\n"
             "| R1 | avec priorité | P2 | mesurée |\n"
             "| R2 | sans priorité | — | mesurée |\n"
             "| R3 | priorité vide |  | mesurée |\n"
             "## suite\n")
    ids = [r[0] for r in mod._INDEX_ROW.findall(
        mod._section(piege, "## 📋 Tâches ouvertes"))]
    assert ids == ["R1", "R2", "R3"], (
        f"une ligne d'index sans priorité sort de l'écran sans un mot (vu {ids})")


def test_an_unreadable_timestamp_does_not_disarm_the_thresholds() -> None:
    """`_age_minutes` rend `None`, jamais un nombre qui passe sous les seuils.

    Il rendait **-1** sur `ValueError`. `-1 > 90` et `-1 > 180` sont faux : un
    horodatage corrompu désarmait l'avertissement de `status` ET l'invariant de `check`,
    en se faisant passer pour une unité toute jeune.
    `une-erreur-avalée-devient-une-absence`.
    """
    mod = _night_run()
    assert mod._age_minutes("pas une date") is None, (
        "`_age_minutes` rend de nouveau une valeur numérique sur un horodatage "
        "illisible — si elle est négative, les deux seuils redeviennent inopérants "
        "en silence")
    assert mod._age_minutes("") is None
    # Et un horodatage valide rend toujours un nombre.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    assert isinstance(mod._age_minutes(now), int)


def test_the_check_crosses_the_journal_with_the_roadmap() -> None:
    """Un `TASK=` inventé ne doit pas traverser le contrôle en silence.

    `make night-note TASK=R999` était accepté et journalisé, et `night-check` ne le
    voyait pas. Et `cmd_park` IMPRIME « écrire la même question dans la roadmap » sans
    que rien ne le vérifie : une question parquée jamais écrite dans `checklist.md`
    n'existe pour aucun humain.

    Vérifié à la première exécution du croisement : il a trouvé DEUX divergences
    réelles — une unité dont l'identifiant n'avait jamais eu de ligne, et une question
    parquée dont la roadmap disait qu'elle attendait du trafic, pas un humain.
    """
    import ast

    tree = ast.parse(_NIGHT.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "cmd_check"), None)
    assert fn is not None, "`cmd_check` a disparu"
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_open_tasks" in called, (
        "`cmd_check` ne lit plus l'index de la roadmap : un `TASK=` inventé, ou une "
        "question parquée jamais écrite dans `checklist.md`, redeviennent invisibles")
    assert "open_questions" in called, (
        "`cmd_check` ne croise plus les questions PARQUÉES avec la roadmap — c'est la "
        "moitié du défaut : `cmd_park` demande de les y écrire et rien ne le vérifiait")


def test_every_roadmap_reader_names_both_index_tables() -> None:
    """La classe est fermée PARTOUT, pas seulement dans `night_run.py`.

    ⚠️ Ce test est né du `ne couvre pas:` de
    `a-status-screen-that-reads-half-its-source`, écrit le matin même : « ne couvre pas
    les autres lecteurs de la même roadmap — `/resume`, `/sprint` — qui la découpent
    chacun à leur façon, et rien ne compare leurs comptes ».

    Vérifié le 2026-09-17 : les deux ne nommaient QUE `## 📋 Tâches ouvertes`. Le même
    défaut, dans deux endroits de plus, six heures après avoir été corrigé au premier.
    C'est `a-fix-that-stops-at-the-file-where-it-was-seen`, observé sur lui-même.

    ⚠️ Ce garde lit une CONSIGNE en prose, pas du code : il vérifie que les deux titres
    y figurent, pas que le modèle les lise vraiment. C'est le maximum qu'un test puisse
    dire d'un fichier d'instructions — et c'est déjà ce qui manquait.
    """
    readers = {
        ".claude/commands/resume.md",
        ".claude/commands/sprint.md",
    }
    missing = []
    for rel in sorted(readers):
        path = _REPO / rel
        if not path.exists():
            missing.append(f"{rel} : absent")
            continue
        text = path.read_text(encoding="utf-8")
        for table in ("## 📋 Tâches ouvertes", "## 🙋 En attente de toi"):
            if table not in text:
                missing.append(f"{rel} : ne nomme pas `{table}`")
    assert not missing, (
        "ces lecteurs de la roadmap ne nomment pas les deux tables d'index :\n  "
        + "\n  ".join(missing) + "\n\n"
        "Une tâche qui attend un geste humain est OUVERTE — elle n'est simplement pas "
        "commençable par une séance. Un lecteur qui n'en voit qu'une annonce « aucune "
        "tâche » sur un dépôt qui en a une, et c'est ce qu'on lit en premier après une "
        "compaction.")
