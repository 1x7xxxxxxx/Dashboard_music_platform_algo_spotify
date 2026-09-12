"""Le grain de la figure se DÉRIVE de la fenêtre — il ne se demande plus.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Signalé le 2026-09-12 : « filtre 30 jours, quand je sélectionne "année" du filtre en
bas, c'est incohérent ». La barre proposait les quatre pas à toutes les fenêtres, donc
« Année » sur 30 jours — un seau, une figure qui se replie, et une note sous elle pour
s'en excuser.

Le premier correctif FILTRAIT la barre selon la fenêtre. L'artiste a proposé mieux le
même jour : « on ne devrait pas supprimer le filtre jour semaine mois année et
automatiquement trier […] ». Il avait raison, et la raison vaut au-delà de ce widget :
**le pas pertinent est entièrement déterminé par la fenêtre, donc le demander revient à
faire trancher une question dont la réponse est calculable.** Un contrôle dont toutes
les options sauf une sont mauvaises n'est pas un contrôle.

La barre est donc supprimée. Ce garde suit la RÈGLE, pas le widget :

  * fenêtre < `_DAY_UNTIL_YEAR` (360 j)  → **jour**
  * fenêtre ≥ 360 j                      → **mois**, sauf au-delà de `_MAX_BUCKETS`
                                            points, où c'est **année**

⚠️ **Il vérifie aussi que le grain reste AFFICHÉ.** C'est la contrepartie de
l'automatisation : « chaque point est un mois » n'est pas lisible sur l'axe d'une
courbe de 44 points, et un pas appliqué en silence se lit comme une panne — c'est ce
que ce dépôt garde depuis le 2026-09-08.

Mutations vues rouges avant écriture (2026-09-12) :
  * `_DAY_UNTIL_YEAR` porté à 3 000 → test_a_long_window_never_draws_daily ÉCHOUE
    en nommant la fenêtre et le pas obtenu ;
  * la branche `elif _window_days / 30 <= _MAX_BUCKETS` retirée →
    test_a_very_long_history_coarsens_to_the_year ÉCHOUE ;
  * le `st.caption` du grain retiré → test_the_applied_grain_is_written_on_screen
    ÉCHOUE.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_HOME = Path(__file__).resolve().parents[1] / "src/dashboard/views/home.py"


def _tree() -> ast.Module:
    return ast.parse(_HOME.read_text(encoding="utf-8"))


def _const(name: str):
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def _step_for(window_days: int) -> str:
    """Rejoue la règle de `_render_trend` sur une fenêtre donnée."""
    day_until, max_buckets = _const("_DAY_UNTIL_YEAR"), _const("_MAX_BUCKETS")
    if window_days < day_until:
        return "day"
    if window_days / 30 <= max_buckets:
        return "month"
    return "year"


def test_the_rule_is_readable_at_all():
    """Non-vacuité : sans ces deux constantes, tout ce fichier rejoue du vide."""
    assert _const("_DAY_UNTIL_YEAR"), (
        "`_DAY_UNTIL_YEAR` a disparu de `home.py` : la règle du grain n'est plus "
        "lisible, et les tests ci-dessous vérifient une règle qui n'existe plus")
    assert _const("_MAX_BUCKETS"), "`_MAX_BUCKETS` a disparu de `home.py`"
    assert 300 <= _const("_DAY_UNTIL_YEAR") <= 400, (
        f"`_DAY_UNTIL_YEAR` vaut {_const('_DAY_UNTIL_YEAR')} : la bascule jour → mois "
        "doit se faire autour de l'année, sans quoi « 12 mois » et « 90 jours » "
        "tombent du même côté.")


@pytest.mark.parametrize(("window", "expected"), [
    (3, "day"), (30, "day"), (90, "day"), (359, "day"),
    (365, "month"), (730, "month"), (1344, "month"),
])
def test_each_window_of_the_filter_gets_the_grain_it_deserves(window, expected):
    """Les fenêtres réelles du filtre, et le grain que chacune doit produire."""
    got = _step_for(window)
    assert got == expected, (
        f"une fenêtre de {window} jours rend le pas « {got} » au lieu de "
        f"« {expected} ». Sous un an le jour est lisible et c'est le grain le plus "
        "informatif ; au-delà il produit des centaines de points et la courbe "
        "devient une bande.")


def test_a_long_window_never_draws_daily():
    """Au-delà de l'année, jamais le jour — c'est la demande exacte du 2026-09-12."""
    for window in (365, 400, 730, 1344):
        assert _step_for(window) != "day", (
            f"une fenêtre de {window} jours dessine encore au pas du jour : "
            f"{window} points par plateforme, que l'artiste a décrits comme "
            "illisibles.")


def test_a_very_long_history_coarsens_to_the_year():
    """Le garde-fou du haut existe et se déclenche — sinon il n'est qu'un commentaire."""
    # ⚠️ UNE FENÊTRE FIXE, JAMAIS DÉRIVÉE DE `_MAX_BUCKETS`. La première version
    # calculait `huge = (_MAX_BUCKETS + 1) * 30 + 1` : l'entrée du test venait de la
    # constante testée, donc porter `_MAX_BUCKETS` à 99 999 laissait le test VERT —
    # l'entrée grandissait avec le plafond. Mesuré le 2026-09-12, mutation restée
    # verte. Un test dont l'entrée dépend de son sujet ne peut pas le contredire ;
    # c'est la même famille que le garde satisfait par l'effondrement qu'il devait
    # attraper.
    #
    # 7 300 jours = vingt ans. Aucun locataire n'en est proche, et c'est le but :
    # la borne du test est un FAIT extérieur à la règle.
    huge = 7_300
    assert _const("_MAX_BUCKETS") < huge / 30, (
        f"`_MAX_BUCKETS` vaut {_const('_MAX_BUCKETS')} : à ce niveau, même vingt ans "
        "d'historique resteraient au pas du mois (243 points), et le garde-fou du "
        "haut ne se déclencherait jamais. Une borne qui ne peut pas être atteinte "
        "n'est pas une borne.")
    assert _step_for(huge) == "year", (
        f"une fenêtre de {huge} jours ({huge / 30:.0f} mois) reste au pas du mois "
        f"alors que le plafond est de {_const('_MAX_BUCKETS')} points. Au-delà, les "
        "points se chevauchent et la courbe devient une bande.")
    # ET IL NE SE DÉCLENCHE PAS SUR LE PARC ACTUEL. Le plus ancien locataire porte
    # 1 344 jours (mesuré le 2026-09-12) : si « année » sortait déjà là, le
    # garde-fou serait en fait la règle, et la figure aurait 4 points.
    assert _step_for(1344) == "month", (
        "le plafond se déclenche sur l'historique réel du plus ancien locataire : "
        "ce n'est plus un garde-fou, c'est la règle, et la courbe tombe à 4 points")


def test_the_step_bar_is_really_gone():
    """Un widget supprimé qui survit quelque part rend la règle inatteignable."""
    calls = [n for n in ast.walk(_tree())
             if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "segmented_control"]
    keys = {kw.value.value for c in calls for kw in c.keywords
            if kw.arg == "label_visibility" or isinstance(kw.value, ast.Constant)
            for kw in [kw] if isinstance(kw.value, ast.Constant)}
    assert not any("step" in str(k) for k in keys), (
        "une barre de pas subsiste dans `home.py`. Le grain est dérivé de la "
        "fenêtre : un widget qui prétend encore le choisir affiche une valeur que "
        "la figure ignore — pire qu'avant, parce que le contrôle a l'air de marcher.")


def test_the_applied_grain_is_written_on_screen():
    """Un pas appliqué en silence se lit comme une panne."""
    tree = _tree()
    # Par `ast` : une clé d'i18n `home.grain_*` passée à un appel, et non une
    # chaîne trouvée dans un commentaire. Trois gardes de ce dépôt ont été pris au
    # vert sur la prose de leur propre correctif le 2026-09-04.
    grains = {n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value.startswith("home.grain_")}
    assert {"home.grain_day", "home.grain_month", "home.grain_year"} <= grains, (
        f"le grain n'est plus annoncé pour les trois pas : {sorted(grains)}. "
        "« Chaque point est un mois » n'est pas lisible sur l'axe d'une courbe de "
        "44 points, et l'artiste n'a plus de barre pour le déduire.")
    # ET LA CLÉ DOIT ATTERRIR DANS UN RENDU, pas dans un dict mort. Par `ast` :
    # un appel à `st.caption` existe-t-il dans la fonction ? La version d'avant
    # écrivait `assert "st.caption(" in src`, satisfait par n'importe quel
    # commentaire citant l'appel — `test_a_guard_reads_structure_not_text` l'a
    # attrapée, pour la deuxième fois dans la même séance.
    rendered = any(
        isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "caption"
        for f in ast.walk(tree)
        if isinstance(f, ast.FunctionDef) and f.name == "_render_trend"
        for n in ast.walk(f))
    assert rendered, (
        "`_render_trend` n'appelle plus `st.caption` : les clés `home.grain_*` "
        "existent mais rien ne les affiche — du texte correct que rien n'atteint, "
        "la forme que ce dépôt paie le plus souvent.")
