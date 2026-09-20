"""Toute vue qu'une migration déclare existe encore dans la base.

Type: Test
Uses: migrations/*.sql, la base joignable
Depends on: —
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-20, et il a attrapé un défaut que j'allais livrer.

`migrations/127_identity_columns_are_text_not_integers.sql` doit convertir
`soundcloud_tracks_daily.track_id`, et PostgreSQL refuse `ALTER COLUMN … TYPE` tant
qu'une vue lit la colonne. Sa première version capturait les vues dépendantes, les
déposait avec `CASCADE`, puis les recréait — mais sa capture ne regardait que les
dépendances **DIRECTES**, alors que `CASCADE` agit **transitivement**.

`v_platform_totals` lit `v_soundcloud_track_latest`. Le `CASCADE` l'emportait, la capture
ne l'avait pas vue, rien ne la recréait. Sur la production, une vue aurait disparu **en
silence** — la migration se serait terminée sans erreur.

⚠️ Ce qui l'a trouvé n'est pas une relecture : c'est la suite, **23 tests rouges** dont
l'invariant de la couche or. Et ce qui a NOMMÉ la cause est le contrôle ci-dessous, écrit
à la main ce jour-là. Il est ici pour que la prochaine fois ce ne soit pas une enquête.

⚠️ Le prédicat porte sur la PROPRIÉTÉ — « cette vue existe-t-elle » — et non sur la forme
« telle migration contient-elle un CASCADE ». Une vue peut disparaître par un `CASCADE`
non recréé, par une migration à moitié appliquée, ou par un `DROP` manuel ; les trois
donnent le même symptôme, et le garde les couvre tous les trois.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = ROOT / "migrations"

#: Les vues créées puis DÉLIBÉRÉMENT retirées par une migration ultérieure. Vide
#: aujourd'hui ; une entrée ici doit nommer la migration qui l'a retirée, sinon elle
#: devient l'échappatoire par laquelle ce garde cesse de garder.
_RETIREES: dict[str, str] = {}


def _vues_declarees() -> set[str]:
    """Les vues qu'une migration crée. Lues dans le SQL, sans exécuter la base."""
    vues: set[str] = set()
    for f in sorted(_MIGRATIONS.glob("*.sql")):
        texte = f.read_text(encoding="utf-8", errors="replace")
        vues |= {m.group(1).lower() for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", texte, re.I)}
    return vues


def _db():
    from src.database.postgres_handler import PostgresHandler
    try:
        return PostgresHandler.from_env_or_config()
    except Exception:                      # noqa: BLE001 — pas de base = pas de mesure
        return None


def test_the_migrations_declare_some_views_at_all() -> None:
    """Anti-vacuité : sans vues déclarées, l'assertion suivante est vraie pour rien."""
    vues = _vues_declarees()
    assert len(vues) >= 15, (
        f"seulement {len(vues)} vue(s) lue(s) dans `migrations/*.sql`. Le motif de "
        "lecture a raté sa cible, et le garde ci-dessous n'affirme plus rien.")


def test_every_view_a_migration_declares_still_exists() -> None:
    """LE GARDE. Une vue déclarée et absente, quelle qu'en soit la cause.

    Le cas qui l'a fait écrire : un `DROP VIEW … CASCADE` dont la capture ne voyait que
    le premier niveau de dépendance. La migration se terminait **sans erreur**, et la
    vue manquait.
    """
    db = _db()
    if db is None:
        pytest.skip("base injoignable — la mesure n'est pas possible")
    try:
        presentes = {r[0].lower() for r in db.fetch_query(
            "SELECT viewname FROM pg_views WHERE schemaname = 'public' "
            "UNION SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'")}
    finally:
        db.close()
    manquantes = sorted(_vues_declarees() - presentes - set(_RETIREES))
    assert not manquantes, (
        f"vue(s) déclarée(s) par une migration et ABSENTE(s) de la base : {manquantes}\n\n"
        "Une migration s'est terminée sans erreur en laissant moins de vues qu'elle n'en "
        "a trouvé. La cause la plus probable est un `DROP VIEW … CASCADE` dont la capture "
        "ne regardait qu'un niveau de dépendance : `CASCADE` agit transitivement, une "
        "capture directe ne le sait pas.\n"
        "Rejouer la migration qui crée cette vue, puis corriger la capture — la "
        "migration 127 porte le CTE récursif qui calcule la fermeture.")


def test_the_exemption_list_names_its_reason() -> None:
    """Une exemption sans motif est le trou par lequel le garde cesse de garder."""
    muettes = [v for v, motif in _RETIREES.items() if not motif.strip()]
    assert not muettes, (
        f"exemption(s) sans motif : {muettes}. Nommer la migration qui a retiré la vue, "
        "ou retirer l'exemption.")
