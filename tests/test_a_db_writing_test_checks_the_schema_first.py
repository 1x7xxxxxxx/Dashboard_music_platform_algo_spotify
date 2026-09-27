"""R228 — a changed test that writes rows, or a migration, triggers the local↔canonical check.

Two fixtures green locally went red in CI on a NOT NULL only the canonical schema
carried (R219). The check existed (`make schema-check-local`); nothing ran it.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(spec):
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_TRIGGER = importlib.util.spec_from_file_location(
    "changed_tests_write_db", ROOT / "tools/dev/changed_tests_write_db.py")
_DRIFT = importlib.util.spec_from_file_location(
    "schema_drift_check", ROOT / "tools/dev/schema_drift_check.py")


def test_a_write_is_seen_and_a_read_is_not():
    m = _load(_TRIGGER)
    assert m.writes_db('cur.execute("INSERT INTO saas_artists (name) VALUES (%s)")')
    assert m.writes_db("db.upsert_many('x', rows, ['id'])")
    assert not m.writes_db('db.fetch_df("SELECT * FROM saas_artists")')


def test_a_migration_alone_triggers_the_check():
    m = _load(_TRIGGER)
    assert m.needs_schema_check(["migrations/142_apple_daily_from_single_day_exports.sql"])
    assert not m.needs_schema_check(["src/dashboard/app.py"])


def test_a_local_only_table_does_not_gate_but_a_shared_nullability_does():
    c = _load(_DRIFT)
    canon = {"col": {"a.x"}, "key": set(), "uix": set(), "nn": {"a.x"}}
    debris = {"col": {"a.x", "junk.id"}, "key": {"junk:PRIMARY KEY (id)"},
              "uix": {"junk:USING btree (id)"}, "nn": {"a.x"}}
    assert c.find_drift(debris, canon)["found"]
    assert not c.on_shared_tables(c.find_drift(debris, canon))["found"]
    nullable = {"col": {"a.x"}, "key": set(), "uix": set(), "nn": set()}
    assert c.on_shared_tables(c.find_drift(nullable, canon))["found"], \
        "the R219 drift — NOT NULL on a table both carry — must still gate"


def test_test_changed_runs_it():
    recipe = (ROOT / "Makefile").read_text().split("\ntest-changed:", 1)[1].split("\n\n", 1)[0]
    assert "changed_tests_write_db.py" in recipe and "schema-check-shared" in recipe
