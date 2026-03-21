#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отчёт бэктеста на данных 2025 года (симулированные данные).

Реальные исторические данные: The Odds API historical (платно) или ручной экспорт.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.historical import generate_demo_events, run_backtest


def main():
    # 2025: Jan 1 - полный год симуляции (~500 событий с edge)
    events = generate_demo_events(n=500, seed=2025, year=2025)
    r = run_backtest(events, bankroll=1000, min_edge=0.03)

    print("\n" + "=" * 55)
    print("  BACKTEST 2025 (simulated data)")
    print("=" * 55)
    print(f"  Events loaded:    {len(events)}")
    print(f"  Bets placed:      {r.total_bets}")
    print(f"  Win Rate:         {r.win_rate:.1f}%  ({r.wins}W / {r.losses}L)")
    print(f"  Total P&L:        ${r.total_pnl:+.2f}")
    print(f"  ROI:              {r.roi:.1f}%")
    print(f"  Sharpe Ratio:     {r.sharpe_ratio:.2f}")
    print(f"  Max Drawdown:     {r.max_drawdown_pct:.1f}%")
    print("\n  By league:")
    for k, v in r.by_league.items():
        wr = v["wins"] / v["bets"] * 100 if v["bets"] > 0 else 0
        print(f"    {k}: {v['bets']} bets, WR={wr:.1f}%, P&L=${v['pnl']:+.2f}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
