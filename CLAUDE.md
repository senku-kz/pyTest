# CLAUDE.md

Учебный проект для освоения автотестов на Python + FastAPI.

**Что делает сервис:** читает данные из **БД-1 (источник)** и переносит их в **БД-2 (приёмник)**.

**Главная цель тестирования:** эмулировать **ошибки соединения с БД-1** и проверять
**повторные запросы (retry)** — что сервис переживает временный обрыв БД-1, дожимает
перенос после нескольких попыток, а при исчерпании попыток корректно отдаёт ошибку.

## Стек

- **Python** + **FastAPI** — веб-фреймворк для API
- **PostgreSQL ×2** — две базы: `source_db` (:5442) и `target_db` (:5443), обе через Docker
- **pytest** — фреймворк автотестов
- **httpx** / `fastapi.testclient` — HTTP-клиент для тестов API
- **psycopg** (psycopg3) — драйвер PostgreSQL; работаем **чистым SQL**, ORM (SQLAlchemy и т.п.) не используем
- Виртуальное окружение — **`.venv`** (в корне проекта)

> Важно: весь доступ к БД — через SQL-запросы (см. `sql/*.sql`, параметризованные запросы в коде). ORM не применяем.

## Стиль кода

Проект учебный — код должен быть простым и понятным:

- **Процедурный стиль**: функции и модульные переменные. Свои классы **не создаём**
  (никакого ООП, декораторов-обёрток, Pydantic-моделей). Конфиг — константы в `app/config.py`.
- **Логи — только через общий `logger`** (`app/logger.py`):

  ```python
  from app.logger import logger
  logger.info("сообщение")
  logger.warning("подозрительно")
  logger.error("ошибка")
  ```

  `print()` для сообщений не используем.

## Окружение

Всегда работаем внутри `.venv`. Активация:

```bash
source .venv/bin/activate
```

Создание окружения (первый раз):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Все команды `python`, `pip`, `pytest`, `uvicorn` запускаем только при активированном `.venv`.

## Базы данных

Две PostgreSQL поднимаются через Docker Compose из `docker-compose.yml`:

- **db1 / source_db** — порт `5442`, источник (division, position, employee)
- **db2 / target_db** — порт `5443`, приёмник (employee_transfer)

Запуск / остановка:

```bash
docker compose up -d
docker compose down
```

Эмуляция обрыва соединения с БД-1 (для retry-тестов):

```bash
docker compose pause db1
docker compose unpause db1
```

Параметры подключения читаем из переменных окружения / `.env` (отдельно для db1 и db2).

Применение схем и данных:

```bash
# БД-1 (источник)
psql "postgresql://app:app@localhost:5442/source_db" -f sql/schema_source.sql
psql "postgresql://app:app@localhost:5442/source_db" -f sql/seed_source.sql
# БД-2 (приёмник)
psql "postgresql://app:app@localhost:5443/target_db" -f sql/schema_target.sql
```

## Запуск приложения

```bash
uvicorn app.main:app --reload
```

API по умолчанию доступно на http://127.0.0.1:8000, интерактивная документация — http://127.0.0.1:8000/docs

## Автотесты

Основная тема проекта. Запуск тестов:

```bash
pytest
```

Полезные варианты:

```bash
pytest -v                 # подробный вывод
pytest tests/test_x.py    # один файл
pytest -k "имя"           # по маске имени теста
pytest -x                 # остановиться на первом падении
```

### Правила по тестам

- Тесты лежат в каталоге `tests/`, файлы называем `test_*.py`, функции — `test_*`.
- Для тестов поднимаем PostgreSQL из `docker-compose.yml` (не мокаем БД без причины — учимся работать с реальной базой).
- Общие фикстуры (клиент API, сессия БД, откат транзакций) держим в `tests/conftest.py`.
- Каждый тест должен быть изолирован: после теста БД возвращается в исходное состояние (транзакция с откатом или очистка таблиц).
- Перед запуском тестов убедиться, что контейнер с БД запущен.

## Структура проекта (целевая)

```
pyTest/
├── app/                    # код приложения
│   ├── main.py             # точка входа FastAPI (эндпоинты)
│   ├── config.py           # настройки — константы из окружения / .env
│   ├── logger.py           # общий logger проекта
│   ├── db_source.py        # БД-1 (источник): подключение + поэтапное чтение
│   ├── db_target.py        # БД-2 (приёмник): подключение + запись
│   └── transfer.py         # оркестрация: читает из БД-1, преобразует, пишет в БД-2
├── sql/                    # SQL-скрипты (отдельно от Python)
│   ├── schema_source.sql   # DDL БД-1: division, position, employee
│   ├── seed_source.sql     # наполнение БД-1 (10/10/100 записей)
│   └── schema_target.sql   # DDL БД-2: employee_transfer
├── tests/                  # автотесты
│   ├── conftest.py         # фикстуры pytest
│   └── test_*.py
├── docker-compose.yml      # две PostgreSQL (db1 source, db2 target)
├── requirements.txt
├── .env                    # переменные окружения (не коммитить)
└── .venv/                  # виртуальное окружение
```
