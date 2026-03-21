"""Расчёт размера ставки по критерию Келли, адаптированный для механики акций Polymarket."""
from __future__ import annotations

from dataclasses import dataclass

from config import Settings


@dataclass
class KellyResult:
    kelly_fraction: float  # raw Kelly fraction (before multiplier)
    adjusted_fraction: float  # after multiplier
    bet_size_usd: float  # final dollar amount
    ev_per_dollar: float  # expected value per $1 wagered


def kelly_yes(true_prob: float, market_price: float) -> float:
    """
    Kelly fraction for buying YES shares at price `market_price`.
    YES share costs `c`, pays $1 if true.
    f* = (p - c) / (1 - c)
    """
    c = market_price
    if c >= 1.0 or c <= 0.0:
        return 0.0
    f = (true_prob - c) / (1.0 - c)
    return max(f, 0.0)


def kelly_no(true_prob: float, market_price_yes: float) -> float:
    """
    Kelly fraction for buying NO shares.
    NO share costs (1 - c), pays $1 if outcome is NO.
    f* = ((1-p) - (1-c)) / c = (c - p) / c
    """
    c = market_price_yes
    if c <= 0.0 or c >= 1.0:
        return 0.0
    f = (c - true_prob) / c
    return max(f, 0.0)


def compute_kelly(
    true_prob: float,
    market_price_yes: float,
    bankroll: float,
    settings: Settings,
    kelly_multiplier_override: float | None = None,
    draw_prob: float = 0.0,
) -> KellyResult:
    """
    Compute bet sizing for the best side (YES or NO).
    Returns a KellyResult with the recommended bet.
    If no edge exists on either side, returns zero.

    draw_prob: для match-winner в футболе — вероятность ничьей (0.27 для EPL).
    p_effective = true_prob * (1 - draw_prob) — консервативная оценка, уменьшает Kelly.
    """
    if draw_prob > 0 and draw_prob < 1:
        true_prob = true_prob * (1.0 - draw_prob)
    f_yes = kelly_yes(true_prob, market_price_yes)
    f_no = kelly_no(true_prob, market_price_yes)

    if f_yes >= f_no:
        raw_f = f_yes
        side_price = market_price_yes
        ev = true_prob - market_price_yes
    else:
        raw_f = f_no
        side_price = 1.0 - market_price_yes
        ev = (1.0 - true_prob) - (1.0 - market_price_yes)

    if raw_f <= 0:
        return KellyResult(
            kelly_fraction=0.0,
            adjusted_fraction=0.0,
            bet_size_usd=0.0,
            ev_per_dollar=0.0,
        )

    km = kelly_multiplier_override if kelly_multiplier_override is not None else settings.kelly_multiplier
    adjusted = raw_f * km

    bet_from_kelly = bankroll * adjusted
    bet_from_pct = bankroll * settings.max_bet_pct
    bet = min(bet_from_kelly, bet_from_pct, settings.max_bet_usd)
    bet = max(bet, 0.0)

    ev_per_dollar = ev / side_price if side_price > 0 else 0.0

    return KellyResult(
        kelly_fraction=raw_f,
        adjusted_fraction=adjusted,
        bet_size_usd=round(bet, 2),
        ev_per_dollar=round(ev_per_dollar, 4),
    )
