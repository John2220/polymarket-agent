"""
Исторический бэктест: симуляция стратегии на архивных данных.

Поддерживает:
- Загрузку из JSON/CSV (формат см. load_historical_events)
- Демо-режим с синтетическими данными (run_demo)
- Опционально: The Odds API historical (платно, ~$15/мес)

Метрики: equity curve, Sharpe Ratio, max drawdown, WR по лигам.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

# Optional deps — graceful fallback
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@dataclass
class HistoricalEvent:
    """Одно событие для исторического бэктеста."""
    sport_key: str
    home_team: str
    away_team: str
    commence_time: datetime
    pinnacle_yes_prob: float  # devigged Pinnacle prob for YES (e.g. home win)
    pm_yes_price: float      # Polymarket YES price at signal time
    matched_team: str        # team we're betting on (for YES) or against (for NO)
    outcome: str             # "Yes" | "No" — фактический исход для matched_team


def load_historical_events(path: Path) -> List[HistoricalEvent]:
    """
    Загрузить события из JSON.

    Формат файла:
    {
      "events": [
        {
          "sport_key": "basketball_nba",
          "home_team": "Lakers",
          "away_team": "Celtics",
          "commence_time": "2024-01-15T19:00:00Z",
          "pinnacle_yes_prob": 0.55,
          "pm_yes_price": 0.50,
          "matched_team": "Lakers",
          "outcome": "Yes"
        }
      ]
    }
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events: List[HistoricalEvent] = []
    for e in data.get("events", data) if isinstance(data, dict) else data:
        dt = e.get("commence_time")
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        events.append(HistoricalEvent(
            sport_key=e.get("sport_key", ""),
            home_team=e.get("home_team", ""),
            away_team=e.get("away_team", ""),
            commence_time=dt,
            pinnacle_yes_prob=float(e.get("pinnacle_yes_prob", 0.5)),
            pm_yes_price=float(e.get("pm_yes_price", 0.5)),
            matched_team=e.get("matched_team", ""),
            outcome=e.get("outcome", "No"),
        ))
    return events


def generate_demo_events(
    n: int = 120,
    seed: int = 42,
    year: int = 2024,
) -> List[HistoricalEvent]:
    """Генерация синтетических событий для демо/тестов."""
    random.seed(seed)
    base = datetime(year, 1, 1, tzinfo=timezone.utc)
    events = []
    leagues = ["basketball_nba", "soccer_epl", "soccer_uefa_champs_league", "soccer_mexico_ligamx"]
    teams = [
        ("Lakers", "Celtics"), ("Arsenal", "Chelsea"), ("Bayern", "Dortmund"),
        ("Real Madrid", "Barcelona"), ("Puebla", "Tigres"), ("Man City", "Liverpool"),
    ]

    for i in range(n):
        sport = random.choice(leagues)
        home, away = random.choice(teams)
        pinnacle_yes = round(random.uniform(0.35, 0.75), 2)
        misprice = random.uniform(-0.08, 0.08)
        pm_yes = max(0.1, min(0.9, pinnacle_yes + misprice))
        outcome = "Yes" if random.random() < pinnacle_yes else "No"
        events.append(HistoricalEvent(
            sport_key=sport,
            home_team=home,
            away_team=away,
            commence_time=base + timedelta(days=i // 3, hours=i % 3 * 4),
            pinnacle_yes_prob=pinnacle_yes,
            pm_yes_price=round(pm_yes, 2),
            matched_team=home,
            outcome=outcome,
        ))
    return events


@dataclass
class BacktestResult:
    """Результат исторического бэктеста."""
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    total_wagered: float = 0.0
    total_pnl: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    by_league: dict = field(default_factory=dict)
    trades: List[dict] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        r = self.wins + self.losses
        return self.wins / r * 100 if r > 0 else 0.0

    @property
    def roi(self) -> float:
        return self.total_pnl / self.total_wagered * 100 if self.total_wagered > 0 else 0.0

    @property
    def sharpe_ratio(self) -> float:
        if not self.equity_curve or len(self.equity_curve) < 2:
            return 0.0
        returns = [
            (self.equity_curve[i] - self.equity_curve[i-1]) / max(1, self.equity_curve[i-1])
            for i in range(1, len(self.equity_curve))
            if self.equity_curve[i-1] != 0
        ]
        if not returns:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std = var ** 0.5 if var > 0 else 0.0001
        return mean_r / std * (252 ** 0.5) if std else 0.0  # annualized

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for v in self.equity_curve:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd


def run_backtest(
    events: List[HistoricalEvent],
    bankroll: float = 1000.0,
    min_edge: float = 0.03,
    kelly_mult: float = 0.25,
    max_bet_pct: float = 0.05,
    max_bet_usd: float = 50.0,
    no_bet_max_yes: float = 0.65,
) -> BacktestResult:
    """
    Запустить исторический бэктест с правилами стратегии.
    """
    sys_path = Path(__file__).resolve().parent.parent
    if str(sys_path) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(sys_path))

    from config import Settings, get_draw_prob
    from data.models import league_tier
    from analysis.kelly import kelly_yes, kelly_no, compute_kelly
    from core.bet_results import calc_pnl

    settings = Settings(
        odds_api_key="backtest",
        kelly_multiplier=kelly_mult,
        min_edge=min_edge,
        max_bet_pct=max_bet_pct,
        max_bet_usd=max_bet_usd,
        no_bet_max_yes=no_bet_max_yes,
    )

    result = BacktestResult()
    equity = bankroll
    result.equity_curve.append(equity)

    for ev in sorted(events, key=lambda e: e.commence_time):
        yes_price = ev.pm_yes_price
        true_prob = ev.pinnacle_yes_prob
        if yes_price <= 0 or yes_price >= 1:
            continue

        f_yes = kelly_yes(true_prob, yes_price)
        f_no = kelly_no(true_prob, yes_price)

        if f_yes >= f_no and f_yes > 0:
            side = "YES"
            edge = true_prob - yes_price
            side_price = yes_price
            raw_kelly = f_yes
        elif f_no > 0:
            side = "NO"
            edge = (1.0 - true_prob) - (1.0 - yes_price)
            side_price = 1.0 - yes_price
            raw_kelly = f_no
        else:
            continue

        if side == "NO" and yes_price >= no_bet_max_yes:
            continue
        if edge < min_edge:
            continue

        tier = league_tier(ev.sport_key)
        if tier == 0:
            continue
        kelly_mult_eff = kelly_mult * (0.4 if tier == 2 else 1.0)
        draw_prob = get_draw_prob(ev.sport_key)

        kr = compute_kelly(
            true_prob, yes_price, equity, settings,
            kelly_multiplier_override=kelly_mult_eff,
            draw_prob=draw_prob,
        )
        bet = kr.bet_size_usd
        if bet < 1.0:
            continue

        bet = min(bet, equity * max_bet_pct, max_bet_usd)
        won = (ev.outcome == "Yes" and side == "YES") or (ev.outcome == "No" and side == "NO")
        pnl = calc_pnl(bet, side_price, won)
        equity += pnl

        result.total_bets += 1
        result.total_wagered += bet
        result.total_pnl += pnl
        result.wins += 1 if won else 0
        result.losses += 1 if not won else 0
        result.equity_curve.append(equity)

        league_key = ev.sport_key or "unknown"
        if league_key not in result.by_league:
            result.by_league[league_key] = {"bets": 0, "wins": 0, "pnl": 0.0}
        result.by_league[league_key]["bets"] += 1
        result.by_league[league_key]["wins"] += 1 if won else 0
        result.by_league[league_key]["pnl"] += pnl

        result.trades.append({
            "sport": ev.sport_key,
            "home": ev.home_team,
            "away": ev.away_team,
            "side": side,
            "price": side_price,
            "bet": bet,
            "pnl": pnl,
            "won": won,
        })

    return result


