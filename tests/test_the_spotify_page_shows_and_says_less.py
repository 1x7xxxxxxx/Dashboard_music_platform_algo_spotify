"""Ce que la page Spotify montre, et ce qu'elle a cessé de dire.

Type: Guard
Uses: ast
Depends on: views/spotify_s4a_combined.py, views/data_wrapped.py
Persists in: nothing

DOUZE DEMANDES D'ÉCRAN — 2026-09-22
------------------------------------
Formulées en regardant la page. Elles se ramènent à deux règles :

  1. **une figure porte son sens elle-même** — son titre, ses libellés de série, son
     axe. Une phrase sous la figure qui redit ce que la légende contient est du bruit,
     et six lignes de réserve sous une figure de deux courbes ne se lisent pas.
  2. **ce qu'on lit ensemble se met côte à côte** — sorties/audience, puis
     ce-qui-bouge/détail, puis les trois figures du bilan annuel.

⚠️ POURQUOI UN GARDE SUR DES SUPPRESSIONS. Une légende retirée revient, parce que la
prochaine personne qui touche la figure aura un scrupule légitime : « il faudrait
expliquer ce que veut dire auditeur-jour ». Le scrupule est bon, la réponse est
ailleurs — dans le libellé de la série et l'unité de l'axe, qui suivent la figure
partout où elle va. Ce fichier écrit la décision pour qu'elle se discute au lieu de se
défaire en silence.

CE QU'IL NE TIENT PAS
---------------------
* **Que la page soit LISIBLE.** Il vérifie l'absence de ce qui a été retiré et la
  présence des colonnes ; qu'elle se lise bien se voit à l'œil.
* **Le geste voisin le plus proche : les autres réserves de la page.** Trois légendes
  survivent (première écoute, deux horloges, Wrapped) parce qu'elles disent quelque
  chose qu'aucune figure ne porte. Rien ici ne les protège d'une suppression.
* **La position des colonnes à l'écran.** `st.columns` place côte à côte sur un écran
  large et empile sur un téléphone ; ce garde lit la STRUCTURE, pas le rendu.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SPOTIFY = _ROOT / "src" / "dashboard" / "views" / "spotify_s4a_combined.py"
_WRAPPED = _ROOT / "src" / "dashboard" / "views" / "data_wrapped.py"


def _chaines(path: pathlib.Path) -> list[str]:
    """Les chaînes qui peuvent ATTEINDRE UN ÉCRAN — ni commentaire, ni docstring.

    ⚠️ DEUX EXCLUSIONS, ET CHACUNE A COÛTÉ UN ROUGE OU AURAIT DÛ.

    Les COMMENTAIRES sont invisibles à l'AST par construction, et c'est voulu : le
    fichier gardé porte huit blocs qui EXPLIQUENT chaque suppression, en citant le
    texte retiré. Un prédicat textuel aurait rougi sur la prose du correctif —
    `a-bash-hook-that-blocks-the-prose-about-the-gesture`, trois commandes bloquées
    d'affilée sur ce dépôt le 2026-09-12.

    Les DOCSTRINGS ne le sont pas, et mon premier jet s'y est pris : le docstring de
    module commence par « Page Spotify & Spotify for Artists — une figure par
    décision », donc le garde du titre retiré rougissait sur la description de la page
    qu'il garde. Un docstring parle du code ; il n'atteint aucun écran.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)) and n.body:
            premier = n.body[0]
            if (isinstance(premier, ast.Expr)
                    and isinstance(premier.value, ast.Constant)
                    and isinstance(premier.value.value, str)):
                docs.add(id(premier.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def _appels(path: pathlib.Path, attr: str) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == attr]


# ══════════════════════════════════════════════════════════════════════════
# NON-VACUITÉ
# ══════════════════════════════════════════════════════════════════════════

def test_the_page_still_draws_and_still_speaks() -> None:
    """Une page vidée rendrait toutes les absences ci-dessous vraies pour rien."""
    figures = _appels(_SPOTIFY, "plotly_chart")
    assert len(figures) >= 5, f"seulement {len(figures)} figures — la page a fondu"
    legendes = _appels(_SPOTIFY, "caption")
    assert len(legendes) >= 2, (
        f"seulement {len(legendes)} légendes : les trois réserves qui DEVAIENT rester "
        "(première écoute, deux horloges, Wrapped) ont disparu avec les autres.")


# ══════════════════════════════════════════════════════════════════════════
# 1. CE QUI A ÉTÉ RETIRÉ DE L'ÉCRAN
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("fragment,quoi", [
    ("Spotify & Spotify for Artists", "le titre de page — le menu le porte déjà"),
    ("Je gagne des auditeurs", "le sous-titre d'audience — la figure le MONTRE"),
    ("Auditeurs (dernier mois complet)", "la jauge d'auditeurs — dernier point de la série"),
    ("Écoutes par auditeur-jour", "la jauge de ratio — dernier point de la série"),
    ("premiers jours", "la légende d'horizon — l'axe des abscisses le porte"),
    ("veille", "la note d'artefact de fuseau — 2 écoutes sur ce catalogue"),
    ("un auditeur unique compté une fois", "l'explication d'auditeur-jour"),
    ("Barre pleine", "la légende des barres — la légende de la figure les nomme"),
])
def test_a_removed_line_stays_removed(fragment: str, quoi: str) -> None:
    """Chacune était JUSTE, et personne ne les lisait."""
    fautifs = [c for c in _chaines(_SPOTIFY) if fragment in c]
    assert not fautifs, (
        f"« {fragment} » est revenu à l'écran ({quoi}) :\n"
        + "\n".join(f"    {c[:100]!r}" for c in fautifs)
        + "\n\nRetiré le 2026-09-22 en regardant la page. Si le sens manque, il va dans "
          "le TITRE de la figure, le libellé de sa série ou l'unité de son axe — qui "
          "la suivent partout, alors qu'une phrase en dessous dépend de la mise en page.")


def test_the_page_has_no_title_of_its_own() -> None:
    """Le menu porte le nom et reste surligné : le titre le répétait à un centimètre."""
    assert not _appels(_SPOTIFY, "title"), (
        "`st.title` est revenu sur cette page. L'entrée de menu « 🎵 Spotify + Spotify "
        "for Artists » reste surlignée pendant tout le rendu ; le titre mangeait la "
        "hauteur du premier écran pour le redire.")


def test_the_dead_counters_went_with_their_caption() -> None:
    """`excluded` et `without_pi` ne nourrissaient QUE la légende retirée.

    Un calcul qui n'alimente plus rien pourrit — ce dépôt a payé « une couche
    débranchée pourrit » et « du code mort cache une conséquence vivante ».
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    noms = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)}
    for mort in ("excluded", "without_pi"):
        assert mort not in noms, (
            f"`{mort}` est revenu : il ne servait qu'à écrire la légende retirée le "
            "2026-09-22, et un calcul sans lecteur est du code mort.")


# ══════════════════════════════════════════════════════════════════════════
# 2. CE QUI EST CÔTE À CÔTE, ET CE QUI EST PERMANENT
# ══════════════════════════════════════════════════════════════════════════

def test_the_detail_is_permanent_not_a_drawer() -> None:
    """« Ouvert par défaut » et « permanent » sont DEUX choses.

    Le bloc était `secondary_analyses(expanded=True)` depuis le 2026-09-21 : ouvert à
    l'écran, et **refermable** — un `st.expander` l'est par construction, donc un clic
    malheureux cachait le détail et rien ne le rouvrait. Demandé le 2026-09-22 : « sans
    possibilité de refermer le bandeau : le rendre permanent ».
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_render_secondary"), None)
    assert fn is not None, "`_render_secondary` a disparu"
    tiroirs = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
               and (getattr(n.func, "id", None) == "secondary_analyses"
                    or getattr(n.func, "attr", None) == "expander")]
    assert not tiroirs, (
        "le détail est redevenu un tiroir. Un `st.expander` reste refermable : "
        "« ouvert par défaut » ne répond pas à la demande, qui est « permanent ».")


