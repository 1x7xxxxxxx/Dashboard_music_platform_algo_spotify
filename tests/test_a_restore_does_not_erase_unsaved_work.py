"""Un rétablissement git ne doit pas effacer du travail que rien ne rendra.

Type: Test
Uses: pytest, subprocess (le hook est un exécutable, pas un module)
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing (restaure chaque fichier qu'il salit)

Ce qui a été mesuré (2026-09-10)
--------------------------------
Le même geste a détruit du travail **deux fois dans la même séance**, à quelques heures
d'intervalle : rétablir un fichier depuis git pour défaire une mutation de test.

* la première fois : un correctif de rendu et deux clés i18n, non commités ;
* la seconde : la conversion de deux figures en petits multiples et l'élargissement d'un
  cliquet — et l'un des fichiers touchés était **gitignoré**, donc pas même restaurable
  par cette voie.

Entre les deux, j'avais écrit la leçon en mémoire. Elle n'a rien empêché : une leçon en
prose ne retient pas un geste réflexe. Ce qui l'a arrêtée est le geste de remplacement
(commiter avant de muter, `git stash` pour défaire) — et un geste ne se garde pas par une
note, il se garde par un hook.

Pourquoi le garde interroge l'état du dépôt au lieu d'interdire une chaîne
--------------------------------------------------------------------------
`git checkout -- .` et `git restore .` étaient déjà bloqués par correspondance de
chaîne. La forme qui coûte n'est pas celle-là : c'est la forme **chirurgicale**, sur un
fichier nommé, qui a l'air maîtrisée. Or sur un fichier propre, ce geste est un no-op
parfaitement légitime et d'usage courant — l'interdire par la chaîne rendrait le garde
insupportable, donc contourné.

Le garde lit donc `git status --porcelain` sur les chemins visés et ne bloque **que s'il
y a réellement quelque chose à perdre**, en le nommant. C'est la différence entre un
garde qu'on apprend à esquiver et un garde qui dit quelque chose de vrai.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ce fichier mute un état de PROCESSUS partagé (sys.modules, un attribut de
# classe, un fichier du dépôt). Sous `--dist loadgroup` ses tests restent donc
# sur UN worker, comme le faisait `--dist loadfile` pour tout le monde.
# Voir `.claude/dev-docs/test-suite-performance.md` et R110.
pytestmark = pytest.mark.xdist_group("writes-readme")

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "guard_destructive.py"

# Assemblé pour que ce fichier de test ne soit pas lui-même bloqué par le garde
# littéral qui cherche cette chaîne dans les commandes Bash.
_RESTORE_VERB = "git " + "checkout"

# Un fichier suivi, gros et inoffensif, qu'on salit puis qu'on rend.
_TARGET = "README.md"


def _hook(command: str) -> tuple[int, str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    # Les DEUX flux, depuis le 2026-09-16. Le contrat PreToolUse remonte **stderr** au
    # modele ; le hook ecrivait son blocage sur stdout, ou il etait avale — l'outil
    # rapportait « No stderr output » et la porte se fermait sans motif visible.
    # Le correctif a deplace le message, et ce test regardait alors le mauvais flux :
    # il verifiait que le refus NOMME ce qui serait perdu, sur un flux desormais vide.
    # Lire les deux garde la propriete vraie quel que soit le flux choisi.
    return r.returncode, (r.stdout or "") + (r.stderr or "")


@pytest.fixture
def dirty_target():
    """Salit un fichier suivi, le rend intact quoi qu'il arrive."""
    path = ROOT / _TARGET
    # BINAIRE, et pas `read_text`/`write_text`. Ce dépôt vit sur un montage Windows :
    # un aller-retour en mode texte réécrit les fins de ligne du fichier entier, et la
    # « restauration » laisse 52 lignes modifiées. Mesuré le 2026-09-10 en écrivant ce
    # test — la sonde censée vérifier qu'on n'abîme rien a abîmé sa propre cible.
    original = path.read_bytes()
    path.write_bytes(original + b"\n<!-- sonde du garde -->\n")
    try:
        yield _TARGET
    finally:
        path.write_bytes(original)


def test_a_clean_path_is_a_no_op_and_must_pass() -> None:
    """Interdire la forme rendrait le garde contournable ; il ne juge que la perte."""
    rc, _ = _hook(f"{_RESTORE_VERB} -- {_TARGET}")
    assert rc == 0, (
        "le garde bloque un rétablissement sur un fichier PROPRE, où il n'y a rien à "
        "perdre. Un garde qui interdit l'usage courant est un garde qu'on apprend à "
        "esquiver, et il ne protégera plus le jour où il aurait raison.")