def plot_equity_curve(result: BacktestResult, output_path: Optional[Path] = None) -> None:
    """Построить equity curve и сохранить в файл."""
    if not HAS_MATPLOTLIB:
        print("[WARN] matplotlib не установлен. Установите: pip install matplotlib")
        return

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[2, 1])

    # Equity curve
    ax1 = axes[0]
    ax1.plot(result.equity_curve, color="steelblue", linewidth=1.5)
    ax1.axhline(y=result.equity_curve[0], color="gray", linestyle="--", alpha=0.5)
    ax1.set_title("Equity Curve (Historical Backtest)")
    ax1.set_ylabel("Bankroll ($)")
    ax1.set_xlabel("Trade #")
    ax1.grid(True, alpha=0.3)

    # Drawdown
    ax2 = axes[1]
    peak = result.equity_curve[0]
    drawdowns = []
    for v in result.equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        drawdowns.append(-dd)
    ax2.fill_between(range(len(drawdowns)), drawdowns, 0, color="coral", alpha=0.5)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Trade #")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out = output_path or Path("backtest_equity.png")
    plt.savefig(out, dpi=120)
    plt.close()
    print(f"Saved: {out}")


def run_demo(
    n_events: int = 120,
    output_dir: Optional[Path] = None,
) -> BacktestResult:
    """
    Демо: синтетические данные + бэктест + визуализация.
    """
    events = generate_demo_events(n=n_events)
    result = run_backtest(events)

    print("\n=== Historical Backtest (Demo) ===\n")
    print(f"  Total bets:    {result.total_bets}")
    print(f"  Win rate:     {result.win_rate:.1f}% ({result.wins}W / {result.losses}L)")
    print(f"  Total P&L:    ${result.total_pnl:.2f}")
    print(f"  ROI:          {result.roi:.1f}%")
    print(f"  Sharpe:       {result.sharpe_ratio:.2f}")
    print(f"  Max drawdown: {result.max_drawdown_pct:.1f}%")
    print("\n  By league:")
    for k, v in result.by_league.items():
        wr = v["wins"] / v["bets"] * 100 if v["bets"] > 0 else 0
        print(f"    {k}: {v['bets']} bets, WR={wr:.1f}%, P&L=${v['pnl']:.2f}")

    out_dir = output_dir or Path(__file__).parent.parent
    plot_equity_curve(result, out_dir / "backtest_equity.png")
    return result


if __name__ == "__main__":
    run_demo(n_events=150)
