"""Анализ forward-test: статистика накопленных данных и оценка стратегии."""
from __future__ import annotations

import logging
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from core.bet_results import calc_pnl, snapshot_entry_price
from storage.db import Database

logger = logging.getLogger(__name__)
console = Console()


async def show_forward_test_stats(db: Database):
    """Отобразить подробную статистику forward-test."""
    stats = await db.get_snapshot_stats()
    total = stats.get("total", 0) or 0
    wins = stats.get("wins", 0) or 0
    losses = stats.get("losses", 0) or 0
    pending = stats.get("pending", 0) or 0
    resolved = wins + losses
    virtual_pnl = stats.get("virtual_pnl", 0.0) or 0.0
    virtual_wagered = stats.get("virtual_wagered", 0.0) or 0.0

    console.print("\n[bold cyan]Статистика Forward-Test[/bold cyan]")
    console.print(f"  Всего записей: {total}")
    console.print(f"  Завершено: {resolved}  |  Ожидают: {pending}")

    if resolved > 0:
        win_rate = wins / resolved * 100
        roi = virtual_pnl / virtual_wagered * 100 if virtual_wagered > 0 else 0
        console.print(f"  Процент побед: {win_rate:.1f}%  ({wins}В / {losses}П)")
        console.print(f"  Виртуальный P&L: ${virtual_pnl:.2f}")
        console.print(f"  Виртуальный оборот: ${virtual_wagered:.2f}")
        console.print(f"  ROI: {roi:.1f}%")
    else:
        console.print("  [dim]Нет завершённых записей. Продолжайте накапливать данные![/dim]")

    recent = await db.get_recent_snapshots(limit=15)
    if recent:
        table = Table(title="Последние записи Forward-Test")
        table.add_column("Дата", style="dim")
        table.add_column("Рынок", max_width=40)
        table.add_column("Сторона")
        table.add_column("Цена PM", justify="right")
        table.add_column("Истин. вер.", justify="right")
        table.add_column("Edge", justify="right")
        table.add_column("Ставка $", justify="right")
        table.add_column("Результат")

        for s in recent:
            result = "ожидание"
            if s.get("resolved"):
                won = s.get("outcome_won")
                pnl = s.get("virtual_pnl", 0)
                result = f"[green]ВЫИГРЫШ +${pnl:.2f}[/green]" if won else f"[red]ПРОИГРЫШ ${pnl:.2f}[/red]"
            side_ru = "ДА" if s.get("side") == "YES" else "НЕТ"

            table.add_row(
                str(s.get("created_at", ""))[:16],
                str(s.get("market_question", ""))[:40],
                side_ru,
                f"{s.get('pm_price', 0):.2f}",
                f"{s.get('pinnacle_true_prob', 0):.2f}",
                f"{s.get('edge', 0):.3f}",
                f"${s.get('recommended_bet_usd', 0):.2f}",
                result,
            )
        console.print(table)


