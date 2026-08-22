"""Тесты API-эндпоинта /transfer. Логику переноса мокаем."""

import psycopg

import app.main as main


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_transfer_ok(client, monkeypatch):
    """Успешный перенос → 200 и сводка read/inserted."""
    monkeypatch.setattr(main, "transfer", lambda: {"read": 100, "inserted": 100})

    resp = client.post("/transfer")

    assert resp.status_code == 200
    assert resp.json() == {"read": 100, "inserted": 100}


def test_transfer_source_unavailable_returns_503(client, monkeypatch):
    """БД-1 недоступна (повторы исчерпаны) → 503."""

    def boom():
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(main, "transfer", boom)

    resp = client.post("/transfer")

    assert resp.status_code == 503
    assert "БД-1 недоступна" in resp.json()["detail"]
