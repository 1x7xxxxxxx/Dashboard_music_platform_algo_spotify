"""Un axe double et une clé de widget non scopée ne peuvent que devenir plus rares.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/
Persists in: nothing

Le constat qui a produit ce fichier (2026-09-10)
------------------------------------------------
Une correction faite sur une vue « exemplaire » reste locale à ce fichier. Deux
décisions sont écrites, correctement appliquées là où elles ont été pensées, et absentes
partout ailleurs :

* la figure principale documente en commentaire pourquoi elle **refuse un axe double** —
  et 12 axes secondaires vivent sur 5 autres vues, dont une figure à **quatre axes
  superposés** ;
* l'accueil scope ses clés `session_state` par locataire — et 77 clés littérales
  subsistent sur 24 vues. L'une d'elles a été trouvée capable de **casser une page** :
  un administrateur qui change d'artiste retrouve la sélection du précédent, et si ce
  titre n'existe pas chez le suivant, Streamlit lève.

Le dépôt a déjà nommé ce phénomène six fois sous d'autres formes. Il n'avait pas de
contrôle mécanique du côté visuel : la garantie reposait sur le commentaire d'un fichier
voisin. Un exemple n'est pas une règle.

Ce que le prédicat ne voyait pas (mesuré le 2026-09-10, après coup)
------------------------------------------------------------------
Le compte est descendu à 0 et le cliquet est passé au vert — alors que **trois figures
portaient encore un axe secondaire**, sur `trigger_algo/_tab_algos.py` et
`_tab_budget_roi.py`. Le prédicat ne cherchait que `yaxis2…yaxis9`, la forme produite
par `update_layout`. Plotly en a une seconde, qui ne fait apparaître ce nom nulle part :
`make_subplots(specs=[[{"secondary_y": True}]])`, puis `add_trace(..., secondary_y=True)`.

Septième instance de « la portée d'un garde est le défaut » dans ce dépôt, et la
première sur un cliquet écrit **le jour même**. Un cliquet gelé à 0 sur un prédicat
partiel ne dit pas « il n'y en a plus » ; il dit « je n'en vois plus ». Le prédicat
compte désormais les DEUX formes, et sa non-vacuité est vérifiée sur les deux.

Pourquoi des CLIQUETS
----------------------
Interdire d'un coup rendrait ces tests rouges en permanence, donc ignorés. On gèle le
compte du jour ; il ne peut que descendre. C'est le mécanisme qui a déjà fait passer le
cliquet des gardes textuels de 32 à 21.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# ⚠️ LA PORTÉE ÉTAIT L'ANGLE MORT — troisième fois le 2026-09-12, sur un troisième
# cliquet. Elle ne nommait que `views/`, alors que `utils/charts.py` fabrique une
# figure à DEUX AXES (`pareto_spend_cpr`, `overlaying: 'y'`, `side: 'right'`) rendue
# par deux vues. Le plafond affichait 0 axe secondaire pendant qu'il y en avait un,
# vivant. Et `utils/` portait six clés de widget littérales de plus.
#
# La portée est donc tout `src/dashboard`. Un composant de figure n'est pas moins une
# surface parce qu'il vit dans `utils/`.
SCANNED = Path(__file__).resolve().parent.parent / "src" / "dashboard"

# Gelés le 2026-09-10. CES NOMBRES NE PEUVENT QUE DESCENDRE.
# Descendu de 12 à 0 le 2026-09-10 : les douze axes ont été convertis en
# petits multiples. Ce n'est plus un cliquet, c'est une RÈGLE.
#
# Le plafond des clés monte de 77 à 119 le 2026-09-12, et c'est un progrès : 77 était
# la mesure d'un périmètre trop étroit. À partir d'ici il ne peut que descendre.
_MAX_SECONDARY_AXES = 0
_MAX_LITERAL_KEYS = 119

# Mutation record — 2026-09-12, quatre mutations, quatre rouges :
#   * une fonction avec `fig.update_layout(yaxis2=dict(overlaying='y'))` ajoutée à
#     `views/sacem.py` → « 1 axes secondaires contre un plafond de 0 » ;
#   * la même fonction avec `st.slider('x', key='une_cle_litterale')` → « 78 clés
#     de widget littérales contre un plafond de 77 » (avant l'élargissement) ;
#   * l'axe de `utils/charts.py` retiré alors qu'il reste déclaré → l'exemption est
#     devenue du budget, et le test de déclaration le nomme ;
#   * un SECOND axe ajouté dans ce même fichier exempté → « 2 trouvé(s), 1 déclaré ».
#
# La même fonction ajoutée à `utils/platform_chart.py` laissait tout VERT avant le
# 2026-09-12 : c'est cette mutation-là qui a révélé que la portée s'arrêtait à
# `views/`, et donc que le plafond « 0 axe secondaire » était faux pendant que
# `utils/charts.py` en portait un, vivant, rendu par deux vues.

# Le second axe DÉCLARÉ, avec sa raison — pas un plafond relevé.
#
# `pareto_spend_cpr` superpose une dépense (€, un total) et un CPR (€ par résultat,
# un TAUX). Ce sont deux NATURES différentes, seul cas où
# `tests/test_a_dual_axis_only_joins_two_different_natures.py` admet la forme : le
# lecteur ne peut pas confondre les deux échelles parce qu'elles ne mesurent pas la
# même chose. Un second axe entre deux totaux reste interdit.
#
# L'exemption est nominative pour qu'un axe ajouté À CÔTÉ rougisse quand même.
_DECLARED_AXES: dict[str, tuple[int, str]] = {
    "charts.py": (1, "pareto_spend_cpr : dépense (€, total) vs CPR (€/résultat, taux) "
                     "— deux natures, le seul cas admis"),
}

# La source-sonde de la seconde forme, gardée hors des tests pour rester lisible.
SECOND_FORM = ('fig = make_subplots(specs=[[{"secondary_y": True}]])\n'
               'fig.add_trace(tr, secondary_y=True)')

_YAXIS_N = re.compile(r"yaxis[2-9]")


def _docstrings(tree: ast.AST) -> set[int]:
    return {id(p.body[0].value) for p in ast.walk(tree)
            if isinstance(p, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            and p.body and isinstance(p.body[0], ast.Expr)
            and isinstance(p.body[0].value, ast.Constant)
            and isinstance(p.body[0].value.value, str)}


def _count_axes_in(tree: ast.AST) -> int:
    """LE prédicat des axes secondaires — un seul, partagé par le cliquet et sa sonde.

    Deux formes Plotly, et une seule était comptée jusqu'au 2026-09-10 :
    `update_layout(yaxis2=…)`, et `make_subplots(specs=[[{"secondary_y": True}]])`
    avec ses `add_trace(..., secondary_y=True)`, qui n'écrit `yaxis2` nulle part.
    """
    docs = _docstrings(tree)
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and _YAXIS_N.fullmatch(node.arg or ""):
            n += 1
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs and _YAXIS_N.fullmatch(node.value)):
            n += 1
        elif (isinstance(node, ast.keyword) and node.arg == "secondary_y"
              and isinstance(node.value, ast.Constant) and node.value.value is True):
            n += 1
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docs and node.value == "secondary_y"):
            n += 1
        # TROISIÈME forme, trouvée le 2026-09-10 — quelques heures après la seconde,
        # et sur le même prédicat. Un axe peut être CONSTRUIT : `f"yaxis{i + 1}"` ne
        # contient aucune des chaînes cherchées jusqu'ici, et `meta_creatives.py`
        # empilait ainsi jusqu'à six axes pendant que ce cliquet lisait zéro.
        #
        # Une f-string dont la partie littérale vaut « yaxis » ou « y » et qui est
        # suivie d'une interpolation construit un identifiant d'axe. C'est la seule
        # façon d'en fabriquer un que Plotly accepte.
        elif isinstance(node, ast.JoinedStr):
            lit = "".join(v.value for v in node.values
                          if isinstance(v, ast.Constant) and isinstance(v.value, str))
            has_slot = any(isinstance(v, ast.FormattedValue) for v in node.values)
            if has_slot and lit in ("yaxis", "y"):
                n += 1
    return n


def _counts() -> tuple[dict, dict]:
    axes, keys = {}, {}
    for f in sorted(SCANNED.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        n_ax = _count_axes_in(tree)
        # Une clé de widget littérale ne porte pas le locataire ; une f-string le
        # peut. On compte donc les littérales, sans juger chacune.
        n_k = sum(1 for n in ast.walk(tree)
                  if isinstance(n, ast.keyword) and n.arg == "key"
                  and isinstance(n.value, ast.Constant))
        declared = _DECLARED_AXES.get(f.name, (0, ""))[0]
        if n_ax > declared:
            axes[f.name] = n_ax - declared
        if n_k:
            keys[f.name] = n_k
    return axes, keys


def test_no_new_secondary_axis() -> None:
    """Des unités incomparables forcées à partager un repère par décalage de côté."""
    axes, _ = _counts()
    total = sum(axes.values())
    assert total <= _MAX_SECONDARY_AXES, (
        f"{total} axes secondaires contre un plafond de {_MAX_SECONDARY_AXES}. "
        "Un second axe fait partager un même repère visuel à des unités et des ordres "
        "de grandeur incomparables — la figure principale de ce produit documente "
        "pourquoi elle le refuse, et les petits multiples sont la seule alternative "
        "admise.\n"
        + "\n".join(f"  {v:2}  {k}" for k, v in sorted(axes.items(), key=lambda kv: -kv[1])))


def test_no_new_unscoped_widget_key() -> None:
    """Une clé littérale ne porte pas le locataire, donc traverse un changement d'artiste."""
    _, keys = _counts()
    total = sum(keys.values())
    assert total <= _MAX_LITERAL_KEYS, (
        f"{total} clés de widget littérales contre un plafond de {_MAX_LITERAL_KEYS}. "
        "`st.session_state` persiste entre les pages d'une même session : une clé qui "
        "ne porte pas l'identifiant du locataire réinjecte le réglage d'un artiste dans "
        "la page d'un autre, et casse la page quand la valeur n'existe pas chez lui.\n"
        + "\n".join(f"  {v:2}  {k}" for k, v in sorted(keys.items(), key=lambda kv: -kv[1])[:8]))


