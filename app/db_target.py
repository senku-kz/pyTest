"""Работа с БД-2 (ПРИЁМНИК): подключение и запись.

Здесь собрано всё про БД-2: подключение (без повторов — сбои эмулируем только
у БД-1) и идемпотентная запись перенесённых сотрудников.
"""

import psycopg

from app import config
from app.logger import logger

INSERT_TRANSFER = """
    INSERT INTO employee_transfer
        (source_employee_id, first_name, last_name, email,
         division_code, position_title, salary)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_employee_id) DO NOTHING
"""

DELETE_TRANSFER = "DELETE FROM employee_transfer"


def connect_target():
    """Соединение с БД-2 (приёмник), без повторов."""
    logger.info("Подключаемся к БД-2 (приёмник)")
    return psycopg.connect(config.TARGET_DSN, connect_timeout=config.CONNECT_TIMEOUT)


def write_employees(conn, rows):
    """Пишет строки в БД-2. Соединение передаётся параметром.

    Идемпотентно (ON CONFLICT DO NOTHING). Возвращает число вставленных записей.
    """
    if not rows:
        logger.info("Нет данных для записи в БД-2")
        return 0
    with conn.cursor() as cur:
        cur.executemany(INSERT_TRANSFER, rows)
        inserted = cur.rowcount
    conn.commit()
    logger.info("Записано в БД-2: %d новых записей", inserted)
    return inserted


def delete_all(conn):
    """Очищает таблицу-приёмник (employee_transfer). Возвращает число удалённых строк."""
    with conn.cursor() as cur:
        cur.execute(DELETE_TRANSFER)
        deleted = cur.rowcount
    conn.commit()
    logger.info("Очищена БД-2: удалено %d записей", deleted)
    return deleted
