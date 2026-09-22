"""Un verdict de fraîcheur porte sur la date que la DONNÉE porte, pas sur l'écriture.

Type: Guard
Uses: ast, src.dashboard.utils.kpi_helpers
Depends on: kpi_helpers, views/home.py, views/alerts.py, pdf_exporter/_renderers.py
Persists in: nothing

DEUX DÉFAUTS, MESURÉS EN PRODUCTION LE 2026-09-22
---------------------------------------------------
**1. La MAUVAISE COLONNE.** La grille de l'accueil lisait `col`, la date d'ÉCRITURE.

    source          écriture      mesure        écart
    Meta Ads        2026-09-20    2024-09-30    **722 jours**
    SACEM           2026-06-11    2026-04-07    65 jours

Le DAG Meta réécrit chaque matin les mêmes lignes de 2024, donc la tuile affichait
« 🟢 il y a 0h » **et** la date d'aujourd'hui : **la couleur et la date mentaient
ensemble**, ce qui est pire qu'une seule des deux. La supervision admin lisait déjà la
bonne colonne depuis R154 — deux surfaces répondaient différemment à la même question.

**2. LA MAUVAISE REPRÉSENTATION.** `alerts.py` cherchait les sources à traiter ainsi :

    if freshness_status(info['last_dt'])[1] in ('#e74c3c', '#f39c12')

`freshness_status` rend `#1DB954`, `#FFA500`, `#FF4444`. **L'intersection est VIDE.** La
liste « sources périmées » ne pouvait donc JAMAIS se remplir, et l'écran affichait
« ✅ All data sources are fresh » sur un catalogue dont la moitié dort depuis des mois.
Un verdict ne se lit pas dans sa PRÉSENTATION : la couleur est ce qu'on dessine, l'état
est ce qu'on mesure.

CE QUE CE GARDE TIENT
---------------------
1. Les trois surfaces de verdict lisent `mesure_dt`, jamais `last_dt`.
2. Aucun appelant ne compare une COULEUR pour décider d'un état.
3. `get_source_freshness` rend les deux dates et distingue l'échec de l'absence.
4. La divergence se dit **sans seuil neuf** : quand les deux dates ne rendent pas le
   même verdict sur le barème existant.

⚠️ CE QU'IL NE TIENT PAS
------------------------
* **La JUSTESSE de `metric_col`** dans le registre — il est tenu à la main, et une table
  dont la colonne de mesure serait mal déclarée passerait ici sans un mot.
* **Le geste voisin le plus proche : les autres surfaces qui datent quelque chose.**
  `db_health` suit des jeux de données par leur date d'écriture — et c'est CORRECT pour
  sa question (« cet import grossit-il »). Rien ici ne distingue les deux usages ailleurs.
* **Les seuils eux-mêmes** (`_FRESH_H`, `_WARN_H`) : ce garde vérifie sur QUOI ils
  s'appliquent, jamais s'ils sont bien calibrés.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Les surfaces qui rendent un VERDICT de fraîcheur à un humain.
_SURFACES = (
    "src/dashboard/views/home.py",
    "src/dashboard/views/alerts.py",
    "src/dashboard/utils/pdf_exporter/_renderers.py",
)

#: Les couleurs que `freshness_status` rend. Comparer l'une d'elles pour DÉCIDER est le
#: défaut ; les écrire pour DESSINER ne l'est pas.
_COULEURS = ("#1DB954", "#FFA500", "#FF4444", "#888888", "#e74c3c", "#f39c12")


def _arbre(rel: str) -> ast.AST:
    return ast.parse((_ROOT / rel).read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════
# 1. LA BONNE COLONNE
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("rel", _SURFACES)
def test_a_verdict_is_computed_on_the_measurement_date(rel: str) -> None:
    """`freshness_status` / `freshness_state` reçoivent `mesure_dt`, jamais `last_dt`.

    Par l'AST : on regarde l'ARGUMENT de chaque appel, pas le texte du fichier — les
    docstrings de ces trois fichiers nomment `last_dt` une dizaine de fois pour
    expliquer POURQUOI il est parti, et un prédicat textuel rougirait sur sa propre
    explication.
    """
    fautes = []
    for n in ast.walk(_arbre(rel)):
        if not isinstance(n, ast.Call):
            continue
        nom = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
        if nom not in ("freshness_status", "freshness_state") or not n.args:
            continue
        arg = ast.unparse(n.args[0])
        if "last_dt" in arg:
            fautes.append(f"ligne {n.lineno} : {nom}({arg})")
    assert not fautes, (
        f"`{rel}` calcule un verdict de fraîcheur sur la date d'ÉCRITURE :\n"
        + "\n".join(f"    {f}" for f in fautes)
        + "\n\nMesuré en production le 2026-09-22 : `meta_insights_performance_day` "
          "porte un `MAX(collected_at)` du jour même et un `MAX(day_date)` au "
          "2024-09-30 — 722 jours. Passer `mesure_dt`.")


def test_the_query_returns_both_dates() -> None:
    """Les deux sont nécessaires : l'une date la donnée, l'autre DIAGNOSTIQUE."""
    from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG, get_source_freshness

    class _Muet:
        def fetch_query(self, *_a, **_k):
            return []

    # ⚠️ UN `artist_id` DISTINCT PAR CAS. `get_source_freshness` est décorée
    # `@st.cache_data`, et son premier paramètre s'appelle `_db` — le tiret bas le
    # SORT de la clé de cache. Trois faux clients de base avec le même `artist_id`
    # partagent donc un seul résultat : mon test d'échec lisait le succès du test
    # précédent. Le cache n'est pas en cause, ma clé l'était.
    out = get_source_freshness(_Muet(), 900001)
    assert set(out) == {s["label"] for s in SOURCES_CONFIG}
    for label, info in out.items():
        for cle in ("last_dt", "mesure_dt", "ecart_j", "lu"):
            assert cle in info, f"{label} ne porte pas `{cle}`"


def test_the_measurement_column_comes_from_the_registry() -> None:
    """Pas de seconde déclaration : `colonne_de_mesure` est la seule source."""
    src = (_ROOT / "src" / "dashboard" / "utils" / "kpi_helpers.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    appelle = any(isinstance(n, ast.Call)
                  and (getattr(n.func, "id", None) == "colonne_de_mesure")
                  for n in ast.walk(tree))
    assert appelle, (
        "`kpi_helpers` ne demande plus la colonne de mesure au registre : elle est "
        "donc déclarée une seconde fois, et les deux divergeront.")


# ══════════════════════════════════════════════════════════════════════════
# 2. UN VERDICT NE SE LIT PAS DANS SA COULEUR
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_decides_by_comparing_a_colour(rel: str) -> None:
    """LE DÉFAUT QUI NE POUVAIT JAMAIS SE DÉCLENCHER.

    On cherche une COMPARAISON (`==`, `in`, `!=`) dont un membre est un littéral de
    couleur. Dessiner une couleur est légitime ; DÉCIDER avec l'est pas — et les deux
    listes avaient divergé sans qu'aucun test ne le voie.
    """
    fautes = []
    for n in ast.walk(_arbre(rel)):
        if not isinstance(n, ast.Compare):
            continue
        morceaux = [n.left, *n.comparators]
        for m in morceaux:
            for c in ast.walk(m):
                if (isinstance(c, ast.Constant) and isinstance(c.value, str)
                        and c.value in _COULEURS):
                    fautes.append(f"ligne {n.lineno} : {ast.unparse(n)[:80]}")
                    break
    assert not fautes, (
        f"`{rel}` DÉCIDE en comparant une couleur :\n"
        + "\n".join(f"    {f}" for f in dict.fromkeys(fautes))
        + "\n\nLes deux listes avaient divergé : `alerts.py` cherchait `#e74c3c` et "
          "`#f39c12`, `freshness_status` rendait `#FF4444` et `#FFA500` — intersection "
          "VIDE, donc la liste des sources périmées ne pouvait jamais se remplir. "
          "Comparer `freshness_state(...)` contre `ETATS_A_TRAITER`.")


def test_the_states_and_the_colours_still_agree() -> None:
    """NON-VACUITÉ : chaque état doit produire une couleur DISTINCTE.

    Sans ce test, un barème qui rendrait la même couleur partout passerait le garde
    ci-dessus en rendant la comparaison de couleurs inoffensive — et inutile.
    """
    from src.dashboard.utils.kpi_helpers import freshness_state, freshness_status

    now = datetime.now(timezone.utc)
    vus = {}
    for jours in (0, 2, 800, None):
        dt = None if jours is None else now - timedelta(days=jours)
        vus[freshness_state(dt)] = freshness_status(dt)[1]
    assert len(vus) == 4, f"les quatre états ne sont plus atteignables : {vus}"
    assert len(set(vus.values())) == 4, (
        f"deux états rendent la même couleur : {vus} — le garde des couleurs "
        "deviendrait sans objet.")


def test_the_states_to_act_on_are_named_once() -> None:
    """`ETATS_A_TRAITER` existe pour qu'aucun appelant ne réécrive la liste."""
    from src.dashboard.utils.kpi_helpers import (
        ETAT_ATTENTION, ETAT_FRAIS, ETAT_INCONNU, ETAT_PERIME, ETATS_A_TRAITER)

    assert ETATS_A_TRAITER == {ETAT_ATTENTION, ETAT_PERIME}
    assert ETAT_FRAIS not in ETATS_A_TRAITER
    assert ETAT_INCONNU not in ETATS_A_TRAITER, (
        "« on ne sait pas » compte comme « à traiter » : une source jamais branchée "
        "remplirait la liste des pannes.")