def test_what_is_read_together_sits_together() -> None:
    """Trois paires côte à côte, chacune une question posée de deux côtés."""
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "show"), None)
    assert fn is not None, "`show()` a disparu"
    colonnes = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "columns"]
    assert len(colonnes) >= 2, (
        f"seulement {len(colonnes)} `st.columns` dans `show()` : sorties/audience et "
        "ce-qui-bouge/détail ne sont plus côte à côte.")
    appels = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
    for f in ("_render_momentum", "_render_secondary"):
        assert f in appels, f"`{f}` n'est plus appelée depuis `show()`"


def test_the_three_wrapped_charts_share_one_row() -> None:
    """Volumes, pays et heures racontent la même année : on les lit d'un regard."""
    tree = ast.parse(_WRAPPED.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_tab_charts"), None)
    assert fn is not None, "`_tab_charts` a disparu"
    trois = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "columns"
             and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 3]
    assert trois, (
        "les trois figures du bilan annuel ne partagent plus une rangée : "
        "`st.columns(3)` a disparu de `_tab_charts`.")


# ══════════════════════════════════════════════════════════════════════════
# 3. LE BILAN ANNUEL
# ══════════════════════════════════════════════════════════════════════════

def test_the_wrapped_is_named_by_what_it_is() -> None:
    """« Data Wrapped » était le nom du FICHIER, pas celui de la chose."""
    for path in (_WRAPPED, _SPOTIFY):
        bons = [c for c in _chaines(path) if "Spotify Wrapped (bilan annuel)" in c]
        if path is _WRAPPED or any("wrapped_header" in c for c in _chaines(path)):
            assert bons, (
                f"{path.name} ne porte plus « Spotify Wrapped (bilan annuel) ».")
    assert not [c for c in _chaines(_WRAPPED) if "Data Wrapped — Bilan" in c], (
        "« Data Wrapped — Bilan » est revenu : c'était le nom du fichier.")


