"""Une vue d'analyse ne fabrique pas son propre sélecteur de période.

Type: Test
Uses: ast, pytest
Depends on: src/dashboard/views/**, src/dashboard/utils/period_filter.py
Persists in: nothing

La demande, et pourquoi elle mérite un garde
---------------------------------------------
2026-09-21 : « pour le top contenus, mets la période de contenu comme les autres
filtres temporels de l'app et fais ainsi pour toute l'app, il faut qu'on ait les
mêmes filtres à chaque fois. »

Le mot qui compte est **à chaque fois**. Corriger YouTube à la main répond à
l'instance ; le prochain sélecteur maison naîtra dans la vue suivante, et rien ne
le dira. Ce fichier est la moitié mécanisable de la demande.

Ce que le sélecteur maison de YouTube perdait, mesuré
------------------------------------------------------
Il offrait cinq préréglages écrits à la main convertis en `timedelta`. Par rapport
à `smart_period_filter`, il perdait :

  · l'**ancrage sur la dernière sortie**, qui est le défaut de toute l'app ;
  · la **plage personnalisée** ;
  · et surtout la borne sur l'**étendue RÉELLE** des données — un artiste pouvait
    y choisir « 30 derniers jours » sur une chaîne sans publication récente et
    obtenir une section vide, ce que `smart_period_filter` rend impossible par
    construction (`_data_span`).

Trois définitions de « période » dans un produit, c'est trois réponses possibles à
la même question.

Ce que ce garde NE tient PAS, et c'est délibéré
------------------------------------------------
Il ne regarde que les vues du PARCOURS ARTISTE. Trois familles en sortent, chacune
pour une raison écrite dans `_HORS_PARCOURS` :

  · l'ops et l'admin — une fenêtre de supervision n'est pas une fenêtre d'analyse,
    et son public n'est pas le même ;
  · les sélecteurs de MOIS DE RELEVÉ (revenus, uploads) — on y choisit un
    document, pas un intervalle ;
  · la fenêtre de campagne de `meta_x_spotify`, bespoke et documentée : tous les
    préréglages partagés finissent AUJOURD'HUI, ce qui étirait l'axe d'une
    campagne de 31 jours sur 662.

⚠️ Et un faux positif a été écarté à la lecture, pas par le prédicat :
`trigger_algo/_tab_algo_streams.py` porte un widget nommé « Fenêtre » qui n'est
pas une période — c'est `time_window`, une VALEUR DE COLONNE de
`s4a_song_algo_outcomes` (la fenêtre S4A de la saisie). Un prédicat qui cherche le
mot « fenêtre » l'attrape ; il cherche donc une PROPRIÉTÉ : un widget dont les
options se convertissent en dates.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"

_CANONIQUES = {"smart_period_filter", "entity_period_filter", "smart_date_range"}

# Hors du parcours artiste — chacune avec SA raison, jamais une liste nue.
_HORS_PARCOURS = {
    "admin.py": "supervision : on y choisit un mois de facturation, pas une fenêtre",
    "airflow_kpi.py": "ops : fenêtre de supervision des DAG, public exploitant",
    "etl_logs.py": "ops : profondeur du journal, public exploitant",
    "usage_analytics.py": "ops : fenêtre d'usage produit, public exploitant",
    "export_pdf.py": "paramètre d'un RAPPORT, pas la fenêtre d'une figure à l'écran",
    "upload_csv.py": "période COUVERTE par un export déposé — une métadonnée du fichier",
    "imusician.py": "mois de RELEVÉ : on choisit un document comptable, pas un intervalle",
    "meta_x_spotify.py": "fenêtre de CAMPAGNE, bespoke et documentée : tous les "
                         "préréglages partagés finissent aujourd'hui, ce qui étirait "
                         "l'axe d'une campagne de 31 jours sur 662",
    "_tab_algo_streams.py": "« Fenêtre » y est `time_window`, une valeur de colonne de "
                            "`s4a_song_algo_outcomes` — pas une période",
}

# Les mots qui, dans un LIBELLÉ de widget, annoncent un intervalle de temps.
_LIBELLE_TEMPOREL = re.compile(
    r"(p[ée]riode|fen[êe]tre|derniers?\s+(jours|mois)|depuis|intervalle)", re.I)
_WIDGETS = {"selectbox", "radio", "segmented_control", "slider", "date_input"}


def _libelle(node: ast.Call) -> str:
    """Le texte du premier argument — littéral, ou défaut d'un `t(clé, défaut)`."""
    if not node.args:
        return ""
    a = node.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        return a.value
    if isinstance(a, ast.Call) and a.args and isinstance(a.args[-1], ast.Constant) \
            and isinstance(a.args[-1].value, str):
        return a.args[-1].value
    return ""


