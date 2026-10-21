"""Применение миграций Alembic из кода (при старте приложения и в тестах).

Скрипты миграций лежат внутри пакета (`db/alembic`), поэтому работают
и из установленного пакета в контейнере.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

SCRIPT_LOCATION = Path(__file__).resolve().parent / "alembic"


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(SCRIPT_LOCATION))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_to_head(database_url: str) -> None:
    if database_url.startswith("sqlite:///") and ":memory:" not in database_url:
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(database_url), "head")
