"""Une plateforme a UNE couleur, et le nombre de copies ne peut que descendre.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/**, src/dashboard/utils/platform_colors.py
Persists in: nothing

Ce que la mesure a rendu, le 2026-09-21
----------------------------------------
La palette de plateformes était MESURÉE — balayage sur ~1,7 M de combinaisons,
CIEDE2000, simulation deutan/protan — et elle vivait à l'intérieur de
`platform_chart.py`, le module qui dessine UNE figure. Toute autre surface
écrivait donc ses couleurs à la main.

Compté par l'AST, docstrings exclues : **42 constantes de marque en dur, dans
18 fichiers.** Dont **36 pour le seul vert `#1DB954`** — c'est-à-dire la couleur
de marque exacte de Spotify, celle que la mesure du 2026-09-08 a précisément
REFUSÉE (`youtube ↔ soundcloud` à ΔE 4,6 en deutéranopie avec les teintes de
marque).

Ce n'est pas un défaut de style. Le vert « Spotify » de l'accueil et celui d'une
autre page ne sont pas le même vert, et un artiste qui passe de l'une à l'autre
n'a aucune raison de comprendre que les deux parlent de la même plateforme.

Pourquoi un CLIQUET et pas un interdit
---------------------------------------
Migrer 42 sites en une passe est un changement que personne ne peut relire, et
`code-critic` a déjà refusé exactement ça pour `semantic_colors` (R133,
BUILD-MODIFIED, condition explicite : « ne pas migrer les figures existantes en
une passe »). On gèle le compte du jour ; il ne peut que descendre. C'est le
mécanisme qui a fait passer les gardes textuels de 32 à 21 et les axes
secondaires de 12 à 0.

Ce que ce fichier NE tient PAS, et il faut le dire : il compte des constantes
littérales. Une couleur calculée, lue dans un thème ou passée en argument lui est
invisible. Il attrape la forme qui a produit les 42 — `marker_color="#1DB954"` —
pas toutes les façons imaginables d'écrire une couleur.
"""
from __future__ import annotations

import ast
import collections
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_DASH = _ROOT / "src" / "dashboard"

# Les teintes de MARQUE, celles qu'on écrit de mémoire. La clé est la couleur
# telle qu'on la tape ; la valeur nomme la plateforme, pour que le message dise
# quoi importer à la place.
_MARQUES = {
    "#1db954": "spotify", "#1ed760": "spotify", "#00d166": "spotify",
    "#ff0000": "youtube", "#cc0000": "youtube",
    "#ff5500": "soundcloud",
    "#fa243c": "apple", "#ff2d55": "apple",
    "#0866ff": "meta", "#1877f2": "meta", "#4267b2": "meta",
    "#e1306c": "instagram",
}

# Gelé le 2026-09-21 par la mesure ci-dessus. CE NOMBRE NE PEUT QUE DESCENDRE.
_PLAFOND = 42

# Le module qui PORTE la palette écrit forcément ces valeurs : c'est sa raison
# d'être. L'exemption est nominative — un fichier ajouté à côté rougit.
_PORTEURS = {"platform_colors.py"}


def _docstrings(arbre: ast.AST) -> set[int]:
    out = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = getattr(n, "body", None)
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                out.add(id(corps[0].value))
    return out


def _compte() -> collections.Counter:
    """Les constantes de marque par fichier — docstrings EXCLUES.

    Par l'AST et non par le texte : ce fichier-ci, et `platform_colors.py`,
    CITENT ces couleurs dans leur prose pour expliquer pourquoi elles sont
    refusées. Un garde textuel s'accuserait lui-même — c'est arrivé trois fois
    dans ce dépôt, dont deux fois le 2026-09-21.
    """
    out: collections.Counter = collections.Counter()
    for p in sorted(_DASH.rglob("*.py")):
        if "__pycache__" in str(p) or p.name in _PORTEURS:
            continue
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover
            continue
        docs = _docstrings(arbre)
        for n in ast.walk(arbre):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and id(n) not in docs and n.value.strip().lower() in _MARQUES:
                out[str(p.relative_to(_DASH))] += 1
    return out


