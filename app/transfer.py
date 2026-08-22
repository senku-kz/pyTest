"""Оркестрация переноса (синхронизации) БД-1 → БД-2.

Связывает два модуля:
    db_source  — читает из БД-1 (источник)
    db_target  — пишет в БД-2 (приёмник)

Здесь только последовательность шагов и преобразование данных. Сама работа
с базами вынесена в db_source.py и db_target.py — так понятнее, где что.
"""

import psycopg

from app.db_source import connect_source, read_source
from app.db_target import connect_target, delete_all, write_employees
from app.logger import logger


def build_transfer_rows(divisions, positions, employees):
    """Собирает строки для БД-2, подставляя код отдела и название должности."""
    code_by_division = {div_id: code for div_id, code in divisions}
    title_by_position = {pos_id: title for pos_id, title in positions}

    rows = []
    for emp_id, first_name, last_name, email, division_id, position_id, salary in employees:
        rows.append(
            (
                emp_id,
                first_name,
                last_name,
                email,
                code_by_division[division_id],
                title_by_position[position_id],
                salary,
            )
        )
    return rows


def transfer():
    """Полная синхронизация БД-1 → БД-2.

    Сначала ПОЛНОСТЬЮ читаем источник (поэтапно). Только если чтение прошло —
    собираем строки и пишем в БД-2. Любая ошибка (недоступность БД-1 при
    подключении или при чтении) прерывает синхронизацию до записи, и об этом
    пишется явное сообщение.
    """
    logger.info("Старт синхронизации БД-1 → БД-2")
    source_conn = None
    target_conn = None
    try:
        source_conn = connect_source()
        target_conn = connect_target()
        divisions, positions, employees = read_source(source_conn)
        rows = build_transfer_rows(divisions, positions, employees)
        inserted = write_employees(target_conn, rows)
    except psycopg.OperationalError as error:
        logger.error("Синхронизация НЕ выполнена: %s", error)
        raise  # пробрасываем наружу — запись в БД-2 не состоялась
    finally:
        if source_conn is not None:
            source_conn.close()
        if target_conn is not None:
            target_conn.close()
        logger.info("Соединения с БД-1 и БД-2 закрыты")

    logger.info(
        "Синхронизация выполнена: прочитано %d, вставлено %d", len(employees), inserted
    )
    return {"read": len(employees), "inserted": inserted}


def clear_target():
    """Очищает таблицу-приёмник в БД-2. Возвращает сводку."""
    logger.info("Старт очистки таблицы-приёмника (БД-2)")
    conn = connect_target()
    try:
        deleted = delete_all(conn)
    finally:
        conn.close()
        logger.info("Соединение с БД-2 закрыто")
    return {"deleted": deleted}