def test_work_that_nothing_would_give_back_blocks_the_command(dirty_target) -> None:
    rc, out = _hook(f"{_RESTORE_VERB} -- {dirty_target}")
    assert rc == 2, (
        "un rétablissement sur un fichier PORTANT du travail non commité est passé : "
        "c'est exactement la commande qui a détruit deux correctifs le 2026-09-10")
    assert dirty_target in out, (
        "le garde bloque sans NOMMER ce qui serait perdu. Un refus sans inventaire "
        "oblige à deviner, et on redemande la même commande")
    assert "stash" in out, (
        "le message ne propose pas le geste de remplacement : un blocage sans "
        "alternative se contourne au lieu de changer l'habitude")


def test_git_restore_is_the_same_gesture(dirty_target) -> None:
    """Deux orthographes, un seul effet — en garder une seule serait la portée du défaut."""
    rc, _ = _hook(f"git restore {dirty_target}")
    assert rc == 2, "`git restore` détruit exactement la même chose et passait"


def test_the_separator_is_optional_and_the_bare_form_is_the_one_hands_write(
        dirty_target) -> None:
    """La TROISIÈME orthographe, et celle qui a réellement détruit du travail.

    ⚠️ Mesuré le 2026-09-18 : `git checkout <fichier>`, sans `--`, a effacé
    `tests/test_dag_fleet_isolation.py` en plein milieu d'une séance, après une
    mutation. Le motif du hook exigeait le séparateur, donc cette forme — la plus
    courante — passait.

    Le test juste au-dessus, `test_git_restore_is_the_same_gesture`, portait déjà pour
    docstring « deux orthographes, un seul effet — en garder une seule serait la portée
    du défaut ». Le garde avait NOMMÉ sa classe et s'y est fait prendre quand même : il
    était écrit sur la FORME (`--`) et non sur la PROPRIÉTÉ (un rétablissement git
    visant un chemin qui porte du travail non commité).
    """
    rc, out = _hook(f"{_RESTORE_VERB} {dirty_target}")
    assert rc == 2, (
        "`checkout <fichier>` SANS `--` est passé. C'est la forme que les mains "
        "écrivent, et celle qui a détruit un fichier de garde entier le 2026-09-18.")
    assert dirty_target in out, "le refus ne nomme pas ce qui serait perdu"


def test_a_revision_before_the_path_is_the_same_gesture(dirty_target) -> None:
    """`checkout HEAD <fichier>` écrase l'arbre de travail exactement pareil."""
    rc, _ = _hook(f"{_RESTORE_VERB} HEAD {dirty_target}")
    assert rc == 2, (
        "`checkout HEAD <fichier>` est passé : le motif exigeait un `--` après la "
        "révision, que personne n'écrit.")


@pytest.mark.parametrize("cmd", ["main", "-b une-branche-neuve"])
def test_widening_the_pattern_does_not_block_a_branch_switch(cmd: str) -> None:
    """Le prix de l'élargissement, mesuré — et il est nul.

    Rendre `--` optionnel fait matcher `checkout main` par le MOTIF. Le verdict ne vient
    pas du motif : `_paths_that_would_lose_work` écarte les drapeaux puis interroge
    `git status --porcelain -- <chemin>`. Une branche n'est pas un chemin sale, donc
    rien n'est bloqué. Sans ce test, l'élargissement serait un pari ; avec lui c'est une
    mesure, et il rougira le jour où quelqu'un durcira le motif au point d'interdire
    l'usage courant — le mode d'échec que ce fichier documente depuis sa première ligne.
    """
    rc, _ = _hook(f"{_RESTORE_VERB} {cmd}")
    assert rc == 0, (
        f"`checkout {cmd}` est bloqué : le garde interdit un changement de branche, "
        "qui ne peut rien effacer. Un garde qui gêne l'usage courant se fait esquiver.")


def test_staged_only_does_not_touch_the_working_tree(dirty_target) -> None:
    """`--staged` désindexe ; il ne peut rien effacer de l'arbre de travail."""
    rc, _ = _hook(f"git restore --staged {dirty_target}")
    assert rc == 0, (
        "le garde bloque `--staged`, qui ne touche pas l'arbre de travail — un faux "
        "positif sur un geste sans perte possible")


def test_the_gesture_is_seen_inside_a_compound_command(dirty_target) -> None:
    """Le geste voyage rarement seul ; il est souvent le second membre d'un `&&`."""
    rc, _ = _hook(f"echo bonjour && {_RESTORE_VERB} -- {dirty_target}")
    assert rc == 2, (
        "le garde ne lit que la tête de la commande : `… && <rétablissement>` est la "
        "forme la plus courante du geste, et elle passait")


def test_an_untracked_file_is_not_accused() -> None:
    """`checkout --` ne touche pas un fichier non suivi : l'accuser serait un faux positif."""
    probe = ROOT / "_probe_untracked_guard.txt"
    probe.write_bytes(b"sonde\n")
    try:
        rc, _ = _hook(f"{_RESTORE_VERB} -- {probe.name}")
        assert rc == 0, (
            "le garde accuse un fichier NON SUIVI, que ce geste ne peut pas toucher. "
            "Un garde qui crie sur ce qui ne risque rien perd sa crédibilité sur ce "
            "qui risque quelque chose")
    finally:
        probe.unlink(missing_ok=True)


