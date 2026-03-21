#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утренний сценарий (для планировщика задач Windows / cron):

  1) Проверка результатов — закрытые рынки Gamma → обновление snapshots и bets в agent.db
     (как `python check_results.py`).
  2) Один цикл сканирования — Pinnacle vs Polymarket → сигналы с положительным edge
     проходят фильтры риска → в режиме recommend запись в БД/Excel-логика как в main,
     в режиме auto — реальные ордера (нужны ключи Polymarket).

«Благоприятный исход» в смысле проекта = оценочное преимущество (edge) от sharp-линии
и прохождение RiskManager (окно до матча, лимиты, slippage при auto).

Использование:
  python scripts/daily_morning.py
  python scripts/daily_morning.py --mode auto --bankroll 5000
  python scripts/daily_morning.py --skip-resolve   # только сканирование

Планировщик Windows: ежедневно в 08:00 — см. docs/DAILY_SCHEDULE.md
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows: избежать UnicodeEncodeError в Rich при не-ASCII в вопросах рынков
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _setup_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


async def _run_resolve() -> None:
    from check_results import resolve_bets
    from storage.db import Database

    log = logging.getLogger("daily_morning")
    log.info("Шаг 1/2: проверка результатов (check_results.resolve_bets)")
    db = Database()
    await db.connect()
    try:
        await resolve_bets(db)
    finally:
        await db.close()
    log.info("Шаг 1/2 завершён.")


async def _run_scan(mode: str, bankroll: float) -> None:
    from rich.console import Console

    from main import run_scan_cycle
    from config import load_settings
    from data.collector import PolymarketCollector
    from data.odds_api import OddsApiClient
    from storage.db import Database
    from trading.risk import RiskManager
    from trading.executor import Executor

    console = Console()
    log = logging.getLogger("daily_morning")

    log.info("Шаг 2/2: сканирование и сигналы (режим %s)", mode)
    settings = load_settings(mode)
    db = Database()
    await db.connect()
    collector = PolymarketCollector(settings)
    odds_client = OddsApiClient(settings)
    risk = RiskManager(settings, db)
    executor = Executor(settings, db, risk, collector, mode=mode)

    try:
        await run_scan_cycle(
            settings,
            collector,
            odds_client,
            executor,
            bankroll,
            mode,
            db=db,
        )
    finally:
        await collector.close()
        await odds_client.close()
        await db.close()

    console.print(
        f"[green]Утренний цикл завершён {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC[/green]"
    )
    log.info("Шаг 2/2 завершён.")


async def main_async(args: argparse.Namespace) -> None:
    log_path = Path(args.log_file) if args.log_file else None
    _setup_logging(log_path)

    if not args.skip_resolve:
        try:
            await _run_resolve()
        except Exception:
            logging.exception("Ошибка при проверке результатов — продолжаем сканирование")
            if args.strict:
                raise

    await _run_scan(args.mode, args.bankroll)


def main() -> None:
    parser = argparse.ArgumentParser(description="Утренний цикл: результаты + новые сигналы")
    parser.add_argument(
        "--mode",
        choices=["recommend", "auto"],
        default="recommend",
        help="recommend — только рекомендации в БД; auto — реальные ордера",
    )
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument(
        "--skip-resolve",
        action="store_true",
        help="Не вызывать check_results (только сканирование)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="При ошибке шага 1 не запускать шаг 2",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=str(ROOT / "logs" / "daily_morning.log"),
        help="Путь к лог-файлу",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Не писать в файл, только stdout",
    )
    args = parser.parse_args()
    if args.no_log_file:
        args.log_file = None

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
