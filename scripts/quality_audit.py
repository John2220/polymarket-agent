#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт аудита качества Polymarket Analytics Agent.

Проверяет:
1. Единый расчёт P&L (calc_pnl)
2. Floating P&L использует правильную цену стороны (YES/NO)
3. Правило «1 ставка — 1 событие» (event_key)
4. draw_prob по лигам
5. Стресс-тесты формул (pytest)
6. Импорты и зависимости
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_check(name: str, ok: bool, msg: str = "") -> bool:
    status = "[OK]" if ok else "[FAIL]"
    print(f"  {status} {name}" + (f": {msg}" if msg else ""))
    return ok


def main() -> int:
    print("=== Polymarket Agent - Quality Audit ===\n")
    all_ok = True

    # 1. calc_pnl используется везде
    print("1. P&L source (calc_pnl)")
    try:
        from core.bet_results import calc_pnl
        r = calc_pnl(10, 0.5, True)
        all_ok &= run_check("calc_pnl ok", r == 10.0)
    except Exception as e:
        all_ok &= run_check("calc_pnl", False, str(e))

    # 2. check_and_update: get_current_prices и cur_side_price для NO
    print("\n2. Floating P&L - side price (YES/NO)")
    try:
        code = (ROOT / "check_and_update.py").read_text(encoding="utf-8")
        has_prices = "get_current_prices" in code and "yes_p, no_p" in code
        has_side = "cur_side_price" in code and "no_p if side" in code
        all_ok &= run_check("get_current_prices (yes, no)", has_prices)
        all_ok &= run_check("cur_side_price для NO", has_side)
    except Exception as e:
        all_ok &= run_check("Floating P&L", False, str(e))

    # 3. event_key группирует O/U
    print("\n3. Rule: 1 bet per event (event_key)")
    try:
        code = (ROOT / "analyze_and_place.py").read_text(encoding="utf-8")
        has_event_key = "def event_key" in code and "O/U" in code
        has_strip = "re.sub" in code and "o/u|over|under|total" in code.lower()
        all_ok &= run_check("event_key exists and strips O/U", has_event_key and has_strip)
    except Exception as e:
        all_ok &= run_check("event_key", False, str(e))

    # 4. DRAW_PROB_BY_LEAGUE
    print("\n4. Draw probability by league")
    try:
        from config import DRAW_PROB_BY_LEAGUE, get_draw_prob
        all_ok &= run_check("soccer_epl в DRAW_PROB", "soccer_epl" in DRAW_PROB_BY_LEAGUE)
        all_ok &= run_check("basketball_nba = 0", get_draw_prob("basketball_nba") == 0)
    except Exception as e:
        all_ok &= run_check("DRAW_PROB", False, str(e))

    # 5. Стресс-тесты
    print("\n5. Stress tests (pytest)")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=no", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        passed = result.returncode == 0
        if result.stdout:
            lines = [l for l in result.stdout.strip().split("\n") if "passed" in l or "failed" in l]
            if lines:
                print(f"    {lines[-1]}")
        all_ok &= run_check("All tests passed", passed)
    except subprocess.TimeoutExpired:
        all_ok &= run_check("pytest", False, "timeout")
    except Exception as e:
        all_ok &= run_check("pytest", False, str(e))

    # 6. Импорты основных модулей
    print("\n6. Key module imports")
    modules = ["config", "analysis.kelly", "analysis.signals", "storage.db", "core.bet_results"]
    for m in modules:
        try:
            __import__(m)
            all_ok &= run_check(m, True)
        except Exception as e:
            all_ok &= run_check(m, False, str(e)[:50])

    print("\n" + "=" * 50)
    print("RESULT:", "ALL CHECKS PASSED" if all_ok else "SOME ISSUES")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
