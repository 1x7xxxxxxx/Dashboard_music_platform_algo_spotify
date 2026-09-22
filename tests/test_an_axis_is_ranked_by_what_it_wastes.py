"""Un axe se classe sur ce qu'il COÛTE, pas sur son rapport de coûts.

Type: Guard
Uses: src.dashboard.utils.meta_axes
Persists in: nothing

La différence entre un rapport et une décision
-----------------------------------------------
Un ×3 sur 40 € engagés ne coûte rien. Un ×1,3 sur 1 400 € coûte cher. Classer trois
axes sur le rapport de leurs coûts produit un joli tableau ; les classer sur ce que
l'écart COÛTE produit un geste.

Mesuré sur le catalogue de l'artiste 1 le 2026-09-22, bout en bout par la requête de
l'accueil, les deux classements ne sont pas seulement différents — ils sont **inversés** :

    par facteur       pays ×1,92  >  âge ×1,67  >  placement ×1,27
    par gaspillage    âge ~768 €  >  pays ~289 €  >  placement ~182 €

Le pays a le rapport le plus spectaculaire et coûte **2,7 fois moins cher** que l'âge.

⚠️ Les fixtures ci-dessous ne portent que les QUATRE premiers pays, pas les onze de la
base : elles rendent donc ~69 € et ×1,09 sur cet axe, pas les chiffres ci-dessus. C'est
volontaire — une fixture courte se lit — mais il ne faut pas confondre les deux relevés,
et c'est précisément le genre de confusion qui fait publier un nombre faux.

Le plancher de fiabilité, et ce qu'il a intercepté
---------------------------------------------------
`MIN_DEPENSE` vient de `utils/meta_confidence`, **importé et non recopié**. Il
y a été descendu le 2026-09-22 : un module partagé ne peut pas importer une vue sans
la charger entière — 1 073 ms mesurés au premier rendu pour un budget de 287 ms. Ce n'est
pas un seuil de modèle : c'est « la borne en dessous de laquelle le classement de CE
catalogue s'inverse d'une annonce à l'autre ».

Le 2026-09-22, avant de l'appliquer, j'avais mesuré le meilleur pays à **0,0528 € aux
États-Unis — sur 31 € dépensés** — et j'en avais tiré un titre pour l'écran. Le
plancher l'écarte, et le meilleur devient l'Allemagne à 0,1016 €. **Le garde ci-dessous
est celui qui aurait arrêté ce chiffre.**
"""
from __future__ import annotations

from src.dashboard.utils.meta_axes import Ecart, Ligne, classer_axes, ecart

#: Les lignes RÉELLES de production, artiste 1, relevées le 2026-09-22. Une fixture
#: inventée prouverait que le code fait ce qu'il dit ; celle-ci prouve qu'il le fait
#: sur la forme des données qui existent.
_AGE = [Ligne("35-44", 167, 1891), Ligne("45-54", 123, 1342), Ligne("55-64", 49, 467),
        Ligne("65+", 38, 344), Ligne("18-24", 565, 4081), Ligne("25-34", 1398, 9503)]
_PAYS = [Ligne("US", 31, 583), Ligne("DE", 271, 2669), Ligne("BE", 98, 892),
         Ligne("MX", 844, 7628)]
_PLACEMENT = [Ligne("ig/explore_grid", 1, 270), Ligne("an/rewarded", 15, 818),
              Ligne("ig/reels", 1218, 9593), Ligne("an/classic", 70, 547),
              Ligne("ig/stories", 226, 1510), Ligne("ig/feed", 707, 4395)]
_AXES = {"age": _AGE, "pays": _PAYS, "placement": _PLACEMENT}


# ══════════════════════════════════════════════════════════════════════════
# 1. LE PLANCHER — celui qui a intercepté mon chiffre
# ══════════════════════════════════════════════════════════════════════════

def test_the_floor_comes_from_the_module_that_measured_it() -> None:
    """`MIN_DEPENSE` est IMPORTÉ, pas retapé.

    Deux seuils de fiabilité dans un même produit divergent au premier ajustement,
    et le classement d'un écran cesserait d'accorder avec celui d'un autre sans que
    rien ne le dise.
    """
    import ast
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "src" / "dashboard" / "utils" / "meta_axes.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    importe = any(
        isinstance(n, ast.ImportFrom) and "meta_confidence" in (n.module or "")
        and any(a.name == "MIN_DEPENSE" for a in n.names)
        for n in ast.walk(tree))
    assert importe, (
        "`meta_axes` ne prend plus `MIN_DEPENSE` chez `utils/meta_confidence` : le "
        "seuil est écrit deux fois, et les deux divergeront.")

    # ⚠️ PAR L'AST, PAS PAR LE TEXTE. Le premier jet écrivait
    # `assert "MIN_DEPENSE = " not in src` — satisfait par un COMMENTAIRE, et ce
    # fichier-ci en porte plusieurs qui nomment la constante.
    # `test_a_guard_reads_structure_not_text` l'a refusé, avec sa raison : trois
    # gardes ont été pris au vert sur leur propre défaut le 2026-09-04, dont deux sur
    # le commentaire qui expliquait le correctif.
    redefinit = any(
        isinstance(n, ast.Assign)
        and any(getattr(c, "id", None) == "MIN_DEPENSE" for c in n.targets)
        for n in ast.walk(tree))
    assert not redefinit, (
        "`meta_axes` AFFECTE `MIN_DEPENSE` — c'est la seconde copie que l'import "
        "existe pour éviter.")


