"""`NaN` est VRAI en Python — donc `or 0` ne rattrape jamais une absence.

Type: Test
Uses: ast, pathlib (aucune base, aucun Streamlit)
Depends on: src/dashboard/**, src/dashboard/utils/safe_number.py
Persists in: nothing

⚠️ TROUVÉ PAR UN TEST LE 2026-09-22, pas par une relecture.

Le dépôt écrivait, en **huit endroits**, la forme :

    float(pd.to_numeric(valeur, errors="coerce") or 0)

Le `or 0` a l'air de couvrir l'absence. Il ne la couvre pas : `pd.to_numeric` rend
`NaN` sur une valeur manquante, et **`NaN` est vrai**. Le `or` ne se déclenche donc
jamais.

Le cas qui l'a révélé : `SUM()` sur zéro ligne rend `NULL`. Un artiste sans aucun
relevé de ventes obtenait `{'eur_par_stream': nan}` au lieu de `None` — et le garde
juste en dessous, `if streams <= 0: return None`, ne l'attrapait pas davantage,
puisque **`nan <= 0` est faux**. Deux filets à la suite, tous deux traversés par la
même valeur.

Deux modes d'échec, tous deux mesurés dans l'arbre :

  · `float(nan)` — se propage **en silence** jusqu'à l'écran, qui affiche « nan € » ;
  · `int(nan)` — `ValueError: cannot convert float NaN to integer`, donc un
    **plantage** sur une ligne dont une colonne est nulle (`meta_creatives.py`, le
    funnel par créative).

Classe : `an-absence-that-becomes-a-nan-because-nan-is-truthy`.
Remède : `src/dashboard/utils/safe_number.py` — `nombre()`, `entier()`, `mesure()`.

Ce que ce garde NE couvre PAS
------------------------------
(1) Les autres façons de produire un `NaN` : une division `0/0`, un `reindex` sans
`fill_value`, une soustraction de séries mal alignées. Le prédicat ne voit que la
conjonction `to_numeric(...) or <défaut>`. (2) `src/collectors/` et `airflow/`, hors
du balayage. (3) Le choix entre `nombre()` (zéro) et `mesure()` (`None`) : qu'un
site ait pris le mauvais des deux lui est invisible — et c'est le choix qui compte,
puisqu'un zéro affiché est un fait affirmé.
"""
from __future__ import annotations

import ast
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[1] / "src" / "dashboard"
_REMEDE = _RACINE / "utils" / "safe_number.py"


def _sites_nan_vrai(arbre: ast.Module) -> list[int]:
    """Les `<conv>(pd.to_numeric(...) or X)`, par numéro de ligne, lus à l'AST.

    À l'AST et pas au texte : ce fichier et `safe_number.py` PARLENT du motif en
    toutes lettres pour l'expliquer. Un prédicat textuel rougirait donc sur la
    documentation du correctif — ce dépôt a déjà pris quatre gardes au vert sur
    leur propre commentaire.
    """
    trouves = []
    for n in ast.walk(arbre):
        # on cherche un BoolOp `or` dont le membre gauche est un appel to_numeric
        if not isinstance(n, ast.BoolOp) or not isinstance(n.op, ast.Or):
            continue
        gauche = n.values[0]
        if not isinstance(gauche, ast.Call):
            continue
        nom = getattr(gauche.func, "attr", "") or getattr(gauche.func, "id", "")
        if nom == "to_numeric":
            trouves.append(n.lineno)
    return sorted(trouves)


def _balayer() -> dict[str, list[int]]:
    out = {}
    for f in sorted(_RACINE.rglob("*.py")):
        if f == _REMEDE:
            continue
        try:
            arbre = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        lignes = _sites_nan_vrai(arbre)
        if lignes:
            out[str(f.relative_to(_RACINE.parents[1]))] = lignes
    return out


def test_the_remedy_exists_and_catches_nan():
    """Le module de secours est là, et il fait ce qu'il promet."""
    assert _REMEDE.exists(), f"{_REMEDE} a disparu — les huit sites n'ont plus de porte"
    from src.dashboard.utils.safe_number import entier, mesure, nombre

    nan = float("nan")
    assert nombre(nan) == 0.0
    assert entier(nan) == 0                      # ne lève pas — c'était le plantage
    assert mesure(nan) is None                   # une absence reste une absence
    assert mesure(None) is None
    assert nombre(12) == 12.0 and entier("3.5") == 3


def test_no_site_relies_on_or_to_catch_a_nan():
    """Le cliquet à zéro : les huit sont corrigés, aucun neuvième."""
    sites = _balayer()
    assert not sites, (
        "site(s) où `or` prétend rattraper une absence que `to_numeric` rend en "
        "`NaN` :\n  " + "\n  ".join(f"{f} → lignes {lg}" for f, lg in sites.items())
        + "\n\n`NaN` est VRAI : le `or` ne se déclenche pas. Utiliser "
          "`safe_number.nombre()` (zéro) ou `safe_number.mesure()` (None) — et "
          "choisir en se demandant si un zéro affiché serait un fait affirmé."
    )


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path):
    """Le garde se prouve lui-même — sinon son zéro ne vaut rien."""
    faux = tmp_path / "vue.py"
    faux.write_text(
        "import pandas as pd\n"
        "# un commentaire qui PARLE de `pd.to_numeric(x, errors='coerce') or 0`\n"
        "def show(r):\n"
        "    return float(pd.to_numeric(r['n'], errors='coerce') or 0)\n",
        encoding="utf-8")
    lignes = _sites_nan_vrai(ast.parse(faux.read_text(encoding="utf-8")))
    assert lignes == [4], (
        f"le détecteur rend {lignes} — il ne voit pas le vrai site, ou il compte le "
        "commentaire qui en parle"
    )


def test_the_corrected_form_leaves_the_detector_silent(tmp_path):
    """La réciproque : un prédicat qui dit oui à tout passerait le test précédent."""
    bon = tmp_path / "vue.py"
    bon.write_text(
        "from src.dashboard.utils.safe_number import nombre\n"
        "def show(r):\n"
        "    return nombre(r['n'])\n",
        encoding="utf-8")
    assert _sites_nan_vrai(ast.parse(bon.read_text(encoding="utf-8"))) == []


def test_an_unrelated_or_is_not_a_false_positive(tmp_path):
    """Le faux positif à écarter : tous les `or` ne sont pas ce défaut."""
    autre = tmp_path / "vue.py"
    autre.write_text(
        "def show(cfg, r):\n"
        "    nom = cfg.get('nom') or 'inconnu'\n"
        "    return (r.get('a') or 0) + (r.get('b') or 0)\n",
        encoding="utf-8")
    assert _sites_nan_vrai(ast.parse(autre.read_text(encoding="utf-8"))) == [], (
        "un `or` ordinaire est compté comme le défaut — le prédicat cherche une "
        "forme d'écriture au lieu de la conjonction avec `to_numeric`"
    )
