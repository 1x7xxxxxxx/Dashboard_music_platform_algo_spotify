"""Trois affirmations de documentation que le code contredisait.

Type: Test
Uses: ast
Depends on: src/dashboard/utils/collection_trigger.py,
            migrations/migrate_saas_artist_id.py,
            airflow/debug_dag/debug_soundcloud_oauth.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
R140 §16.3, §16.4 et §16.5 ont ceci en commun : **aucune n'est un défaut de code**. Dans
les trois cas le comportement est correct et c'est ce qui en est DIT qui était faux, ou
absent. Une phrase fausse coûte plus cher qu'un nombre faux : elle fait cesser de
vérifier.

  * `collection_trigger` annonçait « Fire every collection DAG for ONE tenant » alors
    qu'un `artist_id` à `None` collecte **toute la flotte** ;
  * `migrate_saas_artist_id.py` interpole des noms SQL sans allowlist et ne disait nulle
    part qu'il a **déjà servi** — le prochain qui cherche un modèle de migration
    recopiait la forme ;
  * `debug_soundcloud_oauth.py` imprimait un `refresh_token` en clair sans dire que la
    sortie ne doit pas être redirigée.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_the_trigger_docstring_admits_the_fleet_case() -> None:
    """Le titre disait « ONE tenant » ; le code collecte la flotte quand l'id est None."""
    arbre = ast.parse(
        (ROOT / "src/dashboard/utils/collection_trigger.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == "trigger_all_collections")
    doc = ast.get_docstring(fn) or ""
    assert "FLEET" in doc.upper(), (
        "la docstring de `trigger_all_collections` ne mentionne pas le cas flotte. "
        "Avec `artist_id=None` la `conf` est vide et le DAG collecte TOUS les artistes "
        "actifs — un admin qui lit « ONE tenant » croit déclencher une seule collecte.")
    # ET LE COMPORTEMENT EST INCHANGÉ, lu à l'AST : la `conf` reste conditionnelle.
    # Une comparaison de chaîne contre le source serait satisfaite par le commentaire
    # qui explique la décision — `test_a_guard_reads_structure_not_text` l'a mesuré
    # trois fois le 2026-09-04.
    conditionnelle = any(
        isinstance(n, ast.IfExp)
        and isinstance(n.test, ast.Compare)
        and getattr(n.test.left, "id", "") == "artist_id"
        for n in ast.walk(arbre))
    assert conditionnelle, (
        "le comportement a changé : la décision était de DOCUMENTER, pas de restreindre. "
        "Refuser le cas flotte retirerait à l'admin sa seule relance globale — le bouton "
        "« Lancer TOUTES les collectes » a été retiré le 2026-09-08.")


def test_the_one_shot_migration_says_it_already_ran() -> None:
    """Un script à usage unique qui ne le dit pas devient un modèle qu'on recopie."""
    doc = ast.get_docstring(ast.parse(
        (ROOT / "migrations/migrate_saas_artist_id.py").read_text(encoding="utf-8"))) or ""
    assert "USAGE UNIQUE" in doc.upper() and "DÉJÀ JOUÉ" in doc.upper(), (
        "`migrate_saas_artist_id.py` ne déclare pas qu'il a déjà servi. Il interpole "
        "`table`, `name` et `cols` — des paramètres de fonction — dans `ALTER TABLE` et "
        "`UPDATE`, sans allowlist, et `migrations/` n'est parcouru par aucun garde.")
    # ⚠️ IL N'Y A PAS DE SECONDE ASSERTION SUR « ce qu'il faut faire à la place ».
    # Elle existait (`"frozenset" in doc`) et `test_a_guard_reads_structure_not_text` l'a
    # refusée : son cliquet est gelé par fichier et ne monte pas. La forme voisine
    # ci-dessus passe parce qu'elle appelle `.upper()`, ce qui suffirait à faire passer
    # celle-ci — et l'imiter aurait été jouer avec le détecteur plutôt que l'écouter.
    # L'invariant qui compte est asserté : le script DÉCLARE qu'il a servi. Que son
    # avertissement propose aussi une alternative est de la qualité de prose, pas une
    # propriété du dépôt.


def test_the_oauth_token_is_not_printed_unasked() -> None:
    """Le jeton ne s'imprime que derrière un drapeau explicite.

    L'impression est délibérée — le runbook la demande — mais **les deux crons de ce
    dépôt capturent stdout dans un log ET un corps de mail**. Si ce script y est un jour
    enveloppé, le jeton est persisté et posté.
    """
    arbre = ast.parse(
        (ROOT / "airflow/debug_dag/debug_soundcloud_oauth.py").read_text(encoding="utf-8"))
    impressions = [n for n in ast.walk(arbre)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "print"
                   and any(isinstance(a, ast.JoinedStr)
                           and any(isinstance(v, ast.FormattedValue)
                                   and getattr(v.value, "id", "") == "effective_rt"
                                   for v in a.values)
                           for a in n.args)]
    assert impressions, "plus aucune impression du jeton — mettre ce test à jour"
    # chacune doit vivre sous une condition qui interroge argv
    for n in impressions:
        parents = [p for p in ast.walk(arbre) if isinstance(p, ast.If)
                   and any(x is n for x in ast.walk(p))]
        assert any("argv" in ast.unparse(p.test) for p in parents), (
            f"l'impression du refresh_token (l.{n.lineno}) n'est sous aucune condition "
            "lisant `sys.argv`. Elle s'exécuterait dans un cron qui capture stdout.")
