"""Les gardes Bash bloquent un GESTE, jamais une phrase qui le nomme.

Type: Test
Uses: pytest, .claude/hooks/guard_destructive.py
Depends on: .claude/hooks/guard_destructive.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Le 2026-09-12, trois commandes d'affilée ont été bloquées par le hook du dépôt — et
aucune ne faisait ce qu'il croyait. Elles ÉCRIVAIENT la classe d'erreur du geste,
donc elles le NOMMAIENT, et le hook comparait des sous-chaînes.

Le mode d'échec du garde de rétablissement est pire qu'un faux positif ordinaire.
Sa phrase d'exemple contenait `git checkout -- <fichier> … : ne bloquer que si`, et
les jetons de la phrase deviennent des chemins passés à `git status`. L'un d'eux
était `:` — en syntaxe de pathspec git, **cela désigne tous les fichiers du dépôt**.
Une phrase en prose faisait donc croire au garde que le dépôt entier allait être
écrasé, et il bloquait. Documenter le garde rendait le garde inutilisable.

C'est `a-textual-guard-is-blind`, appliqué aux hooks et non aux tests : un garde qui
inspecte du CODE doit lire sa structure. Ici, la structure minimale suffit — le geste
doit être la COMMANDE de son segment (premiers jetons, `sudo`/`time`/`nohup` admis),
pas un mot dans un argument.

Ce que ce fichier tient, et ce qu'il ne tient pas
--------------------------------------------------
Il tient les deux sens pour les deux gardes : le vrai geste bloque, la mention passe.
Il ne juge PAS l'avertissement générique (`warn`) — celui-ci n'empêche rien et son
bruit est assumé depuis longtemps.

Journal de mutation — 2026-09-12 : avec le filtre structurel retiré de l'un ou
l'autre garde, le cas « mention » correspondant vire au rouge en nommant la phrase.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

# Ce fichier mute un état de PROCESSUS partagé (sys.modules, un attribut de
# classe, un fichier du dépôt). Sous `--dist loadgroup` ses tests restent donc
# sur UN worker, comme le faisait `--dist loadfile` pour tout le monde.
# Voir `.claude/dev-docs/test-suite-performance.md` et R110.
pytestmark = pytest.mark.xdist_group("writes-readme")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_HOOK = _ROOT / ".claude" / "hooks" / "guard_destructive.py"

# Les noms sont assemblés pour que CE fichier ne soit pas lui-même un appel aux yeux
# d'un lecteur naïf — la blague est sérieuse : c'est exactement le piège qu'il teste.
_KILL = "p" + "kill"
_GIT = "g" + "it"


def _check(command: str):
    sys.path.insert(0, str(_HOOK.parent))
    try:
        from guard_destructive import check_command
        return check_command(command)
    finally:
        sys.path.pop(0)


def _clean_tracked_file() -> str:
    """Un fichier suivi et NON modifié — sinon le garde a raison de bloquer."""
    listed = subprocess.run([_GIT, "ls-files", "src/"], cwd=_ROOT,
                            capture_output=True, text=True, timeout=20)
    for path in listed.stdout.splitlines()[:200]:
        st = subprocess.run([_GIT, "status", "--porcelain", "--", path], cwd=_ROOT,
                            capture_output=True, text=True, timeout=20)
        if st.returncode == 0 and not st.stdout.strip():
            return path
    pytest.skip("aucun fichier suivi propre — l'arbre entier est modifié")
    return ""


@pytest.mark.parametrize("command,label", [
    (f'{_KILL} -f "pytest tests/" ; echo la_suite', "suivi d'une autre commande"),
    (f'sudo {_KILL} -f node && echo ok', "précédé de sudo, suivi"),
])
def test_a_real_kill_that_would_take_the_shell_with_it_is_blocked(command, label):
    """Le motif est dans la ligne du shell : il se tue, et la suite ne part pas."""
    got = _check(command)
    assert got and got[0] == "block", (
        f"{label} : le garde laisse passer. Le shell mourra en 144 et ce qui suit "
        f"ne tournera jamais — arrivé trois fois le 2026-09-12. Obtenu : {got}")


@pytest.mark.parametrize("command,label", [
    (f'echo "on parle de {_KILL} -f pytest ; et ensuite"', "kill nommé dans une phrase"),
    (f'echo "le garde de {_GIT} checkout -- <f> au-dessus : ne bloquer que si"',
     "rétablissement nommé dans une phrase"),
])
def test_merely_naming_the_gesture_never_blocks(command, label):
    """Écrire SUR le défaut ne doit pas déclencher le garde du défaut.

    Sinon la seule façon de garder le travail possible est d'arrêter de documenter —
    la leçon du 2026-08-03, repayée ici sur un hook au lieu d'une signature.
    """
    got = _check(command)
    assert not got or got[0] != "block", (
        f"{label} : une simple MENTION bloque. Documenter le garde rend le garde "
        f"inutilisable. Obtenu : {got}")


def test_a_restore_on_a_clean_file_stays_a_no_op():
    """Le garde de rétablissement est à ÉTAT : rien à perdre, rien à bloquer."""
    path = _clean_tracked_file()
    got = _check(f"{_GIT} checkout -- {path}")
    assert not got or got[0] != "block", (
        f"`checkout` d'un fichier PROPRE ({path}) est bloqué : le garde a cessé de "
        f"lire l'état et bloque la forme. Obtenu : {got}")


def test_a_restore_that_would_lose_work_still_blocks():
    """NON-VACUITÉ : sans ce sens-là, tout assouplir rendrait ce fichier vert.

    Le garde existe pour un dégât réel — deux correctifs perdus le 2026-09-10. On
    vérifie donc qu'il mord encore, sur un fichier qu'on salit puis qu'on rend.
    """
    victim = _ROOT / "README.md"
    if not victim.exists():
        pytest.skip("pas de README.md à salir")
    before = victim.read_bytes()          # BINAIRE : le mode texte réécrirait les
    try:                                   # fins de ligne du fichier entier.
        victim.write_bytes(before + b"\n<!-- sonde du garde -->\n")
        got = _check(f"{_GIT} checkout -- README.md")
        assert got and got[0] == "block", (
            "un fichier porte du travail non commité et le garde laisse passer : "
            f"il ne lit plus l'état du dépôt. Obtenu : {got}")
        assert "README.md" in got[1], "le message ne NOMME pas ce qui serait perdu"
    finally:
        victim.write_bytes(before)


# ── Le niveau LITTERAL de guard_destructive, corrige le 2026-09-16 ───────────
#
# Il comparait une SOUS-CHAINE sur la commande entiere (`pattern in cmd_lower`), donc
# il bloquait tout ce qui MENTIONNE un geste : un heredoc qui ecrit un script, un
# message de commit qui explique un correctif, une chaine Python entre guillemets.
#
# Trois blocages d'affilee dans la meme seance, tous en train d'ECRIRE ou de DOCUMENTER
# un retour arriere, aucun en train d'en faire un. Le depot avait deja corrige ses
# gardes A ETAT (shlex par segment) mais pas ce niveau-la, qui est le premier lu.
#
# La table ci-dessous epingle les DEUX directions : le geste reel bloque, sa mention
# passe. Un garde qui ne verifierait que la premiere se resserrerait jusqu'a tout
# bloquer ; un qui ne verifierait que la seconde se relacherait jusqu'a ne rien garder.

# Concatene, pour que ce FICHIER ne porte pas le geste en clair : il serait alors son
# propre cas de test, et une recherche de texte le trouverait ici.
_RESET = "git " + "reset --hard"


def _run_destructive_hook(command: str):
    import json as _json
    import subprocess as _sp
    import sys as _sys
    from pathlib import Path as _Path
    hook = _Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard_destructive.py"
    payload = _json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    r = _sp.run([_sys.executable, str(hook)], input=payload, capture_output=True,
                text=True, cwd=str(hook.parents[2]), timeout=60)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


_CAS = [
    ("le geste REEL, en commande",        "%(R)s HEAD~1",                                   2),
    ("le geste REEL, apres sudo",         "sudo %(R)s HEAD",                                2),
    ("le geste REEL, apres une variable", "FOO=1 %(R)s HEAD",                               2),
    ("le geste dans un HEREDOC",          "cat > /tmp/x.sh <<'EOF'\n%(R)s $before\nEOF",    0),
    ("le geste dans un MESSAGE",          "git commit -m 'on ajoute %(R)s au rollback'",    0),
    ("le geste dans une CHAINE python",   "python3 -c \"s='%(R)s'\"",                       0),
    ("un push force REEL",                "git push --force origin main",                   2),
    ("un push force CITE",                "echo 'jamais de git push --force ici'",          0),
]


@pytest.mark.parametrize("libelle,commande,attendu",
                         [(d, c % {"R": _RESET}, rc) for d, c, rc in _CAS])
def test_the_literal_tier_blocks_the_gesture_not_its_mention(libelle, commande, attendu):
    rc, sortie = _run_destructive_hook(commande)
    assert rc == attendu, (
        f"{libelle} : rc={rc}, attendu {attendu}\n"
        f"  commande : {commande!r}\n"
        "Un garde qui bloque la MENTION d'un geste interdit de le documenter ; un garde "
        "qui laisse passer le geste ne garde rien."
    )
    if attendu == 2:
        assert sortie.strip(), (
            "le garde bloque SANS motif visible. Le contrat PreToolUse remonte stderr : "
            "ecrit sur stdout, le message est avale et la porte se ferme sans raison."
        )

# ── LE SECOND crochet qui lit des commandes Bash, ajouté le 2026-09-17 ───────
#
# Ce fichier ne couvrait que `guard_destructive.py`. Mesuré : DEUX crochets de ce
# dépôt inspectent une commande Bash, et `pre_commit_scan.py` testait
# `"git commit" not in command` — une SOUS-CHAINE. Il se déclenchait donc sur
# `grep -rn "git commit" .claude/dev-docs/` et sur un `echo` qui en parle : un
# balayage en lecture seule lançait un scan complet des fichiers indexés et
# pouvait BLOQUER dessus.
#
# La classe était déjà écrite, le garde déjà là — et il regardait un seul des deux
# sites. C'est la portée du garde qui était le défaut, pour la Nième fois.
_COMMIT_HOOK = _ROOT / ".claude" / "hooks" / "pre_commit_scan.py"

_COMMIT = _GIT + " commit"

_PROSE_ABOUT_COMMITTING = [
    (f'echo "attention au {_COMMIT} sans --no-verify"', "un echo qui en parle"),
    (f'grep -rn "{_COMMIT}" .claude/dev-docs/', "un balayage de la doc"),
    (f'{_GIT} log --oneline | head -3', "une lecture d'historique"),
]

_REAL_COMMITS = [
    (f'{_COMMIT} -m x', "la forme nue"),
    (f'cd /tmp && {_COMMIT} -m y', "dans une chaîne"),
]


def _commit_hook():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_pre_commit_scan", _COMMIT_HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("command,label", _PROSE_ABOUT_COMMITTING,
                         ids=[lbl for _c, lbl in _PROSE_ABOUT_COMMITTING])
def test_writing_about_committing_is_not_committing(command: str, label: str) -> None:
    assert not _commit_hook()._is_really_a_commit(command), (
        f"{label} déclenche le scanner de secrets : `{command}`.\n"
        "Un balayage en lecture seule lançait un scan complet des fichiers indexés et "
        "pouvait BLOQUER dessus. Le geste doit être la COMMANDE de son segment.")


@pytest.mark.parametrize("command,label", _REAL_COMMITS,
                         ids=[lbl for _c, lbl in _REAL_COMMITS])
def test_a_real_commit_is_still_seen(command: str, label: str) -> None:
    assert _commit_hook()._is_really_a_commit(command), (
        f"un vrai commit n'est plus vu ({label}) : `{command}`. Le scanner de secrets "
        "ne tournerait plus — pire que le faux positif qu'on vient de retirer.")

def test_the_commit_hook_actually_uses_its_own_predicate() -> None:
    """La PRÉSENCE ne suffit pas : `main()` doit APPELER `_is_really_a_commit`.

    ⚠️ Mesuré le 2026-09-17, sur ce fichier même. Les deux tests ci-dessus appellent
    le prédicat DIRECTEMENT : remettre `"git commit" not in command` dans `main()` les
    laissait tous les deux VERTS, parce qu'ils prouvent que la fonction est juste, pas
    qu'elle est branchée. C'est `guard-asserts-presence-not-reachability`, écrite dans
    le garde même qui venait fermer une autre classe.
    """
    import ast

    tree = ast.parse(_COMMIT_HOOK.read_text(encoding="utf-8"))
    main = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, "`main()` a disparu de pre_commit_scan.py"
    appels = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(main) if isinstance(n, ast.Call)}
    assert "_is_really_a_commit" in appels, (
        "`main()` n'appelle PAS `_is_really_a_commit` — le prédicat structurel existe "
        "et n'est pas branché. S'il est retombé sur une sous-chaîne, un `grep` sur la "
        "documentation relance un scan complet des fichiers indexés.")


# ── 2026-09-24 : le crochet ne protege que sa propre ecriture ────────────────────
_SEPT_24 = ("pid=$(rtk proxy sh -c 'ps -eo pid,args | grep \"[s]treamlit run "
            "src/dashboard/app.py\"' | awk '{print $1}'); kill $pid; sleep 2; "
            "nohup .venv/bin/streamlit run src/dashboard/app.py --server.port 8501 &")


def test_the_bracket_does_not_save_a_pattern_written_elsewhere_on_the_line() -> None:
    """Non-vacuite, dans les deux sens, sur la ligne EXACTE du 2026-09-24."""
    got = _check(_SEPT_24)
    assert got and got[0] == "block", (
        f"la ligne qui a tue le shell le 2026-09-24 passe : {got}")
    # La forme saine : la relance quitte la ligne — plus rien ne porte le texte en clair.
    sain = _SEPT_24.split("; sleep")[0] + "; echo termine"
    got = _check(sain)
    assert not got or got[0] != "block", (
        f"un kill par motif CRANTE, sans le texte en clair ailleurs, est bloque : {got}")


def test_a_bracketed_probe_without_a_kill_is_left_alone() -> None:
    """Sonder n'est pas tuer : une sonde crantee suivie d'une relance ne meurt pas."""
    sonde = ('ps -eo pid,args | grep "[s]treamlit run app.py"; '
             "nohup streamlit run app.py &")
    got = _check(sonde)
    assert not got or got[0] != "block", f"une sonde sans kill est bloquee : {got}"


@pytest.mark.parametrize("command,label", [
    ('(pgrep -f "[s]treamlit run" >/dev/null && echo deja) || '
     "(nohup .venv/bin/streamlit run src/dashboard/app.py &)", "sonde du 2026-09-22"),
    ('ps -eo pid,args | grep "[s]treamlit run" | awk \'{print $1}\' | xargs kill; '
     "nohup streamlit run app.py &", "xargs kill en queue de tube"),
])
def test_a_bracketed_pattern_written_in_clear_elsewhere_is_seen(command, label) -> None:
    got = _check(command)
    assert got and got[0] == "block", f"{label} : passe — {got}"


def test_a_grep_over_a_log_file_is_not_a_process_probe() -> None:
    """Faux positif mesure le 2026-09-24 : grep lit un fichier, pas la liste des
    processus ; il ne peut pas trouver la ligne du shell."""
    cmd = ('pid=$(grep "worker-3" /var/log/app.log | tail -1 | cut -d: -f1); '
           'kill "$pid"; echo "worker-3 shift done"')
    got = _check(cmd)
    assert not got or got[0] != "block", f"un grep sur un log est bloque : {got}"
