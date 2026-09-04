"""Un compte non configuré atterrit sur ses étapes — quelle que soit l'URL.

Type: Test
Uses: app._SETUP_PAGES, app._NAV_SECTIONS, setup_completion (pur)
Depends on: src/dashboard/app.py
Persists in: nothing

Le défaut, reproduit au navigateur le 2026-09-04
------------------------------------------------
« Pourquoi dès que je m'inscris après reset et que j'ai le mail, ça ne nous emmène pas
direct sur les steps de configuration et on arrive direct sur l'app ? Il faudrait le
même parcours tout le temps. »

Le parcours mesuré, pas supposé :

  1. l'artiste entre dans l'application ; le miroir d'URL écrit `?page=home` ;
  2. il se déconnecte — l'écran de connexion garde `?page=home` dans son adresse ;
  3. il se reconnecte. `session_state.clear()` a effacé `_page_mirrored`, donc la
     garde « c'est nous qui avons écrit ce paramètre » ne s'applique plus : le bloc
     d'URL pose `_nav_page = 'home'` ;
  4. `resolve_nav_page` trouve une page valide en session et n'a plus rien à
     décider. L'artiste entre dans l'app avec une configuration à **0/4**, sans
     jamais voir ses étapes.

Deux mécanismes justes qui se contredisaient. Le miroir existe pour qu'un rechargement
retrouve sa page ; l'atterrissage, pour qu'un compte non configuré voie sa mise en
route. Le second gagne : une page retrouvée n'a de valeur que pour quelqu'un qui sait
déjà où il va.

Ce que ce fichier fige
----------------------
La RÈGLE d'arbitrage, pas la séquence de clics — un test de navigation qui rejoue six
écrans casse au premier changement de libellé et ne dit plus rien. Ici : quelles pages
peuvent survivre à une première arrivée, et lesquelles doivent lui céder.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.app import _LANDING_LINKS, _NAV_SECTIONS, _SETUP_PAGES

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"


def _nav_keys() -> set[str]:
    return {key for _s, _h, items in _NAV_SECTIONS for _l, key in items}


# ── La règle d'arbitrage ─────────────────────────────────────────────────────

def test_the_setup_pages_are_the_ones_a_first_arrival_may_keep():
    """`_SETUP_PAGES` doit contenir l'assistant — sinon le lien du mail se casse.

    Le mot de bienvenue envoie sur `?page=onboarding`. Si l'assistant sortait de cet
    ensemble, l'arbitrage l'écraserait… par lui-même, et le lien tomberait sur une
    boucle. C'est la moitié du garde qu'on oublie en écrivant l'autre.
    """
    assert "onboarding" in _SETUP_PAGES, (
        "l'assistant n'est plus une page de mise en route : le lien `?page=onboarding` "
        "du mot de bienvenue serait écrasé par l'atterrissage"
    )
    assert "credentials" in _SETUP_PAGES, (
        "la page de saisie n'est plus une page de mise en route : un lien profond "
        "vers Credentials pendant l'installation serait détourné"
    )
    assert "home" not in _SETUP_PAGES, (
        "l'accueil est devenu une page de mise en route — c'est précisément la page "
        "qui détournait l'atterrissage (`?page=home` hérité de la session précédente)"
    )


def test_every_setup_page_is_a_real_menu_entry():
    """Non-vacuité : un ensemble de pages fantômes n'arbitrerait rien."""
    unknown = sorted(_SETUP_PAGES - _nav_keys())
    assert not unknown, (
        f"`_SETUP_PAGES` nomme des pages absentes du menu : {unknown}. Elles ne "
        "seraient jamais comparées au paramètre d'URL, donc l'arbitrage serait muet "
        "pour elles."
    )


# ── L'ordre des opérations, qui EST le défaut ───────────────────────────────

def _main_body_src() -> str:
    src = _APP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_main_body")
    return ast.get_source_segment(src, fn) or ""


def test_the_first_run_decision_is_taken_before_the_url_is_honoured():
    """`arm_first_run_once` AVANT le bloc d'URL, sinon l'arbitrage n'a rien à lire.

    C'est tout le correctif. Elle n'était appelée que dans `resolve_nav_page`, qui
    tourne APRÈS — au moment où `_nav_page` porte déjà la page héritée de l'URL et
    où il n'y a plus rien à décider.
    """
    body = _main_body_src()
    i_arm = body.find("arm_first_run_once(")
    i_url = body.find("if _page_param:")
    assert i_arm != -1, "`arm_first_run_once` n'est plus appelée dans `_main_body`"
    assert i_url != -1, "le bloc qui honore `?page=` a disparu"
    assert i_arm < i_url, (
        "`arm_first_run_once` est appelée APRÈS le bloc d'URL : au moment où "
        "l'arbitrage se joue, personne n'a encore décidé si cette arrivée est une "
        "première connexion. C'est l'ordre exact qui produisait le défaut."
    )


