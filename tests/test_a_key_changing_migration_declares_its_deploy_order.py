"""A migration that changes a KEY opens with the deployment-order banner, or it does not ship.

Type: Sub
Uses: migrations/*.sql
Depends on: nothing — reads SQL files, strips comments, no database

Class `migration-ahead-of-its-code` (P1). On 2026-08-20 migration 065 moved the primary key of
`youtube_channels` and was applied before the code that upserted on the new conflict target:
every tenant's YouTube collection failed. The remedy was a CONVENTION — a key-changing
migration opens with « ORDRE DE DÉPLOIEMENT » and is applied after `make deploy` — and a
convention nothing executes is guarded by memory: the nightly `p1-classes` pass found it
unguarded on 2026-09-25.

Only migrations numbered ABOVE the watermark are held to it. The ones below are already
applied in production, where the deployment-order risk no longer exists; relabelling 24 old
files would prove nothing about the next one.
"""
import re
from pathlib import Path

_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
_WATERMARK = 136          # last migration that existed when the guard was written (2026-09-26)
_BANNER = "ORDRE DE DÉPLOIEMENT"
_KEY_CHANGE = re.compile(
    r"\b(ADD\s+(CONSTRAINT\s+\w+\s+)?(PRIMARY\s+KEY|UNIQUE)"
    r"|DROP\s+CONSTRAINT"
    r"|CREATE\s+UNIQUE\s+INDEX"
    r"|DROP\s+INDEX)\b", re.I)


def _sql_without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def changes_a_key(text: str) -> bool:
    return bool(_KEY_CHANGE.search(_sql_without_comments(text)))


def carries_the_banner(text: str) -> bool:
    return _BANNER in "\n".join(text.splitlines()[:20])


def _number(p: Path) -> int | None:
    m = re.match(r"(\d+)_", p.name)
    return int(m.group(1)) if m else None


def test_every_new_key_changing_migration_carries_the_banner() -> None:
    offenders = [p.name for p in sorted(_MIGRATIONS.glob("*.sql"))
                 if (_number(p) or 0) > _WATERMARK
                 and changes_a_key(p.read_text(encoding="utf-8"))
                 and not carries_the_banner(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        f"{offenders} change a key (PK / UNIQUE / constraint / unique index) without the "
        f"« {_BANNER} » banner in their first 20 lines. Applied before the code, every "
        "ON CONFLICT on the old target fails. Open the file with the banner and apply it "
        "AFTER `make deploy` — model: migrations/065_youtube_surrogate_pk.sql.")


def test_the_reference_migration_still_carries_its_banner() -> None:
    """The model the error message points to must stay a model."""
    text = (_MIGRATIONS / "065_youtube_surrogate_pk.sql").read_text(encoding="utf-8")
    assert changes_a_key(text) and carries_the_banner(text)


def test_the_detector_sees_the_defect_it_is_written_for() -> None:
    """Non-vacuity, both halves: the shape of 065 without its banner is caught; additive
    migrations and a key change named only in a COMMENT are not."""
    bare = "ALTER TABLE youtube_channels DROP CONSTRAINT youtube_channels_pkey;\n" \
           "ALTER TABLE youtube_channels ADD PRIMARY KEY (id);\n"
    assert changes_a_key(bare) and not carries_the_banner(bare)
    assert carries_the_banner(f"-- ⚠️  {_BANNER} — apply after deploy\n" + bare)
    assert changes_a_key("CREATE UNIQUE INDEX ux_a ON t (artist_id, video_id);")
    assert not changes_a_key("ALTER TABLE t ADD COLUMN x INT;\nCREATE INDEX ix ON t (x);")
    assert not changes_a_key("-- we will DROP CONSTRAINT later, not here\nSELECT 1;")