def test_no_artist_question_when_the_answer_is_forced() -> None:
    """Quatre sélecteurs demandaient à un artiste de choisir entre lui-même et rien.

    `_artiste()` n'affiche le sélecteur QUE s'il y a plusieurs options — il survit donc
    pour l'admin, qui voit toute la flotte sur la route autonome.
    """
    tree = ast.parse(_WRAPPED.read_text(encoding="utf-8"))
    helper = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                   and n.name == "_artiste"), None)
    assert helper is not None, (
        "`_artiste()` a disparu : les sélecteurs d'artiste redemandent un choix forcé.")
    # Le sélecteur ne s'ouvre qu'au-delà d'une option : la borne est dans le helper.
    assert any(isinstance(n, ast.Compare) for n in ast.walk(helper)), (
        "`_artiste()` ne compare plus le nombre d'options : il affiche toujours, ou "
        "jamais, et les deux sont faux.")
    for cle in ("form_artist", "chart_artist", "del_artist"):
        direct = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and getattr(n.func, "attr", None) == "selectbox"
                  and any(isinstance(k.value, ast.Constant) and k.value.value == cle
                          for k in n.keywords if k.arg == "key")]
        hors_helper = [n for n in direct
                       if not (helper.lineno <= n.lineno <= (helper.end_lineno or 0))]
        assert not hors_helper, (
            f"un `st.selectbox` d'artiste (`key={cle}`) est revenu hors de `_artiste()` "
            "— il redemande un choix que le compte a déjà fait.")


def test_the_delete_sits_last_and_stays_folded() -> None:
    """Un geste irréversible ne se met pas sur le chemin d'un geste de création.

    Il vivait sous le formulaire de saisie : il fallait passer devant lui pour
    atteindre les courbes. En bas, l'ordre raconte — je saisis, je regarde, je corrige.
    Et il reste REPLIÉ : c'est le seul geste irréversible de la page.
    """
    # ⚠️ `brut` ET NON `src` : le nom compte. `test_a_guard_reads_structure_not_text`
    # travaille par NOM DE VARIABLE — dès qu'un `src` est assigné depuis un `read_text`
    # sur un `.py`, TOUTE comparaison de chaîne contre un `src` du même fichier est
    # signalée, y compris celle qui lit `code_of()` vingt lignes plus bas. Il a raison
    # de travailler ainsi : l'inverse — exempter le fichier entier — est le défaut qu'il
    # a lui-même payé le 2026-09-04. Deux lectures différentes prennent donc deux noms.
    brut = _WRAPPED.read_text(encoding="utf-8")
    tree = ast.parse(brut)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_render_wrapped_body"), None)
    assert fn is not None, "`_render_wrapped_body` a disparu"
    suppr = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_delete_wrapped"]
    charts = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "_tab_charts"]
    assert suppr and charts, f"suppression={suppr} charts={charts}"
    assert min(suppr) > max(charts), (
        f"la suppression (ligne {min(suppr)}) précède les courbes (ligne {max(charts)}) : "
        "un geste irréversible est de nouveau sur le chemin de la lecture.")
    plies = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "expander"]
    assert plies, (
        "la suppression n'est plus dans un `st.expander` : le seul geste irréversible "
        "de la page est à un clic de distance de zéro.")


