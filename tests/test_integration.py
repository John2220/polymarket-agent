"""Integration tests: full pipeline with mock data, DB operations, risk checks, matching."""
from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings
from data.models import (
    BetRecord, Event, Market, OddsLine, OddsOutcome, OrderBook,
    OrderBookLevel, Side, Signal, SnapshotRecord,
)
from data.odds_api import _normalize, _team_in_question, match_odds_to_markets
from analysis.kelly import kelly_yes, kelly_no, compute_kelly
from analysis.signals import generate_signals, _find_true_prob
from analysis.backtest import resolve_pending_snapshots
from storage.db import Database
from trading.risk import RiskManager
from trading.executor import Executor


def _settings(**overrides) -> Settings:
    defaults = dict(
        odds_api_key="test_key",
        kelly_multiplier=0.25,
        min_edge=0.05,
        min_liquidity=500,
        max_bet_pct=0.05,
        max_bet_usd=50.0,
        max_slippage=0.02,
        daily_loss_limit=100.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _market(question="Will Lakers win?", yes_price=0.55, liquidity=5000, **kw) -> Market:
    return Market(
        condition_id=kw.get("condition_id", "0xABC"),
        question=question,
        yes_token_id=kw.get("yes_token_id", "tok_yes_1"),
        no_token_id=kw.get("no_token_id", "tok_no_1"),
        yes_price=yes_price,
        no_price=round(1 - yes_price, 4),
        volume=kw.get("volume", 100000),
        liquidity=liquidity,
    )


def _odds_line(home="Lakers", away="Celtics", home_price=1.80, away_price=2.10) -> OddsLine:
    home_imp = 1 / home_price
    away_imp = 1 / away_price
    line = OddsLine(
        sport_key="basketball_nba",
        sport_title="NBA",
        home_team=home,
        away_team=away,
        commence_time=datetime(2026, 3, 15, 20, 0),
        outcomes=[
            OddsOutcome(name=home, price=home_price, implied_prob=home_imp),
            OddsOutcome(name=away, price=away_price, implied_prob=away_imp),
        ],
    )
    line.devig()
    return line


# ═══════════════════════════════════════════════════════
# 1. Matching logic tests
# ═══════════════════════════════════════════════════════

def test_normalize():
    assert _normalize("Los Angeles Lakers") == "los angeles lakers"
    assert _normalize("  FC  Barcelona!! ") == "fc barcelona"
    assert _normalize("O'Brien's Team") == "obriens team"


def test_team_in_question_exact():
    assert _team_in_question("Lakers", "Will the Lakers win the NBA Championship?")
    assert _team_in_question("Celtics", "Will the Celtics win tonight?")
    assert not _team_in_question("Warriors", "Will the Lakers win?")


def test_team_in_question_partial():
    assert _team_in_question("Los Angeles Lakers", "Will the Lakers beat Boston?")
    assert _team_in_question("Boston Celtics", "Will Celtics win the series?")


def test_match_odds_to_markets_both_teams():
    line = _odds_line()
    mkt = _market(question="Will the Lakers beat the Celtics?")
    matches = match_odds_to_markets([line], [mkt])
    assert len(matches) == 1
    assert matches[0][2] == "Lakers"  # matched team


def test_match_odds_to_markets_one_team():
    line = _odds_line()
    mkt = _market(question="Will the Lakers win tonight?")
    matches = match_odds_to_markets([line], [mkt])
    assert len(matches) == 1
    assert matches[0][2] == "Lakers"


def test_match_odds_to_markets_no_match():
    line = _odds_line(home="Warriors", away="Nets")
    mkt = _market(question="Will the Lakers win?")
    matches = match_odds_to_markets([line], [mkt])
    assert len(matches) == 0


# ═══════════════════════════════════════════════════════
# 2. Signal generation tests
# ═══════════════════════════════════════════════════════

def test_find_true_prob():
    line = _odds_line()
    prob = _find_true_prob(line, "Lakers")
    assert prob is not None
    assert 0.5 < prob < 0.7  # Lakers are favored at 1.80
    prob_away = _find_true_prob(line, "Celtics")
    assert prob_away is not None
    assert abs(prob + prob_away - 1.0) < 0.001


def test_find_true_prob_not_found():
    line = _odds_line()
    prob = _find_true_prob(line, "Warriors")
    assert prob is None


def test_generate_signals_with_edge():
    settings = _settings(min_edge=0.05, min_liquidity=500)
    line = _odds_line(home_price=1.60, away_price=2.50)
    line.devig()
    # Lakers true_prob ~ 0.610
    mkt = _market(question="Will Lakers win?", yes_price=0.50, liquidity=5000)
    matched = [(line, mkt, "Lakers")]
    signals = generate_signals(matched, bankroll=1000, settings=settings)
    assert len(signals) == 1
    s = signals[0]
    assert s.side == Side.YES
    assert s.edge > 0.05
    assert s.bet_size_usd > 0


def test_generate_signals_no_edge():
    settings = _settings(min_edge=0.05)
    line = _odds_line(home_price=2.00, away_price=2.00)
    line.devig()
    # both teams ~0.50, market at 0.50 → no edge
    mkt = _market(question="Will Lakers win?", yes_price=0.50, liquidity=5000)
    matched = [(line, mkt, "Lakers")]
    signals = generate_signals(matched, bankroll=1000, settings=settings)
    assert len(signals) == 0


def test_generate_signals_no_side():
    settings = _settings(min_edge=0.05)
    line = _odds_line(home_price=1.60, away_price=2.50)
    line.devig()
    mkt = _market(question="Will Lakers win?", yes_price=0.50, liquidity=100)  # below min_liquidity
    matched = [(line, mkt, "Lakers")]
    signals = generate_signals(matched, bankroll=1000, settings=settings)
    assert len(signals) == 0  # filtered by liquidity


def test_generate_signals_picks_no_side():
    settings = _settings(min_edge=0.05)
    # Away team heavily favored: Celtics ~0.625 true prob
    line = _odds_line(home_price=2.50, away_price=1.60)
    line.devig()
    # Market YES (for Lakers) at 0.50 → Lakers overpriced, buy NO
    mkt = _market(question="Will Lakers win?", yes_price=0.50, liquidity=5000)
    matched = [(line, mkt, "Lakers")]
    signals = generate_signals(matched, bankroll=1000, settings=settings)
    assert len(signals) == 1
    assert signals[0].side == Side.NO


def test_generate_signals_no_filter_when_yes_high():
    """NO-ставка фильтруется если YES >= 0.65 (ставка против рынка)."""
    settings = _settings(min_edge=0.03, min_liquidity=500)
    settings.no_bet_max_yes = 0.65
    # true_prob home=0.60, yes_price=0.75 → NO edge = 0.15, но yes>=0.65 → skip
    line = _odds_line(home_price=1.67, away_price=2.50)  # ~0.6/0.4 devig
    line.devig()
    mkt = _market(question="Will Home win?", yes_price=0.75, liquidity=5000)
    matched = [(line, mkt, "Home")]
    signals = generate_signals(matched, bankroll=1000, settings=settings)
    assert len(signals) == 0  # filtered by no_bet_max_yes


# ═══════════════════════════════════════════════════════
# 3. Kelly edge-case tests
# ═══════════════════════════════════════════════════════

def test_kelly_extreme_edge():
    f = kelly_yes(0.99, 0.01)
    assert f > 0.98  # near certain bet


def test_kelly_tiny_edge():
    f = kelly_yes(0.51, 0.50)
    assert 0 < f < 0.03  # very small edge → very small Kelly


def test_compute_kelly_respects_max_bet():
    settings = _settings(kelly_multiplier=1.0, max_bet_pct=1.0, max_bet_usd=25.0)
    result = compute_kelly(0.90, 0.50, bankroll=10000, settings=settings)
    assert result.bet_size_usd == 25.0  # capped by max_bet_usd


def test_compute_kelly_respects_pct_cap():
    settings = _settings(kelly_multiplier=1.0, max_bet_pct=0.01, max_bet_usd=1000)
    result = compute_kelly(0.90, 0.50, bankroll=1000, settings=settings)
    assert result.bet_size_usd <= 10.0  # 1% of 1000


# ═══════════════════════════════════════════════════════
# 4. OrderBook model tests
# ═══════════════════════════════════════════════════════

def test_orderbook_properties():
    ob = OrderBook(
        token_id="tok1",
        bids=[OrderBookLevel(price=0.54, size=100), OrderBookLevel(price=0.53, size=200)],
        asks=[OrderBookLevel(price=0.56, size=150)],
    )
    assert ob.best_bid == 0.54
    assert ob.best_ask == 0.56
    assert abs(ob.spread - 0.02) < 0.001


def test_orderbook_empty():
    ob = OrderBook(token_id="tok1")
    assert ob.best_bid is None
    assert ob.best_ask is None
    assert ob.spread is None


# ═══════════════════════════════════════════════════════
# 5. Database tests (async)
# ═══════════════════════════════════════════════════════

async def _test_db_insert_and_query():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))

    await db.connect()

    bet = BetRecord(
        market_condition_id="0xABC",
        market_question="Will Lakers win?",
        side=Side.YES,
        price=0.55,
        size_usd=25.0,
        edge=0.10,
        kelly_fraction=0.22,
        mode="recommend",
        status="recommended",
    )
    bet_id = await db.insert_bet(bet)
    assert bet_id > 0

    bets = await db.get_todays_bets()
    assert len(bets) == 1
    assert bets[0]["market_question"] == "Will Lakers win?"
    assert bets[0]["size_usd"] == 25.0

    wagered = await db.get_todays_wagered()
    assert wagered == 25.0

    pnl = await db.get_todays_pnl()
    assert pnl == 0.0  # no resolved bets

    await db.resolve_bet(bet_id, pnl=12.50)
    pnl = await db.get_todays_pnl()
    assert pnl == 12.50

    stats = await db.get_overall_stats()
    assert stats["total"] == 1
    assert stats["wins"] == 1

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


