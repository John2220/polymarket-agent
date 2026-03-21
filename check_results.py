"""
Проверка результатов ставок и обновление БД.

Запуск:
    python check_results.py              — проверить все незавершённые ставки и снимки
    python check_results.py --schedule   — запуск по расписанию (проверка каждый час)

Обновляет: snapshots (forward-test) и bets (реальные ставки) из Gamma API.
"""
from __future__ import annotations

import argparse
import sys
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Settings
from core.bet_results import calc_pnl, snapshot_entry_price
from data.collector import PolymarketCollector
from storage.db import Database
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


async def _fetch_resolved_markets_bulk(collector: PolymarketCollector, total_limit: int = 2000) -> list:
    """Загрузить закрытые рынки с определённым исходом (пагинация)."""
    all_markets = []
    offset = 0
    batch = 200
    while len(all_markets) < total_limit:
        batch_markets = await collector.fetch_resolved_markets(limit=batch, offset=offset)
        if not batch_markets:
            break
        all_markets.extend(batch_markets)
        if len(batch_markets) < batch:
            break
        offset += batch
    return all_markets[:total_limit]


async def resolve_bets(db: Database):
    """Обновить результаты snapshots и bets из Gamma API (закрытые рынки)."""
    settings = Settings()
    collector = PolymarketCollector(settings)

    try:
        console.print("[dim]Загрузка закрытых рынков с Polymarket...[/dim]")
        resolved_markets = await _fetch_resolved_markets_bulk(collector)
        if not resolved_markets:
            console.print("[yellow]Закрытых рынков с определённым исходом не найдено.[/yellow]")
            return

        resolved_by_cid = {m.condition_id: m for m in resolved_markets}
        resolved_by_question = {(m.question or "").strip().lower()[:80]: m for m in resolved_markets if m.question}

        snap_count = 0
        bet_count = 0

        # 1. Snapshots (forward-test)
        unresolved_snaps = await db.get_unresolved_snapshots()
        for snap in unresolved_snaps:
            cid = snap.get("market_condition_id", "")
            q = (snap.get("market_question") or "").strip().lower()[:80]
            market = resolved_by_cid.get(cid) or (resolved_by_question.get(q) if q else None)
            if not market or not market.outcome:
                continue

            side = snap.get("side", "YES")
            won = (market.outcome.upper() == "YES" and side == "YES") or (
                market.outcome.upper() == "NO" and side == "NO"
            )
            entry = snapshot_entry_price(snap)
            bet_usd = float(snap.get("recommended_bet_usd") or 0)
            virtual_pnl = calc_pnl(bet_usd, entry, won) if entry > 0 else (-bet_usd if not won else 0)

            await db.resolve_snapshot(snap.get("id"), won=won, virtual_pnl=round(virtual_pnl, 2))
            snap_count += 1
            res_str = f"[green]+${virtual_pnl:.2f}[/green]" if won else f"[red]-${bet_usd:.2f}[/red]"
            console.print(f"  [snapshot] {q[:50]} — {res_str}")

        # 2. Bets (реальные ставки)
        unresolved_bets = await db.get_unresolved_bets()
        for bet in unresolved_bets:
            cid = bet.get("market_condition_id", "")
            q = (bet.get("market_question") or "").strip().lower()[:80]
            market = resolved_by_cid.get(cid) or (resolved_by_question.get(q) if q else None)
            if not market or not market.outcome:
                continue

            side = bet.get("side", "YES")
            won = (market.outcome.upper() == "YES" and side == "YES") or (
                market.outcome.upper() == "NO" and side == "NO"
            )
            price = float(bet.get("price") or 0)
            size_usd = float(bet.get("size_usd") or 0)
            pnl = calc_pnl(size_usd, price, won) if price > 0 else (-size_usd if not won else 0)

            await db.resolve_bet(bet.get("id"), pnl=round(pnl, 2))
            bet_count += 1
            res_str = f"[green]+${pnl:.2f}[/green]" if won else f"[red]${pnl:.2f}[/red]"
            console.print(f"  [bet] {q[:50]} — {res_str}")

        total = snap_count + bet_count
        if total > 0:
            console.print(f"\n[green]Обновлено: {snap_count} snapshots, {bet_count} bets[/green]")
        else:
            console.print("[dim]Нет совпадений с закрытыми рынками.[/dim]")

    finally:
        await collector.close()

    # 3. Показать обновлённую статистику
    snap_stats = await db.get_snapshot_stats()
    bet_stats = await db.get_overall_stats()
    st = snap_stats
    bt = bet_stats

    console.print(f"\n[bold cyan]Forward-Test (snapshots):[/bold cyan]")
    console.print(f"  Записей: {st.get('total', 0)}  |  Завершено: {(st.get('wins', 0) or 0) + (st.get('losses', 0) or 0)}  |  Ожидают: {st.get('pending', 0)}")
    if (st.get("wins", 0) or 0) + (st.get("losses", 0) or 0) > 0:
        w, l = st.get("wins", 0) or 0, st.get("losses", 0) or 0
        console.print(f"  WR: {w/(w+l)*100:.1f}%  |  P&L: ${st.get('virtual_pnl', 0) or 0:.2f}")

    total_bets = bt.get("total", 0) or 0
    if total_bets > 0:
        console.print(f"\n[bold cyan]Реальные ставки:[/bold cyan]")
        console.print(f"  Всего: {total_bets}  |  P&L: ${bt.get('pnl', 0) or 0:.2f}")