def test_no_new_hardcoded_platform_colour() -> None:
    """Le cliquet. 42 le 2026-09-21."""
    compte = _compte()
    total = sum(compte.values())
    assert total <= _PLAFOND, (
        f"{total} couleur(s) de plateforme en dur contre un plafond de {_PLAFOND}.\n"
        "Une couleur recopiée est une DÉFINITION qui diverge : le vert de l'accueil "
        "et celui d'une autre page cessent d'être le même vert, et rien ne le dit.\n"
        "Remède : `from src.dashboard.utils.platform_colors import platform_color` "
        "puis `platform_color('spotify')`.\n"
        + "\n".join(f"  {v:3}  {k}" for k, v in compte.most_common(8)))


def test_the_counter_is_not_vacuous() -> None:
    """NON-VACUITÉ. `total <= 42` est vrai quand le compteur rend zéro.

    Il le ferait si `_MARQUES` se vidait, si `_DASH` cessait d'exister, ou si le
    parcours cessait de parser — les trois laisseraient le plafond au vert en ne
    mesurant plus rien.
    """
    assert _MARQUES, "`_MARQUES` est vide : le cliquet ne cherche plus aucune couleur"
    fichiers = [p for p in _DASH.rglob("*.py") if "__pycache__" not in str(p)]
    assert len(fichiers) >= 50, (
        f"{len(fichiers)} fichier(s) balayé(s) sous {_DASH.name}/ — il y en avait "
        "bien plus le 2026-09-21. Le parcours est devenu aveugle.")
    total = sum(_compte().values())
    assert total >= 20, (
        f"{total} couleur(s) vues — il y en avait 42 le 2026-09-21. Une chute "
        "brutale est soit une vraie migration (baisse alors le plafond dans le "
        "même commit), soit un compteur cassé.")


def test_the_detector_ignores_a_colour_named_in_prose() -> None:
    """Une couleur citée dans une docstring n'est pas une couleur utilisée.

    Mutation record — 2026-09-21 : c'est la forme exacte qui a fait rougir deux
    gardes neufs sur leur propre texte le même jour.
    """
    sonde = _DASH / "_probe_platform_colour.py"
    sonde.write_text(
        'def f():\n'
        '    """Ne jamais écrire #1DB954 à la main."""\n'
        '    return 1\n', encoding="utf-8")
    try:
        assert str(sonde.relative_to(_DASH)) not in _compte(), (
            "le détecteur compte une couleur citée dans une docstring")
        sonde.write_text(
            'def f():\n'
            '    """Rien à signaler."""\n'
            '    return {"color": "#1DB954"}\n', encoding="utf-8")
        assert _compte().get(str(sonde.relative_to(_DASH))) == 1, (
            "le détecteur ne voit plus une couleur RÉELLEMENT écrite")
    finally:
        sonde.unlink()


@pytest.mark.parametrize("plateforme", sorted(set(_MARQUES.values())))
def test_every_named_platform_has_a_measured_alternative(plateforme: str) -> None:
    """Un interdit sans remplacement nommé se fait contourner.

    ⚠️ Instagram est l'exception, et elle est MESURÉE : sept teintes attribuables
    sont impossibles dans cette palette (recherche conjointe du 2026-09-21, ΔE 9,6
    en clair contre un plancher de 15 — la deutéranopie fait converger un cyan et
    un violet vers le même bleu). Elle n'a donc pas de couleur, et sa donnée
    s'affiche en CHIFFRE. Le détail est dans `platform_colors`.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.platform_colors import PALETTE_DARK, PALETTE_LIGHT
    if plateforme == "instagram":
        assert plateforme not in PALETTE_LIGHT, (
            "Instagram a gagné une couleur : soit la borne de 9,6 a été refaite et "
            "franchie — écris la mesure — soit elle a été choisie au jugé.")
        return
    assert plateforme in PALETTE_LIGHT and plateforme in PALETTE_DARK, (
        f"'{plateforme}' est interdite en dur et n'a pas de couleur mesurée dans "
        "`platform_colors` : l'interdiction n'a rien à proposer.")
