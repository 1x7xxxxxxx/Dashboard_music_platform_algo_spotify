"""A migration replayed ALONE must never damage a schema a later one repaired.

Measured 2026-08-21, while introducing the schema_migrations ledger.

Until then the strategy was "reapply all 70 files every time", and 024 failing was
survivable only because 044 ran afterwards and put the right primary key back. The
ledger changed that: a file that never succeeds is never recorded, so it is retried
ALONE on every run — and 024's first statement was an unguarded
`DROP CONSTRAINT s4a_song_playlist_adds_pkey`.

Each retry therefore DESTROYED 044's key and failed to create its own, leaving
`s4a_song_playlist_adds` with no primary key at all. Observed live: the table was
found keyless, and it was the ledger's own introduction that did it.

Error class: unguarded-drop-replayed-alone (.claude/dev-docs/error-classes.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = sorted((ROOT / "migrations").glob("*.sql"))

# A DROP is safe when it says IF EXISTS, or when it sits inside a DO block that
# tested for the object first (the 061 shape).
_DROP = re.compile(r"\bDROP\s+(CONSTRAINT|COLUMN|INDEX|TABLE|VIEW)\b", re.I)
_GUARDED = re.compile(r"\bDROP\s+(CONSTRAINT|COLUMN|INDEX|TABLE|VIEW)\s+IF\s+EXISTS\b", re.I)


def _strip_sql_comments(text: str) -> str:
    """A file that DOCUMENTS the defect in a comment must not trip its own guard."""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def test_there_are_migrations_to_check() -> None:
    """Without this, an empty glob would make the sweep below pass on nothing."""
    assert len(MIGRATIONS) > 50, f"only {len(MIGRATIONS)} migrations found — bad path?"


def unguarded_drops(sql: str) -> list[tuple[int, str]]:
    """(ligne, instruction) de chaque DROP nu hors d'un bloc DO gardé.

    Extraite pour être APPELABLE sur du SQL fabriqué. Tant qu'elle vivait dans le
    corps du test paramétré, la seule façon de savoir si elle mordait encore était
    d'abîmer une vraie migration — donc personne ne le faisait, et le paramétré
    serait resté vert sur 127 fichiers avec un prédicat aveugle (mesuré).
    """
    code = _strip_sql_comments(sql)
    out: list[tuple[int, str]] = []
    inside_do = False
    for lineno, line in enumerate(code.splitlines(), 1):
        stripped = line.strip()
        if re.search(r"\bDO\s*\$\$", stripped, re.I):
            inside_do = True
        elif stripped.startswith("END $$") or stripped.startswith("END$$"):
            inside_do = False
        if not _DROP.search(line) or _GUARDED.search(line):
            continue
        if not inside_do:
            out.append((lineno, stripped))
    return out


def test_the_drop_detector_sees_the_shape_it_is_written_for() -> None:
    """Non-vacuité : le DROP nu est FABRIQUÉ ici, et les trois formes sûres aussi.

    Mesuré le 2026-09-18 : en neutralisant le prédicat (`… or True`), les **127 cas
    paramétrés restent verts**. Un cliquet qui ne voit rien certifie alors une
    propriété qu'il ne vérifie plus, et c'est un P1 — un DROP rejoué seul détruit
    ce qui porte le nom aujourd'hui.
    """
    nu = "ALTER TABLE t DROP CONSTRAINT t_pkey;\n"
    assert unguarded_drops(nu) == [(1, "ALTER TABLE t DROP CONSTRAINT t_pkey;")], (
        f"le détecteur rend {unguarded_drops(nu)} sur un DROP nu écrit noir sur "
        "blanc : le cliquet ne garde plus rien.")

    # Les trois formes SÛRES doivent rester muettes, sans quoi corriger un défaut
    # rendrait la CI rouge et la seule issue serait de désarmer le garde.
    assert unguarded_drops("ALTER TABLE t DROP CONSTRAINT IF EXISTS t_pkey;\n") == [], (
        "`IF EXISTS` fait rougir le détecteur — la première des deux portes.")
    garde = ("DO $$ BEGIN\n"
             "  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 't_pkey') THEN\n"
             "    ALTER TABLE t DROP CONSTRAINT t_pkey;\n"
             "  END IF;\n"
             "END $$;\n")
    assert unguarded_drops(garde) == [], (
        "un DROP dans un bloc DO qui teste d'abord l'objet fait rougir le détecteur "
        "— c'est la forme 061, la seconde porte.")
    assert unguarded_drops("-- ALTER TABLE t DROP CONSTRAINT t_pkey;\n") == [], (
        "le détecteur mord sur un COMMENTAIRE : documenter le défaut ferait rougir "
        "la CI, et la seule issue serait de cesser de le documenter.")


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_no_unguarded_drop(path: Path) -> None:
    for lineno, stripped in unguarded_drops(path.read_text(encoding="utf-8")):
        assert False, (
            f"{path.name}:{lineno} drops an object with no IF EXISTS and outside a "
            f"guarded DO block:\n    {stripped}\n"
            "Replayed on its own — which the ledger now does for any file that never "
            "succeeds — this destroys whatever currently holds that name."
        )


def test_024_is_neutralised_once_044_has_run() -> None:
    """The specific pair. 024's key became impossible the day 044 made it windowed."""
    text = (ROOT / "migrations/024_s4a_song_playlist_adds_redesign.sql").read_text(
        encoding="utf-8")
    assert "time_window" in text and "RETURN;" in text, (
        "024 no longer checks for 044's marker column before touching the primary "
        "key. Replaying it alone drops the live key and cannot recreate its own."
    )
    code = _strip_sql_comments(text)
    assert "DROP CONSTRAINT s4a_song_playlist_adds_pkey;" not in code, (
        "024 drops the primary key unguarded again — the exact statement that left "
        "the table keyless on 2026-08-21."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Le fichier qui n'entre JAMAIS au registre — 2026-09-16
# ─────────────────────────────────────────────────────────────────────────────
#
# Les gardes ci-dessus lisent le TEXTE des migrations. Ils ne peuvent pas voir la
# forme suivante, qui est la même famille vue de l'autre bout : une migration qui
# échoue à chaque rejeu, n'est donc jamais enregistrée, et se re-tente seule pour
# toujours.
#
# `106_gold_remaining_grains.sql` était dans cet état depuis le jour où 108 a élargi
# `v_meta_creative_daily` : `CREATE OR REPLACE VIEW` ne sait pas retirer une colonne,
# donc le rejeu rendait `cannot drop columns from view`, à chaque exécution de
# `tools/migrate.sh`, sans que rien ne s'arrête — le script continue après erreur À
# DESSEIN (le jeu n'est idempotent qu'en run complet).
#
# Ce qui l'a rendu invisible n'est pas l'erreur, c'est la porte de déploiement : elle
# comparait 119 fichiers à 119 lignes de registre et concluait que tout était appliqué.
# Le 119ᵉ enregistrement était `create_missing_tables.sql`, pas 106. Deux erreurs qui
# s'annulent donnent un total juste et un verdict faux.
#
# Ce test compare des ENSEMBLES, contre la base vivante. Il est le seul contrôle qui
# puisse voir un fichier absent du registre.

def test_every_migration_on_disk_is_recorded_in_the_ledger() -> None:
    """Chaque `migrations/*.sql` a une ligne dans `schema_migrations`.

    Sauté sans base : c'est un contrôle d'ÉTAT, il n'a pas d'équivalent statique.

    Sauté AUSSI quand le registre est vide, et il faut dire pourquoi. Toutes les bases
    de ce projet ne sont pas tenues par `tools/migrate.sh` : celle de la CI est
    provisionnée par `.github/actions/provision-postgres`, qui applique chaque fichier
    avec `psql` et ne touche jamais `schema_migrations` — délibérément, le runner n'a
    pas de conteneur Postgres à `docker exec`. Contre une telle base, « tous les
    fichiers manquent au registre » est l'état NORMAL, pas un défaut. Mesuré le
    2026-09-16 : la première version de ce test était verte en local et rouge sur le
    shard 2/4, en listant les 120 migrations.

    Le registre VIDE est donc le signal « cette base n'est pas de ce type ». Un registre
    peuplé mais incomplet reste un défaut, et c'est le cas qui compte.
    """
    from tests.db_gate import db_ready

    if not db_ready():
        pytest.skip("pas de Postgres joignable — ce contrôle lit l'état réel")

    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        rows = db.fetch_query("SELECT filename FROM schema_migrations")
    finally:
        db.close()

    ledger = {r[0] for r in rows}
    if not ledger:
        pytest.skip(
            "`schema_migrations` est VIDE : cette base n'est pas tenue par "
            "`tools/migrate.sh` (c'est le cas de la base jetable de la CI). Le "
            "contrôle de parité n'a de sens que contre une base à registre."
        )
    on_disk = {p.name for p in MIGRATIONS}
    missing = sorted(on_disk - ledger)

    assert not missing, (
        "migration(s) présente(s) sur le disque et absente(s) du registre :\n  "
        + "\n  ".join(missing)
        + "\n\nUne migration absente du registre est re-tentée SEULE à chaque run de "
        "`tools/migrate.sh`, et elle n'y entre que le jour où elle réussit. Si elle "
        "échoue toujours, la base ne porte pas ce que le fichier décrit — et rien ne "
        "le dit, parce que le script continue après erreur à dessein.\n"
        "Diagnostic : `bash tools/migrate.sh` et lire l'erreur nommée pour ce fichier."
    )


def test_the_comment_stripper_sees_the_forms_it_is_written_for() -> None:
    """Non-vacuité : c'est ce dépouillement qui permet de DOCUMENTER le défaut.

    Ajouté le 2026-09-18. Sans lui, une migration qui explique en commentaire
    pourquoi un `DROP` non gardé est dangereux ferait rougir son propre garde — la
    classe `a-noisy-signature-teaches-that-red-is-noise`, payée le 2026-08-03. Les
    deux moitiés sont fabriquées : le commentaire est retiré, le SQL est gardé.
    """
    texte = ("DROP VIEW v_x;              -- ce DROP-ci est réel\n"
             "-- DROP VIEW v_y; celui-ci n'est qu'une explication\n")
    net = _strip_sql_comments(texte)
    assert "DROP VIEW v_x" in net, (
        "le SQL réel a été emporté avec le commentaire : le garde ne verrait plus "
        "les `DROP` qu'il existe pour attraper.")
    assert "v_y" not in net, (
        "un `DROP` cité en COMMENTAIRE survit au dépouillement : écrire SUR le défaut "
        "ferait rougir la CI, et la seule façon de la garder verte serait d'arrêter "
        "de documenter les migrations.")
