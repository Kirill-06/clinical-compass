"""Командная строка: `clinical-compass serve | migrate | seed | check-contracts | evaluate-extractor`."""

import argparse
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

import uvicorn

from clinical_compass.api.runtime import Runtime
from clinical_compass.config import Settings, get_settings
from clinical_compass.db.migrations import upgrade_to_head
from clinical_compass.domain.contracts import ContractError, load_contracts
from clinical_compass.domain.rules import RuleConfigError
from clinical_compass.evaluation import evaluate_extractor, write_eval_outputs
from clinical_compass.seed import seed_if_empty

logger = logging.getLogger("clinical_compass")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    command: Callable[[argparse.Namespace, Settings], int] = _COMMANDS[args.command]
    return command(args, get_settings())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinical-compass", description="Клинический компас — backend v0.2")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="запустить API (миграции и демо-данные применяются при старте)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    sub.add_parser("migrate", help="применить миграции БД")
    sub.add_parser("seed", help="загрузить демо-данные в пустую БД")
    sub.add_parser("check-contracts", help="проверить согласованность contracts/")
    evaluate = sub.add_parser("evaluate-extractor", help="прогнать текущий Extractor по gold JSONL")
    evaluate.add_argument("dataset", type=Path)
    evaluate.add_argument("--out-dir", type=Path, default=Path("evaluation/out"))
    return parser


def _serve(args: argparse.Namespace, _settings: Settings) -> int:
    uvicorn.run("clinical_compass.main:app_factory", factory=True, host=args.host, port=args.port)
    return 0


def _migrate(_args: argparse.Namespace, settings: Settings) -> int:
    upgrade_to_head(settings.database_url)
    logger.info("Миграции применены")
    return 0


def _seed(_args: argparse.Namespace, settings: Settings) -> int:
    upgrade_to_head(settings.database_url)
    runtime = Runtime.build(settings)
    with runtime.session_factory() as session:
        loaded = seed_if_empty(runtime.deps(session))
        session.commit()
    logger.info("Демо-данные загружены" if loaded else "База не пуста — демо-данные не загружались")
    return 0


def _evaluate_extractor(args: argparse.Namespace, settings: Settings) -> int:
    result = evaluate_extractor(Runtime.build(settings).extractor, args.dataset)
    write_eval_outputs(
        result,
        metrics_path=args.out_dir / "metrics.json",
        predictions_path=args.out_dir / "predictions.jsonl",
    )
    print(json.dumps(result.metrics, ensure_ascii=False, indent=2))
    return 0


def _check_contracts(_args: argparse.Namespace, settings: Settings) -> int:
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


_COMMANDS: dict[str, Callable[[argparse.Namespace, Settings], int]] = {
    "serve": _serve,
    "migrate": _migrate,
    "seed": _seed,
    "check-contracts": _check_contracts,
    "evaluate-extractor": _evaluate_extractor,
}


if __name__ == "__main__":
    sys.exit(main())
