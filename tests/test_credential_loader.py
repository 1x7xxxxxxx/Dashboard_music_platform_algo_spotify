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

    def test_db_error_raises_instead_of_looking_unconnected(self):
        """Une erreur DB LÈVE — elle ne se déguise pas en « pas connecté ».

        Contrat inversé le 2026-08-20. L'ancien test affirmait `result == {}`, et
        c'est exactement ce qui rendait la panne dangereuse : les appelants
        écrivaient `creds.get('user_id') or os.getenv('SOUNDCLOUD_USER_ID')`, donc
        une coupure DB faisait collecter l'identité de l'ADMIN pour tous les
        locataires. Une absence de ligne reste `{}` (test suivant) ; une panne non.
        """
        import psycopg2
        from src.utils.credential_loader import CredentialLoadError
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("conn refused")):
            with pytest.raises(CredentialLoadError):
                load_platform_credentials(1, "youtube")

    def test_missing_row_still_returns_empty(self):
        """Pas de ligne = pas connecté : ça, ça reste un dict vide."""
        mock_conn = self._mock_conn(None)
        with patch("psycopg2.connect", return_value=mock_conn):
            assert load_platform_credentials(1, "youtube") == {}

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

    def test_db_error_raises(self):
        """Même inversion : les DAGs traduisaient `[]` par « prends l'artiste 1 »."""
        import psycopg2
        from src.utils.credential_loader import CredentialLoadError
        with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("down")):
            with pytest.raises(CredentialLoadError):
                get_active_artists()

    def test_unknown_or_inactive_artist_raises(self):
        """`conf={'artist_id': 12}` sur un artiste inactif ne doit pas devenir
        « collecte la chaîne de l'admin sous artist_id=1 »."""
        from src.utils.credential_loader import UnknownArtistError
        mock_conn = self._mock_conn([])
        with patch("psycopg2.connect", return_value=mock_conn):
            with pytest.raises(UnknownArtistError):
                get_active_artists(include_artist_id=12)

    def test_no_active_artist_is_still_an_empty_list(self):
        """Zéro artiste actif reste `[]` — c'est un déploiement vide, pas une panne."""
        mock_conn = self._mock_conn([])
        with patch("psycopg2.connect", return_value=mock_conn):
            assert get_active_artists() == []


# ---------------------------------------------------------------------------
# R33 — one connection factory, not four copies
# ---------------------------------------------------------------------------

class TestSingleConnectionFactory:
    """Four functions each built their own DSN from the same five variables.

    Nothing was broken by it — this is duplication, not a defect. But four copies
    of a DSN is four places to forget a parameter, and the one most easily
    forgotten here is the port: a container reaches Postgres on 5432 internally
    while this repo publishes 5433 on the host. Extracted 2026-08-21 into
    `_connect()`; this pins it so the copies cannot grow back.
    """

    @staticmethod
    def _source() -> str:
        from pathlib import Path

        import src.utils.credential_loader as mod
        return Path(mod.__file__).read_text(encoding="utf-8")

    @staticmethod
    def _code_lines(src: str) -> str:
        """Source with docstrings and comments stripped — prose is not a call."""
        import ast
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and node.body and isinstance(node.body[0], ast.Expr):
                    node.body.pop(0)
                    if not node.body:
                        node.body.append(ast.Pass())
        return ast.unparse(ast.fix_missing_locations(tree))

    def test_exactly_one_place_opens_a_connection(self):
        code = self._code_lines(self._source())
        n = code.count("psycopg2.connect(")
        assert n == 1, (
            f"{n} call(s) to psycopg2.connect in credential_loader — route them "
            "through `_connect()` instead of rebuilding the DSN."
        )

    def test_exactly_one_place_reads_the_connection_variables(self):
        code = self._code_lines(self._source())
        for var in ("DATABASE_HOST", "DATABASE_PORT", "DATABASE_NAME",
                    "DATABASE_USER", "DATABASE_PASSWORD"):
            n = code.count(var)
            assert n == 1, (
                f"{var} is read {n} times — it belongs in `_connect()` only."
            )

    def test_the_factory_still_honours_autocommit(self):
        """Two of the four call sites write; they must not silently lose it."""
        from unittest.mock import MagicMock, patch

        from src.utils.credential_loader import _connect
        fake = MagicMock()
        with patch("psycopg2.connect", return_value=fake):
            _connect()
            assert fake.autocommit is False
            _connect(autocommit=True)
            assert fake.autocommit is True
