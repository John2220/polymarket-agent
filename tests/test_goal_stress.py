"""
Стресс-тесты и косвенные проверки под цель: устойчивый рост депозита
(в т.ч. ориентир «до $1M») при ставках на исходы.

Не гарантируют прибыль — проверяют согласованность математики, лимитов и
реалистичность масштабирования при текущих настройках (.env).
"""
from __future__ import annotations

import asyncio
import random
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.kelly import compute_kelly
from config import Settings
from core.bet_results import calc_pnl
from core.gamma_resolve import is_no_side, is_yes_side, market_fully_resolved
from storage.db import Database
from trading.risk import RiskManager


def _settings(**kw) -> Settings:
    base = dict(
        odds_api_key="stress",
        kelly_multiplier=0.25,
        min_edge=0.03,
        max_bet_pct=0.05,
        max_bet_usd=50.0,
        max_slippage=0.02,
        daily_loss_limit=500.0,
        max_consecutive_losses=5,
        max_drawdown_pct=25.0,
    )
    base.update(kw)
    return Settings(**base)


def _simulate_bankroll_path(
    *,
    initial: float,
    true_prob: float,
    price_yes: float,
    n_bets: int,
    settings: Settings,
    seed: int,
) -> float:
    """
    Упрощённая модель: на каждом шаге размер ставки как в compute_kelly,
    исход — Bernoulli(true_prob) для стороны YES (как «честный» рынок по модели).
    """
    rng = random.Random(seed)
    br = initial
    for _ in range(n_bets):
        if br < settings.max_bet_usd * 2:
            break
        r = compute_kelly(true_prob, price_yes, br, settings, draw_prob=0.0)
        bet = r.bet_size_usd
        if bet < 1.0:
            break
        win = rng.random() < true_prob
        br += calc_pnl(bet, price_yes, win)
        if br <= 0:
            return 0.0
    return br


def test_goal_01_high_bankroll_bet_capped():
    """При крупном банкролле действует жёсткий MAX_BET_USD — ставка не растёт бесконечно."""
    s = _settings(max_bet_usd=50.0, max_bet_pct=0.05, kelly_multiplier=0.25)
    r = compute_kelly(0.72, 0.52, bankroll=2_000_000, settings=s)
    assert r.bet_size_usd <= 50.0
    assert r.bet_size_usd == 50.0  # Kelly тянет выше, кап режет


def test_goal_02_monte_carlo_positive_edge_median_grows():
    """При edge > 0 медианный банкролл за много ставок растёт (упрощённая модель)."""
    s = _settings()
    initial = 5000.0
    n_paths = 300
    n_bets = 800
    finals = [
        _simulate_bankroll_path(
            initial=initial,
            true_prob=0.62,
            price_yes=0.52,
            n_bets=n_bets,
            settings=s,
            seed=1000 + i,
        )
        for i in range(n_paths)
    ]
    med = statistics.median(finals)
    assert med > initial * 1.02, f"median {med} should beat {initial} with edge"


def test_goal_03_monte_carlo_negative_edge_median_shrinks():
    """При отрицательном edge (p < price) медиана падает."""
    s = _settings()
    initial = 5000.0
    finals = [
        _simulate_bankroll_path(
            initial=initial,
            true_prob=0.48,
            price_yes=0.52,
            n_bets=600,
            settings=s,
            seed=2000 + i,
        )
        for i in range(250)
    ]
    med = statistics.median(finals)
    assert med < initial * 0.98, f"median {med} should shrink vs {initial} with -EV"


def test_goal_04_million_dollars_requires_many_bets_with_current_cap():
    """
    Косвенная проверка цели $1M: при MAX_BET_USD=50 рост «на ставку» ограничен;
    за разумное число шагов почти ни один путь не достигает 1M от $1k.
    """
    s = _settings(max_bet_usd=50.0)
    initial = 1000.0
    target = 1_000_000.0
    n_paths = 150
    n_bets = 25_000
    hits = 0
    for i in range(n_paths):
        final = _simulate_bankroll_path(
            initial=initial,
            true_prob=0.58,
            price_yes=0.48,
            n_bets=n_bets,
            settings=s,
            seed=3000 + i,
        )
        if final >= target:
            hits += 1
    # Допускаем редкий выброс, но не «лёгкий миллион»
    assert hits <= max(2, n_paths // 50), (
        f"С капом $50 достижение $1M за {n_bets} шагов должно быть редким; hits={hits}"
    )


def test_goal_05_stress_calc_pnl_batch():
    """Массовый вызов P&L без ошибок и деградации."""
    acc = 0.0
    for i in range(5000):
        p = 0.05 + (i % 90) / 100.0
        acc += calc_pnl(25.0, p, i % 2 == 0)
    assert acc == acc  # finite
    assert -125000 < acc < 500000


def test_goal_06_gamma_resolve_binary_helpers():
    """Косвенно: резолв ставок не ломается на типичных строках."""
    assert is_yes_side("YES")
    assert is_yes_side("ДА")
    assert is_no_side("НЕТ")
    assert market_fully_resolved(
        {"closed": True, "outcomePrices": '["1","0"]', "outcomes": '["Yes","No"]'}
    )


def test_goal_07_risk_slippage_boundary():
    """Порог max_slippage: в risk.py строгое > (2% уже отклонение)."""

    async def _run():
        s = _settings(max_slippage=0.02)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            path = Path(tmp.name)
        db: Database | None = None
        try:
            db = Database(path)
            await db.connect()
            risk = RiskManager(s, db)
            # 1.8% — допускается
            assert await risk.check_slippage(0.50, 0.509)
            # ровно 2% — отклоняется (slip > max)
            assert not await risk.check_slippage(0.50, 0.51)
            assert not await risk.check_slippage(0.50, 0.531)
        finally:
            if db is not None:
                await db.close()
            path.unlink(missing_ok=True)

    asyncio.run(_run())


def test_goal_08_risk_rejects_after_daily_loss():
    """Дневной лимит убытка блокирует новые ставки."""

    async def _run():
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock

        from data.models import Market, OddsLine, Signal, Side

        s = _settings(daily_loss_limit=50.0)
        db = MagicMock()
        db.get_todays_pnl = AsyncMock(return_value=-55.0)
        db.get_consecutive_losses = AsyncMock(return_value=0)
        db.get_todays_wagered = AsyncMock(return_value=0.0)
        db.get_peak_equity_and_drawdown = AsyncMock(return_value=(10000.0, 0.0))

        risk = RiskManager(s, db)
        line = OddsLine(
            sport_key="soccer_epl",
            home_team="A",
            away_team="B",
            commence_time=datetime(2026, 6, 1),
            outcomes=[],
        )
        sig = Signal(
            market=Market(
                condition_id="x",
                question="Test?",
                yes_price=0.5,
                liquidity=5000,
            ),
            side=Side.YES,
            market_price=0.5,
            true_prob=0.6,
            edge=0.1,
            kelly_fraction=0.05,
            bet_size_usd=40.0,
            odds_line=line,
        )
        v = await risk.check(sig, bankroll=5000.0, initial_bankroll=5000.0)
        assert not v.approved
        assert "Daily loss" in v.reason

    asyncio.run(_run())


def test_goal_09_kelly_stable_under_jitter():
    """Небольшой дребезг вероятностей не даёт отрицательной ставки при устойчивом edge."""
    s = _settings()
    for eps in [0.0, 0.005, -0.005, 0.01]:
        r = compute_kelly(0.55 + eps, 0.50, 8000.0, s)
        assert r.bet_size_usd >= 0
        if 0.55 + eps > 0.50 + 1e-6:
            assert r.bet_size_usd > 0