async def show_betting_stats(db: Database):
    """Отобразить статистику реальных ставок."""
    stats = await db.get_overall_stats()
    total = stats.get("total", 0) or 0
    wins = stats.get("wins", 0) or 0
    losses = stats.get("losses", 0) or 0
    wagered = stats.get("wagered", 0.0) or 0.0
    pnl = stats.get("pnl", 0.0) or 0.0

    console.print("\n[bold cyan]Статистика ставок[/bold cyan]")
    console.print(f"  Всего ставок: {total}")

    resolved = wins + losses
    if resolved > 0:
        win_rate = wins / resolved * 100
        roi = pnl / wagered * 100 if wagered > 0 else 0
        console.print(f"  Завершено: {resolved}  ({wins}В / {losses}П)")
        console.print(f"  Процент побед: {win_rate:.1f}%")
        console.print(f"  Общий оборот: ${wagered:.2f}")
        console.print(f"  P&L: ${pnl:.2f}")
        console.print(f"  ROI: {roi:.1f}%")

    recent = await db.get_recent_bets(limit=15)
    if recent:
        table = Table(title="Последние ставки")
        table.add_column("Дата", style="dim")
        table.add_column("Рынок", max_width=40)
        table.add_column("Сторона")
        table.add_column("Цена", justify="right")
        table.add_column("Сумма $", justify="right")
        table.add_column("Edge", justify="right")
        table.add_column("Статус")
        table.add_column("P&L", justify="right")

        status_names = {
            "filled": "исполнен",
            "recommended": "рекоменд.",
            "cancelled": "отменён",
            "rejected": "отклонён",
            "resolved": "завершён",
            "pending": "ожидание",
        }

        for b in recent:
            pnl_str = ""
            if b.get("resolved") and b.get("pnl") is not None:
                p = b["pnl"]
                pnl_str = f"[green]+${p:.2f}[/green]" if p > 0 else f"[red]${p:.2f}[/red]"
            side_ru = "ДА" if b.get("side") == "YES" else "НЕТ"

            table.add_row(
                str(b.get("created_at", ""))[:16],
                str(b.get("market_question", ""))[:40],
                side_ru,
                f"{b.get('price', 0):.2f}",
                f"${b.get('size_usd', 0):.2f}",
                f"{b.get('edge', 0):.3f}",
                status_names.get(b.get("status", ""), b.get("status", "")),
                pnl_str,
            )
        console.print(table)


async def show_signal_calibration(db: Database):
    """Сравнение predicted vs actual: ожидаемый WR (из edge) vs реальный WR."""
    snaps = await db.get_resolved_snapshots_for_calibration()
    if len(snaps) < 5:
        console.print("\n[dim]Калибровка: нужно минимум 5 завершённых snapshots. Сейчас: %d[/dim]" % len(snaps))
        return

    # Общая калибровка
    total = len(snaps)
    wins = sum(1 for s in snaps if s.get("outcome_won"))
    actual_wr = wins / total * 100
    pred_prob_avg = sum(s.get("pinnacle_true_prob", 0) or 0 for s in snaps) / total
    pred_wr = pred_prob_avg * 100

    # Slippage (order-book sim)
    slippage_vals = [s.get("slippage_bps") for s in snaps if s.get("slippage_bps") is not None]
    avg_slippage = sum(slippage_vals) / len(slippage_vals) if slippage_vals else None

    console.print("\n[bold cyan]Калибровка сигналов (predicted vs actual)[/bold cyan]")
    console.print(f"  Завершённых записей: {total}")
    console.print(f"  Ожидаемый WR (avg true_prob): {pred_wr:.1f}%")
    console.print(f"  Реальный WR: {actual_wr:.1f}%  ({wins}В / {total - wins}П)")
    if avg_slippage is not None:
        console.print(f"  Средний slippage (order-book sim): {avg_slippage:.1f} bps  (n={len(slippage_vals)})")
    diff = actual_wr - pred_wr
    if abs(diff) < 5:
        console.print(f"  [green]Разница: {diff:+.1f}% — стратегия калибрована[/green]")
    elif diff > 0:
        console.print(f"  [green]Разница: {diff:+.1f}% — реальность лучше ожиданий[/green]")
    else:
        console.print(f"  [yellow]Разница: {diff:+.1f}% — пересмотреть edge / фильтры[/yellow]")

    # По диапазонам edge
    ranges = [(0.03, 0.05, "3-5%"), (0.05, 0.08, "5-8%"), (0.08, 1.0, ">8%")]
    rows_added = []
    for lo, hi, lbl in ranges:
        subset = [s for s in snaps if lo <= (s.get("edge") or 0) < hi]
        if not subset:
            continue
        n = len(subset)
        w = sum(1 for s in subset if s.get("outcome_won"))
        pred_p = sum(s.get("pinnacle_true_prob") or 0 for s in subset) / n * 100
        act_wr = w / n * 100
        delta = act_wr - pred_p
        rows_added.append((lbl, str(n), f"{pred_p:.1f}%", f"{act_wr:.1f}%", f"{delta:+.1f}%"))
    if rows_added:
        table = Table(title="WR по диапазону edge")
        table.add_column("Edge", justify="center")
        table.add_column("N", justify="right")
        table.add_column("Ожид.WR", justify="right")
        table.add_column("Реальн.WR", justify="right")
        table.add_column("Δ", justify="right")
        for r in rows_added:
            table.add_row(*r)
        console.print(table)


