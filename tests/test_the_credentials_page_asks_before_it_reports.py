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


def test_the_matrix_still_has_a_home_even_out_of_the_menu():
    """Déplacer sans réattacher, c'est supprimer — six fois payé dans ce dépôt.

    Ce test exigeait une ENTRÉE DE MENU. Elle a été retirée le 2026-09-05 : chaque
    onglet de Credentials porte désormais les quatre pastilles de SA plateforme,
    calculées par les mêmes fonctions, donc une page entière pour redire cela est une
    redirection de plus et pas une information de plus.

    La question survit, un cran plus bas : la matrice complète est-elle encore
    ATTEIGNABLE ? Elle reste la seule vue qui montre les six sources d'un coup, et
    des messages y renvoient. Une route sans entrée de menu est un choix ; une route
    supprimée transforme ces renvois en culs-de-sac.
    """
    assert _PAGE.exists(), "la page 📋 État de tes plateformes n'existe pas"
    src = _PAGE.read_text(encoding="utf-8")
    assert "render_status_matrix(" in src, "la page ne rend pas la matrice"

    app = _APP.read_text(encoding="utf-8")
    tree = ast.parse(app)
    routed = {n.comparators[0].value for n in ast.walk(tree)
              if isinstance(n, ast.Compare) and getattr(n.left, "id", "") == "page"
              and n.comparators and isinstance(n.comparators[0], ast.Constant)}
    assert "platform_status" in routed, (
        "la route a disparu : cliquer sur un renvoi vers l'état n'afficherait rien")

def test_the_csv_import_is_a_tab_not_a_separate_menu_entry():
    """Deux entrées de menu pour un seul geste se cherchent.

    Demandé le 2026-09-04, avec son motif : « dès qu'on clique sur *Ajouter mes
    chiffres S4A & Apple*, ça nous ramène à la mise en route » — une régression
    corrigée le même jour — puis « supprime la page, elle sera intégrée à l'onglet
    Credentials API ».

    UN onglet et non deux, contre la demande littérale : le dépôt reconnaît la source
    depuis le fichier. Deux onglets obligeraient l'artiste à classer son fichier avant
    de le déposer, sur une page où aucun locataire n'a jamais terminé un import.
    """
    src = _ROUTER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "show")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "render_uploader"]
    assert len(calls) == 1, (
        f"{len(calls)} appel(s) à `render_uploader` dans la page Credentials — il en "
        "faut exactement un : le dépôt détecte le type, le dupliquer par plateforme "
        "rendrait à l'artiste une décision que le code prend mieux")

    labels = {n.value for n in ast.walk(fn)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert any("credentials.csv_tab" == x for x in labels), (
        "l'onglet de dépôt n'a plus de libellé traduit")


def test_the_old_csv_route_still_answers():
    """Supprimer une route, c'est transformer ses pointeurs en culs-de-sac.

    Six visent `upload_csv` : les boutons d'étape de `setup_completion`, la
    destination de S4A et d'Apple Music (`platform_destination`), la colonne
    « prochaine étape » de la matrice, et les signets. Le dépôt a déjà payé six fois
    « du code correct que rien n'atteint » ; sa réciproque coûte autant.
    """
    app = _APP.read_text(encoding="utf-8")
    assert 'page == "upload_csv"' in app, (
        "la route `upload_csv` a disparu : les pointeurs qui la visent ne mènent plus "
        "nulle part")

    from src.dashboard.utils.setup_completion import _STEP_PAGES
    from src.dashboard.views.credentials.router import platform_destination
    targets = {page for _key, page in _STEP_PAGES}
    targets |= {platform_destination(k).split(":", 1)[1]
                for k in ("s4a", "apple_music")}
    tree = ast.parse(app)
    routed = {n.comparators[0].value for n in ast.walk(tree)
              if isinstance(n, ast.Compare) and getattr(n.left, "id", "") == "page"
              and n.comparators and isinstance(n.comparators[0], ast.Constant)}
    missing = sorted(t for t in targets if t not in routed)
    assert not missing, (
        f"ces destinations ne sont routées nulle part : {missing}")


def test_the_menu_offers_one_place_to_connect_a_source():
    """Le menu ne doit plus porter l'ancienne entrée séparée."""
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    entries = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(x, "id", "") == "_NAV_SECTIONS" for x in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
                    a, b = sub.elts
                    if (isinstance(a, ast.Constant) and isinstance(b, ast.Constant)
                            and isinstance(b.value, str)):
                        entries.append((a.value, b.value))
    keys = [k for _lbl, k in entries]
    assert "upload_csv" not in keys, (
        "l'entrée de menu séparée pour l'import CSV est revenue : deux entrées pour "
        "un seul geste (« connecter mes sources ») se cherchent")
    creds = [lbl for lbl, k in entries if k == "credentials"]
    assert creds and "CSV" in creds[0], (
        f"l'entrée Credentials ne dit pas qu'elle porte aussi les imports : {creds}")
