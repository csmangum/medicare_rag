"""Tests for config module (safe env parsing, centralized constants)."""
import os
from unittest.mock import patch

from medicare_rag.config import _safe_float, _safe_int


class TestSafeInt:
    def test_returns_default_when_key_missing(self) -> None:
        key = "_TEST_SAFE_INT_MISSING_X"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(key, None)
            assert _safe_int(key, 42) == 42

    def test_parses_valid_int(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_INT_VALID": "100"}, clear=False):
            assert _safe_int("_TEST_SAFE_INT_VALID", 0) == 100

    def test_returns_default_on_invalid_value(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_INT_BAD": "not_a_number"}, clear=False):
            assert _safe_int("_TEST_SAFE_INT_BAD", 7) == 7

    def test_returns_default_on_empty_string(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_INT_EMPTY": ""}, clear=False):
            assert _safe_int("_TEST_SAFE_INT_EMPTY", 3) == 3


class TestSafeFloat:
    def test_returns_default_when_key_missing(self) -> None:
        key = "_TEST_SAFE_FLOAT_MISSING_X"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(key, None)
            assert _safe_float(key, 1.5) == 1.5

    def test_parses_valid_float(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_FLOAT_VALID": "2.25"}, clear=False):
            assert _safe_float("_TEST_SAFE_FLOAT_VALID", 0.0) == 2.25

    def test_returns_default_on_invalid_value(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_FLOAT_BAD": "nope"}, clear=False):
            assert _safe_float("_TEST_SAFE_FLOAT_BAD", 1.05) == 1.05

    def test_returns_default_on_empty_string(self) -> None:
        with patch.dict(os.environ, {"_TEST_SAFE_FLOAT_EMPTY": ""}, clear=False):
            assert _safe_float("_TEST_SAFE_FLOAT_EMPTY", 60.0) == 60.0
