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


def test_connect_source_succeeds_on_first_try(monkeypatch):
    """БД-1 доступна сразу → одна попытка, пауз нет."""
    slept = []
    monkeypatch.setattr("app.db_source.time.sleep", slept.append)
    monkeypatch.setattr(psycopg, "connect", lambda dsn, **kwargs: "готовое-соединение")

    conn = source.connect_source()

    assert conn == "готовое-соединение"
    assert slept == []


def test_connect_source_backoff_between_attempts(monkeypatch):
    """Между попытками подключения растущие паузы: base, base*2."""
    delays = []
    monkeypatch.setattr("app.db_source.time.sleep", delays.append)

    def always_down(dsn, **kwargs):
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(psycopg, "connect", always_down)

    with pytest.raises(psycopg.OperationalError):
        source.connect_source()

    base = source.config.RETRY_BASE_DELAY
    assert delays == pytest.approx([base, base * 2])


def test_connect_source_uses_expected_parameters(monkeypatch):
    """Подключение к БД-1 идёт с нужными таймаутами и autocommit."""
    captured = {}

    def fake_connect(dsn, **kwargs):
        captured["dsn"] = dsn
        captured.update(kwargs)
        return "conn"

    monkeypatch.setattr(psycopg, "connect", fake_connect)

    source.connect_source()

    assert captured["dsn"] == source.config.SOURCE_DSN
    assert captured["connect_timeout"] == source.config.CONNECT_TIMEOUT
    assert captured["tcp_user_timeout"] == source.config.TCP_USER_TIMEOUT_MS
    assert captured["autocommit"] is True
    # statement_timeout передаётся через options="-c statement_timeout=..."
    assert f"statement_timeout={source.config.STATEMENT_TIMEOUT_MS}" in captured["options"]


# ------------------------- read_table -------------------------

def test_read_succeeds_on_first_try(make_conn):
    """Данные есть сразу → одна попытка."""
    conn, cur = make_conn()
    cur.fetchall.return_value = [(1, "DEV"), (2, "QA")]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert len(rows) == 2
    assert cur.execute.call_count == 1


def test_read_retries_after_connection_drop(make_conn):
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


def test_read_retries_on_query_timeout(make_conn):
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


def test_read_gives_up_on_persistent_timeout(make_conn):
    """Запрос отменяется всегда → ровно N попыток, затем ошибка наружу."""
    conn, cur = make_conn()
    cur.execute.side_effect = errors.QueryCanceled("timeout")

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    assert cur.execute.call_count == source.config.RETRY_MAX_ATTEMPTS


def test_read_retries_until_data(make_conn):
    """Первые 2 раза пусто, на 3-й — данные → попыток ровно 3."""
    conn, cur = make_conn()
    cur.fetchall.side_effect = [[], [], [(1, "DEV")]]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert rows == [(1, "DEV")]
    assert cur.execute.call_count == 3


def test_read_gives_up_when_always_empty(make_conn):
    """Всегда пусто → ровно N попыток, затем ошибка."""
    conn, cur = make_conn()
    cur.fetchall.return_value = []

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    assert cur.execute.call_count == source.config.RETRY_MAX_ATTEMPTS


def test_read_backoff_between_attempts(make_conn, monkeypatch):
    """Между попытками растущие паузы: base, base*2."""
    delays = []
    monkeypatch.setattr("app.db_source.time.sleep", delays.append)
    conn, cur = make_conn()
    cur.fetchall.return_value = []

    with pytest.raises(psycopg.OperationalError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    base = source.config.RETRY_BASE_DELAY
    assert delays == pytest.approx([base, base * 2])


def test_read_does_not_retry_on_non_connection_error(make_conn):
    """Ошибка НЕ про соединение (кривой SQL) → без повторов, сразу наружу."""
    conn, cur = make_conn()
    cur.execute.side_effect = psycopg.ProgrammingError("syntax error")

    with pytest.raises(psycopg.ProgrammingError):
        source.read_table(conn, "SELECT ...", "Чтение division")

    assert cur.execute.call_count == 1  # повторов не было


def test_read_retries_across_different_errors(make_conn):
    """Разные подвиды ошибки соединения подряд → всё равно повтор и успех."""
    conn, cur = make_conn()
    cur.execute.side_effect = [
        psycopg.OperationalError("обрыв"),
        errors.QueryCanceled("таймаут долгого запроса"),
        None,
    ]
    cur.fetchall.return_value = [(1, "DEV")]

    rows = source.read_table(conn, "SELECT ...", "Чтение division")

    assert rows == [(1, "DEV")]
    assert cur.execute.call_count == 3


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


def test_read_source_stops_when_middle_table_fails(monkeypatch):
    """Провал на 2-м этапе (position) → employee уже НЕ читается."""
    read_order = []

    def fake_read_table(conn, sql, what):
        read_order.append(what)
        if what == "Чтение position":
            raise psycopg.OperationalError("сбой на 2-м этапе")
        return [("data",)]

    monkeypatch.setattr(source, "read_table", fake_read_table)

    with pytest.raises(psycopg.OperationalError):
        source.read_source(MagicMock())

    assert read_order == ["Чтение division", "Чтение position"]


def test_read_source_returns_all_tables_and_reuses_one_connection(monkeypatch):
    """read_source возвращает три набора и передаёт ОДНО соединение во все чтения."""
    conn = object()  # маркер-соединение
    seen_conns = []
    data = {
        "Чтение division": [(1, "DEV")],
        "Чтение position": [(10, "Senior")],
        "Чтение employee": [(100, "Иван")],
    }

    def fake_read_table(c, sql, what):
        seen_conns.append(c)
        return data[what]

    monkeypatch.setattr(source, "read_table", fake_read_table)

    divisions, positions, employees = source.read_source(conn)

    assert divisions == [(1, "DEV")]
    assert positions == [(10, "Senior")]
    assert employees == [(100, "Иван")]
    assert seen_conns == [conn, conn, conn]  # одно и то же соединение