def test_the_guard_never_raises_on_a_command_it_cannot_parse() -> None:
    """Ce hook précède CHAQUE appel Bash : une exception y bloquerait tout le travail."""
    for weird in (f"{_RESTORE_VERB} -- 'guillemet non fermé",
                  f"{_RESTORE_VERB} -- $(une substitution)",
                  "git restore",
                  f"{_RESTORE_VERB} -- /chemin/qui/n/existe/pas"):
        rc, _ = _hook(weird)
        assert rc in (0, 2), f"le hook a planté sur {weird!r} (rc={rc})"


# ── `git clean`, le frère mesuré le 2026-09-18 ────────────────────────────────
#
# Balayage de la FAMILLE du geste (« écraser du travail que rien ne rendra »)
# plutôt que de son verbe : **9 gestes sondés, 5 bloqués, 4 non**. Sur les quatre,
# `git stash` sort de la classe — il est récupérable par `git stash list`. Restent
# `git clean -fd`, une redirection `>` et un `cp` par-dessus un fichier sale.
#
# Seul `git clean` est ajouté, et le choix est un arbitrage écrit : bloquer toute
# redirection vers un fichier suivi et modifié produirait du bruit à chaque
# génération de document, et un garde bruyant apprend que le rouge est du bruit
# (classe `a-noisy-signature-teaches-that-red-is-noise`). Les deux autres sont
# déclarés dans `guard_scope` comme mesurés et NON couverts.
#
# ⚠️ Pourquoi le garde du rétablissement ne pouvait pas l'attraper : il ignore
# délibérément les lignes `??` de `git status`, parce qu'un `checkout -- <f>` ne
# touche pas un fichier non suivi. `clean` ne touche QUE ceux-là. Deux gestes, une
# cause, des prédicats exactement complémentaires.

@pytest.fixture
def untracked_target(tmp_path_factory):
    """Un fichier NON SUIVI dans le dépôt — ce que `git clean` supprime."""
    cible = ROOT / "_untracked_probe_for_the_clean_guard.tmp"
    cible.write_text("du travail que rien ne rendrait\n", encoding="utf-8")
    try:
        yield cible.name
    finally:
        cible.unlink(missing_ok=True)


def test_clean_with_nothing_untracked_is_a_no_op_and_must_pass() -> None:
    """Anti-bruit : sans rien à perdre, le geste passe. Sinon on le contournerait."""
    subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                   capture_output=True, text=True, timeout=10)
    rc, _ = _hook("git clean -nd")
    assert rc == 0, "un `git clean --dry-run` ne supprime rien et ne doit jamais bloquer"


def test_clean_that_would_delete_untracked_work_blocks(untracked_target) -> None:
    rc, out = _hook("git clean -fd")
    assert rc != 0, (
        "`git clean -fd` supprimerait un fichier non suivi et n'est pas bloqué. Un "
        "test ou un script qu'on vient d'écrire et pas encore `git add` n'est dans "
        "aucun commit, aucun stash, aucun reflog — c'est la même perte que le "
        "`checkout` chirurgical, par l'autre bout de `git status`.")
    assert untracked_target in out, (
        "le message ne NOMME pas le fichier qui serait perdu. Un garde qui dit "
        "« dangereux » sans dire quoi est un garde qu'on contourne.")


def test_a_forced_dry_run_still_deletes_nothing(untracked_target) -> None:
    """`git clean -fdn` porte `-f` ET `-n` : il n'efface rien, il LISTE.

    Cette assertion a été ajoutée après une mutation : retirer la branche
    `--dry-run` du hook laissait le garde VERT, parce que toutes les formes
    testées jusque-là (`-nd`, `--dry-run`) échouaient déjà sur l'absence de
    `-f`. La branche existait sans être gardée — un cas de plus de
    `guard-branch-only-reached-when-it-fails`, trouvé en mutant.
    """
    rc, _ = _hook("git clean -fdn")
    assert rc == 0, (
        "`git clean -fdn` est bloqué alors qu'il ne supprime rien : `-n` gagne "
        "sur `-f`. Un garde qui refuse la commande servant à VOIR ce qui partirait "
        "pousse à la contourner, et c'est celle que son propre message propose.")


def test_clean_without_force_is_left_to_git() -> None:
    """`git clean` sans `-f` échoue de lui-même : le doubler serait du bruit."""
    rc, _ = _hook("git clean")
    assert rc == 0


def test_the_clean_guard_reads_the_command_not_the_prose(untracked_target) -> None:
    """Écrire SUR le geste ne doit pas déclencher le garde du geste."""
    rc, _ = _hook("echo 'git clean -fd supprime les fichiers non suivis'")
    assert rc == 0, (
        "documenter `git clean` déclenche son propre garde — c'est la classe "
        "`a-bash-hook-that-blocks-the-prose-about-the-gesture`, déjà payée trois "
        "fois le 2026-09-12.")
