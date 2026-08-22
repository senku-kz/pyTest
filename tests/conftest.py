"""Общие фикстуры pytest."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _make_conn():
    """Фейковое соединение с курсором-контекст-менеджером (conn, cur)."""
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    return conn, cur


@pytest.fixture
def make_conn():
    """Фабрика фейкового соединения: conn, cur = make_conn()."""
    return _make_conn


@pytest.fixture
def client():
    """HTTP-клиент FastAPI для тестов API."""
    return TestClient(app)