def _url_block_names() -> set[str]:
    """Les NOMS que le bloc d'URL lit vraiment — arbre, pas texte.

    Ces deux assertions ont été écrites sur la chaîne du bloc, et elles se sont
    trouvées satisfaites par un COMMENTAIRE : celui qui explique, dans ce bloc même,
    que le test valait `_SETUP_PAGES` avant le 2026-09-04. Troisième garde textuel
    pris sur sa propre documentation dans la même journée.
    """
    src = _APP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_main_body")
    # `if _page_param:` — le test de VÉRITÉ, pas les `if _page_param == "register":`
    # qui routent les pages publiques plus haut dans la même fonction. Sans cette
    # précision le helper attrapait le premier venu et lisait un bloc sans rapport.
    node = next(n for n in ast.walk(fn)
                if isinstance(n, ast.If)
                and isinstance(n.test, ast.Name) and n.test.id == "_page_param")
    return {x.id for x in ast.walk(node) if isinstance(x, ast.Name)}


def test_the_url_block_consults_the_first_run_flag():
    """Le bloc d'URL doit lire le drapeau — pas seulement `_page_mirrored`.

    `_page_mirrored` répond à « est-ce nous qui avons écrit ce paramètre ? ». Après
    `session_state.clear()` la réponse est non, ce qui est vrai et sans rapport avec
    la question qui compte ici : « cet artiste a-t-il fini sa configuration ? »
    """
    names = _url_block_names()
    assert "FIRST_RUN_FOCUS" in names, (
        "le bloc d'URL ne consulte pas le drapeau de première arrivée : un "
        "`?page=home` hérité de la session précédente reprendrait la main"
    )
    assert "_LANDING_LINKS" in names, (
        "le bloc d'URL n'exempte plus le lien du mot de bienvenue : "
        "`?page=onboarding` serait écrasé lui aussi"
    )


# ── La décision elle-même, sur des états lisibles ───────────────────────────

@pytest.mark.parametrize("page,first_run,honoured", [
    ("home",        True,  False),   # le défaut signalé
    ("credentials", True,  True),    # lien profond pendant l'installation
    ("onboarding",  True,  True),    # le lien du mot de bienvenue
    ("home",        False, True),    # configuration finie : l'URL reprend ses droits
    ("youtube",     False, True),
    ("youtube",     True,  False),
])
def test_which_pages_survive_a_first_arrival(page, first_run, honoured):
    """La règle, énoncée une fois, vérifiée sur les six cas qui comptent.

    Elle est recopiée ici volontairement plutôt qu'importée : ce test répond à
    « la règle est-elle celle qu'on veut ? », pas à « le code fait-il ce que le code
    fait ». Un import de la vraie fonction rendrait les six lignes tautologiques.
    """
    detourned = first_run and page not in _SETUP_PAGES
    assert (not detourned) is honoured, (
        f"page={page!r}, première arrivée={first_run} : le paramètre d'URL devrait "
        f"{'être honoré' if honoured else 'céder à la mise en route'}"
    )


# ── L'admin, qui ne sera jamais amené ici ────────────────────────────────────

def test_an_admin_is_told_why_the_landing_never_arms_for_them():
    """La règle est juste ; c'est son silence qui coûtait.

    `_setup_is_unfinished` renvoie `False` dès la première ligne pour `role ==
    'admin'` — un admin n'a pas d'`artist_id`, donc pas de mise en route. C'est
    voulu, et c'est invisible : il se connecte, atterrit sur l'accueil avec le menu
    complet, ouvre l'assistant depuis le menu, et conclut que l'atterrissage est
    cassé. Demandé deux fois le 2026-09-04 — « on n'arrive pas directement sur mise
    en route, c'est normal ? », « pourquoi on retrouve le volet de navigation ? ».

    Vérifié en base de production avant d'écrire quoi que ce soit : le compte qui
    posait la question est `role=admin`, `artist_id` NULL, et les deux locataires
    artistes sont à 0/4 — le mécanisme marche, il ne s'adressait simplement pas à
    celui qui le testait.

    Le test porte sur la RÈGLE — la sortie de l'admin est gardée par `is_admin()` —
    et sur le fait qu'elle nomme le bac à sable, qui est la façon de tester le
    parcours pour de vrai.
    """
    import ast as _ast

    onb = _ROOT / "src" / "dashboard" / "views" / "onboarding.py"
    src = onb.read_text(encoding="utf-8")
    tree = _ast.parse(src)
    fn = next(f for f in _ast.walk(tree)
              if isinstance(f, _ast.FunctionDef) and f.name == "_step_welcome")

    guarded = [n for n in _ast.walk(fn)
               if isinstance(n, _ast.If)
               and any(isinstance(c, _ast.Call) and getattr(c.func, "id", "") == "is_admin"
                       for c in _ast.walk(n.test))]
    assert guarded, (
        "rien n'explique à un admin pourquoi l'atterrissage ne s'arme pas pour lui — "
        "il conclura que c'est cassé, comme deux fois le 2026-09-04")

    literals = [n.value for n in _ast.walk(guarded[0])
                if isinstance(n, _ast.Constant) and isinstance(n.value, str)]
    joined = " ".join(literals).lower()
    assert "sandbox" in joined or "bac à sable" in joined, (
        "le message n'indique pas le compte bac à sable : il dit que c'est normal "
        "sans dire comment tester le parcours pour de vrai")

    from src.dashboard.utils.i18n_catalog.onboarding import EN
    assert "onboarding.admin_preview" in EN, (
        "l'explication n'a pas de traduction : un admin anglophone lirait le français")


