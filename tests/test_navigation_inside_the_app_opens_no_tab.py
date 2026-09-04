"""Aller d'un écran de l'application à un autre ne doit jamais ouvrir un onglet.

Type: Test
Uses: les vues et les catalogues i18n (toute chaîne visible)
Depends on: src/dashboard/**/*.py
Persists in: nothing

Le défaut, signalé le 2026-09-04
--------------------------------
« Quand on clique sur créer un compte, ça nous ouvre une autre page du navigateur,
est-ce qu'on pourrait lancer via le même onglet pour éviter de dupliquer ? »

Un `[texte](?page=register)` écrit en markdown devient un `<a>` dans l'iframe de
Streamlit, et le navigateur l'ouvre où il veut. Mesuré au navigateur le même jour :
le seul lien markdown restant sur l'écran de connexion porte `target="_blank"`, posé
par Streamlit lui-même. L'artiste se retrouvait donc avec deux onglets de la même
application, dont un resté sur l'écran qu'il venait de quitter — et deux sessions
Streamlit distinctes, ce qui est la vraie facture : l'état de l'une n'est pas celui
de l'autre.

Le remède est `st.query_params` + `st.rerun()` : le script est relancé sans aucune
navigation HTML, donc aucun onglet n'est possible. C'est déjà ce que fait le lien de
validation d'e-mail depuis le matin du même jour, corrigé pour la même raison — et
c'est la troisième fois de la journée qu'un correctif s'applique à un site et pas à
ses frères.

Ce qui est ADMIS, et pourquoi
------------------------------
Les liens vers la politique de confidentialité restent des liens. Ce n'est pas un
écran de l'application, c'est un document : l'ouvrir à côté est le bon comportement,
et le contraire ferait perdre un formulaire d'inscription à moitié rempli. La
distinction n'est donc pas « lien ou bouton » mais « document ou écran ».
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DASHBOARD = _ROOT / "src" / "dashboard"

# Les pages qu'on a le droit d'atteindre par un `<a>` : celles qu'on LIT, pas celles
# où l'on continue son parcours. Toute autre page atteinte par un lien markdown est
# une navigation interne, donc un onglet en trop.
_DOCUMENT_PAGES = {"privacy"}

_MD_LINK = re.compile(r"\]\(/?\?page=([a-z_]+)")


def test_the_sweep_actually_reads_the_views():
    """Non-vacuité : sans fichiers lus, ce garde ne prouverait rien."""
    files = list(_DASHBOARD.rglob("*.py"))
    assert len(files) > 40, f"seulement {len(files)} fichiers lus sous src/dashboard/"


def test_no_markdown_link_navigates_between_screens():
    """Lit les CHAÎNES du code, pas ses lignes.

    Première version : une regex sur chaque ligne du fichier. Elle a immédiatement
    accusé `auth.py` — sur le commentaire que je venais d'écrire pour expliquer
    pourquoi le lien avait été retiré. Deuxième fois dans la même journée qu'un garde
    trouve un défaut dans de la documentation ; l'arbre syntaxique, lui, ne contient
    aucun commentaire.
    """
    offenders: list[str] = []
    for path in sorted(_DASHBOARD.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                      # noqa: PERF203 — un fichier cassé
            continue                             # a son propre test
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            for page in _MD_LINK.findall(node.value):
                if page not in _DOCUMENT_PAGES:
                    offenders.append(
                        f"{path.relative_to(_ROOT)}:{node.lineno} → ?page={page}")

    assert not offenders, (
        "Ces liens markdown font naviguer d'un écran de l'application à un autre :\n  "
        + "\n  ".join(offenders)
        + "\n\nStreamlit les rend en `<a target=\"_blank\">` : l'artiste garde un "
          "onglet mort sur l'écran qu'il vient de quitter, et repart sur une session "
          "distincte. Utilise un `st.button` qui pose `st.query_params` puis "
          "`st.rerun()` — le script est relancé sans navigation HTML.\n"
          f"Seules ces pages peuvent rester des liens : {sorted(_DOCUMENT_PAGES)} "
          "(des documents, qu'on lit à côté sans perdre ce qu'on remplissait)."
    )


def test_the_two_signup_paths_are_buttons():
    """Le trajet signalé ET son retour — les deux, ou le défaut vit encore à moitié.

    L'aller a été corrigé parce qu'il a été signalé ; le retour ne l'avait pas été et
    portait exactement la même forme. Un aller-retour entre connexion et inscription
    est le parcours le plus banal de l'application.
    """
    auth = (_DASHBOARD / "auth.py").read_text(encoding="utf-8")
    register = (_DASHBOARD / "views" / "register.py").read_text(encoding="utf-8")

    assert 'st.query_params["page"] = "register"' in auth, (
        "l'écran de connexion ne renvoie plus vers l'inscription par un rerun")
    assert "_goto_register" in auth, "le bouton « Créez-en un » a disparu"
    assert "_goto_login" in register, (
        "l'écran d'inscription ne renvoie plus vers la connexion par un bouton")


def test_the_labels_carry_no_link_syntax():
    """Un libellé de bouton qui garde ses crochets affiche du markdown brut.

    C'est la moitié qu'on oublie en convertissant : le code devient juste, et l'écran
    montre `[Créez-en un](?page=register)`.
    """
    from src.dashboard.utils.i18n_catalog.auth import EN as AUTH_EN
    from src.dashboard.utils.i18n_catalog.register import EN as REG_EN

    for name, catalog, key in (("auth", AUTH_EN, "auth.register_link"),
                               ("register", REG_EN, "register.already_have")):
        value = catalog.get(key, "")
        assert value, f"{name}: la clé {key} a disparu du catalogue anglais"
        assert "](" not in value and "[" not in value, (
            f"{name}/{key} garde une syntaxe de lien : {value!r} — un bouton "
            "l'afficherait tel quel")