async def _test_db_snapshots():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))

    await db.connect()

    snap = SnapshotRecord(
        market_condition_id="0xDEF",
        market_question="Will Celtics win?",
        sport_key="basketball_nba",
        home_team="Lakers",
        away_team="Celtics",
        side=Side.NO,
        pm_price=0.45,
        pinnacle_true_prob=0.52,
        edge=0.07,
        kelly_fraction=0.15,
        recommended_bet_usd=15.0,
    )
    snap_id = await db.insert_snapshot(snap)
    assert snap_id > 0

    unresolved = await db.get_unresolved_snapshots()
    assert len(unresolved) == 1

    await db.resolve_snapshot(snap_id, won=True, virtual_pnl=18.33)

    unresolved = await db.get_unresolved_snapshots()
    assert len(unresolved) == 0

    stats = await db.get_snapshot_stats()
    assert stats["wins"] == 1
    assert stats["virtual_pnl"] == 18.33

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


async def _test_db_empty_stats():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()

    stats = await db.get_overall_stats()
    assert stats["total"] == 0

    snap_stats = await db.get_snapshot_stats()
    assert snap_stats["total"] == 0

    recent = await db.get_recent_bets()
    assert len(recent) == 0

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


def test_db_insert_and_query():
    asyncio.run(_test_db_insert_and_query())


