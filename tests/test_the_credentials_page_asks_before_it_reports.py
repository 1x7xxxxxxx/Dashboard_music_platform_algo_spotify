"""La page où l'on saisit ne commence pas par un bilan.

Type: Test
Uses: credentials.router (AST), app._NAV_SECTIONS, views/platform_status.py
Depends on: src/dashboard/views/credentials/router.py, src/dashboard/app.py
Persists in: nothing

Le défaut, signalé QUATRE FOIS
------------------------------
« Pourquoi il n'y a toujours pas l'image screen pour copier la page artiste dans
Credentials API alors que ça fait 4 fois que je te demande de le faire ? »

Elle y était depuis le premier signalement. Ce qui manquait n'était pas l'image, c'est
la place. Mesuré au navigateur avant / après, à 1440 px :

    avant : page 2141 px · champ y=1475 · capture y=1569   (hors écran)
    après : page 1351 px · champ y=686  · capture y=779    (premier écran)

Deux blocs occupaient le haut : la matrice « 📋 État de tes plateformes » (~900 px)
et un récapitulatif de la sélection suivi d'un bandeau « 👉 Suivante ».

Aucun des deux n'était faux. C'est leur PLACE qui l'était : une page dont le geste est
« colle une valeur » ne peut pas commencer par un bilan, parce qu'un bilan se lit et
qu'un formulaire s'utilise. Un correctif de contenu ne pouvait rien y faire, et c'est
pourquoi quatre passages sur le texte n'ont rien changé.

Ce que ce fichier fige
----------------------
Que le premier bloc de la page de saisie reste la SAISIE. Il ne mesure pas des pixels
— `st.tabs` et le thème les décident — il vérifie qu'aucun des deux blocs déplacés
n'est revenu, et que la matrice a bien une page atteignable où vivre.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ROUTER = _ROOT / "src" / "dashboard" / "views" / "credentials" / "router.py"
_APP = _ROOT / "src" / "dashboard" / "app.py"
_PAGE = _ROOT / "src" / "dashboard" / "views" / "platform_status.py"


def _router_strings() -> list[str]:
    """Les CHAÎNES du routeur — jamais ses commentaires.

    Le fichier explique en clair pourquoi chaque bloc est parti, et cite les phrases
    retirées. Un garde qui lit des lignes accuserait donc l'explication du correctif :
    c'est arrivé deux fois le 2026-09-04, sur deux gardes différents.
    """
    tree = ast.parse(_ROUTER.read_text(encoding="utf-8"))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_the_router_is_readable_at_all():
    """Non-vacuité : sans chaînes lues, tout ce fichier passerait pour rien."""
    assert len(_router_strings()) > 30, (
        "la lecture du routeur n'a presque rien rendu — les assertions ci-dessous "
        "ne prouveraient plus rien")


def test_the_status_matrix_is_not_rendered_on_the_credentials_page():
    tree = ast.parse(_ROUTER.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "render_status_matrix"]
    assert not calls, (
        "la matrice est revenue en tête de la page de saisie : elle y occupait "
        "900 px et repoussait le champ à remplir sous la ligne de flottaison"
    )


def test_no_selection_recap_precedes_the_tabs():
    """Le récapitulatif et le bandeau « Suivante » disaient ce que les onglets montrent.

    Ils ont eu leur raison d'être : ils datent d'avant que les onglets soient RÉDUITS
    à la sélection le premier jour et ORDONNÉS pour que le premier soit celui qu'on
    annonçait. Le bandeau décrivait alors une mise en page qui n'allait pas de soi —
    son propre texte le disait, « son onglet est le premier ci-dessous ». Depuis, il
    ne fait que redire l'écran.
    """
    retired = {
        "credentials.focus_recap": "le récapitulatif « Ce que tu as choisi de brancher »",
        "credentials.focus_banner": "le bandeau « 👉 Suivante »",
        "credentials.focus_item_done": "les lignes du récapitulatif",
        "credentials.focus_item_todo": "les lignes du récapitulatif",
    }
    present = {k: why for k, why in retired.items() if k in _router_strings()}
    assert not present, (
        "Ces blocs sont revenus au-dessus des onglets :\n  "
        + "\n  ".join(f"{k} — {why}" for k, why in present.items())
        + "\n\nIls repoussent le champ à remplir, et disent ce que les onglets "
          "montrent déjà : ils sont réduits à la sélection et ordonnés."
    )


def test_what_the_tabs_cannot_show_survives():
    """Une plateforme cochée qui ne se configure PAS ici n'a aucun onglet pour le dire.

    C'est la moitié à ne pas emporter avec le reste : sans cette ligne, Apple Music ou
    Spotify for Artists s'évaporent entre les deux pages — ni onglet, ni repli, ni
    message. Le défaut a déjà été payé une fois.
    """
    strings = _router_strings()
    assert "credentials.focus_elsewhere" in strings, (
        "la ligne qui nomme les plateformes s'important par fichier est partie avec "
        "le récapitulatif : une case cochée mènerait de nouveau nulle part")
    assert "credentials.focus_elsewhere_go" in strings, (
        "le bouton qui mène à la page d'import a disparu")


def test_the_matrix_has_a_reachable_page_of_its_own():
    """Déplacer sans réattacher, c'est supprimer — six fois payé dans ce dépôt."""
    assert _PAGE.exists(), "la page 📋 État de tes plateformes n'existe pas"
    src = _PAGE.read_text(encoding="utf-8")
    assert "render_status_matrix(" in src, "la page ne rend pas la matrice"

    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    pages, labels = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(x, "id", "") == "_NAV_SECTIONS" for x in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
                    a, b = sub.elts
                    if (isinstance(a, ast.Constant) and isinstance(b, ast.Constant)
                            and isinstance(b.value, str)):
                        pages.add(b.value)
                        labels.add(str(a.value))
    assert "platform_status" in pages, (
        "la page n'est pas dans le menu : la matrice serait rendue par du code que "
        "rien n'atteint — exactement ce que ce dépôt a payé six fois en une séance")
    assert any("État de tes plateformes" in x for x in labels), (
        "l'entrée de menu ne porte pas le nom demandé")

    routed = _APP.read_text(encoding="utf-8")
    assert 'page == "platform_status"' in routed, (
        "la page est au menu mais aucune branche ne la rend : cliquer dessus "
        "n'afficherait rien")
