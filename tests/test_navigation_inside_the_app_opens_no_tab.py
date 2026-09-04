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
    # L'ARBRE, pas le texte. Ces trois assertions cherchaient `_goto_register` et
    # `st.query_params["page"] = "register"` dans la CHAÎNE du fichier : un
    # commentaire les satisfait, y compris celui qui explique le correctif. C'est
    # exactement le défaut que `test_a_guard_reads_structure_not_text` traque, et il
    # ne le voyait pas — son prédicat exemptait tout fichier qui parse ailleurs.
    def _buttons(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {next((k.value.value for k in n.keywords
                      if k.arg == "key" and isinstance(k.value, ast.Constant)), None): n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "button"}

    auth_btn = _buttons(_DASHBOARD / "auth.py")
    reg_btn = _buttons(_DASHBOARD / "views" / "register.py")

    assert "_goto_register" in auth_btn, "le bouton « Créez-en un » a disparu"
    assert "_goto_login" in reg_btn, (
        "l'écran d'inscription ne renvoie plus vers la connexion par un bouton")

    # Le bouton pose bien le paramètre de page, et il le pose dans SA branche.
    tree = ast.parse((_DASHBOARD / "auth.py").read_text(encoding="utf-8"))
    posts = [n for n in ast.walk(tree)
             if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Subscript)
                     and "query_params" in ast.dump(t.value)
                     and isinstance(t.slice, ast.Constant) and t.slice.value == "page"
                     for t in n.targets)]
    assert any(isinstance(a.value, ast.Constant) and a.value.value == "register"
               for a in posts), (
        "l'écran de connexion ne renvoie plus vers l'inscription par un rerun")


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


def test_the_highlight_wraps_a_translated_label():
    """La surbrillance entoure `_t(...)`, jamais une chaîne française en dur.

    Demandé le 2026-09-04, puis corrigé une heure plus tard par son auteur : « mets en
    couleur de police bleu au lieu de la surbrillance, je me suis mal exprimé ». Le
    fond transformait la ligne en bandeau — plus lourd que le lien qu'elle remplace.

    Le piège d'une décoration posée au dernier moment est de figer le texte avec elle — `st.button(":blue-background[Pas encore de compte ?…]")` est plus
    court à écrire, s'affiche pareil, et rend le bouton unilingue.

    Le test lit l'ARBRE : l'argument de `st.button` doit contenir un appel à `_t`.
    Vérifié au navigateur, et c'est la moitié que l'AST ne voit pas : Streamlit ne
    rend cette syntaxe que sur les widgets qui acceptent du markdown. Sur les autres,
    `:blue[…]` s'affiche littéralement.
    """
    tree = ast.parse((_DASHBOARD / "auth.py").read_text(encoding="utf-8"))
    call = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.Call)
         and getattr(n.func, "attr", "") == "button"
         and any(k.arg == "key" and getattr(k.value, "value", "") == "_goto_register"
                 for k in n.keywords)),
        None)
    assert call is not None, "le bouton « Créez-en un » a disparu ou changé de clé"

    label = call.args[0]
    literals = [n.value for n in ast.walk(label)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert any(x.startswith(":blue[") for x in literals), (
        "le libellé n'est plus en bleu — il redevient une ligne grise de même poids "
        "que la mention RGPD posée juste sous lui, alors qu'une seule est une action")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_t"
               for n in ast.walk(label)), (
        "la surbrillance entoure un texte figé au lieu d'un `_t(...)` : le bouton "
        "resterait en français pour un lecteur anglophone")