def test_db_snapshots():
    asyncio.run(_test_db_snapshots())


def test_db_empty_stats():
    asyncio.run(_test_db_empty_stats())


# ═══════════════════════════════════════════════════════
# 6. Risk manager tests (async)
# ═══════════════════════════════════════════════════════

async def _test_risk_approves_valid():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()
    settings = _settings()
    risk = RiskManager(settings, db)

    signal = Signal(
        market=_market(),
        side=Side.YES,
        market_price=0.55,
        true_prob=0.65,
        edge=0.10,
        kelly_fraction=0.22,
        bet_size_usd=25.0,
    )
    verdict = await risk.check(signal, bankroll=1000)
    assert verdict.approved
    assert verdict.adjusted_size > 0
    assert verdict.adjusted_size <= 50.0

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


async def _test_risk_rejects_low_bankroll():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()
    settings = _settings(max_bet_usd=50.0)
    risk = RiskManager(settings, db)

    signal = Signal(
        market=_market(),
        side=Side.YES,
        market_price=0.55,
        true_prob=0.65,
        edge=0.10,
        bet_size_usd=25.0,
    )
    verdict = await risk.check(signal, bankroll=50)  # < max_bet_usd * 2
    assert not verdict.approved
    assert "Bankroll too low" in verdict.reason

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


