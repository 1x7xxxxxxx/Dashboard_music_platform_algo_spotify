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
