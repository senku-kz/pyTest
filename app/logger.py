"""Единый логгер проекта.

Импортируем `logger` в любом модуле и пишем сообщения:
    from app.logger import logger
    logger.info("что-то произошло")
    logger.warning("подозрительно")
    logger.error("ошибка")
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("pytest_app")
