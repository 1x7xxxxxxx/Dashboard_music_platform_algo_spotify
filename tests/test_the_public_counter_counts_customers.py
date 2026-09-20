"""Le compteur PUBLIC ne compte que des clients.

Type: Test
Uses: ast, la base joignable
Depends on: src/dashboard/views/live_pulse.py, src/utils/tenant_kind
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-20 (R140 §16.9d) : `live_pulse.py:71` — une page **publique** —
annonçait **10 artistes**. Neuf étaient des artefacts de test :

    8 × « Oracle Probe »   créés le 2026-09-15 entre 18h32 et 18h34
    1 × « Smoke smoke-… »  créé le 2026-09-06
    1 × « 1x7xxxxxxx »     le seul vrai locataire

Les huit portent `created_at` dans un intervalle de DEUX MINUTES : une seule exécution
de `test_registration_is_not_an_oracle.py`, dont les inscriptions passent par le VRAI
formulaire et n'étaient donc marquées d'aucun drapeau.

⚠️ **Marquer, pas effacer.** Effacer est irréversible et ne règle rien : la prochaine
exécution recrée des lignes identiques. Les deux fixtures posent maintenant `is_sandbox`
— à la création pour `test_views_render_smoke`, après coup pour l'autre — et la migration
129 rattrape les lignes déjà là.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.tenant_kind import HUMAN_TENANTS  # noqa: E402


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        return None


def test_no_test_artifact_is_counted_as_a_customer() -> None:
    """LE GARDE. Un nom de fixture dans le compte public est un artefact non marqué."""
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        restants = db.fetch_query(
            f"SELECT id, name FROM saas_artists WHERE {HUMAN_TENANTS} "
            "AND (name = 'Oracle Probe' OR name LIKE 'Smoke smoke-%%' "
            "     OR name LIKE 'Taken %%')") or []
    finally:
        db.close()
    assert not restants, (
        f"artefact(s) de test compté(s) comme client(s) : {restants}\n"
        "Une fixture a créé un locataire sans le marquer `is_sandbox`. La page "
        "`live_pulse` est PUBLIQUE : elle annonçait 10 artistes pour 1 réel.")


def _sql_du_fichier(rel: str) -> str:
    """Le SQL que ce fichier CONTIENT, lu dans ses littéraux — pas dans son texte.

    ⚠️ La première version comparait `"is_sandbox" in texte` au SOURCE, et
    `test_a_guard_reads_structure_not_text` l'a refusée — pour la QUATRIÈME fois de la
    soirée. Elle a raison : le commentaire qui EXPLIQUE le correctif contient le mot, et
    aurait tenu le garde à lui seul. Quatre gardes de ce dépôt ont été pris au vert sur
    leur propre défaut en une seule soirée, pour exactement cette raison.

    Passer par `ast` règle le problème par construction : un commentaire n'est pas un
    nœud, et les docstrings sont écartées explicitement.
    """
    arbre = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    docs = {ast.get_docstring(n) for n in ast.walk(arbre)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))}
    return "\n".join(
        n.value for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docs)


def test_both_fixtures_mark_what_they_create() -> None:
    """La source, pas seulement l'état. Nettoyer la base ne protège pas la suivante."""
    smoke = _sql_du_fichier("tests/test_views_render_smoke.py")
    assert "is_sandbox" in smoke, (
        "`test_views_render_smoke` crée un locataire sans `is_sandbox` dans son SQL. Sa "
        "fixture nettoie derrière elle — mais une exécution morte en route laisse sa "
        "ligne, et le nettoyage ne peut pas être la seule défense.")
    oracle = _sql_du_fichier("tests/test_registration_is_not_an_oracle.py")
    assert "is_sandbox" in oracle, (
        "`test_registration_is_not_an_oracle` ne marque pas ses inscriptions. Elles "
        "passent par le vrai formulaire — c'est son objet — donc rien ne peut les "
        "marquer à la création : il lui faut un nettoyage explicite.")


def test_the_human_predicate_still_excludes_something() -> None:
    """ANTI-VACUITÉ : si `HUMAN_TENANTS` n'excluait plus rien, tout ceci serait vide."""
    db = _db()
    if db is None:
        pytest.skip("base injoignable")
    try:
        total = db.fetch_query("SELECT count(*) FROM saas_artists")[0][0]
        humains = db.fetch_query(
            f"SELECT count(*) FROM saas_artists WHERE {HUMAN_TENANTS}")[0][0]
    finally:
        db.close()
    assert humains < total, (
        f"{humains} locataires « humains » sur {total} au total : le prédicat n'exclut "
        "RIEN. Soit il est cassé, soit plus aucun canari ni bac à sable n'existe — et "
        "dans les deux cas le compteur public ne protège plus rien.")