def _view_files() -> list[str]:
    return [str(p.relative_to(_ROOT)) for p in sorted(_VIEWS.rglob("*.py"))
            if "__pycache__" not in str(p) and not p.name.startswith("__")]


def _maison(rel: str, racine: pathlib.Path | None = None) -> list[str]:
    """Les widgets dont le LIBELLÉ annonce un intervalle de temps."""
    tree = ast.parse(((racine or _ROOT) / rel).read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") in _WIDGETS:
            lbl = _libelle(n)
            if lbl and _LIBELLE_TEMPOREL.search(lbl):
                out.append(f"L{n.lineno} {n.func.attr}({lbl!r})")
    return out


@pytest.mark.parametrize("rel", _view_files())
def test_no_view_rolls_its_own_period_selector(rel: str) -> None:
    nom = pathlib.Path(rel).name
    if nom in _HORS_PARCOURS:
        pytest.skip(f"{nom} : {_HORS_PARCOURS[nom]}")
    maison = _maison(rel)
    assert not maison, (
        f"{rel} fabrique son propre sélecteur de période :\n  " + "\n  ".join(maison)
        + "\nUtilise `smart_period_filter` / `entity_period_filter` : eux seuls "
          "bornent sur l'étendue RÉELLE des données (donc ne proposent jamais une "
          "fenêtre vide), offrent la plage personnalisée et l'ancrage sur la dernière "
          "sortie.\nSi ce widget n'est PAS une période — `trigger_algo` en a un nommé "
          "« Fenêtre » qui est une valeur de colonne — inscris-le dans "
          "`_HORS_PARCOURS` AVEC sa raison.")


def test_the_detector_sees_a_home_made_selector(tmp_path) -> None:
    """NON-VACUITÉ. Sans elle, le test passe aussi sur un prédicat mort."""
    sonde = tmp_path / "_probe_period.py"  # tmp_path, never the real tree: a probe written there races the tree's scanners under xdist (2026-09-26)
    sonde.write_text(
        "import streamlit as st\n"
        "def show():\n"
        "    st.selectbox('Période de publication', ['12 derniers mois'])\n",
        encoding="utf-8")
    try:
        assert _maison(sonde.name, tmp_path), (
            "le détecteur ne voit plus un sélecteur de période écrit à la main")
    finally:
        sonde.unlink()


def test_the_detector_ignores_a_widget_that_is_not_a_period(tmp_path) -> None:
    """Le FAUX POSITIF qui compte, et il est réel.

    `trigger_algo/_tab_algo_streams.py` nomme « Fenêtre » un widget qui choisit
    `time_window`, une valeur de colonne. Un prédicat qui cherche le mot l'attrape ;
    celui-ci doit être écartable NOMMÉMENT, et l'être — pas par hasard.
    """
    sonde = tmp_path / "_probe_not_period.py"  # tmp_path, never the real tree: a probe written there races the tree's scanners under xdist (2026-09-26)
    sonde.write_text(
        "import streamlit as st\n"
        "def show():\n"
        "    st.selectbox('Type de contenu', ['Short', 'Vidéo'])\n"
        "    st.slider('Nombre de vidéos', 5, 50, 10)\n",
        encoding="utf-8")
    try:
        assert not _maison(sonde.name, tmp_path), (
            "le détecteur accuse un widget qui n'a rien de temporel")
    finally:
        sonde.unlink()
    assert "_tab_algo_streams.py" in _HORS_PARCOURS, (
        "le faux positif connu n'est plus déclaré : il reviendra sans sa raison")


def test_the_scan_is_not_vacuous() -> None:
    """Une liste de vues vide ne produirait aucun cas, et rien ne rougirait."""
    vues = _view_files()
    assert len(vues) >= 30, (
        f"{len(vues)} vue(s) balayée(s) — il y en avait bien plus le 2026-09-21.")
    couvertes = [v for v in vues if pathlib.Path(v).name not in _HORS_PARCOURS]
    assert len(couvertes) >= 25, (
        f"{len(couvertes)} vue(s) réellement vérifiées : les exemptions ont mangé "
        "le garde.")


def test_the_canonical_selectors_still_exist() -> None:
    """Un interdit dont le remplacement a disparu se fait contourner."""
    pf = ast.parse((_ROOT / "src" / "dashboard" / "utils" / "period_filter.py")
                   .read_text(encoding="utf-8"))
    definies = {n.name for n in ast.walk(pf) if isinstance(n, ast.FunctionDef)}
    manquantes = _CANONIQUES - definies - {"smart_date_range"}
    assert not manquantes, (
        f"{sorted(manquantes)} n'existe(nt) plus : ce garde n'a plus rien à proposer.")
