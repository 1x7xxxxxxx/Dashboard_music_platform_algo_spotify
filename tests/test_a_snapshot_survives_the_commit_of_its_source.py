"""Un instantané peut être commité AVEC sa source, sans devenir périmé au même instant.

Type: Test
Uses: tools.dev.error_class_health
Depends on: .claude/dev-docs/error-classes.md
Persists in: rien

Ce qui a été mesuré (2026-09-18)
--------------------------------
`error-class-health.json` tire une partie de ses faits de l'historique git du
catalogue. Commiter le catalogue ajoutait donc une révision, et l'instantané commité à
côté décrivait l'état d'AVANT — périmé d'exactement un, à la seconde de son commit.

Le dépôt avait répondu par le remède écrit dans
`a-document-that-cannot-be-current-in-its-own-commit` : « deux commits, et le second ne
touche pas la source ». Il est correct. Il coûte :

* **50 des 104 commits du 2026-09-18** étaient « Regenerer l instantane apres le commit
  du catalogue » — 48 % du journal de la journée ; 85 sur 440 en sept jours ;
* chacun démarrait une exécution de CI complète que `cancel-in-progress` tuait aussitôt
  — 13 runs annulés sur 60 ce jour-là.

Le remède retenu à la place : `_revisions()` compte **l'arbre de travail comme une
révision en attente**. Le nombre vaut alors N+1 des deux côtés du commit. C'est aussi la
lecture honnête de la grandeur — « combien d'états distincts de ce catalogue ont
existé » — et l'état courant en est un.

Ce que ce fichier tient
-----------------------
La propriété, pas le mécanisme : **ce que le générateur produit ne doit pas dépendre du
fait que le catalogue soit commité ou non.** Elle est vérifiée sans toucher à git : on
demande le compte de révisions pour l'arbre tel qu'il est, puis pour le même contenu
qu'on déclare « identique à HEAD ». Les deux doivent coïncider.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_GEN = ROOT / "tools" / "dev" / "error_class_health.py"


@pytest.fixture(scope="module")
def health():
    spec = importlib.util.spec_from_file_location("error_class_health", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_revision_count_does_not_move_when_the_source_is_committed(
        health, monkeypatch) -> None:
    """Le cœur : N+1 avant le commit, N+1 après.

    On simule les deux côtés du commit sans en faire un. `_catalogue_differs_from_head`
    est la seule chose qui distingue « il reste une révision en attente » de « tout est
    commité » ; le reste du calcul est identique.
    """
    monkeypatch.setattr(health, "_catalogue_differs_from_head", lambda: True)
    avant = health._revisions()

    # Après le commit : plus rien en attente, mais git porte une révision de plus.
    vrai_git = health._git

    def git_avec_une_revision_de_plus(*args):
        out = vrai_git(*args)
        if args[:2] == ("log", "--reverse") and out:
            derniere = out.rstrip("\n").splitlines()[-1]
            return out.rstrip("\n") + "\n" + derniere.replace(
                derniere.split()[0], "0" * 40) + "\n"
        return out

    monkeypatch.setattr(health, "_git", git_avec_une_revision_de_plus)
    monkeypatch.setattr(health, "_catalogue_differs_from_head", lambda: False)
    apres = health._revisions()

    assert len(avant) == len(apres), (
        f"{len(avant)} révisions sur un catalogue modifié, {len(apres)} une fois "
        "commité. L'instantané commité avec sa source serait donc périmé d'exactement "
        "un, et il faudrait un SECOND commit pour le rafraîchir — 48 % du journal du "
        "2026-09-18 était fait de ces seconds commits.")


def test_the_pending_revision_is_read_from_disk_and_not_from_git(
        health, monkeypatch) -> None:
    """Non-vacuité : la révision en attente porte le contenu du DISQUE.

    Sans cette moitié, `_revisions()` pourrait rendre le bon NOMBRE sans que le rejeu
    voie le travail en cours — un compteur juste posé sur une lecture fausse, la forme
    d'aveuglement que ce dépôt mesure le plus souvent.

    ⚠️ La première version de ce test cherchait `"CATALOGUE.read_text" in source`. Elle
    est restée VERTE sur la mutation qui retirait précisément cette lecture, parce que
    la chaîne apparaît ailleurs dans le même fichier. C'est
    `guard-satisfied-by-its-own-comment`, troisième instance de la journée. La propriété
    se vérifie donc en EXÉCUTANT le rejeu sur une seule révision, celle du disque, avec
    un `git show` qui explose s'il est appelé.
    """
    def git_qui_refuse_de_montrer(*args):
        if args and args[0] == "show":
            raise AssertionError(
                "le rejeu a demandé `git show` pour la révision EN ATTENTE : elle est "
                "comptée sans être lue, donc une classe écrite et non commitée "
                "n'existerait pour aucun compteur.")
        return health._git(*args)

    monkeypatch.setattr(health, "_revisions",
                        lambda: [(health.WORKTREE, "2026-09-18")])
    monkeypatch.setattr(health, "_git", git_qui_refuse_de_montrer)

    observed = health._observed()
    assert observed["per_class"], (
        "le rejeu sur la seule révision du disque ne rend AUCUNE classe — il ne lit "
        "pas le catalogue tel qu'il est maintenant.")
    assert observed["revisions"] == 1


def test_the_generator_concludes_on_a_dirty_catalogue(health, monkeypatch) -> None:
    """Le refus exit 3 est parti AVEC sa prémisse, pas avant elle.

    Il disait « git et le fichier décrivent deux états ». C'était vrai tant que le rejeu
    ignorait le disque ; ça ne l'est plus. Retirer le refus SANS corriger le compte
    aurait produit un instantané réellement incohérent : l'ordre des deux gestes est le
    sujet.

    ⚠️ Ce test lisait d'abord le SOURCE du générateur et y cherchait `_tree_is_dirty`,
    `return 3` et `_catalogue_differs_from_head`. `test_a_guard_reads_structure_not_text`
    l'a refusé — et c'est la SECONDE fois dans ce même fichier. On exécute donc
    `main(["--check"])` en déclarant le catalogue modifié, et on regarde le code rendu.
    """
    monkeypatch.setattr(health, "_catalogue_differs_from_head", lambda: True)
    monkeypatch.setattr(sys, "argv", ["error_class_health.py", "--check"])
    code = health.main()
    assert code != 3, (
        "le générateur refuse de nouveau de conclure sur un catalogue modifié (code 3). "
        "La cérémonie des deux commits revient avec lui : 48 % du journal du 2026-09-18.")
    assert code == 0, (
        f"`--check` rend {code} sur un catalogue modifié dont l'instantané est à jour. "
        "Si c'est 1, le compte de révisions est redevenu instable — vérifier que "
        "l'arbre de travail est toujours compté comme une révision en attente.")
