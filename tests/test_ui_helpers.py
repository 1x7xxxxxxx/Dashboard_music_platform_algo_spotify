"""Unit tests for src/dashboard/utils/ui.py."""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.dashboard.utils.ui import show_empty_state


def _st():
    return MagicMock()


def test_empty_df_returns_true_and_calls_info():
    st = _st()
    with patch("src.dashboard.utils.ui.st", st):
        assert show_empty_state(pd.DataFrame(), "rien") is True
    st.info.assert_called_once_with("rien")


def test_none_returns_true():
    st = _st()
    with patch("src.dashboard.utils.ui.st", st):
        assert show_empty_state(None, "rien") is True
    st.info.assert_called_once()


def test_non_empty_returns_false_and_no_message():
    st = _st()
    with patch("src.dashboard.utils.ui.st", st):
        assert show_empty_state(pd.DataFrame({"a": [1]}), "rien") is False
    st.info.assert_not_called()


def test_level_warning_routes_to_st_warning():
    st = _st()
    with patch("src.dashboard.utils.ui.st", st):
        show_empty_state(pd.DataFrame(), "warn", level="warning")
    st.warning.assert_called_once_with("warn")
    st.info.assert_not_called()


def test_invalid_level_raises():
    with pytest.raises(ValueError):
        show_empty_state(pd.DataFrame(), "x", level="critical")
