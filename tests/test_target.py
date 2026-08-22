"""Тесты работы с БД-2 (приёмник): подключение без повторов и запись."""

import psycopg
import pytest

import app.db_target as target


def test_connect_target_has_no_retry(monkeypatch):
    """У БД-2 нет retry — ошибка соединения пробрасывается сразу, одной попыткой."""
    calls = {"n": 0}

    def always_down(dsn, **kwargs):
        calls["n"] += 1
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(psycopg, "connect", always_down)

    with pytest.raises(psycopg.OperationalError):
        target.connect_target()

    assert calls["n"] == 1


def test_write_employees_inserts_rows(make_conn):
    """Есть строки → executemany + commit, возвращается число вставленных."""
    conn, cur = make_conn()
    cur.rowcount = 3
    rows = [(1,), (2,), (3,)]

    inserted = target.write_employees(conn, rows)

    assert inserted == 3
    cur.executemany.assert_called_once()
    conn.commit.assert_called_once()


def test_write_employees_empty_does_nothing(make_conn):
    """Пустой список → 0, запись не выполняется."""
    conn, _ = make_conn()

    inserted = target.write_employees(conn, [])

    assert inserted == 0
    conn.commit.assert_not_called()
