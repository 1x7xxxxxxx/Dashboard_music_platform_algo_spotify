"""Une jointure sur un titre normalise les DEUX côtés, ou elle est muette.

Type: Test
Uses: ast, re
Depends on: src/dashboard/, src/utils/track_matching.py
Persists in: nothing

Trouvé le 2026-09-17 en triant la dernière signature `heuristic` non triée du
catalogue — `song-name-convention-mismatch`. **Deux sites vivants, tous deux
visibles par l'artiste.**

Spotify for Artists remplace `< > : " / \\ | ? *` par `_` dans le nom de ses
FICHIERS d'export. Le même titre arrive donc épelé de deux façons selon qu'il vient
d'un fichier ou d'une API :

  · `s4a_song_timeline.song`         — dérivé d'un nom de fichier → `_`
  · `track_popularity_history`       — écrite par l'API Spotify  → vrais caractères
  · `campaign_track_mapping`         — saisie via « Titre Spotify » → vrais caractères

Les deux sites comparaient un nom de FICHIER à une table d'API :

  · `trigger_algo/_tab_budget_roi.py` — `WHERE track_name = %s`, deux requêtes ;
  · `trigger_algo/_common/_budget_roi.py` — `LOWER(ctm.track_name) = LOWER(%s)`,
    où `LOWER` normalise la CASSE et pas la substitution.

⚠️ La courbe de popularité était donc MUETTE pour tout titre ponctué, sans erreur ni
message. **5 titres concernés sur la base de développement**, mesuré.

⚠️ Le routeur qui remplit le sélecteur normalisait DÉJÀ pour sa propre jointure
(`router.py:94`). La convention existait, `canonical_song_sql` existait — elles se
perdaient un appel plus loin. C'est la forme exacte de « une règle extraite dont un
seul appelant a été recâblé ».

Mutation record — 2026-09-17. **Ce garde a dû être corrigé QUATRE fois**, et chaque
correction vient d'une mutation qui passait au vert :
  1. `"canonical_song_sql" in src` → retirer l'IMPORT le laissait satisfait, les appels
     restant écrits dans les f-strings. Corrigé : `ast.Call`.
  2. exemption écrite `if "<phrase>" in texte` → refusée par
     `test_a_guard_reads_structure_not_text`, à raison : un commentaire la satisfait.
     Corrigé : une LISTE NOMMÉE, avec la raison de chaque entrée.
  3. `"def canonical_song_sql" in src` → passé à l'AST.
  4. `if "canonical_song_sql" in texte` dans la boucle → le COMMENTAIRE que je venais
     d'écrire dans `meta_x_spotify.py` contenait le nom, donc le fichier s'exemptait
     tout seul et la liste nommée était MORTE sans que rien ne le dise. Corrigé : `ast.Call`.

État final, les deux mutations qui comptent sont rouges : retirer les appels de
`_tab_budget_roi.py` (1 échec), et vider `_SAME_SOURCE_BOTH_SIDES` (1 échec — donc
l'exemption est bien atteinte, ce qui n'était pas le cas avant le point 4).

---
rex: []
---
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# Les tables dont le titre vient d'une API (vrais caractères). Une comparaison entre
# l'une d'elles et un nom venu d'un FICHIER doit normaliser.
_API_SPELLED = ("track_popularity_history", "campaign_track_mapping", "tracks")

# Les comparaisons VÉRIFIÉES comme sûres : les deux côtés viennent de la même source,
# donc aucune substitution de nom de fichier n'entre en jeu. Chaque entrée porte la
# raison — c'est ce qui la distingue d'un oubli.
_SAME_SOURCE_BOTH_SIDES = {
    "src/dashboard/views/meta_x_spotify.py":
        "`mapped_track` vient de `campaign_track_mapping` (sélecteur « Titre Spotify », "
        "donc API) et `track_popularity_history` est écrite par `spotify_api_daily` : "
        "aucun nom de FICHIER n'entre dans la comparaison. Vérifié le 2026-09-17.",
}

# Les jointures connues, avec le fichier qui les porte. La liste grandit par
# `test_no_new_song_join_escapes_this_guard`.
_JOINS = {
    "src/dashboard/views/trigger_algo/_tab_budget_roi.py": "track_popularity_history",
    "src/dashboard/views/trigger_algo/_common/_budget_roi.py": "campaign_track_mapping",
    "src/dashboard/views/trigger_algo/router.py": "tracks",
}


def test_the_normaliser_still_exists() -> None:
    """Anti-vacuité : sans l'outil, tout le reste passe."""
    arbre = ast.parse(
        (_ROOT / "src" / "utils" / "track_matching.py").read_text(encoding="utf-8"))
    defini = any(isinstance(n, ast.FunctionDef) and n.name == "canonical_song_sql"
                 for n in ast.walk(arbre))
    assert defini, (
        "`canonical_song_sql` a disparu de `track_matching.py` — c'est la seule "
        "normalisation partagée, et ce garde n'a plus de remède à nommer.")
    assert _JOINS, "`_JOINS` est vide : ce garde ne regarde plus aucune jointure"