def test_the_admin_note_is_not_shown_to_artists():
    """Sept artistes n'ont aucune raison de lire une note sur les comptes admin.

    C'est la moitié qu'on rate en ajoutant une explication : la rendre générale. Le
    dépôt a déjà payé « du texte adressé au mauvais lecteur » — un parcours artiste
    entier où l'information existait, sous un titre où le lecteur ne se reconnaît pas.
    """
    import ast as _ast

    onb = _ROOT / "src" / "dashboard" / "views" / "onboarding.py"
    tree = _ast.parse(onb.read_text(encoding="utf-8"))
    calls = [n for n in _ast.walk(tree) if isinstance(n, _ast.Call)
             and any(isinstance(c, _ast.Constant) and c.value == "onboarding.admin_preview"
                     for c in _ast.walk(n))]
    assert calls, "la clé `onboarding.admin_preview` n'est plus rendue"

    fn = next(f for f in _ast.walk(tree)
              if isinstance(f, _ast.FunctionDef) and f.name == "_step_welcome")
    inside_guard = any(
        isinstance(n, _ast.If)
        and any(isinstance(c, _ast.Call) and getattr(c.func, "id", "") == "is_admin"
                for c in _ast.walk(n.test))
        and any(isinstance(k, _ast.Constant) and k.value == "onboarding.admin_preview"
                for k in _ast.walk(n))
        for n in _ast.walk(fn))
    assert inside_guard, (
        "la note admin est rendue hors du `if is_admin()` : tous les artistes la "
        "liraient")


# ── Un vestige d'URL ne bat pas l'atterrissage ───────────────────────────────

def test_only_a_link_we_actually_send_may_beat_the_landing():
    """`_SETUP_PAGES` répondait à DEUX questions ; c'était le défaut.

    « Je viens de me connecter avec le reset et je tombe directement sur la page
    Credentials API alors qu'on devrait tomber vers Mise en route » (2026-09-04).
    L'URL portait encore `?page=credentials` de la session précédente, et comme
    Credentials appartient au parcours d'installation, elle était honorée.

    Les deux questions ne sont pas la même :

        « le mode première connexion survit-il à cette page ? »  → _SETUP_PAGES
        « ce paramètre d'URL peut-il battre l'atterrissage ? »   → _LANDING_LINKS

    Seule la seconde décide de l'atterrissage, et elle a une réponse courte : les
    pages vers lesquelles on envoie VRAIMENT un lien. Il n'y en a qu'une, celle du
    mot de bienvenue. Tout le reste est un onglet resté ouvert.
    """
    assert _LANDING_LINKS == {"onboarding"}, (
        f"`_LANDING_LINKS` vaut {sorted(_LANDING_LINKS)}. Chaque page ajoutée ici "
        "peut détourner une première arrivée : n'y mets qu'une page vers laquelle "
        "l'application envoie elle-même un lien.")
    assert _LANDING_LINKS < _SETUP_PAGES, (
        "les liens d'atterrissage doivent être un sous-ensemble STRICT des pages de "
        "mise en route — sinon les deux ensembles répondent de nouveau à la même "
        "question, ce qui est le défaut d'origine")
    assert "credentials" not in _LANDING_LINKS, (
        "un `?page=credentials` hérité de la session précédente reprendrait la main "
        "sur l'assistant, exactement comme le 2026-09-04")


def test_the_url_block_arbitrates_on_the_narrow_set():
    """Le bloc d'URL doit lire `_LANDING_LINKS`, pas `_SETUP_PAGES`.

    Les deux constantes se ressemblent assez pour qu'une relecture les échange sans
    que rien ne change à l'écran — jusqu'à la première arrivée avec un onglet resté
    ouvert.
    """
    names = _url_block_names()
    assert "_LANDING_LINKS" in names, (
        "le bloc d'URL n'arbitre plus sur les liens d'atterrissage")
    assert "_SETUP_PAGES" not in names, (
        "le bloc d'URL est revenu à `_SETUP_PAGES` : Credentials, l'import CSV et "
        "l'état des plateformes détourneraient de nouveau l'atterrissage")


@pytest.mark.parametrize("page,first_run,honoured", [
    ("credentials", True,  False),   # le défaut signalé : l'onglet d'hier
    ("upload_csv",  True,  False),
    ("onboarding",  True,  True),    # le lien du mot de bienvenue
    ("home",        True,  False),
    ("credentials", False, True),    # configuration finie : l'URL reprend ses droits
])
def test_which_links_survive_a_first_arrival(page, first_run, honoured):
    detourned = first_run and page not in _LANDING_LINKS
    assert (not detourned) is honoured
