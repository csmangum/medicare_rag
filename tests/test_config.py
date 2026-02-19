"""Tests for config module (safe env parsing, centralized constants)."""
import os
from unittest.mock import patch

from medicare_rag.config import (
    LCD_CHUNK_OVERLAP,
    LCD_CHUNK_SIZE,
    LCD_RETRIEVAL_K,
    _safe_float,
    _safe_float_positive,
    _safe_int,
    _safe_positive_int,
)


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


class TestSafePositiveInt:
    def test_returns_default_when_zero(self) -> None:
        with patch.dict(os.environ, {"_TEST_POS_INT_ZERO": "0"}, clear=False):
            assert _safe_positive_int("_TEST_POS_INT_ZERO", 100) == 100

    def test_returns_default_when_negative(self) -> None:
        with patch.dict(os.environ, {"_TEST_POS_INT_NEG": "-5"}, clear=False):
            assert _safe_positive_int("_TEST_POS_INT_NEG", 500) == 500

    def test_accepts_positive(self) -> None:
        with patch.dict(os.environ, {"_TEST_POS_INT_OK": "42"}, clear=False):
            assert _safe_positive_int("_TEST_POS_INT_OK", 1) == 42


class TestSafeFloatPositive:
    def test_returns_default_when_zero(self) -> None:
        with patch.dict(os.environ, {"_TEST_FLOAT_POS_ZERO": "0.0"}, clear=False):
            assert _safe_float_positive("_TEST_FLOAT_POS_ZERO", 60.0) == 60.0

    def test_returns_default_when_negative(self) -> None:
        with patch.dict(os.environ, {"_TEST_FLOAT_POS_NEG": "-1.0"}, clear=False):
            assert _safe_float_positive("_TEST_FLOAT_POS_NEG", 60.0) == 60.0

    def test_accepts_positive(self) -> None:
        with patch.dict(os.environ, {"_TEST_FLOAT_POS_OK": "30.5"}, clear=False):
            assert _safe_float_positive("_TEST_FLOAT_POS_OK", 60.0) == 30.5


class TestLCDConfigDefaults:
    def test_lcd_chunk_size_default(self) -> None:
        assert LCD_CHUNK_SIZE >= 1
        assert LCD_CHUNK_SIZE == 1500

    def test_lcd_chunk_overlap_default(self) -> None:
        assert LCD_CHUNK_OVERLAP >= 0
        assert LCD_CHUNK_OVERLAP < LCD_CHUNK_SIZE
        assert LCD_CHUNK_OVERLAP == 300

    def test_lcd_retrieval_k_default(self) -> None:
        assert LCD_RETRIEVAL_K >= 1
        assert LCD_RETRIEVAL_K == 12

    def test_lcd_chunk_size_larger_than_standard(self) -> None:
        from medicare_rag.config import CHUNK_SIZE
        assert LCD_CHUNK_SIZE > CHUNK_SIZE