async def _test_risk_rejects_tiny_bet():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()
    settings = _settings(max_bet_usd=50.0, max_bet_pct=0.001)
    risk = RiskManager(settings, db)

    signal = Signal(
        market=_market(),
        side=Side.YES,
        market_price=0.55,
        true_prob=0.65,
        edge=0.10,
        bet_size_usd=0.50,  # will be capped below $1
    )
    verdict = await risk.check(signal, bankroll=200)
    assert not verdict.approved

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


async def _test_slippage_check():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()
    settings = _settings(max_slippage=0.02)
    risk = RiskManager(settings, db)

    assert await risk.check_slippage(0.55, 0.56)  # 1.8% < 2%
    assert not await risk.check_slippage(0.55, 0.58)  # 5.4% > 2%
    assert await risk.check_slippage(0.55, 0.55)  # 0% < 2%
    assert not await risk.check_slippage(0.0, 0.55)  # invalid price

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


def test_risk_approves_valid():
    asyncio.run(_test_risk_approves_valid())


def test_risk_rejects_low_bankroll():
    asyncio.run(_test_risk_rejects_low_bankroll())


def test_risk_rejects_tiny_bet():
    asyncio.run(_test_risk_rejects_tiny_bet())


def test_slippage_check():
    asyncio.run(_test_slippage_check())


# ═══════════════════════════════════════════════════════
# 6b. Executor recommend mode (risk-executor task)
# ═══════════════════════════════════════════════════════

async def _test_executor_recommend_mode():
    """Executor in recommend mode: records snapshots, risk check, BetRecords with status recommended."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()

    settings = _settings()
    risk = RiskManager(settings, db)

    class MockCollector:
        async def fetch_price(self, token_id):
            return 0.55
        async def close(self):
            pass

    executor = Executor(settings, db, risk, MockCollector(), mode="recommend")

    market = _market(question="Lakers vs Celtics", yes_price=0.50, liquidity=5000)
    # 4 hours from now — within betting window (2–24h)
    market.end_date = datetime.now(timezone.utc) + timedelta(hours=4)
    signal = Signal(
        market=market,
        side=Side.YES,
        market_price=0.50,
        true_prob=0.60,
        edge=0.10,
        kelly_fraction=0.20,
        bet_size_usd=20.0,
    )

    records = await executor.execute_signals([signal], bankroll=1000)
    assert len(records) >= 1
    assert records[0].status == "recommended"
    assert records[0].size_usd > 0

    snap_count = (await db.get_recent_snapshots(limit=5))
    assert len(snap_count) >= 1

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


def test_executor_recommend_mode():
    asyncio.run(_test_executor_recommend_mode())


async def _test_resolve_snapshots():
    """resolve_pending_snapshots: matches resolved markets to snapshots."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()

    # Insert unresolved snapshot
    from data.models import SnapshotRecord
    snap = SnapshotRecord(
        market_condition_id="0xRESOLVED",
        market_question="Lakers vs Celtics",
        side=Side.YES,
        pm_price=0.55,
        pinnacle_true_prob=0.60,
        edge=0.05,
        kelly_fraction=0.10,
        recommended_bet_usd=10.0,
        resolved=False,
    )
    await db.insert_snapshot(snap)

    class MockCollector:
        async def fetch_resolved_markets(self, limit=100, offset=0):
            from data.models import Market
            m = Market(
                condition_id="0xRESOLVED",
                question="Lakers vs Celtics",
                resolved=True,
                outcome="Yes",
            )
            return [m] if offset == 0 else []

    n = await resolve_pending_snapshots(db, MockCollector())
    assert n == 1

    snaps = await db.get_resolved_snapshots_for_calibration()
    assert len(snaps) == 1
    assert snaps[0]["outcome_won"] == 1
    assert snaps[0]["virtual_pnl"] > 0

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


