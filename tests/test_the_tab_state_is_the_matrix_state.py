"""L'état montré dans un onglet est CELUI de la matrice, pas une seconde opinion.

Type: Test
Uses: status_matrix (AST + fonctions pures), credentials/_render
Depends on: src/dashboard/utils/status_matrix.py,
    src/dashboard/views/credentials/_render.py
Persists in: nothing

Ce que remplacent les pastilles
--------------------------------
« Valeur enregistrée le 05/09/2026 03:49 — enregistrée ne veut pas dire vérifiée :
c'est le test ci-dessous qui le dit. » La phrase disait la bonne chose et la disait
mal : une ligne de prose pour une nuance que la couleur montre, répétée sous chaque
onglet. Demandé le 2026-09-05 : « mets uniquement des états vert orange rouge très
petit que pour l'onglet sélectionné, copié de l'onglet état de tes plateformes ».

« Copié de » au pied de la lettre
----------------------------------
Le risque de cette demande est d'en écrire une deuxième version. Deux surfaces qui
décrivent le même état avec deux codes couleur produisent un désaccord qu'AUCUNE des
deux ne peut voir — le dépôt l'a payé sur la fraîcheur, sur les compteurs publics, et
sur la durée de mise en route. Ce fichier vérifie que ce sont les MÊMES fonctions.
"""
from __future__ import annotations

import ast
import re as _re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MATRIX = _ROOT / "src" / "dashboard" / "utils" / "status_matrix.py"
_RENDER = _ROOT / "src" / "dashboard" / "views" / "credentials" / "_render.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(f for f in ast.walk(tree)
                if isinstance(f, ast.FunctionDef) and f.name == name)


def test_the_tab_state_reuses_the_matrix_cells():
    """`_box` et `_responds_cell`, pas des jumelles."""
    fn = _fn(_MATRIX, "render_platform_state")
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    # `row_cells` depuis le 2026-09-05 : c'est elle qui porte les quatre états, et
    # `_shape_cell` / `_responds_cell` sont devenues ses détails. Exiger les appels
    # DIRECTS ferait rougir la factorisation qu'on vient de faire — un garde ancré sur
    # le chemin d'appel argumente contre le refactor qui le simplifie.
    for helper in ("_box", "row_cells", "artist_readiness"):
        assert helper in called, (
            f"`render_platform_state` n'appelle plus `{helper}` : il porterait sa "
            "propre idée de l'état, et deux surfaces diraient deux choses du même "
            "fait sans qu'aucune puisse le voir")


