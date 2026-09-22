"""L'entonnoir d'inscription se mesure, et le fil survit à l'effacement de session.

Type: Guard
Uses: ast, pathlib
Depends on: src/dashboard/app.py, src/dashboard/auth.py, utils/usage_tracker.py
Persists in: nothing

Le trou, mesuré en production le 2026-09-22
--------------------------------------------
`track_page_view` était appelé dans `app.py`, **après** la porte de connexion. La
production portait alors :

    811 évènements `page_view`, sur 12 pages distinctes
      0 sur `register`
      0 sur `login`
    241 connexions réussies
     63 sessions anonymes, dont rien ne dit ce qu'elles ont fait

On mesurait donc finement tout ce qui se passe une fois entré, et **rien** de ce qui
décide d'entrer. Conséquence concrète : la question « est-ce que la connexion Google
réduit la friction d'inscription ? » était INVÉRIFIABLE — on aurait livré la
fonctionnalité sans jamais pouvoir dire si elle avait servi.

C'est la forme exacte de `an-instrument-placed-after-the-thing-it-measures`.

Le second défaut, qui aurait rendu l'instrument MENTEUR
-------------------------------------------------------
`auth.py` efface tout le `session_state` au moment de la connexion — c'est la défense
contre la fixation de session (MEDIUM-01), et elle est juste. Mais `_session_id`, le
corrélateur de la télémétrie, meurt avec. La session anonyme qui a vu l'écran et la
session authentifiée qui en sort portent donc **deux identifiants différents**.

Poser la sonde sans traiter ça aurait donné deux moitiés d'entonnoir impossibles à
recoudre : on aurait su combien ont vu l'écran, combien sont entrés, et jamais si
c'étaient les mêmes. Un instrument qui rend deux nombres qu'on ne peut pas diviser
l'un par l'autre ressemble à une mesure et n'en est pas une.

D'où `_clear_session_keeping_the_funnel_thread()` : l'effacement reste entier, un seul
corrélateur voyage, et il ne donne accès à rien.

Ce que ce garde vérifie, et ce qu'il ne peut pas
------------------------------------------------
Il vérifie la STRUCTURE : la sonde est appelée avant la porte, et aucun chemin de
connexion n'efface la session à la main. Il ne vérifie pas que les lignes arrivent en
base — ça, c'est `usage_events` qu'il faut interroger, et seul le temps le dira.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"
_AUTH = _ROOT / "src" / "dashboard" / "auth.py"

#: Le nom de la fonction qui efface la session SANS couper le fil.
_HELPER = "_clear_session_keeping_the_funnel_thread"


def _appels(tree: ast.AST, nom: str) -> list[ast.Call]:
    """Tous les appels à `nom`, qu'il soit nu ou attribut (`x.nom(...)`)."""
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and (getattr(n.func, "id", None) == nom
                 or getattr(n.func, "attr", None) == nom)]


def _premier_argument_constant(appel: ast.Call) -> str | None:
    if appel.args and isinstance(appel.args[0], ast.Constant):
        return appel.args[0].value
    return None


def test_the_two_screens_before_the_gate_are_instrumented() -> None:
    """`register` et `login` sont sondés, et par leur NOM.

    Le prédicat lit les arguments d'appel, pas le texte du fichier : une mention de
    `"register"` dans un commentaire ou dans une docstring — et il y en a, ce
    fichier-ci en porte — satisferait un `grep` sans qu'aucune sonde existe.
    """
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    sondees = {_premier_argument_constant(a)
               for a in _appels(tree, "track_page_view")}
    for page in ("register", "login"):
        assert page in sondees, (
            f"aucun appel `track_page_view({page!r})` dans `app.py`. Cet écran "
            "s'affiche AVANT la porte de connexion, donc la sonde du corps "
            "authentifié ne le voit pas : la production a porté 811 `page_view` et "
            f"zéro sur `{page}` jusqu'au 2026-09-22. Sans lui, on ne peut pas dire "
            "combien de gens ont vu le formulaire et sont partis.")


def test_the_login_probe_only_fires_when_nobody_is_logged_in() -> None:
    """Sinon elle compterait une vue de l'écran de connexion à chaque rerun.

    `require_login()` rend `True` sans rien dessiner quand la session est valide.
    Une sonde inconditionnelle juste avant lui gonflerait `page='login'` de tout le
    trafic authentifié — un nombre qui MONTE quand l'app va bien, c'est-à-dire
    l'inverse de ce qu'on veut mesurer.

    Le contrôle est structurel : l'appel doit vivre sous un `if` qui teste
    `authenticated`.
    """
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    sous_condition = False
    for noeud in ast.walk(tree):
        if not isinstance(noeud, ast.If):
            continue
        test = ast.dump(noeud.test)
        if "authenticated" not in test:
            continue
        for interne in ast.walk(noeud):
            if (isinstance(interne, ast.Call)
                    and getattr(interne.func, "id", None) == "track_page_view"
                    and _premier_argument_constant(interne) == "login"):
                sous_condition = True
    assert sous_condition, (
        "la sonde `track_page_view('login')` n'est pas sous un test "
        "`authenticated` : elle se déclencherait à chaque rerun d'une session "
        "déjà connectée, et `page='login'` compterait le trafic de l'app au lieu "
        "de l'écran de connexion.")


