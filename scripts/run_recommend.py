#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск recommend mode — один цикл сканирования (для cron/scheduler).

Использование:
  python scripts/run_recommend.py [--bankroll 1000]

Для накопления данных forward-test 1+ неделю:
  - Запускать каждые 1-2 часа (cron: 0 */2 * * *)
  - Или в цикле: python main.py --mode recommend --once
  - Результаты пишутся в agent.db (snapshots), stats: python main.py --mode stats
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main():
    import argparse
    from main import run_scan_cycle, setup_logging
    from config import load_settings
    from data.collector import PolymarketCollector
    from data.odds_api import OddsApiClient
    from check_results import resolve_bets
    from storage.db import Database
    from trading.risk import RiskManager
    from trading.executor import Executor
    from rich.console import Console

    parser = argparse.ArgumentParser(description="Run recommend mode once")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    args = parser.parse_args()
    setup_logging("INFO")
    console = Console()

    settings = load_settings("recommend")
    db = Database()
    await db.connect()

    collector = PolymarketCollector(settings)
    odds_client = OddsApiClient(settings)
    risk = RiskManager(settings, db)
    executor = Executor(settings, db, risk, collector, mode="recommend")

    try:
        await run_scan_cycle(
            settings, collector, odds_client, executor,
            args.bankroll, "recommend", db=db,
        )
        # Resolve pending snapshots and bets from closed markets (reuse collector)
        await resolve_bets(db, collector=collector)
    finally:
        await collector.close()
        await odds_client.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
