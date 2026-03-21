"""Core tests for Kelly criterion, signals, and EV calculations."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.kelly import kelly_yes, kelly_no, compute_kelly
from core.bet_results import calc_pnl, snapshot_entry_price
from backtest.simulator import sim_fill_orderbook
from data.models import OrderBook, OrderBookLevel, OddsLine, OddsOutcome, Market
from datetime import datetime


def test_calc_pnl_yes_no():
    """P&L формула одинакова для YES и NO. См. FORMULAS_AUDIT.md"""
    assert calc_pnl(30, 0.27, True) == 81.11  # NO bet Auxerre
    assert calc_pnl(17.01, 0.265, True) == 47.18  # YES Tijuana
    assert calc_pnl(10, 0.5, False) == -10
    assert calc_pnl(30, 0.27, False) == -30


def test_kelly_yes_basic():
    # p_true=0.65, price=0.55 → edge=0.10, f* = 0.10/0.45 ≈ 0.2222
    f = kelly_yes(0.65, 0.55)
    assert abs(f - 0.2222) < 0.01, f"Expected ~0.222, got {f}"


def test_kelly_no_basic():
    # p_true=0.35, price_yes=0.45 → NO side: (0.45-0.35)/0.45 ≈ 0.2222
    f = kelly_no(0.35, 0.45)
    assert abs(f - 0.2222) < 0.01, f"Expected ~0.222, got {f}"


def test_kelly_no_edge():
    # p_true=0.50, price=0.50 → no edge
    assert kelly_yes(0.50, 0.50) == 0.0
    assert kelly_no(0.50, 0.50) == 0.0


def test_kelly_negative_ev():
    # p_true=0.40, price=0.60 → YES has negative EV
    assert kelly_yes(0.40, 0.60) == 0.0
    # NO side: (0.60-0.40)/0.60 ≈ 0.333 — positive
    f = kelly_no(0.40, 0.60)
    assert f > 0.3


def test_kelly_boundary():
    assert kelly_yes(0.5, 0.0) == 0.0
    assert kelly_yes(0.5, 1.0) == 0.0
    assert kelly_no(0.5, 0.0) == 0.0
    assert kelly_no(0.5, 1.0) == 0.0


def test_compute_kelly_picks_best_side():
    from config import Settings
    settings = Settings(
        odds_api_key="test",
        kelly_multiplier=0.25,
        max_bet_pct=0.05,
        max_bet_usd=50.0,
    )
    # p_true=0.70, price=0.55 → YES edge=0.15
    result = compute_kelly(0.70, 0.55, bankroll=1000, settings=settings)
    assert result.kelly_fraction > 0
    assert result.bet_size_usd > 0
    assert result.bet_size_usd <= 50.0


def test_compute_kelly_no_edge():
    from config import Settings
    settings = Settings(
        odds_api_key="test",
        kelly_multiplier=0.25,
        max_bet_pct=0.05,
        max_bet_usd=50.0,
    )
    result = compute_kelly(0.50, 0.50, bankroll=1000, settings=settings)
    assert result.kelly_fraction == 0.0
    assert result.bet_size_usd == 0.0


def test_ev_formula():
    # EV for YES: p_true - c
    p, c = 0.65, 0.55
    ev = p - c
    assert abs(ev - 0.10) < 0.001


def test_odds_devig():
    line = OddsLine(
        sport_key="basketball_nba",
        home_team="Lakers",
        away_team="Celtics",
        commence_time=datetime(2026, 3, 1),
        outcomes=[
            OddsOutcome(name="Lakers", price=1.80, implied_prob=1 / 1.80),
            OddsOutcome(name="Celtics", price=2.10, implied_prob=1 / 2.10),
        ],
    )
    line.devig()
    total_true = sum(o.true_prob for o in line.outcomes)
    assert abs(total_true - 1.0) < 0.001, f"Devig should sum to 1.0, got {total_true}"
    assert line.outcomes[0].true_prob > line.outcomes[1].true_prob


def test_market_model():
    m = Market(
        condition_id="0x123",
        question="Will Lakers win?",
        yes_price=0.55,
        no_price=0.45,
        liquidity=5000.0,
    )
    assert m.yes_price + m.no_price == 1.0


def test_snapshot_entry_price_prefers_sim_fill():
    assert snapshot_entry_price({"sim_fill_price": 0.52, "pm_price": 0.5}) == 0.52
    assert snapshot_entry_price({"sim_fill_price": None, "pm_price": 0.48}) == 0.48
    assert snapshot_entry_price({"pm_price": 0.4}) == 0.4


def test_sim_fill_orderbook_walks_asks():
    ob = OrderBook(
        token_id="t1",
        asks=[
            OrderBookLevel(price=0.50, size=100),
            OrderBookLevel(price=0.52, size=100),
        ],
        bids=[],
    )
    ref = 0.50
    shares = 150.0
    fill, bps = sim_fill_orderbook(ob, "YES", shares, ref)
    # 100 @ 0.50 + 50 @ 0.52 → avg = (50 + 26) / 150 = 0.5067
    assert abs(fill - 0.5067) < 0.001
    assert bps > 0


if __name__ == "__main__":
    tests = [
        test_kelly_yes_basic,
        test_kelly_no_basic,
        test_kelly_no_edge,
        test_kelly_negative_ev,
        test_kelly_boundary,
        test_compute_kelly_picks_best_side,
        test_compute_kelly_no_edge,
        test_ev_formula,
        test_odds_devig,
        test_market_model,
        test_snapshot_entry_price_prefers_sim_fill,
        test_sim_fill_orderbook_walks_asks,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {t.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__} — {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