def test_the_colours_are_defined_once():
    """Un seul jeu de couleurs dans le dépôt pour cet état."""
    src = _MATRIX.read_text(encoding="utf-8")
    tree = ast.parse(src)
    # `_GREEN, _RED, _GREY, _AMBER = …` est une affectation par TUPLE : la cible
    # n'est pas un `Name` mais un `Tuple` de `Name`. Chercher `_GREEN` parmi les
    # cibles directes rendait 0 — un garde qui compte zéro et exige un est rouge sur
    # du code juste, ce qui est la façon la plus rapide de se faire désarmer.
    palettes = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(getattr(x, "id", "") == "_GREEN"
                        for t in n.targets for x in ast.walk(t))]
    assert len(palettes) == 1, (
        "la palette est définie plusieurs fois : deux verts qui divergent d'un ton "
        "sont deux verdicts qui divergent")

    # Les CHAÎNES de l'arbre, pas le texte : le cliquet
    # `test_a_guard_reads_structure_not_text` a refusé la version textuelle — pour la
    # cinquième fois de la journée, et il a raison : un code couleur cité dans un
    # commentaire (« la matrice utilise #28a745 ») rendrait ce garde rouge sur du code
    # juste.
    literals = {n.value for n in ast.walk(ast.parse(_RENDER.read_text(encoding="utf-8")))
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    # Un vrai code hexadécimal, pas « ### » : la première version comptait la
    # longueur et le `#` initial, et accusait un titre markdown. Un prédicat qui
    # hurle sur ce qu'il ne vise pas se fait désarmer — troisième fois de la journée.
    hard = {x for x in literals
            if _re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", x)}
    assert not hard, (
        f"la page de saisie code des couleurs en dur ({sorted(hard)}) au lieu de "
        "passer par la matrice")


def test_the_tab_shows_the_state_and_not_the_sentence():
    """La phrase est partie ; l'état la remplace, dans le même onglet."""
    fn = _fn(_RENDER, "_render_platform_tab")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "render_platform_state" in called, (
        "l'onglet ne montre plus l'état de sa plateforme")

    literals = [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any("ne veut pas dire vérifiée" in x for x in literals), (
        "la phrase est revenue : elle explique en prose ce que la couleur montre")


def test_it_shows_only_the_platforms_of_that_tab():
    """Un onglet peut porter DEUX lignes — Meta et Instagram — et c'est voulu.

    Elles se saisissent au même endroit et échouent séparément : Instagram peut être
    muet pendant que Meta Ads répond. Filtrer sur la clé d'onglet, et non sur la clé
    logique, est donc obligatoire — c'est la traduction qui a déjà produit deux
    défauts dans ce dépôt quand on l'a oubliée d'un côté.
    """
    fn = _fn(_MATRIX, "render_platform_state")
    called = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "platform_destination" in called, (
        "le filtre ne passe plus par `platform_destination` : un onglet montrerait "
        "l'état d'une plateforme qui ne s'y saisit pas, ou raterait Instagram")


def test_a_broken_read_shows_nothing_instead_of_raising():
    """Décoratif : une pastille absente ne doit jamais fermer la page de saisie."""
    class _Boom:
        def fetch_df(self, *a, **k):
            raise RuntimeError("db down")

        def fetch_query(self, *a, **k):
            raise RuntimeError("db down")

    from src.dashboard.utils.status_matrix import render_platform_state

    render_platform_state(_Boom(), 1, "spotify")     # ne doit pas lever


# ── Les QUATRE colonnes, et la page qui devient redondante ──────────────────

def test_the_tab_shows_every_column_of_the_matrix():
    """Saisi · Format · Répond · Données — les quatre, pas un résumé.

    Demandé le 2026-09-05 : « intègre les indicateurs verts orange rouge sur toutes
    les colonnes ». Les deux premières versions n'en montraient que deux (Format et
    Répond), ce qui est un résumé, donc une troisième opinion : « Saisi » et
    « Données » répondent à des questions différentes — la valeur est-elle là, et
    des lignes sont-elles arrivées.

    Mesuré sur SoundCloud : Saisi ✅ vert · Format ✅ vert · Répond 🟠 · Données 🔴.
    """
    from src.dashboard.utils.status_matrix import _COLUMN_TITLES, row_cells

    assert _COLUMN_TITLES == ("Saisi", "Format", "Répond", "Données"), (
        f"les colonnes ont changé : {_COLUMN_TITLES}")

    row = {"key": "soundcloud", "label": "☁️ SoundCloud", "status": "no_data",
           "icon": "🔴", "status_label": "Connecté — aucune donnée"}
    cells = row_cells(row, {}, {})
    assert len(cells) == len(_COLUMN_TITLES), (
        "le nombre de pastilles ne correspond plus au nombre de colonnes : "
        "l'étiquette sous chaque pastille nommerait la mauvaise")
    for state, glyph, tip in cells:
        assert state in ("green", "amber", "red", "grey"), state
        assert glyph and tip, "une pastille sans glyphe ou sans infobulle est un carré muet"


def test_the_matrix_row_is_computed_in_one_place():
    """La matrice et l'onglet appellent `row_cells` — pas deux copies de la règle.

    Elle vivait dans la boucle d'affichage de `render_status_matrix`. La recopier
    dans l'onglet aurait donné deux verdicts pour un même fait, et le partage de
    `_box` seul ne l'aurait pas empêché : ce sont les ÉTATS qui doivent être calculés
    une fois, pas seulement leur mise en forme.
    """
    src = _MATRIX.read_text(encoding="utf-8")
    tree = ast.parse(src)
    callers = {f.name for f in ast.walk(tree)
               if isinstance(f, ast.FunctionDef)
               and any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "row_cells"
                       for n in ast.walk(f))}
    assert {"render_platform_state", "render_status_matrix"} <= callers, (
        f"`row_cells` n'est appelée que par {sorted(callers)} : l'autre surface "
        "recalcule les états, et les deux peuvent diverger sans que rien ne le voie")


def test_the_status_page_left_the_menu_but_not_the_router():
    """Redondante au menu, pas supprimée : des liens la visent.

    « Supprime l'onglet (ou archive) état des plateformes car c'est redondant » —
    exact depuis que chaque onglet porte les quatre pastilles de SA plateforme. Mais
    la matrice complète reste la seule vue qui montre les six sources d'un coup, et
    des messages y renvoient : retirer la ROUTE transformerait ces renvois en
    culs-de-sac, ce que ce dépôt a payé six fois en une séance.
    """
    app = (_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app)

    entries = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(x, "id", "") == "_NAV_SECTIONS" for x in node.targets):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
                    a, b = sub.elts
                    if isinstance(b, ast.Constant) and isinstance(b.value, str):
                        entries.append(b.value)
    assert entries, "la lecture du menu a cassé — ce garde ne prouverait rien"
    assert "platform_status" not in entries, (
        "la page d'état est revenue au menu : chaque onglet montre déjà les quatre "
        "pastilles de sa plateforme, là où l'on agit")

    routed = {n.comparators[0].value for n in ast.walk(tree)
              if isinstance(n, ast.Compare) and getattr(n.left, "id", "") == "page"
              and n.comparators and isinstance(n.comparators[0], ast.Constant)}
    assert "platform_status" in routed, (
        "la ROUTE a disparu avec l'entrée de menu : les messages qui y renvoient ne "
        "mènent plus nulle part")


# ── Une mesure bat une prédiction ───────────────────────────────────────────

def test_a_failing_probe_yields_to_data_that_actually_landed():
    """« J'ai les barres vertes alors que ça ne marche pas » — les barres avaient raison.

    Vérifié en production le 2026-09-05 : la sonde SoundCloud lit
    `/users/{id}/tracks` avec le jeton d'application et conclut « aucun titre public —
    il n'y aura donc rien à collecter ». Le collecteur avait ramené **17 titres le
    matin même** pour ce locataire, et `soundcloud_tracks_daily` les portait.

    Les deux lisent le même compte et se contredisent. La sonde affirme une
    CONSÉQUENCE qu'elle ne peut pas connaître ; la collecte l'a démentie. Une mesure
    qui a réellement eu lieu bat une prédiction.

    Le message n'est pas effacé — il peut nommer un vrai problème — il devient un
    avertissement, sous le fait qui le contredit.
    """
    render = _RENDER.read_text(encoding="utf-8")
    tree = ast.parse(render)

    helper = next((f for f in ast.walk(tree)
                   if isinstance(f, ast.FunctionDef) and f.name == "_data_already_landed"),
                  None)
    assert helper is not None, (
        "rien ne réconcilie plus la sonde et la donnée : un test qui échoue "
        "affichera « rien à collecter » à côté de lignes déjà collectées")

    called = {getattr(n.func, "id", "") for n in ast.walk(helper) if isinstance(n, ast.Call)}
    assert "artist_readiness" in called, (
        "la réconciliation n'interroge plus `artist_readiness` : elle porterait sa "
        "propre idée de « des données sont arrivées », et les pastilles diraient "
        "autre chose")

    # ÉLARGI le 2026-09-05. La version d'origine cherchait un appel « quelque part
    # dans `_render_platform_tab` » et `assert uses` — donc UN SEUL appel suffisait.
    # Il y en avait un, sous le bouton « Tester ». Le verdict d'ENREGISTREMENT, que
    # l'artiste voit sans rien cliquer, n'en avait pas : il a affiché « ❌ … ne
    # répond pas encore » à côté de 358 lignes réellement collectées. La question
    # n'est pas « est-ce utilisé ? » mais « CHAQUE surface qui rend un verdict de
    # sonde le consulte-t-elle ? ».
    #
    # Chaque nom listé rend un verdict issu de `probes` / `VERDICT_KEY`. Ajouter une
    # troisième surface sans la réconciliation fait rougir ce test, pas la prod.
    _VERDICT_SURFACES = ("_render_platform_tab", "render_save_verdict")
    for name in _VERDICT_SURFACES:
        fn = next((f for f in ast.walk(tree)
                   if isinstance(f, ast.FunctionDef) and f.name == name), None)
        assert fn is not None, f"{name} a disparu — la liste des surfaces est périmée"
        uses = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "_data_already_landed"]
        assert uses, (
            f"{name} rend un verdict de sonde sans demander si des données sont "
            "arrivées : il contredira les pastilles, qui lisent la même source")


def test_the_platform_name_is_written_only_when_two_rows_share_a_tab():
    """Une seule ligne : l'onglet sélectionné dit déjà de quoi il parle.

    Deux lignes : c'est Meta / Instagram, deux sources qui se saisissent au même
    endroit et échouent SÉPARÉMENT — Instagram peut être muet pendant que Meta Ads
    répond. Là, le nom est la seule chose qui distingue les deux séries de pastilles.
    """
    fn = next(f for f in ast.walk(ast.parse(_MATRIX.read_text(encoding="utf-8")))
              if isinstance(f, ast.FunctionDef) and f.name == "render_platform_state")
    guarded = [n for n in ast.walk(fn) if isinstance(n, ast.If)
               and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "len"
                       for c in ast.walk(n.test))]
    assert guarded, (
        "le nom de la plateforme est écrit sans condition : il redit l'onglet "
        "sélectionné sur les quatre onglets qui n'ont qu'une source")
