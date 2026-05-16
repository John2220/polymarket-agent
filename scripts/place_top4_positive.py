"""
Анализ + размещение до 4 реальных ордеров по приоритету положительного edge.

Логика:
1) Грузим рынки Gamma и линии Pinnacle.
2) Генерим сигналы (как в main.py).
3) Фильтруем по betting window и «матчевым» рынкам.
4) Топ-N по edge → исполнение через trading.Executor (RiskManager + slippage), как main.py --mode auto.

ВНИМАНИЕ: реальный счёт. Нужны VPN + корректные POLYMARKET_*.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from analysis.signals import generate_signals
from config import load_settings
from data.odds_api import OddsApiClient, _has_words_in_text, _normalize, _significant_team_words, match_odds_to_markets
from data.collector import PolymarketCollector
from storage.db import Database
from trading.executor import Executor, signal_in_betting_window
from trading.risk import RiskManager

REPORT = ROOT / "reports" / "real_top4_run_latest.txt"

EXCLUDE_Q = (
    "temperature",
    "precipitation",
    "°c",
    "°f",
    "inches of",
    "exact score",
    "spread:",
    "o/u",
    "total corner",
    "halftime",
    "election",
    " oscar",
    "parliament",
)


def _excluded_question(s) -> bool:
    q = (s.market.question or "").lower()
    return any(x in q for x in EXCLUDE_Q)


def _is_sports_match_signal(s) -> bool:
    line = s.odds_line
    if not line or _excluded_question(s):
        return False
    nq = _normalize(s.market.question or "")
    hw = _significant_team_words(line.home_team)
    aw = _significant_team_words(line.away_team)
    return _has_words_in_text(hw, nq) and _has_words_in_text(aw, nq)


def _format_record_line(i: int, record) -> str:
    q = (record.market_question or "")[:90]
    oid = (record.order_id or "")[:24]
    return (
        f"{i}. {record.side.value} edge={record.edge:.4f} size=${record.size_usd:.2f} | "
        f"{q} | status={record.status} orderID={oid} db_id={record.id or ''}"
    )


async def main() -> int:
    ap = argparse.ArgumentParser(description="Топ-4 сигнала с edge → CLOB через Executor")
    ap.add_argument("--bankroll", type=float, default=1000.0, help="Банкролл для RiskManager")
    ap.add_argument("--max-picks", type=int, default=4, help="Макс. число ордеров за запуск")
    args = ap.parse_args()

    settings = load_settings("auto")
    collector = PolymarketCollector(settings)
    odds = OddsApiClient(settings)
    db = Database()
    await db.connect()
    try:
        print("Анализ рынков...", flush=True)
        markets = await collector.fetch_all_active_markets(batch=100)
        lines = await odds.fetch_all_odds()
        if not lines:
            print("[ОШИБКА] Нет линий Pinnacle.")
            return 1
        matched = match_odds_to_markets(lines, markets)
        initial_bankroll = float(args.bankroll)
        current_equity = await db.get_current_equity(initial_bankroll)
        signals = generate_signals(matched, bankroll=current_equity, settings=settings)
        in_window = [s for s in signals if signal_in_betting_window(s, settings)]
        sports = [s for s in in_window if _is_sports_match_signal(s)]
        sports.sort(key=lambda x: x.edge, reverse=True)
        if sports:
            picks = sports[: args.max_picks]
            pick_source = "sports"
        else:
            fallback = [s for s in in_window if not _excluded_question(s)]
            fallback.sort(key=lambda x: x.edge, reverse=True)
            picks = fallback[: args.max_picks]
            pick_source = "in_window_edge"
        if not picks:
            print("[ОШИБКА] Нет подходящих сигналов в окне ставок.")
            return 1
        print(
            f"Сигналов: всего {len(signals)}, в окне {len(in_window)}, "
            f"к исполнению {len(picks)} ({pick_source}) | equity=${current_equity:.2f}",
            flush=True,
        )

        risk = RiskManager(settings, db)
        executor = Executor(settings, db, risk, collector, mode="auto")
        records = await executor.execute_signals(
            picks,
            current_equity,
            initial_bankroll=initial_bankroll,
        )

        rows: list[str] = []
        rows.append(f"run_utc={datetime.now(timezone.utc).isoformat()}")
        rows.append(
            f"selected={len(picks)} executed_records={len(records)} "
            f"source={pick_source} equity={current_equity:.2f}"
        )
        rows.append("path=trading.Executor mode=auto (RiskManager+slippage)")
        rows.append("")

        for i, rec in enumerate(records, start=1):
            line = _format_record_line(i, rec)
            print(line, flush=True)
            rows.append(line)

        if len(records) < len(picks):
            skipped = len(picks) - len(records)
            note = (
                f"# {skipped} сигнал(ов) пропущено: окно времени, RiskManager "
                f"(лимиты/банкролл/дневной стоп) или slippage — см. лог"
            )
            print(note, flush=True)
            rows.append(note)

        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(f"\nОтчёт: {REPORT}", flush=True)
        return 0
    finally:
        await db.close()
        await collector.close()
        await odds.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
