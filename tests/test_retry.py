"""Tests unitaires — décorateur `retry`.

Les tests de `src/utils/error_handler.py` ont été retirés avec le module, le
2026-08-24 (R48). Le module n'a jamais eu d'appelant de production ; ce fichier
était son seul importateur, ce qui rendait la couverture flatteuse et interdisait
de le supprimer sans discussion. Deux raisons de le retirer plutôt que de le
câbler, toutes deux mécaniques :

  * ses trois fonctions interpolent l'exception brute (`f"…: {exc}"`,
    `traceback.format_exc()`). L'invariant du dépôt depuis le 2026-08-22 est *ne
    jamais interpoler une exception brute, nulle part* — le câbler aurait rouvert
    la classe sur trois nouveaux sites, et
    `tests/test_an_exception_passed_as_an_argument_is_redacted.py` le signalait ;
  * `safe_call` et `log_errors(reraise=False)` sont un helper béni pour avaler une
    exception et rendre `None` — exactement le motif que la règle transverse #6 et
    la skill `audit-collectors` existent pour interdire. Offrir l'outil est pire
    que les occurrences isolées.

Le fichier garde les tests du décorateur `retry`, qui, lui, a des appelants.
"""
import time
from unittest.mock import MagicMock, patch, call

import psycopg2
import pytest

from src.utils.retry import retry


# =============================================================================
# retry decorator
# =============================================================================

class TestRetryDecorator:

    def test_success_on_first_attempt(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert func() == "ok"
        assert call_count == 1

    def test_retries_on_retriable_exception(self):
        """Doit retenter 3 fois sur OperationalError puis lever."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            raise psycopg2.OperationalError("conn refused")

        with patch("src.utils.retry.time.sleep"):  # évite les vrais délais
            with pytest.raises(psycopg2.OperationalError):
                func()

        assert call_count == 3

    def test_no_retry_on_value_error(self):
        """ValueError ne doit PAS déclencher de retry."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad data")

        with pytest.raises(ValueError):
            func()

        assert call_count == 1  # Pas de retry

    def test_no_retry_on_key_error(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            raise KeyError("missing key")

        with pytest.raises(KeyError):
            func()

        assert call_count == 1

    def test_no_retry_on_type_error(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            func()

        assert call_count == 1

    def test_success_after_n_failures(self):
        """Succès à la 3ème tentative."""
        results = [psycopg2.OperationalError("fail"), psycopg2.OperationalError("fail"), "ok"]
        call_count = 0

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            r = results[call_count]
            call_count += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch("src.utils.retry.time.sleep"):
            result = func()

        assert result == "ok"
        assert call_count == 3

    def test_exponential_backoff_delays(self):
        """Vérifie que les délais exponentiels sont corrects."""
        sleep_calls = []

        @retry(max_attempts=3, backoff="exponential", base_delay=2.0)
        def func():
            raise psycopg2.OperationalError("fail")

        with patch("src.utils.retry.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            with pytest.raises(psycopg2.OperationalError):
                func()

        # Tentative 1 → délai 2^0 * 2.0 = 2.0, Tentative 2 → 2^1 * 2.0 = 4.0
        assert sleep_calls == [2.0, 4.0]

    def test_linear_backoff_delays(self):
        sleep_calls = []

        @retry(max_attempts=3, backoff="linear", base_delay=1.0)
        def func():
            raise psycopg2.OperationalError("fail")

        with patch("src.utils.retry.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            with pytest.raises(psycopg2.OperationalError):
                func()

        assert sleep_calls == [1.0, 2.0]

    def test_unknown_exception_retried(self):
        """Exceptions non classifiées → retry (comportement par défaut sécuritaire)."""
        call_count = 0

        class MyNetworkError(Exception):
            pass

        @retry(max_attempts=3, base_delay=0)
        def func():
            nonlocal call_count
            call_count += 1
            raise MyNetworkError("timeout")

        with patch("src.utils.retry.time.sleep"):
            with pytest.raises(MyNetworkError):
                func()

        assert call_count == 3

    def test_preserves_function_name(self):
        @retry(max_attempts=2)
        def my_special_func():
            return 1

        assert my_special_func.__name__ == "my_special_func"
