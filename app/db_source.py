"""Работа с БД-1 (ИСТОЧНИК): подключение и поэтапное чтение.

Основной фокус проекта. Здесь собрано всё, что связано с чтением из БД-1:
устойчивое подключение (повторы + таймауты) и чтение таблиц с повторами.

Читаем ПОЭТАПНО (division → position → employee). Если первый этап не прошёл
(после всех повторов) — следующие НЕ выполняются: исключение прерывает чтение.
"""

import time

import psycopg

from app import config
from app.logger import logger

# Читаем каждую таблицу-источник отдельным запросом (поэтапно).
SELECT_DIVISIONS = "SELECT id, code FROM division ORDER BY id"
SELECT_POSITIONS = "SELECT id, title FROM position ORDER BY id"
SELECT_EMPLOYEES = """
    SELECT id, first_name, last_name, email, division_id, position_id, salary
    FROM employee
    ORDER BY id
"""


def connect_source():
    """Соединение с БД-1 (источник). Пытаемся подключиться n раз."""
    logger.info("Подключаемся к БД-1 (источник)")
    attempt = 0
    while True:
        attempt += 1
        try:
            logger.info(
                "Соединение с БД-1: попытка %d из %d",
                attempt,
                config.RETRY_MAX_ATTEMPTS,
            )
            return psycopg.connect(
                config.SOURCE_DSN,
                connect_timeout=config.CONNECT_TIMEOUT,
                # серверный таймаут на запрос: отменит долгий SELECT
                options=f"-c statement_timeout={config.STATEMENT_TIMEOUT_MS}",
                # клиентский таймаут сокета: разорвёт зависшее соединение,
                # если сервер пропал уже во время запроса
                tcp_user_timeout=config.TCP_USER_TIMEOUT_MS,
                keepalives=1,
                # только читаем → autocommit: отменённый по таймауту запрос
                # не оставляет «сломанную» транзакцию, и повтор чтения проходит
                autocommit=True,
            )
        except psycopg.OperationalError as error:
            logger.warning("Соединение с БД-1: попытка %d не удалась: %s", attempt, error)
            if attempt >= config.RETRY_MAX_ATTEMPTS:
                logger.error(
                    "Соединение с БД-1: все %d попыток исчерпаны",
                    config.RETRY_MAX_ATTEMPTS,
                )
                raise  # пробрасываем ошибку наружу
            delay = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info("Ждём %.2f с перед следующей попыткой", delay)
            time.sleep(delay)


def read_table(conn, sql, what):
    """Читает одну таблицу из БД-1 с повторными попытками.

    Если данные не получены (ошибка соединения / отмена долгого запроса /
    пустой ответ) — повторяем n раз (цикл while прямо здесь). После исчерпания
    попыток пробрасываем ошибку наружу — это прерывает весь перенос.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            logger.info("%s: попытка %d из %d", what, attempt, config.RETRY_MAX_ATTEMPTS)
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            if not rows:
                # пустой ответ считаем неудачей — пробуем ещё раз
                raise psycopg.OperationalError("БД-1 вернула пустой результат")
            logger.info("%s: получено %d строк", what, len(rows))
            return rows
        except psycopg.OperationalError as error:
            logger.warning("%s: попытка %d не удалась: %s", what, attempt, error)
            if attempt >= config.RETRY_MAX_ATTEMPTS:
                logger.error("%s: все %d попыток исчерпаны", what, config.RETRY_MAX_ATTEMPTS)
                raise  # прерываем перенос — дальше не идём
            delay = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info("Ждём %.2f с перед следующей попыткой", delay)
            time.sleep(delay)


def read_source(conn):
    """Поэтапно читает все таблицы-источники из БД-1.

    Порядок важен: если ПЕРВЫЙ этап (division) упал, position и employee
    уже НЕ читаются — исключение из read_table прерывает функцию.
    """
    divisions = read_table(conn, SELECT_DIVISIONS, "Чтение division")
    positions = read_table(conn, SELECT_POSITIONS, "Чтение position")
    employees = read_table(conn, SELECT_EMPLOYEES, "Чтение employee")
    return divisions, positions, employees
