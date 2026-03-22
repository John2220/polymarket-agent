"""Polymarket Аналитический Агент — точка входа CLI."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

sys.path.insert(0, str(Path(__file__).parent))

from config import load_settings, Settings
from data.collector import PolymarketCollector
from data.odds_api import OddsApiClient, match_odds_to_markets
from analysis.signals import generate_signals
from analysis.backtest import (
    show_forward_test_stats,
    show_betting_stats,
    show_signal_calibration,
    show_stats_by_league,
)
from check_results import resolve_bets
from storage.db import Database
from trading.risk import RiskManager
from trading.executor import Executor

console = Console()


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket Аналитический Агент")
    parser.add_argument(
        "--mode",
        choices=["recommend", "auto", "stats"],
        default="recommend",
        help="Режим работы (по умолчанию: recommend)",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=1000.0,
        help="Начальный банкролл в USD (по умолчанию: 1000)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Выполнить один цикл сканирования и выйти",
    )
    return parser.parse_args()


def display_signals_table(signals, mode: str):
    """Отобразить сигналы в таблице."""
    if not signals:
        console.print("[dim]Сигналов не найдено в этом цикле.[/dim]")
        return

    max_rows = int(os.environ.get("PM_MAX_SIGNAL_ROWS", "200"))
    total = len(signals)
    to_show = signals[:max_rows]
    if total > max_rows:
        console.print(
            f"[dim]Показано {max_rows} из {total} сигналов (PM_MAX_SIGNAL_ROWS={max_rows})[/dim]"
        )

    table = Table(
        title=f"Торговые сигналы (режим: {mode})",
        show_lines=True,
    )
    table.add_column("№", style="dim", width=3)
    table.add_column("Рынок", max_width=45)
    table.add_column("Сторона", justify="center")
    table.add_column("Цена PM", justify="right")
    table.add_column("Истин. вер.", justify="right")
    table.add_column("Edge", justify="right")
    table.add_column("Келли f", justify="right")
    table.add_column("Ставка $", justify="right")
    table.add_column("EV/$", justify="right")

    for i, sig in enumerate(to_show, 1):
        side_style = "green" if sig.side.value == "YES" else "red"
        side_ru = "ДА" if sig.side.value == "YES" else "НЕТ"
        edge_style = "bold green" if sig.edge >= 0.08 else "green"

        table.add_row(
            str(i),
            sig.market.question[:45],
            f"[{side_style}]{side_ru}[/{side_style}]",
            f"{sig.market_price:.3f}",
            f"{sig.true_prob:.3f}",
            f"[{edge_style}]{sig.edge:.3f}[/{edge_style}]",
            f"{sig.kelly_fraction:.3f}",
            f"${sig.bet_size_usd:.2f}",
            f"{sig.ev:.4f}",
        )

    console.print(table)


def display_execution_results(records):
    """Отобразить результаты исполнения."""
    if not records:
        return

    table = Table(title="Результаты исполнения")
    table.add_column("Рынок", max_width=40)
    table.add_column("Сторона")
    table.add_column("Сумма $", justify="right")
    table.add_column("Статус")
    table.add_column("ID ордера", max_width=20)

    status_names = {
        "filled": "исполнен",
        "recommended": "рекомендация",
        "cancelled": "отменён",
        "rejected": "отклонён",
    }

    for r in records:
        status_style = {
            "filled": "bold green",
            "recommended": "cyan",
            "cancelled": "yellow",
            "rejected": "red",
        }.get(r.status, "white")
        status_ru = status_names.get(r.status, r.status)
        side_ru = "ДА" if r.side.value == "YES" else "НЕТ"

        table.add_row(
            r.market_question[:40],
            side_ru,
            f"${r.size_usd:.2f}",
            f"[{status_style}]{status_ru}[/{status_style}]",
            r.order_id[:20] if r.order_id else "",
        )

    console.print(table)


async def run_scan_cycle(
    settings: Settings,
    collector: PolymarketCollector,
    odds_client: OddsApiClient,
    executor: Executor,
    bankroll: float,
    mode: str,
    db: Database | None = None,
):
    """Выполнить один цикл: сканирование → анализ → исполнение."""
    initial_bankroll = bankroll
    if db is not None:
        current_equity = await db.get_current_equity(initial_bankroll)
    else:
        current_equity = bankroll

    console.print(
        Panel(
            f"[bold]Сканирование рынков...[/bold]  Режим: {mode}  |  Equity: ${current_equity:.2f}",
            style="blue",
        )
    )

    # 1. Получаем рынки Polymarket
    console.print("[dim]Загрузка рынков Polymarket...[/dim]")
    markets = await collector.fetch_all_active_markets(batch=100)
    console.print(f"  Найдено {len(markets)} активных рынков")

    # 2. Получаем котировки Pinnacle
    console.print("[dim]Загрузка котировок Pinnacle...[/dim]")
    odds_lines = await odds_client.fetch_all_odds()
    console.print(f"  Найдено {len(odds_lines)} линий Pinnacle")

    if not odds_lines:
        console.print("[yellow]Котировки Pinnacle недоступны. Пропуск цикла.[/yellow]")
        return

    # 3. Сопоставление котировок с рынками
    matched = match_odds_to_markets(odds_lines, markets)
    console.print(f"  Сопоставлено {len(matched)} пар (котировки, рынок)")

    if not matched:
        console.print("[yellow]Совпадений между Pinnacle и Polymarket не найдено.[/yellow]")
        return

    # 4. Генерация сигналов (adaptive Kelly при drawdown > 20% — BACKTEST 2025)
    kelly_override = None
    if db is not None and initial_bankroll > 0:
        _, dd_pct = await db.get_peak_equity_and_drawdown(initial_bankroll)
        if dd_pct > 20.0:
            kelly_override = settings.kelly_multiplier * 0.5
            console.print(f"[dim]Drawdown {dd_pct:.1f}% — Kelly x0.5[/dim]")
    signals = generate_signals(
        matched, current_equity, settings, kelly_base_override=kelly_override
    )
    display_signals_table(signals, mode)

    if not signals:
        return

    # 5. Исполнение через риск-менеджер
    records = await executor.execute_signals(
        signals, current_equity, initial_bankroll=initial_bankroll
    )
    display_execution_results(records)


async def run_stats(db: Database, resolve: bool = True):
    """Отобразить статистику. При resolve=True — обновить pending snapshots и bets из Gamma API."""
    if resolve:
        try:
            await resolve_bets(db)
        except Exception as exc:
            console.print(f"[yellow]Не удалось обновить snapshots/bets: {exc}[/yellow]")

    await show_forward_test_stats(db)
    await show_stats_by_league(db)
    await show_signal_calibration(db)
    await show_betting_stats(db)


async def main():
    args = parse_args()
    setup_logging(args.log_level)

    if args.mode == "stats":
        db = Database()
        await db.connect()
        try:
            await run_stats(db)
        finally:
            await db.close()
        return

    settings = load_settings(args.mode)

    db = Database()
    await db.connect()

    collector = PolymarketCollector(settings)
    odds_client = OddsApiClient(settings)
    risk = RiskManager(settings, db)
    executor = Executor(settings, db, risk, collector, mode=args.mode)

    console.print(
        Panel(
            Text.assemble(
                ("Polymarket Аналитический Агент\n", "bold white"),
                (f"Режим: {args.mode}  |  ", ""),
                (f"Банкролл: ${args.bankroll:.2f}  |  ", ""),
                (f"Виды спорта: {', '.join(settings.sports)}\n", ""),
                (f"Келли: {settings.kelly_multiplier}x  |  ", "dim"),
                (f"Мин. edge: {settings.min_edge*100:.0f}%  |  ", "dim"),
                (f"Макс. ставка: ${settings.max_bet_usd:.0f}", "dim"),
            ),
            title="Конфигурация",
            style="bold cyan",
        )
    )

    try:
        if args.once:
            await run_scan_cycle(
                settings, collector, odds_client, executor, args.bankroll, args.mode, db=db
            )
        else:
            cycle = 0
            while True:
                cycle += 1
                console.rule(f"[bold]Цикл {cycle}[/bold]")
                try:
                    await run_scan_cycle(
                        settings, collector, odds_client, executor,
                        args.bankroll, args.mode, db=db,
                    )
                except Exception as exc:
                    console.print(f"[red]Ошибка цикла: {exc}[/red]")
                    logging.exception("Ошибка цикла сканирования")

                console.print(
                    f"[dim]Следующее сканирование через {settings.poll_interval} сек...[/dim]"
                )
                await asyncio.sleep(settings.poll_interval)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Завершение работы...[/bold yellow]")
    finally:
        await collector.close()
        await odds_client.close()
        await db.close()
        console.print("[green]Очистка завершена.[/green]")


if __name__ == "__main__":
    asyncio.run(main())
