"""Тесты работы с БД-1 (источник) — основной фокус проекта.

Покрываем:
  - connect_source: подключение с повторами;
  - read_table:     чтение одной таблицы с повторами (обрыв, отмена долгого
                    запроса, пустой ответ, backoff, исчерпание попыток);
  - read_source:    поэтапное чтение и остановка, если первый этап не прошёл.

Соединение мокаем (MagicMock) — живая БД не нужна.
"""

from unittest.mock import MagicMock

import psycopg
import pytest
from psycopg import errors

import app.db_source as source


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Убираем реальные паузы между попытками во всех тестах модуля."""
    monkeypatch.setattr("app.db_source.time.sleep", lambda _: None)


def make_conn():
    """Фейковое соединение с курсором-контекст-менеджером (conn, cur)."""
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    return conn, cur


# ------------------------- connect_source -------------------------

def test_connect_source_retries_then_succeeds(monkeypatch):
    """БД-1 «падает» 1 раз, затем доступна → connect_source вернёт соединение."""
    calls = {"n": 0}

    def fake_connect(dsn, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise psycopg.OperationalError("connection refused (эмуляция)")
        return f"conn:{dsn}"

    monkeypatch.setattr(psycopg, "connect", fake_connect)

    conn = source.connect_source()

    assert conn.startswith("conn:")
    assert calls["n"] == 2


def test_connect_source_gives_up_after_max_attempts(monkeypatch):
    """БД-1 недоступна всегда → OperationalError после исчерпания попыток."""
    calls = {"n": 0}

    def always_down(dsn, **kwargs):
        calls["n"] += 1
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(psycopg, "connect", always_down)

    with pytest.raises(psycopg.OperationalError):
        source.connect_source()

    assert calls["n"] == source.config.RETRY_MAX_ATTEMPTS


# ------------------------- read_table -------------------------

def test_read_succeeds_on_first_try():
    conn, cur = make_conn()
    cur.fetchall.return_value = [(1, "DEV"), (2, "QA")]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert len(rows) == 2
    assert cur.execute.call_count == 1


def test_read_retries_after_connection_drop():
    """execute падает с OperationalError 2 раза, на 3-й — успех."""
    conn, cur = make_conn()
    cur.execute.side_effect = [
        psycopg.OperationalError("соединение потеряно"),
        psycopg.OperationalError("соединение потеряно"),
        None,
    ]
    cur.fetchall.return_value = [(1, "DEV")]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert rows == [(1, "DEV")]
    assert cur.execute.call_count == 3


def test_read_retries_on_query_timeout():
    """Долгий запрос отменяется (QueryCanceled), повтор — и успех."""
    conn, cur = make_conn()
    cur.execute.side_effect = [
        errors.QueryCanceled("canceling statement due to statement timeout"),
        None,
    ]
    cur.fetchall.return_value = [(1, "DEV")]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert rows == [(1, "DEV")]
    assert cur.execute.call_count == 2


def test_read_gives_up_on_persistent_timeout():
    """Запрос отменяется всегда → ровно N попыток, затем ошибка наружу."""
    conn, cur = make_conn()
    cur.execute.side_effect = errors.QueryCanceled("timeout")

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    assert cur.execute.call_count == source.config.RETRY_MAX_ATTEMPTS


def test_read_retries_until_data():
    """Первые 2 раза пусто, на 3-й — данные → попыток ровно 3."""
    conn, cur = make_conn()
    cur.fetchall.side_effect = [[], [], [(1, "DEV")]]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert rows == [(1, "DEV")]
    assert cur.execute.call_count == 3


def test_read_gives_up_when_always_empty():
    """Всегда пусто → ровно N попыток, затем ошибка."""
    conn, cur = make_conn()
    cur.fetchall.return_value = []

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    assert cur.execute.call_count == source.config.RETRY_MAX_ATTEMPTS


def test_read_backoff_between_attempts(monkeypatch):
    """Между попытками растущие паузы: base, base*2."""
    delays = []
    monkeypatch.setattr("app.db_source.time.sleep", delays.append)
    conn, cur = make_conn()
    cur.fetchall.return_value = []

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    base = source.config.RETRY_BASE_DELAY
    assert delays == pytest.approx([base, base * 2])


# ------------------------- read_source: поэтапно + short-circuit -------------------------

def test_read_source_reads_all_tables_in_order(monkeypatch):
    """Успех: читаются все три таблицы по порядку."""
    read_order = []

    def fake_read_table(conn, sql, what):
        read_order.append(what)
        return [("data",)]

    monkeypatch.setattr(source, "read_table", fake_read_table)

    source.read_source(MagicMock())

    assert read_order == ["Чтение division", "Чтение position", "Чтение employee"]


def test_read_source_stops_after_first_table_fails(monkeypatch):
    """Ключевое: первый этап упал → position и employee НЕ читаются."""
    read_order = []

    def fake_read_table(conn, sql, what):
        read_order.append(what)
        raise psycopg.OperationalError("БД-1 недоступна на первом этапе")

    monkeypatch.setattr(source, "read_table", fake_read_table)

    with pytest.raises(psycopg.OperationalError):
        source.read_source(MagicMock())

    assert read_order == ["Чтение division"]
