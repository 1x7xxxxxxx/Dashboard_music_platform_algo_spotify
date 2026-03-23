"""Tests unitaires — retry decorator + error_handler utilities."""
import time
from unittest.mock import MagicMock, patch, call

import psycopg2
import pytest

from src.utils.retry import retry
from src.utils.error_handler import log_errors, log_and_raise, safe_call


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


# =============================================================================
# log_errors decorator
# =============================================================================

class TestLogErrors:

    def test_returns_value_on_success(self):
        @log_errors()
        def func():
            return 42

        assert func() == 42

    def test_reraises_by_default(self):
        @log_errors()
        def func():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            func()

    def test_swallows_error_when_reraise_false(self):
        @log_errors(reraise=False)
        def func():
            raise RuntimeError("boom")

        result = func()
        assert result is None


# =============================================================================
# log_and_raise
# =============================================================================

class TestLogAndRaise:

    def test_raises_original_exception(self):
        exc = ValueError("original error")
        with pytest.raises(ValueError, match="original error"):
            log_and_raise("context message", exc)


# =============================================================================
# safe_call
# =============================================================================

class TestSafeCall:

    def test_returns_result_on_success(self):
        assert safe_call(lambda: 99) == 99

    def test_returns_default_on_exception(self):
        def boom():
            raise RuntimeError("fail")

        assert safe_call(boom) is None
        assert safe_call(boom, default=0) == 0

    def test_passes_args_and_kwargs(self):
        def add(a, b):
            return a + b

        assert safe_call(add, 3, b=4) == 7
