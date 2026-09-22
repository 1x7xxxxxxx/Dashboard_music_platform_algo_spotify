"""Every `ON CONFLICT` target names a unique index the database actually has.

Type: Test
Uses: ast, psycopg2, a live Postgres
Depends on: src/**/*.py, airflow/dags/*.py, the deployed schema
Persists in: nothing

Why this exists
---------------
PostgreSQL requires `ON CONFLICT (cols)` to match a unique index on *exactly*
those columns. Name a set that has no index and the statement does not degrade
— it raises:

    ERROR: there is no unique or exclusion constraint matching the
           ON CONFLICT specification

That is not hypothetical here. Measured against production on 2026-09-11 with a
real INSERT inside a rolled-back transaction, `_upload_apple` in
`src/dashboard/views/admin.py` raised exactly that. Its target was
`(artist_id, song_name)`; migration 093 had moved the key to include
`snapshot_date`, and 094-095 added the period and made it matchable with
`NULLS NOT DISTINCT`. `upload_csv.py:53` followed the migrations. This second
copy of the same gesture did not — one act declared in two places, one of them
corrected.

The class already has a written history: migration 095 exists because Apple's
uniqueness lived on EXPRESSIONS and was therefore unmatchable by any
`ON CONFLICT (col, …)` — five imports failed. This guard is what would have
caught both without anyone running the import.

Why it reads the database and not the migrations
------------------------------------------------
The question is "does this index exist where the code will run", and only the
catalogue answers it. A migration file says what someone intended to apply.

Expression columns, and why the first version of this check lied
----------------------------------------------------------------
`pg_index.indkey` stores 0 for an expression column, so reconstructing the
column list from `pg_attribute` silently DROPS `(collected_at::date)` — and the
first version of this sweep reported `youtube_video_stats` as broken when it is
correct. `pg_get_indexdef` renders the expression, so the definition text is
parsed instead, and both sides are normalised (case, spaces, parentheses) —
Postgres writes `((collected_at)::date)` where the code writes
`(collected_at::date)`.

What it does NOT cover
----------------------
Four call sites build their target at runtime (`src/collectors/_meta_upsert.py`,
`src/dashboard/views/imusician.py`, `src/dashboard/views/upload_csv.py`,
`airflow/dags/ml_scoring_daily.py`). A static reader cannot resolve those, and
this test says so rather than appearing to cover them.

Mutation record — 2026-09-11: with `admin.py` restored to
`['artist_id', 'song_name']`, this guard names that site and fails; with the
corrected five-column target, it passes.
"""
from __future__ import annotations

import ast
import os
import re
import pathlib
import socket

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCANNED = ("src", "airflow", "tools")
_DB_HOST, _DB_PORT = "127.0.0.1", 5433


def _dsn() -> dict | None:
    """Les mots-clés de connexion — par la porte canonique, jamais recopiée.

    ⚠️ 2026-09-22 : ce bloc construisait son DSN à la main et ne lisait que
    l'environnement. Sur un poste dont le mot de passe vit dans
    `config/config.yaml`, la socket s'ouvre et l'authentification échoue — le
    module ne skippe pas, il ERREUR. Dix modules de test portaient exactement
    cette forme, trouvés par balayage après que trois d'entre eux ont rougi.
    `tests/db_gate.dsn()` passe par `src.utils.pg_connect.resolve_kwargs`, qui
    connaît les trois sources (`DATABASE_URL`, les `DATABASE_*`, `config.yaml`).

    Classe : `a-second-door-that-knows-fewer-sources-than-the-first`.
    """
    from tests.db_gate import dsn

    return dsn()


_CONN = _dsn()


def _normalise(columns) -> tuple[str, ...]:
    """A column set comparable whether Postgres or Python spelled it."""
    text = ",".join(columns) if isinstance(columns, (list, tuple)) else columns
    text = text.lower().replace(" ", "").replace("(", "").replace(")", "")
    return tuple(sorted(part for part in text.split(",") if part))


