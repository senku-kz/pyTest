"""Тесты оркестрации transfer(): преобразование данных и провал синхронизации.

Работа с самими БД покрыта в test_source.py (БД-1) и test_target.py (БД-2).
Здесь — связка шагов: маппинг строк и поведение при ошибке.
"""

from unittest.mock import MagicMock

import psycopg
import pytest

import app.transfer as transfer


def test_build_transfer_rows_maps_codes_and_titles():
    """Подставляются код отдела и название должности по id."""
    divisions = [(1, "DEV"), (2, "QA")]
    positions = [(10, "Senior"), (20, "QA-инженер")]
    employees = [
        (100, "Иван", "Иванов", "i@e.com", 1, 10, 500000),
        (101, "Мария", "Сидорова", "m@e.com", 2, 20, 300000),
    ]

    rows = transfer.build_transfer_rows(divisions, positions, employees)

    assert rows == [
        (100, "Иван", "Иванов", "i@e.com", "DEV", "Senior", 500000),
        (101, "Мария", "Сидорова", "m@e.com", "QA", "QA-инженер", 300000),
    ]


def test_transfer_logs_failure_and_skips_write(monkeypatch, caplog):
    """Ошибка чтения → «Синхронизация НЕ выполнена», запись в БД-2 не идёт."""
    monkeypatch.setattr(transfer, "connect_source", lambda: MagicMock())
    monkeypatch.setattr(transfer, "connect_target", lambda: MagicMock())

    def failing_read(conn):
        raise psycopg.OperationalError("БД-1 недоступна")

    monkeypatch.setattr(transfer, "read_source", failing_read)

    write_called = []
    monkeypatch.setattr(
        transfer, "write_employees", lambda conn, rows: write_called.append(True)
    )

    with caplog.at_level("ERROR"):
        with pytest.raises(psycopg.OperationalError):
            transfer.transfer()

    assert any("Синхронизация НЕ выполнена" in m for m in caplog.messages)
    assert write_called == []
