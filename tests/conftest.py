"""Pytest fixtures shared across tests."""

import pytest

from medicare_rag.query.hybrid import reset_bm25_index


@pytest.fixture(autouse=True)
def reset_bm25_index_after_test():
    """Reset the shared BM25 index after each test for isolation."""
    yield
    reset_bm25_index()
