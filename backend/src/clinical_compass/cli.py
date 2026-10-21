"""Командная строка: `clinical-compass serve | migrate | seed | check-contracts`."""

import argparse
import logging
import sys

import uvicorn

from clinical_compass.api.runtime import Runtime
from clinical_compass.config import get_settings
from clinical_compass.db.migrations import upgrade_to_head
from clinical_compass.domain.contracts import ContractError, load_contracts
from clinical_compass.domain.rules import RuleConfigError
from clinical_compass.seed import seed_if_empty

logger = logging.getLogger("clinical_compass")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clinical-compass", description="Клинический компас — backend v0.2")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="запустить API (миграции и демо-данные применяются при старте)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    sub.add_parser("migrate", help="применить миграции БД")
    sub.add_parser("seed", help="загрузить демо-данные в пустую БД")
    sub.add_parser("check-contracts", help="проверить согласованность contracts/")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    if args.command == "serve":
        uvicorn.run("clinical_compass.main:app_factory", factory=True, host=args.host, port=args.port)
        return 0
    if args.command == "migrate":
        upgrade_to_head(settings.database_url)
        logger.info("Миграции применены")
        return 0
    if args.command == "seed":
        upgrade_to_head(settings.database_url)
        runtime = Runtime.build(settings)
        with runtime.session_factory() as session:
            loaded = seed_if_empty(runtime.deps(session))
            session.commit()
        logger.info("Демо-данные загружены" if loaded else "База не пуста — демо-данные не загружались")
        return 0
    try:
        contracts = load_contracts(settings.contracts_dir)
    except (ContractError, RuleConfigError, ValueError) as exc:
        logger.error("Контракты некорректны: %s", exc)
        return 1
    logger.info(
        "Контракты в порядке: %d правил (v%s), %d шаблонов, шкалы %s",
        len(contracts.rules.rules),
        contracts.rules.rule_version,
        len(contracts.templates),
        ", ".join(i.value for i in contracts.instruments),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
