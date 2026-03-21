#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск исторического бэктеста.

  python scripts/run_historical_backtest.py
  python scripts/run_historical_backtest.py --file data/historical_events.json
  python scripts/run_historical_backtest.py --demo --events 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Historical backtest")
    parser.add_argument("--file", type=Path, help="JSON file with historical events")
    parser.add_argument("--demo", action="store_true", help="Use synthetic demo data")
    parser.add_argument("--events", type=int, default=150, help="Number of events for demo (default: 150)")
    parser.add_argument("--output", type=Path, default=ROOT / "backtest_equity.png", help="Output plot path")
    args = parser.parse_args()

    from backtest.historical import (
        run_backtest,
        run_demo,
        load_historical_events,
        generate_demo_events,
        plot_equity_curve,
    )

    if args.demo:
        result = run_demo(n_events=args.events, output_dir=ROOT)
    elif args.file and args.file.exists():
        events = load_historical_events(args.file)
        print(f"Loaded {len(events)} events from {args.file}")
        result = run_backtest(events)
        print(f"\n  Total bets: {result.total_bets}")
        print(f"  Win rate:   {result.win_rate:.1f}%")
        print(f"  P&L:        ${result.total_pnl:.2f}")
        print(f"  ROI:        {result.roi:.1f}%")
        print(f"  Sharpe:     {result.sharpe_ratio:.2f}")
        print(f"  Max DD:     {result.max_drawdown_pct:.1f}%")
        plot_equity_curve(result, args.output)
    else:
        print("Use --demo or --file <path> to run backtest")
        sys.exit(1)


if __name__ == "__main__":
    main()