def _upsert_targets() -> tuple[list[tuple[str, str, list[str]]], list[str]]:
    """(site, table, conflict_columns) for literal calls; sites we cannot resolve."""
    literal: list[tuple[str, str, list[str]]] = []
    dynamic: list[str] = []
    for root in _SCANNED:
        for path in sorted((_ROOT / root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and getattr(node.func, "attr", "") == "upsert_many"):
                    continue
                kwargs = {k.arg: k.value for k in node.keywords}
                table = kwargs.get("table") or (node.args[0] if node.args else None)
                cols = kwargs.get("conflict_columns") or (
                    node.args[2] if len(node.args) >= 3 else None)
                site = f"{path.relative_to(_ROOT)}:{node.lineno}"

                literal_table = isinstance(table, ast.Constant)
                literal_cols = (
                    isinstance(cols, (ast.List, ast.Tuple))
                    and all(isinstance(e, ast.Constant) for e in cols.elts)
                )
                if literal_table and literal_cols:
                    literal.append((site, table.value, [e.value for e in cols.elts]))
                else:
                    dynamic.append(site)
    return literal, dynamic


@pytest.fixture(scope="module")
def unique_indexes() -> dict[str, set[tuple[str, ...]]]:
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname, pg_get_indexdef(x.indexrelid)
                FROM pg_index x
                JOIN pg_class c ON c.oid = x.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND x.indisunique
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    out: dict[str, set[tuple[str, ...]]] = {}
    for table, ddl in rows:
        inner = ddl[ddl.index("(") + 1: ddl.rindex(")")]
        out.setdefault(table, set()).add(_normalise(inner))
    return out


pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — only the catalogue can answer this",
)


def test_every_literal_upsert_target_has_a_matching_unique_index(unique_indexes) -> None:
    literal, _ = _upsert_targets()
    assert literal, "no literal upsert_many call found — the AST reader is broken"

    offenders = []
    for site, table, cols in literal:
        if table not in unique_indexes:
            offenders.append(f"{site}: table {table!r} has no unique index at all")
            continue
        if _normalise(cols) not in unique_indexes[table]:
            have = " | ".join(", ".join(u) for u in sorted(unique_indexes[table]))
            offenders.append(
                f"{site}: ON CONFLICT ({', '.join(cols)}) on {table} matches no unique "
                f"index. The table has: {have}"
            )

    assert not offenders, (
        "An ON CONFLICT target with no matching unique index does not degrade — it\n"
        "raises, and the import fails. Measured in production on 2026-09-11 for\n"
        "admin.py's Apple import. Either fix the target, or ship the migration that\n"
        "creates the index — and ship the migration FIRST.\n\n" + "\n".join(offenders)
    )


def test_the_unresolvable_call_sites_are_named_not_hidden() -> None:
    """A static reader cannot follow a runtime-built target; say which, don't imply cover.

    If this list grows, the guard's coverage shrank without anyone noticing —
    which is how a check quietly stops checking.
    """
    _, dynamic = _upsert_targets()
    known = {
        "src/collectors/_meta_upsert.py:329",
        "src/dashboard/views/imusician.py:122",
        "src/dashboard/views/upload_csv.py:1090",
        "airflow/dags/ml_scoring_daily.py:86",
    }
    new = {site.split(":")[0] for site in dynamic} - {site.split(":")[0] for site in known}
    assert not new, (
        "New upsert_many call site(s) build their ON CONFLICT target at runtime, so "
        f"this guard cannot check them: {sorted(new)}. Prefer a literal target, or "
        "add the file here deliberately."
    )