def test_the_ceilings_are_not_slack() -> None:
    """Une marge devient du budget pour la prochaine régression."""
    axes, keys = _counts()
    assert sum(keys.values()) >= _MAX_LITERAL_KEYS - 12, (
        f"{sum(keys.values())} clés pour un plafond de {_MAX_LITERAL_KEYS} : "
        "descendre le plafond.")


def test_the_declared_axis_still_exists_and_still_has_its_axis() -> None:
    """Une exemption pour un fichier disparu élargit la règle en silence.

    Et une exemption POUR UN AXE QUI N'EST PLUS LÀ est du budget : le jour où
    `pareto_spend_cpr` est converti en petits multiples, le `1` déclaré ici
    autorise gratuitement le prochain second axe du même fichier.
    """
    for name, (count, reason) in _DECLARED_AXES.items():
        matches = [f for f in SCANNED.rglob(name) if "__pycache__" not in f.parts]
        assert matches, f"{name} est exempté mais n'existe plus sous src/dashboard"
        found = sum(_count_axes_in(ast.parse(f.read_text(encoding="utf-8")))
                    for f in matches)
        assert found == count, (
            f"{name} : {found} axe(s) secondaire(s) trouvé(s), {count} déclaré(s) "
            f"— raison : {reason}.\n"
            "Plus que déclaré : un axe a été ajouté et l'exemption le couvre sans "
            "l'avoir décidé. Moins : l'exemption est devenue du budget, retire-la."
        )


def test_the_predicate_sees_both_shapes() -> None:
    """Non-vacuité : un prédicat qui ne trouve rien satisferait les deux cliquets."""
    _, keys = _counts()
    assert keys, "aucune clé littérale trouvée — le prédicat est cassé"

    # Le prédicat des axes ne trouve plus rien, ce qui est le but : on vérifie donc
    # qu'il sait encore VOIR — sur les DEUX formes, parce qu'il n'en voyait qu'une et
    # que trois figures sont passées par l'autre.
    for source, why in (
        ("fig.update_layout(yaxis2=dict(overlaying='y'))",
         "la forme update_layout"),
        (SECOND_FORM,
         "la forme make_subplots — celle qui a traversé ce cliquet le 2026-09-10"),
    ):
        assert _count_axes_in(ast.parse(source)) >= 1, (
            f"le prédicat des axes secondaires est aveugle à {why}")