def test_a_line_below_the_floor_is_never_named_best() -> None:
    """LE CHIFFRE QUE J'ALLAIS PUBLIER.

    Les États-Unis à 0,0528 € sur **31 €** étaient le meilleur coût du catalogue,
    et c'est ce que j'avais écrit avant d'appliquer le plancher. Sans lui, le
    classement recommande de déplacer un budget vers une ligne qui n'a jamais été
    éprouvée.
    """
    e = ecart("pays", _PAYS)
    assert e is not None
    assert e.meilleur != "US", (
        f"« US » est nommé le meilleur pays alors qu'il n'a reçu que 31 € — sous le "
        f"plancher. C'est exactement le chiffre que ce garde existe pour arrêter. "
        f"Obtenu : {e}")
    assert e.meilleur == "DE", f"attendu DE (271 € dépensés), obtenu {e.meilleur}"


def test_removing_the_floor_would_change_the_answer() -> None:
    """NON-VACUITÉ du test ci-dessus : le plancher doit CHANGER quelque chose.

    Un plancher qui n'écarte jamais rien est un plancher décoratif. On le descend à
    zéro et on exige que la réponse bascule.
    """
    avec = ecart("pays", _PAYS)
    sans = ecart("pays", _PAYS, plancher=0.0)
    assert avec is not None and sans is not None
    assert sans.meilleur == "US" and avec.meilleur == "DE", (
        "abaisser le plancher à zéro ne change pas le meilleur : il n'écarte donc "
        f"aucune ligne fragile. avec={avec.meilleur} sans={sans.meilleur}")


# ══════════════════════════════════════════════════════════════════════════
# 2. LE RANG — en euros, jamais en facteur
# ══════════════════════════════════════════════════════════════════════════

def test_the_ranking_is_by_euros_wasted_not_by_ratio() -> None:
    """LE cas fabriqué qui sépare les deux classements sans ambiguïté.

    Un axe à ×3 sur des miettes contre un axe à ×1,2 sur un gros budget. Le
    rapport dit le premier, l'argent dit le second — et c'est l'argent qui décide
    où mettre le budget du mois prochain.
    """
    axes = {
        "miettes": [Ligne("bon", 100, 1000), Ligne("mauvais", 120, 400)],   # ×3
        "gros": [Ligne("bon", 5000, 50000), Ligne("mauvais", 6000, 50000)],  # ×1,2
    }
    rang = classer_axes(axes)
    assert [e.dimension for e in rang] == ["gros", "miettes"], (
        "le classement suit le FACTEUR et non les euros : un ×3 sur 120 € passe "
        f"devant un ×1,2 sur 6 000 €. Obtenu {[(e.dimension, round(e.facteur, 2), round(e.gaspillage)) for e in rang]}")
    assert rang[0].facteur < rang[1].facteur, (
        "la fixture ne sépare plus les deux classements — elle ne prouve donc plus "
        "rien. Le premier axe doit avoir le PLUS PETIT facteur et le PLUS GROS "
        "gaspillage.")


def test_the_real_catalogue_puts_age_first() -> None:
    """Sur les données de production, l'âge est l'axe le plus coûteux.

    Par facteur, le pays l'emporterait. C'est la démonstration que le choix du
    critère change la recommandation sur des données réelles, pas seulement sur une
    fixture construite pour.
    """
    rang = classer_axes(_AXES)
    assert rang, "aucun axe classé sur des données réelles — le module ne sert à rien"
    assert rang[0].dimension == "age", (
        f"attendu l'âge en tête (le plus coûteux), obtenu "
        f"{[(e.dimension, round(e.gaspillage)) for e in rang]}")


# ══════════════════════════════════════════════════════════════════════════
# 3. LES REFUS — deux, et les deux sont des réponses
# ══════════════════════════════════════════════════════════════════════════

def test_a_single_reliable_line_teaches_nothing() -> None:
    """« Un meilleur sans rival mesuré n'est pas un enseignement. »

    Reprise littérale de la règle de `_reglages.recommandation()`, qui exige deux
    lignes fiables. Une seule ligne au-dessus du plancher, c'est la seule chose
    qu'on ait essayée.
    """
    assert ecart("pays", [Ligne("DE", 500, 5000), Ligne("US", 5, 100)]) is None


def test_no_gap_means_nothing_to_move() -> None:
    """Deux lignes au même coût : rien à déplacer, donc rien à dire."""
    assert ecart("age", [Ligne("a", 200, 2000), Ligne("b", 300, 3000)]) is None


def test_a_line_with_no_result_is_not_free() -> None:
    """Zéro résultat n'est pas un coût de zéro — c'est une division impossible.

    Sans ce refus, une ligne à 400 € et zéro résultat sortirait « meilleure » à
    0,00 €, et le conseil serait d'y mettre tout le budget. Le défaut a un
    précédent : « Unknown » à 0,00 € proclamée la plus efficace.
    """
    e = ecart("pays", [Ligne("mort", 400, 0), Ligne("DE", 271, 2669),
                       Ligne("MX", 844, 7628)])
    assert e is not None
    assert e.meilleur != "mort", (
        "une ligne sans aucun résultat est nommée la meilleure : sa division par "
        "zéro a été lue comme un coût nul.")


def test_the_waste_is_zero_when_everything_is_at_the_best_cost() -> None:
    """Borne inférieure : pas d'écart, pas de gaspillage — et pas d'écart rendu."""
    assert ecart("x", [Ligne("a", 1000, 10000), Ligne("b", 1000, 10000)]) is None


def test_the_returned_shape_is_the_declared_one() -> None:
    """Le contrat de sortie, pour que l'affichage ne devine pas."""
    e = ecart("age", _AGE)
    assert isinstance(e, Ecart)
    assert e.fiables >= 2 and e.gaspillage > 0 and e.facteur > 1
    assert e.cpr_min < e.cpr_max