def test_the_recap_table_is_gone_but_the_ranked_one_stays() -> None:
    """Le récap redisait en chiffres ce que les courbes montrent en formes.

    ⚠️ Le petit tableau des super-fans SURVIT, et c'est la moitié qui compte : il porte
    `top_fans_rank`, que AUCUNE figure ne dessine. Supprimer les deux aurait perdu une
    donnée, pas une redondance.
    """
    # ⚠️ `code_of()` ET NON `read_text()`, et c'est un garde du dépôt qui l'a exigé.
    # `test_a_presence_assertion_is_not_satisfied_by_prose` a refusé mon premier jet :
    # j'affirmais `"top_fans_rank" in src` sur le texte BRUT du fichier, et mon propre
    # commentaire dans `data_wrapped.py` cite ce nom pour expliquer pourquoi le tableau
    # survit. L'assertion serait donc restée VERTE le jour où le code perdrait la
    # colonne — la prose du correctif garantissant le correctif. `code_of` retire
    # commentaires et docstrings.
    from tests.code_text import code_of

    src = code_of(_WRAPPED)
    tableaux = [n for n in ast.walk(ast.parse(_WRAPPED.read_text(encoding="utf-8")))
                if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "dataframe"]
    assert len(tableaux) == 1, (
        f"{len(tableaux)} `st.dataframe` dans cette vue. Un seul doit rester — celui "
        "des super-fans, qui porte le rang. Le récap de treize colonnes a été retiré "
        "le 2026-09-22 : chacune de ses colonnes est déjà une courbe.")
    assert "top_fans_rank" in src, (
        "la colonne de rang a disparu du CODE : c'est la seule donnée que le tableau "
        "survivant apporte et qu'aucune figure ne montre.")


# ══════════════════════════════════════════════════════════════════════════
# 4. LA FIGURE D'ENGAGEMENT — trois séries, deux natures, deux axes
# ══════════════════════════════════════════════════════════════════════════

def test_saves_playlists_and_followers_share_one_figure() -> None:
    """Demandé le 2026-09-22 : les trois sur le même graphique.

    C'étaient deux figures empilées (`_saves_fig`, `_followers`).
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    noms = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_engagement_fig" in noms, (
        "`_engagement_fig` a disparu : les trois séries ne partagent plus une figure.")
    for ancien in ("_saves_fig", "_followers"):
        assert ancien not in noms, (
            f"`{ancien}` est revenu : les deux figures se sont resséparées.")


def test_the_followers_level_never_shares_an_axis_with_a_monthly_flow() -> None:
    """DEUX NATURES, DEUX AXES — et ce n'est pas une question de forme.

    Sauvegardes et ajouts en playlist sont des FLUX mensuels (« combien ce mois-ci »).
    Les abonnés sont un NIVEAU quotidien (« combien en tout, aujourd'hui »). Sur la même
    échelle, un niveau se lit comme un flux : c'est `un-cumul-pris-pour-un-quotidien`,
    la famille qui a coûté le plus cher à ce dépôt sur les figures.
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None, "`_engagement_fig` a disparu"
    # ⚠️ SUR LE TRACÉ, PAS SUR LE TEXTE DE LA FONCTION. Mon premier jet cherchait
    # `"secondary_y=True" in src` : il restait vrai parce que `update_yaxes` porte le
    # même mot-clé pour TITRER l'axe. Déplacer la série sur l'axe principal laissait
    # donc le test VERT — trouvé en mutant. C'est
    # `a-sweep-predicate-that-matches-a-form-not-a-property`, commis une fois de plus.
    #
    # La propriété se lit sur les APPELS : chaque `add_trace` déclare de quel côté il
    # va, et on vérifie que les barres et la ligne ne vont pas du même.
    cotes = {}
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "add_trace" and n.args):
            continue
        forme = getattr(getattr(n.args[0], "func", None), "attr", None)  # Bar / Scatter
        sec = next((k.value for k in n.keywords if k.arg == "secondary_y"), None)
        if forme and isinstance(sec, ast.Constant):
            cotes.setdefault(forme, set()).add(bool(sec.value))
    assert cotes.get("Bar") == {False}, (
        f"les flux mensuels ne sont plus tous sur l'axe principal : {cotes}")
    assert cotes.get("Scatter") == {True}, (
        f"les abonnés ne sont plus sur l'axe SECONDAIRE : {cotes}. Un NIVEAU quotidien "
        "sur la même échelle qu'un flux mensuel se lit comme un flux — "
        "`un-cumul-pris-pour-un-quotidien`.")


