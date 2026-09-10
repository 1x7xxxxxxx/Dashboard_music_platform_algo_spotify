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

VIEWS = Path(__file__).resolve().parent.parent / "src" / "dashboard" / "views"

# Gelés le 2026-09-10. CES NOMBRES NE PEUVENT QUE DESCENDRE.
# Descendu de 12 à 0 le 2026-09-10 : les douze axes ont été convertis en
# petits multiples. Ce n'est plus un cliquet, c'est une RÈGLE.
_MAX_SECONDARY_AXES = 0
_MAX_LITERAL_KEYS = 77

_YAXIS_N = re.compile(r"yaxis[2-9]")


def _docstrings(tree: ast.AST) -> set[int]:
    return {id(p.body[0].value) for p in ast.walk(tree)
            if isinstance(p, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            and p.body and isinstance(p.body[0], ast.Expr)
            and isinstance(p.body[0].value, ast.Constant)
            and isinstance(p.body[0].value.value, str)}


def _counts() -> tuple[dict, dict]:
    axes, keys = {}, {}
    for f in sorted(VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        docs = _docstrings(tree)
        n_ax = n_k = 0
        for n in ast.walk(tree):
            # `yaxis2=dict(...)` en argument, ou "yaxis2" en clé de dict de layout.
            if isinstance(n, ast.keyword) and _YAXIS_N.fullmatch(n.arg or ""):
                n_ax += 1
            elif (isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and id(n) not in docs and _YAXIS_N.fullmatch(n.value)):
                n_ax += 1
            # Une clé de widget littérale ne porte pas le locataire ; une f-string le
            # peut. On compte donc les littérales, sans juger chacune.
            if (isinstance(n, ast.keyword) and n.arg == "key"
                    and isinstance(n.value, ast.Constant)):
                n_k += 1
        if n_ax:
            axes[f.name] = n_ax
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


def test_the_predicate_sees_both_shapes() -> None:
    """Non-vacuité : un prédicat qui ne trouve rien satisferait les deux cliquets."""
    _, keys = _counts()
    assert keys, "aucune clé littérale trouvée — le prédicat est cassé"

    # Le prédicat des axes ne trouve plus rien, ce qui est le but : on vérifie donc
    # qu'il sait encore VOIR, sur une source fabriquée pour l'occasion.
    import ast as _ast
    probe = _ast.parse("fig.update_layout(yaxis2=dict(overlaying='y'))")
    seen = sum(1 for n in _ast.walk(probe)
               if isinstance(n, _ast.keyword) and _YAXIS_N.fullmatch(n.arg or ""))
    assert seen == 1, "le prédicat des axes secondaires est devenu aveugle"