@pytest.mark.parametrize("rel,table", sorted(_JOINS.items()))
def test_a_song_join_normalises_the_api_side(rel: str, table: str) -> None:
    """Chaque comparaison sur un titre passe par `canonical_song_sql`."""
    # ⚠️ À l'AST : la fonction doit être APPELÉE, pas seulement nommée. La première
    # version cherchait `"canonical_song_sql" in src` — une sous-chaîne — et retirer
    # l'IMPORT la laissait verte, parce que les appels restaient écrits dans les
    # f-strings. Neuvième lecture textuelle fausse de la séance.
    arbre = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    appele = any(
        isinstance(n, ast.Call)
        and (getattr(n.func, "id", "") or getattr(n.func, "attr", "")) == "canonical_song_sql"
        for n in ast.walk(arbre)
    )
    assert appele, (
        f"{rel} joint sur un titre de `{table}` sans APPELER `canonical_song_sql`.\n"
        "Un titre venu d'un export S4A porte `_` là où l'API porte `: / ? *` : la "
        "jointure rend zéro ligne, sans erreur et sans message. 5 titres concernés "
        "sur la base de développement, mesuré le 2026-09-17.\n"
        "Remède : `canonical_song_sql('<colonne>')` du côté API.")


def test_no_new_song_join_escapes_this_guard() -> None:
    """Et la population du garde grandit toute seule.

    Cherche une comparaison `<colonne>track_name = %s` dans `src/dashboard/` : toute
    nouvelle doit vivre dans un fichier qui importe le normaliseur.
    """
    manquants = []
    for chemin in sorted((_ROOT / "src" / "dashboard").rglob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        if not re.search(r"(?:\w+\.)?track_name\s*\)?\s*=\s*(?:LOWER\()?%s", texte):
            continue
        # ⚠️ À l'AST, pas en texte — DIXIÈME fois de la séance. Ma version précédente
        # faisait `if "canonical_song_sql" in texte`, et le COMMENTAIRE que je venais
        # d'écrire dans `meta_x_spotify.py` pour expliquer pourquoi il n'en a pas besoin
        # contenait le nom : le fichier s'exemptait tout seul, et l'exemption nommée
        # ci-dessous était morte sans que rien ne le dise.
        try:
            arbre_fichier = ast.parse(texte)
        except SyntaxError:                      # pragma: no cover
            continue
        if any(isinstance(n, ast.Call)
               and (getattr(n.func, "id", "") or getattr(n.func, "attr", ""))
               == "canonical_song_sql"
               for n in ast.walk(arbre_fichier)):
            continue
        # Une comparaison peut être LÉGITIMEMENT non normalisée quand les deux côtés
        # viennent de la même source. Ce qui n'est pas négociable, c'est que ce soit
        # ÉCRIT : sans la justification, un lecteur ne peut pas distinguer « vérifié »
        # de « oublié », et les deux se ressemblent exactement dans le code.
        #
        # ⚠️ L'exemption est une LISTE NOMMÉE, pas une phrase cherchée dans le source.
        # Ma première version faisait `if "<phrase>" in texte` — une comparaison de
        # chaîne au texte d'un source Python, que `test_a_guard_reads_structure_not_text`
        # refuse à raison : elle est satisfaite par n'importe quel commentaire, y
        # compris celui qui explique le défaut. Une liste se relit ; une phrase se
        # copie-colle.
        rel = str(chemin.relative_to(_ROOT))
        if rel in _SAME_SOURCE_BOTH_SIDES:
            continue
        manquants.append(rel)
    assert not manquants, (
        "des comparaisons sur `track_name` vivent dans des fichiers qui n'importent "
        f"pas le normaliseur : {manquants}.\n"
        "Soit la normaliser, soit — si les deux côtés viennent de la MÊME source — "
        "l'écrire ici pour que le prochain lecteur n'ait pas à le redéduire.")
