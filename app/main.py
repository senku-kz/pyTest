"""FastAPI-приложение: запуск переноса БД-1 → БД-2. Процедурный стиль."""

import psycopg
from fastapi import FastAPI, HTTPException

from app.logger import logger
from app.transfer import clear_target, transfer

app = FastAPI(title="pyTest transfer service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transfer")
def run_transfer():
    """Переносит сотрудников из БД-1 в БД-2.

    Если БД-1 недоступна и все повторные попытки исчерпаны — отдаём 503.
    """
    try:
        return transfer()
    except psycopg.OperationalError as error:
        logger.error("Синхронизация не прошла, БД-1 недоступна: %s", error)
        raise HTTPException(
            status_code=503,
            detail="Синхронизация не выполнена: БД-1 недоступна",
        )


@app.delete("/target")
def clear_target_table():
    """Очищает таблицу-приёмник (employee_transfer) в БД-2."""
    try:
        return clear_target()
    except psycopg.OperationalError as error:
        logger.error("Очистка БД-2 не выполнена: %s", error)
        raise HTTPException(status_code=503, detail="БД-2 недоступна")
