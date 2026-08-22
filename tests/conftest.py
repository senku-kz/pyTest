"""Общие фикстуры pytest."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """HTTP-клиент FastAPI для тестов API."""
    return TestClient(app)
