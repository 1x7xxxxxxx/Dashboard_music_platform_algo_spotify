"""Tests unitaires — credential_loader (mock DB + Fernet)."""
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from src.utils.credential_loader import load_platform_credentials, get_active_artists


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fernet_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_payload(payload: dict, key: str) -> str:
    f = Fernet(key.encode())
    return f.encrypt(json.dumps(payload).encode()).decode()


# ---------------------------------------------------------------------------
# load_platform_credentials
# ---------------------------------------------------------------------------

class TestLoadPlatformCredentials:

    def _mock_conn(self, row):
        """Retourne un mock psycopg2.connect qui renvoie `row` au fetchone."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn

    def test_returns_empty_when_no_row(self):
        mock_conn = self._mock_conn(None)
        with patch("psycopg2.connect", return_value=mock_conn):
            result = load_platform_credentials(1, "spotify")
        assert result == {}

    def test_decrypts_secrets_correctly(self):
        key = make_fernet_key()
        secrets = {"client_id": "abc", "client_secret": "xyz"}
        token_enc = encrypt_payload(secrets, key)
        extra_config = {"region": "fr"}
        mock_conn = self._mock_conn((token_enc, extra_config))

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch.dict(os.environ, {"FERNET_KEY": key}):
                result = load_platform_credentials(1, "spotify")

        assert result["client_id"] == "abc"
        assert result["client_secret"] == "xyz"
        assert result["region"] == "fr"

    def test_secrets_override_extra_config(self):
        """Les secrets (token_encrypted) ont priorité sur extra_config."""
        key = make_fernet_key()
        secrets = {"client_id": "from_secret"}
        token_enc = encrypt_payload(secrets, key)
        extra_config = {"client_id": "from_extra"}
        mock_conn = self._mock_conn((token_enc, extra_config))

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch.dict(os.environ, {"FERNET_KEY": key}):
                result = load_platform_credentials(1, "spotify")

        assert result["client_id"] == "from_secret"

    def test_no_fernet_key_skips_decryption(self):
        """Sans FERNET_KEY, les secrets chiffrés sont ignorés mais extra_config est retourné."""
        key = make_fernet_key()
        secrets = {"client_id": "abc"}
        token_enc = encrypt_payload(secrets, key)
        extra_config = {"region": "fr"}
        mock_conn = self._mock_conn((token_enc, extra_config))

        env_without_fernet = {k: v for k, v in os.environ.items() if k != "FERNET_KEY"}
        with patch("psycopg2.connect", return_value=mock_conn):
            with patch.dict(os.environ, env_without_fernet, clear=True):
                result = load_platform_credentials(1, "spotify")

        assert result.get("region") == "fr"
        assert "client_id" not in result

    def test_db_error_returns_empty(self):
        """Une erreur de connexion DB retourne {} sans lever d'exception."""
        import psycopg2
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("conn refused")):
            result = load_platform_credentials(1, "youtube")
        assert result == {}

    def test_extra_config_as_json_string(self):
        """extra_config peut être une chaîne JSON — doit être parsée."""
        key = make_fernet_key()
        extra_config_str = json.dumps({"api_version": "v21"})
        mock_conn = self._mock_conn((None, extra_config_str))

        with patch("psycopg2.connect", return_value=mock_conn):
            with patch.dict(os.environ, {"FERNET_KEY": key}):
                result = load_platform_credentials(1, "meta")

        assert result.get("api_version") == "v21"


# ---------------------------------------------------------------------------
# get_active_artists
# ---------------------------------------------------------------------------

class TestGetActiveArtists:

    def _mock_conn(self, rows):
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn

    def test_returns_all_active(self):
        mock_conn = self._mock_conn([(1, "Artist A"), (2, "Artist B")])
        with patch("psycopg2.connect", return_value=mock_conn):
            result = get_active_artists()
        assert result == [(1, "Artist A"), (2, "Artist B")]

    def test_filter_by_artist_id(self):
        mock_conn = self._mock_conn([(1, "Artist A")])
        with patch("psycopg2.connect", return_value=mock_conn):
            result = get_active_artists(include_artist_id=1)
        assert result == [(1, "Artist A")]

    def test_db_error_returns_empty_list(self):
        import psycopg2
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("down")):
            result = get_active_artists()
        assert result == []