def test_resolve_snapshots():
    asyncio.run(_test_resolve_snapshots())


# ═══════════════════════════════════════════════════════
# 6c. Historical backtest (fix-historical-backtest-module)
# ═══════════════════════════════════════════════════════

def test_historical_backtest_demo():
    """Исторический бэктест на синтетических данных."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backtest.historical import generate_demo_events, run_backtest

    events = generate_demo_events(n=50, seed=123)
    assert len(events) == 50
    assert events[0].sport_key in ("basketball_nba", "soccer_epl", "soccer_uefa_champs_league")

    result = run_backtest(events, bankroll=1000, min_edge=0.03)
    assert result.total_bets >= 1
    assert len(result.equity_curve) == result.total_bets + 1
    assert result.sharpe_ratio >= -10  # sanity
    assert result.max_drawdown_pct >= 0


async def _test_db_equity_drawdown():
    """get_current_equity и get_peak_equity_and_drawdown."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db = Database(path=Path(tmp.name))
    await db.connect()

    from data.models import BetRecord
    now = datetime.now(timezone.utc)
    await db.insert_bet(BetRecord(
        market_condition_id="0x1", market_question="Q1", side=Side.YES,
        price=0.5, size_usd=20, edge=0.05, kelly_fraction=0.1, mode="recommend",
        status="resolved", pnl=10.0, resolved=True, created_at=now, resolved_at=now,
    ))

    eq = await db.get_current_equity(1000)
    assert eq == 1010.0

    peak, dd = await db.get_peak_equity_and_drawdown(1000)
    assert peak == 1010.0
    assert dd == 0.0

    await db.insert_bet(BetRecord(
        market_condition_id="0x2", market_question="Q2", side=Side.YES,
        price=0.5, size_usd=20, edge=0.05, kelly_fraction=0.1, mode="recommend",
        status="resolved", pnl=-30.0, resolved=True, created_at=now, resolved_at=now,
    ))

    eq2 = await db.get_current_equity(1000)
    assert eq2 == 980.0
    peak2, dd2 = await db.get_peak_equity_and_drawdown(1000)
    assert peak2 == 1010.0
    assert abs(dd2 - 2.97) < 0.1

    await db.close()
    Path(tmp.name).unlink(missing_ok=True)


def test_db_equity_drawdown():
    asyncio.run(_test_db_equity_drawdown())


