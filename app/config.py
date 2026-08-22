"""Настройки проекта — простые константы из переменных окружения / .env.

Процедурный стиль: никаких классов, только модульные переменные.
"""

import os

from dotenv import load_dotenv

# Подхватываем .env, если он есть (иначе берём значения по умолчанию ниже).
load_dotenv()

# DSN двух баз
SOURCE_DSN = os.getenv("SOURCE_DSN", "postgresql://app:app@localhost:5442/source_db")
TARGET_DSN = os.getenv("TARGET_DSN", "postgresql://app:app@localhost:5443/target_db")

# Параметры повторных попыток соединения с БД-1
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "0.2"))

# Таймаут соединения (сек). Без него недоступная БД подвешивает connect
# на минуты вместо быстрой ошибки — и повторные попытки не запускаются.
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "2"))

# Таймаут выполнения запроса на сервере (мс). Если SELECT идёт дольше —
# Postgres отменит его, psycopg бросит QueryCanceled (это OperationalError),
# и сработает повтор. Покрывает случай «долгий/зависший запрос».
STATEMENT_TIMEOUT_MS = int(os.getenv("STATEMENT_TIMEOUT_MS", "3000"))

# Таймаут «молчания» сокета (мс). Если сервер завис/пропал уже во время
# запроса (обрыв сети, docker pause после connect) — клиент разорвёт
# зависшее соединение через это время, а не будет ждать бесконечно.
TCP_USER_TIMEOUT_MS = int(os.getenv("TCP_USER_TIMEOUT_MS", "3000"))
