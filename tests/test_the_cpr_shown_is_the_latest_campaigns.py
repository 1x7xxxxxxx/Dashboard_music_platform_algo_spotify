"""Le CPR affiché est celui de la DERNIÈRE campagne, pas le record de tous les temps.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/utils/platform_timeseries.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
« Pour le meta ads meilleur CPR : met en automatique la dernière release et pas
forcément les meilleurs résultats qu'on a obtenu toute campagne confondue »
(2026-09-12).

La requête classait par `ORDER BY spend / results ASC LIMIT 1` : le RECORD historique.
Un record a deux défauts qui n'ont rien à voir avec sa justesse. Il est **irréfutable**
— on ne peut pas faire mieux qu'un record, donc le chiffre ne bouge jamais et ne dit
rien de ce qui marche aujourd'hui. Et il vient d'une audience qui n'existe peut-être
plus : mesuré le 2026-09-12 sur l'artiste 1, la campagne la moins chère datait de 2023.

Le classement est donc `ORDER BY last_day DESC` : la campagne la plus récemment
active. Mesuré le même jour, elle est bien celle de la dernière sortie — « O chiotte
l'arbitre Tucome Back » (2024-08-31 → 2024-09-30), CPR 0,109 € sur 755,52 €, là où la
dernière sortie s'appelle « Ô Chiotte l'arbitre Tucome Back - Original ».

⚠️ **ET SURTOUT PAS UN RAPPROCHEMENT DE NOM.** Accent, casse et suffixe diffèrent tous
les trois entre le titre et la campagne. Un rapprochement flou qui se trompe de
campagne en SILENCE est pire qu'une règle simple que l'artiste peut vérifier — le nom
de la campagne retenue est affiché avec le chiffre.

Mutations vues rouges avant écriture (2026-09-12) :
  * `ORDER BY last_day DESC` remis en `ORDER BY spend / results ASC` →
    test_the_campaign_is_ranked_by_recency ÉCHOUE en nommant le critère trouvé ;
  * `MAX(day) AS last_day` retiré de la sous-requête → même test ÉCHOUE.
"""
from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src/dashboard/utils/platform_timeseries.py"


def _executable_sql() -> str:
    """Le SQL de `period_side_metrics`, **commentaires retirés**.

    Deux protections, et il faut les deux :

    1. le littéral est extrait par `ast`, jamais cherché dans le texte du fichier —
       un commentaire PYTHON expliquant le correctif ne peut donc pas le satisfaire ;
    2. les commentaires **SQL** (`--`) sont retirés, parce que le littéral en porte
       beaucoup et qu'ils nomment les clauses qu'ils expliquent. Sans ce second
       filtre, « la CTE classe-t-elle par récence ? » serait satisfaite par la phrase
       qui raconte pourquoi elle le fait. C'est la forme exacte des trois gardes pris
       au vert le 2026-09-04, déplacée d'un langage à l'autre.

    Et les vérifications portent sur une CLAUSE EXTRAITE comparée par `==`, jamais
    sur un « ce texte apparaît quelque part » : une clause extraite dit ce que la
    requête fait, une sous-chaîne dit seulement que les mots existent.
    """
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "period_side_metrics")
    raw = "\n".join(
        n.value for n in ast.walk(fn)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "best_cpr" in n.value)
    return "\n".join(ln.split("--", 1)[0] for ln in raw.splitlines())


def _cte(name: str) -> str:
    """Le corps de la CTE `name`, sans commentaires ni espaces superflus."""
    sql = _executable_sql()
    if f"{name} AS (" not in sql:
        return ""
    body = sql.split(f"{name} AS (", 1)[1].split("\n            ), ", 1)[0]
    return " ".join(body.split())