def test_no_login_path_clears_the_session_by_hand() -> None:
    """LE garde de classe. Un chemin de connexion efface la session PAR LE HELPER.

    La propriété n'est pas « `auth.py` n'appelle jamais `clear()` » — la
    déconnexion et l'expiration de session l'appellent légitimement, et elles ne
    commencent aucun entonnoir. La propriété est : **un `clear()` suivi d'une
    hydratation** coupe le fil, et doit passer par le helper.

    Sans ce contrôle, un troisième chemin de connexion ajouté demain — la connexion
    Google, précisément — recopierait `st.session_state.clear()` et casserait
    l'entonnoir sans qu'aucun test ne rougisse.
    """
    tree = ast.parse(_AUTH.read_text(encoding="utf-8"))
    fautifs: list[int] = []

    for noeud in ast.walk(tree):
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list):
            continue
        for i, stmt in enumerate(corps):
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            appel = stmt.value
            if getattr(appel.func, "attr", None) != "clear":
                continue
            # Une hydratation dans les instructions qui SUIVENT, au même niveau.
            suite = corps[i + 1:]
            hydrate = any(
                isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "_hydrate_session"
                for s in suite for n in ast.walk(s))
            if hydrate:
                fautifs.append(stmt.lineno)

    assert not fautifs, (
        f"`auth.py` efface la session à la main avant d'hydrater, ligne(s) "
        f"{fautifs}. Ce `clear()` détruit `_session_id`, donc la session qui a vu "
        "l'écran de connexion et celle qui entre portent deux identifiants : "
        f"l'entonnoir ne se recoud plus. Appelle `{_HELPER}()` à la place — elle "
        "efface tout pareil et reporte le seul corrélateur.")


def test_the_helper_exists_and_both_login_paths_use_it() -> None:
    """NON-VACUITÉ du test ci-dessus.

    Il passe trivialement si plus aucun `clear()` n'est suivi d'une hydratation —
    par exemple si le helper a été renommé et que les deux sites l'appellent sous
    un autre nom, ou si les chemins de connexion ont disparu. Ce contrôle exige
    que le helper existe ET qu'il soit appelé **deux fois au moins** : le mot de
    passe et le second facteur.
    """
    src = _AUTH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defini = any(isinstance(n, ast.FunctionDef) and n.name == _HELPER
                 for n in ast.walk(tree))
    assert defini, (
        f"`{_HELPER}` n'existe plus dans `auth.py` : le test ci-dessus ne peut "
        "plus rien attraper, il passerait sur un dépôt sans aucune sonde.")

    appels = len(_appels(tree, _HELPER))
    assert appels >= 2, (
        f"`{_HELPER}` n'est appelée que {appels} fois. Les deux chemins de "
        "connexion — mot de passe et second facteur — doivent tous deux passer "
        "par elle ; un seul qui l'utilise laisse l'autre couper le fil.")


def test_the_login_event_carries_the_thread() -> None:
    """Le fil doit être LU quelque part, sinon on le pose pour rien.

    Un corrélateur reporté qu'aucun évènement ne consomme est du code mort qui se
    lit comme une mesure — la classe `dead-code-hiding-a-live-consequence`.
    """
    tracker = (_ROOT / "src" / "dashboard" / "utils" / "usage_tracker.py")
    tree = ast.parse(tracker.read_text(encoding="utf-8"))
    noms = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "track_login" in noms, (
        "`track_login` a disparu de `usage_tracker.py` : le fil "
        "`_session_id_avant_connexion` serait posé par `auth.py` et lu par "
        "personne.")

    lit = any(
        isinstance(n, ast.Call)
        and getattr(n.func, "attr", None) == "pop"
        and n.args and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "_session_id_avant_connexion"
        for n in ast.walk(tree))
    assert lit, (
        "`usage_tracker.py` ne lit plus `_session_id_avant_connexion` : `auth.py` "
        "reporte un corrélateur que rien ne consomme, et l'entonnoir redevient "
        "deux moitiés qu'on ne peut pas diviser l'une par l'autre.")