def test_the_followers_are_identifiable_without_colour() -> None:
    """La couleur ne suffit pas pour qui ne la voit pas : TROIS distinctions.

    L'encre `_FOLLOWER_INK` est mesurée (ΔE 65 en CIELAB contre la plus proche des cinq
    encres de la page), mais ce ΔE est mesuré en vision NORMALE — la deutéranopie n'a
    pas été simulée. Ce sont donc les distinctions NON chromatiques qui portent la
    lecture : l'axe de droite, son titre teinté, et barres contre ligne.
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None
    src = ast.unparse(fn)
    assert "title_font" in src and "_FOLLOWER_INK" in src, (
        "le titre de l'axe des abonnés n'est plus teinté de l'encre de sa série : deux "
        "échelles se lisent alors comme une, et c'est là que naît le faux croisement.")
    assert "go.Bar" in src and "go.Scatter" in src, (
        "les flux et le niveau n'ont plus deux FORMES : la distinction repose alors sur "
        "la seule couleur.")


def test_the_two_follower_sources_are_never_spliced() -> None:
    """Le CSV s'arrête au dernier import, l'API court au jour le jour.

    Les coller ferait passer un changement de source pour une inflexion. La LÉGENDE qui
    l'expliquait a été retirée le 2026-09-22 sur demande — c'est donc le TRAIT qui le dit
    maintenant : plein pour l'API qui mesure tous les jours, pointillé pour le CSV qui
    s'arrête. Sans ce trait, la suppression de la légende aurait perdu le fait.
    """
    tree = ast.parse(_SPOTIFY.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None
    src = ast.unparse(fn)
    assert "groupby" in src and "source" in src, (
        "les abonnés ne sont plus groupés par SOURCE : les deux séries sont raboutées, "
        "et un changement de source se lit comme une inflexion.")
    # ⚠️ LE TRAIT DOIT ÊTRE CONDITIONNEL, pas simplement présent. Mon premier jet
    # cherchait `"dash" in src` : remplacer `dash="dot" if csv else "solid"` par
    # `dash="solid"` laissait le test VERT alors que les deux sources devenaient
    # indistinguables. Trouvé en mutant — une propriété, pas un mot.
    conditionnels = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.keyword) and n.arg == "dash"
        and isinstance(n.value, ast.IfExp)]
    assert conditionnels, (
        "le trait des abonnés n'est plus CONDITIONNEL : les deux sources se dessinent "
        "pareil. La légende « Deux sources, deux horloges » a été retirée le "
        "2026-09-22 — c'est le trait qui porte le fait, et sans lui il est perdu.")


@pytest.mark.parametrize("fragment", [
    "Deux sources, deux horloges",
    "Série démarrée à la **première écoute**",
    "indice de popularité** est relevé par l'API tous les",
])
def test_the_form_explaining_captions_stay_removed(fragment: str) -> None:
    """Elles expliquaient la FORME à quelqu'un qui voulait lire le CONTENU."""
    fautifs = [c for c in _chaines(_SPOTIFY) if fragment in c]
    assert not fautifs, (
        f"« {fragment} » est revenu à l'écran. Retiré le 2026-09-22 : ce que la phrase "
        "disait est porté par la figure elle-même — le trait pour les deux sources, "
        "l'axe pour les deux natures.")


def test_the_absence_that_names_a_gesture_survives() -> None:
    """LA MOITIÉ QUI COMPTE, et elle n'est pas négociable.

    `pi_missing` n'est pas une paraphrase : il dit une ABSENCE et nomme le GESTE qui la
    lève. Une absence muette se lit comme un zéro, et un artiste ne peut pas deviner
    qu'il doit rattacher un titre.
    """
    gardees = [c for c in _chaines(_SPOTIFY)
               if "Aucun indice de popularité" in c]
    assert gardees, (
        "la phrase d'absence d'indice de popularité a disparu avec les autres. Elle "
        "nomme un GESTE — « le rattachement se fait depuis 🔗 Mapping cross-plateforme » "
        "— et c'est la seule forme de texte que ce dépôt tient pour non négociable.")
    assert any("Mapping" in c for c in gardees), (
        "elle ne nomme plus la page où agir : c'est le geste qui la rend utile.")