# ══════════════════════════════════════════════════════════════════════════
# 3. UN ÉCHEC N'EST PAS UNE ABSENCE
# ══════════════════════════════════════════════════════════════════════════

def test_a_failed_read_is_not_an_empty_catalogue() -> None:
    """`lu=False` dit « on n'a pas pu lire », pas « il n'y a rien »."""
    from src.dashboard.utils.kpi_helpers import get_source_freshness

    class _Casse:
        def fetch_query(self, *_a, **_k):
            raise RuntimeError("base injoignable (simulée)")

    out = get_source_freshness(_Casse(), 900002)
    assert out, "une lecture ratée rend un dictionnaire vide : les surfaces lèveront"
    assert all(info["lu"] is False for info in out.values()), (
        "une lecture ratée se présente comme un catalogue vide — indistinguable d'un "
        "locataire sans données. C'est ce que `.claude/rules/python.md` interdit.")


def test_a_real_absence_still_reads_as_read() -> None:
    """NON-VACUITÉ DU DRAPEAU : il doit SÉPARER, pas valoir False partout."""
    from src.dashboard.utils.kpi_helpers import get_source_freshness

    class _Vide:
        def fetch_query(self, *_a, **_k):
            return []

    out = get_source_freshness(_Vide(), 900003)
    assert all(info["lu"] is True for info in out.values()), (
        "une lecture RÉUSSIE qui ne rend aucune ligne est marquée comme un échec : le "
        "drapeau ne distingue plus rien.")
    assert all(info["mesure_dt"] is None for info in out.values())


def test_the_alerts_view_refuses_to_say_all_fresh_on_a_failed_read() -> None:
    """Le cas qui compte : une panne ne doit pas s'afficher « ✅ tout est frais »."""
    src = (_ROOT / "src" / "dashboard" / "views" / "alerts.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_section_freshness_alerts"), None)
    assert fn is not None, "`_section_freshness_alerts` a disparu d'`alerts.py`"
    lit_le_drapeau = any(
        isinstance(n, ast.Constant) and n.value == "lu" for n in ast.walk(fn))
    assert lit_le_drapeau, (
        "la vue Alertes ne regarde plus si la lecture a réussi : une base injoignable "
        "s'y afficherait « ✅ All data sources are fresh ».")