def test_historical_load_json(tmp_path):
    """Загрузка событий из JSON."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backtest.historical import load_historical_events

    j = {
        "events": [
            {
                "sport_key": "basketball_nba",
                "home_team": "A",
                "away_team": "B",
                "commence_time": "2024-01-15T19:00:00Z",
                "pinnacle_yes_prob": 0.55,
                "pm_yes_price": 0.50,
                "matched_team": "A",
                "outcome": "Yes",
            }
        ]
    }
    p = tmp_path / "events.json"
    p.write_text(__import__("json").dumps(j), encoding="utf-8")
    evs = load_historical_events(p)
    assert len(evs) == 1
    assert evs[0].sport_key == "basketball_nba"
    assert evs[0].outcome == "Yes"


# ═══════════════════════════════════════════════════════
# 7. Full pipeline test (mock, no real API)
# ═══════════════════════════════════════════════════════

def test_full_pipeline_mock():
    """Simulate: odds line + market → match → signals → kelly → risk check."""
    settings = _settings(min_edge=0.05, min_liquidity=500)

    line = _odds_line(home_price=1.60, away_price=2.50)
    mkt = _market(question="Will the Lakers beat the Celtics tonight?", yes_price=0.50, liquidity=8000)

    # Step 1: match
    matches = match_odds_to_markets([line], [mkt])
    assert len(matches) >= 1, "Matching failed"

    # Step 2: generate signals
    signals = generate_signals(matches, bankroll=1000, settings=settings)
    assert len(signals) >= 1, f"No signals generated; matches={len(matches)}"

    sig = signals[0]
    assert sig.edge >= 0.05
    assert sig.bet_size_usd > 0
    assert sig.kelly_fraction > 0

    print(f"  Signal: {sig.side.value} @ {sig.market_price:.3f}, "
          f"true_prob={sig.true_prob:.3f}, edge={sig.edge:.3f}, "
          f"kelly={sig.kelly_fraction:.3f}, bet=${sig.bet_size_usd:.2f}")


def test_full_pipeline_no_match():
    """No overlap between odds and markets → no signals."""
    settings = _settings()
    line = _odds_line(home="Warriors", away="Nets")
    mkt = _market(question="Will Bitcoin reach 100k?", yes_price=0.30, liquidity=50000)

    matches = match_odds_to_markets([line], [mkt])
    assert len(matches) == 0

    signals = generate_signals(matches, bankroll=1000, settings=settings)
    assert len(signals) == 0


# ═══════════════════════════════════════════════════════
# 8. Devig math verification
# ═══════════════════════════════════════════════════════

def test_devig_three_way():
    """Three-way market (e.g. soccer h2h with draw)."""
    line = OddsLine(
        sport_key="soccer_epl",
        home_team="Arsenal",
        away_team="Chelsea",
        commence_time=datetime(2026, 3, 20),
        outcomes=[
            OddsOutcome(name="Arsenal", price=2.20, implied_prob=1/2.20),
            OddsOutcome(name="Draw", price=3.30, implied_prob=1/3.30),
            OddsOutcome(name="Chelsea", price=3.40, implied_prob=1/3.40),
        ],
    )
    line.devig()
    total = sum(o.true_prob for o in line.outcomes)
    assert abs(total - 1.0) < 0.001, f"Three-way devig should sum to 1.0, got {total}"
    assert line.outcomes[0].true_prob > line.outcomes[1].true_prob  # Arsenal favored


# ═══════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # Matching
        test_normalize,
        test_team_in_question_exact,
        test_team_in_question_partial,
        test_match_odds_to_markets_both_teams,
        test_match_odds_to_markets_one_team,
        test_match_odds_to_markets_no_match,
        # Signals
        test_find_true_prob,
        test_find_true_prob_not_found,
        test_generate_signals_with_edge,
        test_generate_signals_no_edge,
        test_generate_signals_no_side,
        test_generate_signals_picks_no_side,
        # Kelly
        test_kelly_extreme_edge,
        test_kelly_tiny_edge,
        test_compute_kelly_respects_max_bet,
        test_compute_kelly_respects_pct_cap,
        # OrderBook
        test_orderbook_properties,
        test_orderbook_empty,
        # Database
        test_db_insert_and_query,
        test_db_snapshots,
        test_db_empty_stats,
        # Risk
        test_risk_approves_valid,
        test_risk_rejects_low_bankroll,
        test_risk_rejects_tiny_bet,
        test_slippage_check,
        # Pipeline
        test_full_pipeline_mock,
        test_full_pipeline_no_match,
        # Devig
        test_devig_three_way,
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
            print(f"  ERROR: {t.__name__} — {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")
    sys.exit(1 if failed else 0)
