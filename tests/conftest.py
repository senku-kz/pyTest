"""Общие фикстуры pytest."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """HTTP-клиент FastAPI для тестов API."""
    return TestClient(app)
