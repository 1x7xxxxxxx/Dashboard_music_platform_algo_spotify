"""La page admin n'exécute que la section regardée.

Type: Guard
Uses: ast, streamlit.testing
Depends on: src/dashboard/views/admin.py
Persists in: nothing

Le chiffre qui a décidé de la forme — mesuré le 2026-09-22
----------------------------------------------------------
Dix pages réservées à l'administration, ~4 500 lignes, à regrouper « en plusieurs
onglets sur une même page ». Le coût de chacune, page par page :

    admin 23 · db_health 22 · airflow_kpi 19 · alerts 11 · referral 6
    etl_logs 5 · usage 5 · promo 2                    →  93 requêtes

**`st.tabs` les aurait toutes exécutées à chaque clic sur n'importe quel widget**, et
ce n'est pas une supposition : `admin.py` le documentait déjà pour ses cinq onglets
d'origine — « Streamlit executes every tab's body on every rerun ». Les sept onglets
qu'elle portait coûtaient 23 requêtes ensemble, pour un seul regardé.

Un sélecteur n'exécute que le groupe choisi. Mesuré après :

    business 6 · santé 22 · comptes 1 · réglages 4 · usage 5 · liens 0

La section la plus consultée — les comptes — passe de 23 à **1**.

Ce que ce garde tient
---------------------
1. **Aucun `st.tabs` au premier niveau de cette page.** C'est le geste qui ramènerait
   les 93 : il se lit comme une amélioration d'ergonomie et coûte tout le budget.
2. **Chaque groupe déclaré est atteignable**, et rend quelque chose.
3. **Un groupe qui délègue n'ouvre pas de connexion dans `admin`.** Le plafond est de
   UNE connexion par rendu (`test_a_render_opens_one_connection`, `_KNOWN_MULTI`
   vide : aucune vue n'a d'exemption). La vue déléguée ouvre la sienne.
4. **Le choix voyage dans l'URL**, sinon un lien profond vers une section est
   impossible et le bouton Précédent du navigateur saute la page entière.

⚠️ Ce qu'il ne tient PAS : le nombre de requêtes lui-même. Le compter ici
demanderait d'instrumenter six rendus complets à chaque exécution de la suite, pour
une propriété que l'absence de `st.tabs` garantit structurellement. Le chiffre est
dans cette docstring, daté ; la structure est gardée.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_ADMIN = _ROOT / "src" / "dashboard" / "views" / "admin.py"


def _arbre() -> ast.AST:
    return ast.parse(_ADMIN.read_text(encoding="utf-8"))


def _show() -> ast.FunctionDef:
    fn = next((n for n in ast.walk(_arbre())
               if isinstance(n, ast.FunctionDef) and n.name == "show"), None)
    assert fn is not None, "`show()` a disparu d'`admin.py`"
    return fn


def _groupes() -> list[str]:
    from src.dashboard.views.admin import _GROUPES
    return [k for k, _lbl, _m in _GROUPES]


def test_there_are_several_groups() -> None:
    """NON-VACUITÉ. Un registre vide rendrait tout ce qui suit vert pour rien."""
    g = _groupes()
    assert len(g) >= 4, (
        f"seulement {g} — la page n'est plus regroupée, et les tests ci-dessous ne "
        "vérifient presque rien.")


def test_the_page_does_not_use_tabs_at_the_top_level() -> None:
    """LE geste qui ramènerait les 93 requêtes.

    `st.tabs` se lit comme une amélioration d'ergonomie — vrais onglets, pas de
    rerun au changement — et exécute le corps de TOUS. Sur cette page, ça vaut la
    somme des dix écrans.
    """
    appels = [n for n in ast.walk(_show())
              if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "tabs"]
    assert not appels, (
        f"`show()` appelle `st.tabs` ({len(appels)} fois). Streamlit exécute le corps "
        "de chaque onglet à chaque rerun : cette page coûterait 93 requêtes par clic "
        "au lieu de 1 à 22 selon la section. Utiliser `st.segmented_control` et ne "
        "rendre que le groupe choisi — motif de `views/credentials/router.py`.")


def test_the_selection_travels_in_the_url() -> None:
    """Sans ça, aucun lien profond vers une section, et Précédent saute la page.

    Le motif est celui de la barre d'onglets des identifiants : le sélecteur lit
    `st.query_params` pour son défaut et l'y réécrit quand le choix change.
    """
    src = _ADMIN.read_text(encoding="utf-8")
    from src.dashboard.views.admin import _GROUPE_PARAM

    tree = _arbre()
    lit = any(isinstance(n, ast.Call)
              and getattr(n.func, "attr", None) == "get"
              and isinstance(getattr(n.func, "value", None), ast.Attribute)
              and n.func.value.attr == "query_params"
              for n in ast.walk(tree))
    assert lit, (
        "`admin.py` ne lit plus `st.query_params` : la section choisie ne survit ni "
        "à un lien partagé ni au bouton Précédent.")
    assert _GROUPE_PARAM in src, (
        f"le paramètre d'URL `{_GROUPE_PARAM}` n'apparaît plus dans le fichier.")


@pytest.mark.parametrize("groupe", _groupes())
def test_every_group_renders_something(groupe: str) -> None:
    """Un groupe déclaré et vide est une entrée morte dans une barre de navigation.

    Le rendu est fait pour de vrai, avec le groupe forcé par l'URL — c'est le seul
    moyen de savoir qu'une branche est atteignable, et ce dépôt a payé plusieurs
    fois « du code correct que rien n'atteint ».
    """
    from streamlit.testing.v1 import AppTest

    src = (
        f'import sys; sys.path.insert(0, {str(_ROOT)!r})\n'
        "import streamlit as st\n"
        "st.session_state['role'] = 'admin'\n"
        "st.session_state['artist_id'] = 1\n"
        "st.session_state['email'] = 'probe@test'\n"
        "st.session_state['authenticated'] = True\n"
        f"st.query_params['admin_onglet'] = {groupe!r}\n"
        "from src.dashboard.views.admin import show\n"
        "show()\n"
    )
    at = AppTest.from_string(src)
    at.run(timeout=180)
    assert not at.exception, f"le groupe « {groupe} » lève : {at.exception}"

    # Substantiel = autre chose que la barre de sélection et le titre.
    rendu = (len(list(at.dataframe)) + len(list(at.markdown)) + len(list(at.metric))
             + len(list(at.subheader)) + len(list(at.caption))
             + len(list(at.info)) + len(list(at.warning)) + len(list(at.error)))
    assert rendu > 1, (
        f"le groupe « {groupe} » ne rend qu'un élément : c'est une entrée de "
        "navigation qui ne mène à rien.")


def test_a_delegating_group_opens_no_connection_in_admin() -> None:
    """La contrainte qui décide de toute l'architecture de cette page.

    `test_a_render_opens_one_connection` plafonne un rendu à UNE connexion, et
    `_KNOWN_MULTI` est vide — aucune vue n'a d'exemption. Si `admin` ouvrait la
    sienne AVANT de déléguer, le rendu en compterait deux : la sienne et celle de la
    vue déléguée.

    Par l'AST : chaque `return` qui suit un `_deleguer(...)` doit précéder le
    `get_db_connection()`. On le vérifie par la POSITION des lignes, la seule chose
    qu'un lecteur statique peut établir ici.
    """
    fn = _show()
    delegations = [n.lineno for n in ast.walk(fn)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", None) == "_deleguer"]
    ouvertures = [n.lineno for n in ast.walk(fn)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, "id", None) == "get_db_connection"]
    assert delegations, (
        "`show()` ne délègue plus à aucune vue : soit tout a été recopié dans ce "
        "fichier, soit les groupes délégués ont disparu.")
    assert ouvertures, "`show()` n'ouvre plus aucune connexion — les groupes qui " \
                       "vivent ici ne peuvent plus rien lire."
    assert max(delegations) < min(ouvertures), (
        f"une délégation (ligne {max(delegations)}) survient APRÈS l'ouverture de "
        f"connexion (ligne {min(ouvertures)}) : le rendu en ouvrirait deux — celle "
        "d'`admin` et celle de la vue déléguée — et le plafond est de une.")


def test_the_delegated_views_still_exist() -> None:
    """Un groupe qui délègue vers un module disparu est une entrée morte."""
    import importlib

    src = _ADMIN.read_text(encoding="utf-8")
    tree = _arbre()
    cibles = {n.args[0].value for n in ast.walk(tree)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "_deleguer"
              and n.args and isinstance(n.args[0], ast.Constant)}
    # Les cibles passées par variable sont dans les listes de `_sous_selecteur`.
    for n in ast.walk(tree):
        if isinstance(n, ast.Tuple) and len(n.elts) == 2 \
                and isinstance(n.elts[0], ast.Constant) \
                and isinstance(n.elts[0].value, str):
            v = n.elts[0].value
            if f"views.{v}" in src or (_ROOT / "src" / "dashboard" / "views"
                                       / f"{v}.py").exists():
                cibles.add(v)
    assert len(cibles) >= 5, (
        f"seulement {sorted(cibles)} vues déléguées trouvées — la page ne regroupe "
        "plus grand-chose.")
    for v in sorted(cibles):
        mod = importlib.import_module(f"src.dashboard.views.{v}")
        assert hasattr(mod, "show"), (
            f"`views/{v}.py` n'a plus de `show()` : le groupe qui y mène lèverait.")