async def show_stats_by_league(db: Database):
    """WR и ROI по лигам (sport_key)."""
    rows = await db.get_snapshot_stats_by_league()
    if not rows:
        console.print("\n[dim]WR/ROI по лигам: нет данных (sport_key)[/dim]")
        return
    table = Table(title="WR и ROI по лигам")
    table.add_column("Лига (sport_key)", style="dim")
    table.add_column("N", justify="right")
    table.add_column("WR %", justify="right")
    table.add_column("ROI %", justify="right")
    table.add_column("P&L $", justify="right")
    for r in rows:
        total = r.get("total", 0) or 0
        wins = r.get("wins", 0) or 0
        losses = r.get("losses", 0) or 0
        wagered = r.get("wagered", 0.0) or 0.0
        pnl = r.get("pnl", 0.0) or 0.0
        resolved = wins + losses
        wr = wins / resolved * 100 if resolved > 0 else 0.0
        roi = pnl / wagered * 100 if wagered > 0 else 0.0
        league = (r.get("sport_key") or "")[:35]
        table.add_row(
            league,
            str(total),
            f"{wr:.1f}%",
            f"{roi:.1f}%",
            f"${pnl:.2f}",
        )
    console.print(table)


async def resolve_pending_snapshots(
    db: Database,
    collector,
    limit_per_batch: int = 100,
) -> int:
    """
    Resolve pending snapshots: fetch closed markets from Gamma, match to snapshots,
    compute virtual P&L, update db. Returns number of newly resolved snapshots.
    """
    unresolved = await db.get_unresolved_snapshots()
    if not unresolved:
        return 0

    resolved_markets: List[dict] = []
    offset = 0
    while True:
        batch = await collector.fetch_resolved_markets(limit=limit_per_batch, offset=offset)
        if not batch:
            break
        for m in batch:
            resolved_markets.append({
                "condition_id": m.condition_id,
                "question": (m.question or "").strip().lower(),
                "outcome": (m.outcome or "").strip(),
            })
        if len(batch) < limit_per_batch:
            break
        offset += limit_per_batch

    if not resolved_markets:
        return 0

    resolved_ids = {m["condition_id"] for m in resolved_markets}
    by_question = {m["question"][:80]: m for m in resolved_markets if m["question"]}

    count = 0
    for snap in unresolved:
        sid = snap.get("id")
        cid = snap.get("market_condition_id", "")
        q = (snap.get("market_question") or "").strip().lower()[:80]
        side = snap.get("side", "YES")
        bet_usd = float(snap.get("recommended_bet_usd") or 0)

        match: Optional[dict] = None
        if cid and cid in resolved_ids:
            match = next((m for m in resolved_markets if m["condition_id"] == cid), None)
        if not match and q and q in by_question:
            match = by_question.get(q)

        if not match:
            continue

        outcome = match.get("outcome", "").upper()
        won = (
            (outcome == "YES" and side == "YES")
            or (outcome == "NO" and side == "NO")
        )
        entry = snapshot_entry_price(snap)
        virtual_pnl = calc_pnl(bet_usd, entry, won) if entry > 0 else (-bet_usd if not won else 0)

        await db.resolve_snapshot(sid, won, virtual_pnl)
        count += 1
        logger.info("Resolved snapshot %d: %s %s -> %s P&L=%.2f", sid, q[:40], side, "WIN" if won else "LOSS", virtual_pnl)

    return count
