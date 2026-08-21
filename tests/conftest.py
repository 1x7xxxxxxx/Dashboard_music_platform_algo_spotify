"""Fixtures partagées pour tous les tests."""
import io
import sys
import os
import pytest
import pandas as pd

# Rendre src/ importable sans installation du package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers CSV en mémoire (pas de fichiers temporaires nécessaires)
# ---------------------------------------------------------------------------

def make_csv_bytes(content: str, encoding: str = "utf-8") -> bytes:
    return content.encode(encoding)


def make_tmp_csv(tmp_path, filename: str, content: str, encoding: str = "utf-8"):
    """Crée un fichier CSV temporaire et retourne son Path."""
    p = tmp_path / filename
    p.write_bytes(content.encode(encoding))
    return p


@pytest.fixture
def tmp_csv(tmp_path):
    """Factory fixture : make_tmp_csv(filename, content)."""
    def _factory(filename: str, content: str, encoding: str = "utf-8"):
        return make_tmp_csv(tmp_path, filename, content, encoding)
    return _factory


# ---------------------------------------------------------------------------
# The silence that let four waves of tenant-isolation work ship unverified
# ---------------------------------------------------------------------------
#
# ~160 tests carry `pytestmark = requires_live_db()`. Without Postgres on 5433
# they skip, pytest prints "N passed, 163 skipped", and the run reads as green.
#
# Measured 2026-08-22: four waves of credential and tenant-isolation fixes were
# written, guarded and COMMITTED against that green. Starting the database turned
# "1065 passed" into "1217 passed, 1 FAILED" — and the failure was in the Instagram
# uniqueness protection that had just been presented as closed.
#
# The suite is not required to have a database. It IS required to say, loudly, that
# the guards which need one did not run — because "163 skipped" scrolls past and
# "green" does not.

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from tests.db_gate import DB_HOST, DB_PORT, db_ready

    if db_ready():
        return
    skipped = terminalreporter.stats.get("skipped", [])
    gated = sum(1 for r in skipped
                if "needs the live schema" in " ".join(str(x) for x in r.longrepr or ()))
    if not gated:
        return
    tw = terminalreporter
    tw.write_sep("=", "GARDES NON EXÉCUTÉS", red=True, bold=True)
    tw.write_line(
        f"{gated} test(s) exigeant une base ont été SAUTÉS — dont l'isolation "
        f"locataire, l'unicité d'identité et le parcours d'onboarding."
    )
    tw.write_line(
        "Cette exécution ne prouve RIEN sur ces sujets. Pour les lancer :"
    )
    tw.write_line(
        f"    docker start postgres_spotify_airflow   # puis relancer  "
        f"(attendu sur {DB_HOST}:{DB_PORT})"
    )