# ── Ce que les ÉCRANS de mise au point ANNONCENT — 2026-09-18 ────────────────
#
# Les tests ci-dessus demandent « cette requête EXÉCUTÉE vise-t-elle un index qui
# existe ? ». Ils écartent — à raison — tout `ON CONFLICT` qui n'atteint aucun curseur,
# et les scripts de `airflow/debug_dag/` n'en atteignent aucun : ils IMPRIMENT.
#
# C'est précisément ce qui les a laissés mentir. Mesuré le 2026-09-18 contre le
# catalogue vivant : **cinq clés annoncées sur sept étaient fausses**, toutes de la même
# façon — la forme PRÉ-MULTILOCATAIRE, sans `artist_id`.
#
#     debug_s4a.py         ['song','date']  →  (artist_id, song, date)
#     debug_s4a.py         ['date']         →  (artist_id, date)
#     debug_s4a.py         ['song']         →  (artist_id, song, time_window)
#     debug_spotify_api.py (track_id,date)  →  (artist_id, track_id, date)
#     debug_youtube.py     (video_id)       →  (artist_id, video_id)
#
# Rien ne s'exécute, donc aucune requête ne casse. Ce qui casse est le LECTEUR :
# `CLAUDE.md` désigne `python airflow/debug_dag/debug_<name>.py` comme le chemin pour
# éprouver un DAG sans Airflow, et ces écrans dictent la clé à un opérateur qui les
# croit. Classe `un-document-qui-affirme-un-état-périmé`.
#
# ⚠️ Une forme reste NON couverte, et le dire est le point : `debug_spotify_api.py:201`
# annonce la clé EN PROSE — « Clé Unique : Artist ID + Track ID + Date du jour ». Elle a
# été corrigée à la main le même jour, et aucun prédicat raisonnable ne la lit. Écrire
# que ce garde « couvre les écrans de mise au point » serait faux : il couvre les clés
# écrites en SQL ou en liste Python, pas celles écrites en français.

_DEBUG_DIR = _ROOT / "airflow" / "debug_dag"

# `ON CONFLICT (…)` dans une chaîne imprimée, et `Clé d'unicité (Conflict) : [...]`.
_ANNONCE_SQL = re.compile(r"ON\s+CONFLICT\s*\(([^)]+)\)", re.I)
_ANNONCE_LISTE = re.compile(r"Cl[ée]\s+d'unicit[ée][^:]*:\s*\[([^\]]+)\]")
# La table est annoncée juste au-dessus, dans l'une des deux formes de ces scripts.
_TABLE = re.compile(r"Table\s+Cible\s*:\s*([a-z_0-9]+)|\[Table:\s*([a-z_0-9]+)\]|"
                    r"INSERT\s+INTO\s+([a-z_0-9]+)", re.I)


def _cles_annoncees() -> list[tuple[str, int, str, tuple[str, ...]]]:
    """`(fichier, ligne, table, colonnes)` pour chaque clé ANNONCÉE à l'écran."""
    trouve = []
    for path in sorted(_DEBUG_DIR.glob("debug_*.py")):
        lignes = path.read_text(encoding="utf-8").splitlines()
        table = ""
        for i, ligne in enumerate(lignes, 1):
            mt = _TABLE.search(ligne)
            if mt:
                table = next(g for g in mt.groups() if g)
            for rx in (_ANNONCE_SQL, _ANNONCE_LISTE):
                m = rx.search(ligne)
                if not m or not table:
                    continue
                cols = tuple(sorted(c.strip().strip("'\"") for c in m.group(1).split(",")))
                trouve.append((path.name, i, table, cols))
    return trouve


def test_the_announced_keys_were_really_found() -> None:
    """Non-vacuité : sans extraction, tout le reste est vert pour rien."""
    trouve = _cles_annoncees()
    assert len(trouve) >= 5, (
        f"seulement {len(trouve)} clé(s) annoncée(s) extraite(s) de "
        f"{_DEBUG_DIR.name}/ — l'extraction a raté sa cible, et le test ci-dessous "
        "n'affirme rien. Les écrans ont pu changer de forme.")


@pytest.mark.parametrize("fichier,ligne,table,cols", _cles_annoncees(),
                         ids=lambda v: str(v) if not isinstance(v, tuple) else "-".join(v))
def test_a_debug_screen_announces_a_key_that_exists(unique_indexes, fichier, ligne,
                                                    table, cols) -> None:
    reels = unique_indexes.get(table)
    if reels is None:
        pytest.skip(f"{table} absente du catalogue de cette base")
    assert cols in {tuple(sorted(r)) for r in reels}, (
        f"{fichier}:{ligne} annonce `ON CONFLICT {cols}` sur `{table}`, que le "
        f"catalogue ne porte pas. Clés réelles : "
        f"{sorted(tuple(sorted(r)) for r in reels)}.\n"
        "Rien ne s'exécute ici — c'est le LECTEUR qui casse. `CLAUDE.md` désigne ces "
        "scripts comme le chemin de test local d'un DAG : un opérateur lit cette clé "
        "et la croit. Cinq des sept étaient fausses le 2026-09-18, toutes sans "
        "`artist_id`.")