async def record_bet_to_db():
    """Записать ставку $10 на Aston Villa в базу данных."""
    from data.models import BetRecord, Side, SnapshotRecord

    db = Database()
    await db.connect()

    # Проверяем, не записана ли уже
    recent = await db.get_recent_bets(limit=10)
    for b in recent:
        if "Aston Villa" in b.get("market_question", ""):
            console.print("[yellow]Ставка на Aston Villa уже записана в БД.[/yellow]")
            await db.close()
            return

    bet = BetRecord(
        market_condition_id="aston_villa_2026_02_27",
        market_question="Will Aston Villa FC win on 2026-02-27?",
        side=Side.YES,
        price=0.48,
        size_usd=10.00,
        edge=0.05,
        kelly_fraction=0.10,
        mode="recommend",
        status="recommended",
    )
    bet_id = await db.insert_bet(bet)

    snap = SnapshotRecord(
        market_condition_id="aston_villa_2026_02_27",
        market_question="Will Aston Villa FC win on 2026-02-27?",
        sport_key="soccer_epl",
        home_team="Aston Villa",
        away_team="Unknown",
        side=Side.YES,
        pm_price=0.48,
        pinnacle_true_prob=0.53,
        edge=0.05,
        kelly_fraction=0.10,
        recommended_bet_usd=10.00,
    )
    await db.insert_snapshot(snap)

    console.print(f"[green]Ставка записана в БД (id={bet_id}):[/green]")
    console.print(f"  Рынок: Will Aston Villa FC win on 2026-02-27?")
    console.print(f"  Сторона: ДА  |  Цена: 0.48  |  Сумма: $10.00")
    console.print(f"  Проверить результат: 2026-02-27 21:00 UTC (через 1 час после матча)")

    await db.close()


async def run_scheduled():
    """Запуск проверки по расписанию — каждый час."""
    console.print("[bold cyan]Запуск автопроверки по расписанию (каждые 60 мин)[/bold cyan]")
    console.print("Нажмите Ctrl+C для остановки.\n")

    while True:
        now = datetime.now(timezone.utc)
        console.rule(f"[bold]Проверка {now.strftime('%Y-%m-%d %H:%M')} UTC[/bold]")

        db = Database()
        await db.connect()
        try:
            await resolve_bets(db)
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")
        finally:
            await db.close()

        console.print(f"[dim]Следующая проверка через 60 мин...[/dim]\n")
        await asyncio.sleep(3600)


async def run_once():
    """Одноразовая проверка."""
    db = Database()
    await db.connect()
    try:
        await resolve_bets(db)
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description="Проверка результатов ставок")
    parser.add_argument("--schedule", action="store_true", help="Запуск по расписанию (каждый час)")
    parser.add_argument("--record-bet", action="store_true", help="Записать ставку $10 в БД")
    args = parser.parse_args()

    if args.record_bet:
        asyncio.run(record_bet_to_db())
    elif args.schedule:
        try:
            asyncio.run(run_scheduled())
        except KeyboardInterrupt:
            console.print("\n[yellow]Остановлено.[/yellow]")
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()
