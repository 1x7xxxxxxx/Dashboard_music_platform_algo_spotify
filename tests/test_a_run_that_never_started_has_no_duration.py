"""Un run jamais démarré n'a pas duré zéro seconde : il n'a pas de durée.

Type: Test
Uses: ast
Depends on: src/dashboard/utils/airflow_monitor.py
Persists in: nothing

Pourquoi ce fichier existe — mesuré le 2026-09-18
-------------------------------------------------
`airflow_monitor.py` construisait `duration = 0` pour un `dag_run` sans `start_date` —
c'est-à-dire un run **en file d'attente ou planifié, qui n'a pas encore commencé**. La
colonne était donc remplie sur toutes les lignes, donc MESURÉE en apparence.

`airflow_kpi.py:564` en calcule la moyenne pour la tuile « Temps Exec Moyen (s) », sans
filtrer sur `state`. Effet mesuré sur trois runs dont un en attente :

    moyenne avec None : 10,0 s   (les deux mesures réelles)
    moyenne avec 0    :  6,7 s   (un tiers de moins, inventé)

Et le même fichier portait déjà la forme juste **onze lignes plus bas** :
`_run_summary` fait `duration_sec = None`. Deux chemins lisant la même API REST
répondaient donc différemment à la même question.

`None` devient `NaN`, que `.mean()` de pandas ignore — l'absence cesse d'être une
valeur.

Ce que ce garde ne couvre PAS
------------------------------
* les autres colonnes de mesure du dépôt (`peak_sessions`, `p50_render_ms`…) : elles
  ont leur propre traitement, et `dag_durations_s JSONB DEFAULT '{}'` est le
  contre-exemple correct, posé volontairement le 2026-09-18 ;
* un `0` légitime — un run qui a VRAIMENT duré moins d'une seconde. Le prédicat
  ci-dessous ne regarde que la branche « pas de `start_date` » ;
* les zéros écrits ailleurs que dans ce fichier.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_MONITOR = ROOT / "src" / "dashboard" / "utils" / "airflow_monitor.py"


def _branches_sans_start_date() -> list:
    """Les `else` d'un `if start_str:` — la branche « ce run n'a pas commencé »."""
    arbre = ast.parse(_MONITOR.read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.If) or not n.orelse:
            continue
        if "start_str" not in ast.unparse(n.test):
            continue
        out.append(n)
    return out


def test_the_branch_exists():
    """Non-vacuité : sans la branche, tout le fichier passe sur rien."""
    assert _branches_sans_start_date(), (
        "aucune branche `if start_str: … else:` dans airflow_monitor.py — soit le "
        "fichier a changé de forme, soit le prédicat est cassé. Dans les deux cas le "
        "test ci-dessous ne garde plus rien.")


def test_a_run_with_no_start_date_gets_no_duration():
    """La propriété : cette branche n'assigne JAMAIS un nombre à la durée."""
    fautifs = []
    for branche in _branches_sans_start_date():
        for n in ast.walk(ast.Module(body=branche.orelse, type_ignores=[])):
            if not isinstance(n, ast.Assign):
                continue
            cibles = {ast.unparse(t) for t in n.targets}
            if not any("duration" in c for c in cibles):
                continue
            if isinstance(n.value, ast.Constant) and n.value.value is not None:
                fautifs.append((sorted(cibles), n.value.value, n.lineno))
    assert not fautifs, (
        f"la durée reçoit une VALEUR dans la branche « pas de start_date » : {fautifs}. "
        "Un run qui n'a pas commencé n'a pas duré ce nombre de secondes — il n'a pas de "
        "durée. Écrire `None` : la colonne cesse d'avoir l'air mesurée, et `.mean()` "
        "l'ignore au lieu de la compter. Mesuré : sur trois runs dont un en attente, "
        "un `0` fait chuter la moyenne d'un tiers.")


def test_the_two_paths_of_this_file_agree():
    """`_run_summary` et la boucle principale lisent la MÊME API : même réponse.

    C'est la divergence qui a produit le défaut — deux chemins vers la même question,
    dont un seul avait reçu la bonne réponse.
    """
    from tests.code_text import code_of

    # `code_of`, pas `read_text` : le commentaire que j'ai posé DANS ce fichier cite
    # `duration_sec = None`, et suffirait à satisfaire cette assertion si elle lisait
    # le texte brut. C'est `guard-satisfied-by-its-own-comment`, produite par la prose
    # du correctif lui-même — sixième occurrence de cette forme dans la séance.
    src = code_of(_MONITOR)
    assert "duration_sec = None" in src, (
        "`_run_summary` n'initialise plus la durée à `None` — l'autre chemin du même "
        "fichier vient de perdre la propriété que celui-ci garde")


def test_pandas_really_skips_the_absence():
    """La conséquence, épinglée : `None` est ignoré, `0` est compté.

    Sans ce test, le correctif repose sur une croyance à propos de pandas.
    """
    import pandas as pd

    avec_none = pd.DataFrame([{"d": 12.0}, {"d": None}, {"d": 8.0}])["d"].mean()
    avec_zero = pd.DataFrame([{"d": 12.0}, {"d": 0}, {"d": 8.0}])["d"].mean()
    assert avec_none == 10.0, f"pandas ne saute plus l'absence : {avec_none}"
    assert avec_zero < avec_none, (
        f"un zéro ne tire plus la moyenne vers le bas ({avec_zero} contre {avec_none}) "
        "— la conséquence décrite par ce fichier a changé, le relire")