def _clause(cte_name: str, keyword: str) -> str:
    """La clause `keyword` d'une CTE — « last_day DESC » pour `ORDER BY`.

    Extraire la clause plutôt que chercher son texte est ce qui rend la vérification
    EXACTE : une requête qui classerait par récence PUIS par coût ne passerait pas,
    alors qu'un `in` la laisserait passer.
    """
    body = _cte(cte_name)
    if keyword not in body:
        return ""
    tail = body.split(keyword, 1)[1].strip()
    # ⚠️ PAS DE « ) » DANS LES BORNES. La première version s'y arrêtait et rendait
    # « SUM(results » pour un `HAVING SUM(results) > 0 AND …` : la parenthèse
    # fermante d'un appel de fonction n'est pas la fin de la clause. Le test
    # échouait alors sur sa propre extraction, pas sur son sujet — et un garde qui
    # échoue sur sa mise en scène finit relâché jusqu'à ce qu'il se taise.
    for stop in ("LIMIT", "HAVING", "GROUP BY", "ORDER BY"):
        if stop in tail:
            tail = tail.split(stop, 1)[0]
    # La sous-requête se referme sur « ) <alias> » : on coupe à la parenthèse qui
    # ferme PLUS qu'elle n'ouvre, c'est-à-dire à la profondeur négative.
    depth, cut = 0, len(tail)
    for i, ch in enumerate(tail):
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                cut = i
                break
            depth -= 1
    return " ".join(tail[:cut].split())


def test_the_query_is_readable_at_all():
    """Non-vacuité : sans le littéral SQL, tout ce fichier passe sur du vide."""
    sql = _executable_sql()
    assert _cte("best_cpr"), (
        "le SQL de `period_side_metrics` ne porte plus la CTE `best_cpr` — la "
        "question a changé de fichier et ce garde ne voit plus rien")
    assert "v_meta_campaign_daily" in sql


def test_the_campaign_is_ranked_by_recency():
    """Le classement est la RÉCENCE, jamais le coût."""
    order = _clause("best_cpr", "ORDER BY")
    assert order == "last_day DESC", (
        f"la CTE `best_cpr` classe par « {order or '(rien)'} » au lieu de "
        "« last_day DESC ». Un record de CPR est irréfutable — on ne peut pas faire "
        "mieux qu'un record, donc le chiffre ne bouge jamais — et il vient d'une "
        "audience qui n'existe peut-être plus : mesuré le 2026-09-12, la campagne la "
        "moins chère de l'artiste 1 datait de 2023.")
    assert "MAX(day) AS last_day" in _cte("best_cpr"), (
        "`last_day` n'est plus calculé : le classement par récence porte sur une "
        "colonne absente, et la campagne retenue devient arbitraire")


def test_a_campaign_without_results_is_never_ranked():
    """Un CPR sans résultat n'est pas « infini », il est indéfini."""
    having = _clause("best_cpr", "HAVING")
    assert having == "SUM(results) > 0 AND SUM(spend) > 0", (
        f"le `HAVING` de `best_cpr` vaut « {having or '(rien)'} ». Sans lui, une "
        "campagne à zéro résultat entre dans le classement avec une division par "
        "zéro. Une dépense sans résultat n'est pas une mauvaise performance, c'est "
        "une performance indéfinie.")


def test_the_last_release_is_found_without_a_release_date():
    """`release_date` est NULL deux fois sur trois — on passe par l'ÂGE."""
    order = _clause("last_release", "ORDER BY")
    assert order == "days_since_release ASC", (
        f"la dernière sortie est classée par « {order or '(rien)'} » au lieu de "
        "« days_since_release ASC ». `track_release_reference.release_date` est NULL "
        "pour deux titres sur trois de l'artiste 1 (mesuré le 2026-09-12) : s'y fier "
        "écarterait justement les sorties les plus récentes.")
    assert "MAX(prediction_date)" in _cte("last_release"), (
        "la dernière sortie n'est plus cherchée sur la prédiction la plus RÉCENTE : "
        "on lirait un classement figé d'une ancienne exécution du modèle.")
