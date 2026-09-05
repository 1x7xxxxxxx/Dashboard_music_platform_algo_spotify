"""La suite n'a pas le droit de laisser de fausses données dans la base.

Type: Test
Uses: live Postgres (spotify_etl)
Depends on: tests/conftest.py (_no_synthetic_rows_left_behind)
Persists in: —

R61. Le 2026-09-05, un artiste signale « l'item Données est en vert mais on n'a pas les
data ». Mesuré : `soundcloud_tracks_daily` portait pour le locataire 1 **349 vraies
lignes datées du 12 juin — 85 jours** — et **9 lignes fabriquées** par la suite
(`track_id = 'track-of-<user_id>'`), datées du jour. `artist_readiness` lisant
`MAX(collected_at)`, neuf lignes de test suffisaient à faire passer au vert une
plateforme périmée depuis trois mois.

Troisième frontière du même genre après SMTP et HTTP, et trouvée de la même façon :
par quelqu'un qui regardait l'écran. Les gardes du dépôt demandent tous « le code
est-il juste ? » ; aucun ne demandait « que la suite laisse-t-elle derrière elle ? ».
"""
import os
import socket

import pytest

_DB_HOST, _DB_PORT = "127.0.0.1", 5433
_PREFIX = "track-of-"


def _db():
    if not os.environ.get("DATABASE_URL"):
        try:
            with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
                pass
        except OSError:
            return None
    try:
        from src.dashboard.utils import get_db_connection
        db = get_db_connection()
        db.fetch_query("SELECT 1 FROM saas_artists LIMIT 1")
        return db
    except Exception:  # noqa: BLE001
        return None


pytestmark = pytest.mark.skipif(_db() is None, reason="needs the provisioned DB")


def test_no_synthetic_track_survives_into_the_freshness_computation():
    """Le nettoyage de `conftest` tourne en fin de SESSION.

    Ce test ne peut donc pas constater zéro pendant la session en cours : il constate
    que les lignes fabriquées n'ont pas d'AVANCE sur les vraies. C'est la propriété
    qui compte — une ligne de test plus récente que la dernière collecte réelle
    déplace `MAX(collected_at)` et ment aux pastilles.
    """
    db = _db()
    try:
        rows = db.fetch_query(f"""
            SELECT artist_id,
                   MAX(collected_at) FILTER (WHERE track_id LIKE '{_PREFIX}%%'),
                   MAX(collected_at) FILTER (WHERE track_id NOT LIKE '{_PREFIX}%%')
              FROM soundcloud_tracks_daily GROUP BY artist_id
        """)  # noqa: S608 — préfixe littéral, aucune donnée utilisateur
        offenders = [
            f"locataire {aid} : ligne de test du {fake:%Y-%m-%d}, "
            f"dernière collecte réelle {real:%Y-%m-%d}"
            for aid, fake, real in rows if fake and real and fake > real
        ]
        assert not offenders, (
            "des lignes fabriquées par la suite sont PLUS RÉCENTES que la dernière "
            "collecte réelle : elles déplacent `MAX(collected_at)`, donc la pastille "
            "« Données » passe au vert sur une plateforme muette :\n  "
            + "\n  ".join(offenders))
    finally:
        db.close()


def test_the_cleanup_boundary_is_declared_and_runs_at_session_end():
    """Structurel : le nettoyage doit exister ET être `autouse`, sinon il ne tourne pas.

    Lecture par AST — le commentaire qui documente la frontière cite lui-même le
    préfixe, donc une recherche de chaîne resterait verte après sa suppression.
    """
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).parent / "conftest.py").read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)
               and n.name == "_no_synthetic_rows_left_behind"), None)
    assert fn is not None, "la frontière de données a disparu de conftest.py"

    deco = next((d for d in fn.decorator_list if isinstance(d, ast.Call)), None)
    assert deco is not None, "la frontière n'est plus une fixture"
    kwargs = {k.arg: getattr(k.value, "value", None) for k in deco.keywords}
    assert kwargs.get("autouse") is True, (
        "la frontière n'est plus `autouse` : elle ne tournera que si un test la "
        "demande, c'est-à-dire jamais")
    assert kwargs.get("scope") == "session", (
        "la frontière n'est plus de portée session : nettoyée par test, elle "
        "casserait les tests qui s'appuient sur leurs propres lignes")
    # Et elle doit vraiment supprimer.
    deletes = [n for n in ast.walk(fn)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and "DELETE FROM" in n.value]
    assert deletes, "la frontière ne supprime plus rien"
