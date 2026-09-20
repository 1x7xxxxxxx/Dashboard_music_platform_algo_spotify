"""Une différence entre deux mesures espacées n'est pas un quotidien.

Type: Test
Uses: ast, la base joignable
Depends on: src/dashboard/views/apple_music.py,
            src/dashboard/utils/pdf_exporter/_collectors.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
`plays - LAG(plays) OVER (ORDER BY date)` suppose deux mesures **consécutives**. Apple
Music est nourri par un dépôt de CSV à la main, donc les mesures sont espacées. Mesuré
le 2026-09-20 sur `apple_songs_history` :

    11 paires · **0 consécutive** · plus grand trou **12 jours**

**Cent pour cent des points** portaient donc la croissance de plusieurs jours posée sur
une seule journée. Un artiste lisait un pic là où il y avait une accumulation.

⚠️ **Les DEUX lecteurs, pas un.** La vue et le moteur PDF portaient la même requête ;
corriger l'un aurait laissé l'autre mentir, et c'est la classe que ce dépôt a déjà payée
avec `canonical_song_sql`.

⚠️ La différence non consécutive est **écartée**, pas mise à zéro : la taire serait
inventer un zéro, la dessiner serait inventer un pic. Son absence se voit — c'est la
règle « l'absence devient un pixel ».
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_LECTEURS = (
    "src/dashboard/views/apple_music.py",
    "src/dashboard/utils/pdf_exporter/_collectors.py",
)


def _sql_du_fichier(rel: str) -> str:
    """Le SQL que ce fichier CONTIENT, lu dans ses littéraux — pas dans son texte.

    ⚠️ La première version de ce garde comparait des expressions régulières au TEXTE du
    fichier, et `test_a_guard_reads_structure_not_text` l'a refusée. Elle avait raison :
    **quatre gardes ont été pris au vert sur le défaut qu'ils existaient pour attraper,
    en une seule soirée**, parce qu'un commentaire ou une docstring suffisait à satisfaire
    la correspondance. Ici le commentaire qui EXPLIQUE le correctif contient
    `jours_ecoules = 1` — il aurait tenu le garde à lui seul.

    Passer par `ast` règle le problème par construction : un commentaire n'est pas un
    nœud, et une docstring est écartée explicitement.
    """
    arbre = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    docs = {ast.get_docstring(n) for n in ast.walk(arbre)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))}
    morceaux = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if n.value not in docs:
                morceaux.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            morceaux.extend(v.value for v in n.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return "\n".join(morceaux)


@pytest.mark.parametrize("rel", _LECTEURS)
def test_every_lag_on_apple_is_bounded_by_consecutivity(rel: str) -> None:
    """LE GARDE. Un `LAG` sur `apple_songs_history` sans borne de jours.

    Le prédicat cherche la PROPRIÉTÉ dans le SQL RÉEL : la requête qui fait un
    `LAG(plays)` doit aussi mesurer l'écart de dates ET le contraindre à 1.
    """
    sql = _sql_du_fichier(rel)
    if "apple_songs_history" not in sql:
        pytest.skip(f"{rel} ne lit plus `apple_songs_history`")
    assert re.search(r"LAG\s*\(\s*plays", sql), (
        f"{rel} ne fait plus de `LAG(plays)` — mettre ce garde à jour.")
    assert re.search(r"LAG\s*\(\s*date", sql), (
        f"{rel} calcule un quotidien par `LAG(plays)` sans mesurer l'ÉCART DE DATES. "
        "Sur `apple_songs_history`, 0 paire sur 11 est consécutive et le plus grand "
        "trou vaut 12 jours : chaque point porterait plusieurs jours de croissance.")
    assert re.search(r"(jours_ecoules|jours)\s*=\s*1", sql), (
        f"{rel} mesure l'écart de dates mais ne le CONTRAINT pas à 1. Calculer sans "
        "filtrer ne change rien à ce que l'artiste lit.")


def test_the_data_still_justifies_the_guard() -> None:
    """ANTI-VACUITÉ, et la mesure rejouée plutôt que recopiée.

    Si Apple redevenait quotidien, la contrainte n'écarterait plus rien et ce garde
    deviendrait décoratif. Ce test le dirait — c'est le moment de rouvrir la question
    « faut-il encore écarter ? » plutôt que de la laisser figée.
    """
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable")
    try:
        r = db.fetch_query(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE d = 1), MAX(d) FROM ("
            "  SELECT date - LAG(date) OVER (PARTITION BY song_name ORDER BY date) d"
            "    FROM apple_songs_history) t WHERE d IS NOT NULL")[0]
    finally:
        db.close()
    paires, consecutives, trou = r
    if paires == 0:
        pytest.skip("aucune paire sur cette instance")
    assert consecutives < paires, (
        f"les {paires} paires sont TOUTES consécutives (plus grand trou : {trou} j). "
        "Apple est redevenu quotidien : la contrainte `jours = 1` n'écarte plus rien, "
        "et la question « faut-il encore écarter ? » mérite d'être rouverte.")
