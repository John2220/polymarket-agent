"""Генерация торговых сигналов: сравнение истинных вероятностей Pinnacle с ценами Polymarket."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Tuple

from config import Settings, get_draw_prob
from data.models import Market, OddsLine, Side, Signal, league_tier
from data.team_stats import get_team_form_sync, should_skip_yes_on_team
from analysis.kelly import compute_kelly, kelly_no, kelly_yes

logger = logging.getLogger(__name__)


def generate_signals(
    matched_pairs: List[Tuple[OddsLine, Market, str]],
    bankroll: float,
    settings: Settings,
    kelly_base_override: float | None = None,
) -> List[Signal]:
    """
    For each (odds_line, market, matched_team) triple, compute edge and
    Kelly sizing. Return signals that pass the minimum edge and liquidity filters.
    """
    signals: List[Signal] = []

    for odds_line, market, matched_team in matched_pairs:
        if market.liquidity < settings.min_liquidity:
            continue

        true_prob = _find_true_prob(odds_line, matched_team)
        if true_prob is None or true_prob <= 0 or true_prob >= 1:
            continue

        yes_price = market.yes_price
        if yes_price <= 0 or yes_price >= 1:
            continue

        f_yes = kelly_yes(true_prob, yes_price)
        f_no = kelly_no(true_prob, yes_price)

        if f_yes >= f_no and f_yes > 0:
            side = Side.YES
            edge = true_prob - yes_price
            side_price = yes_price
            raw_kelly = f_yes
        elif f_no > 0:
            side = Side.NO
            edge = (1.0 - true_prob) - (1.0 - yes_price)
            side_price = 1.0 - yes_price
            raw_kelly = f_no
        else:
            continue

        # Запрет NO при YES > 65% — ставка против рынка без sharp обоснования
        if side == Side.NO and yes_price >= getattr(settings, "no_bet_max_yes", 0.65):
            continue

        # Одна поправка на ничью: edge, Kelly и размер — от adj_true (без двойного draw в compute_kelly)
        draw_prob = get_draw_prob(odds_line.sport_key) if odds_line else 0.0
        adj_true = (
            true_prob * (1.0 - draw_prob)
            if (draw_prob > 0 and draw_prob < 1.0)
            else true_prob
        )
        if side == Side.YES:
            edge = adj_true - yes_price
            raw_kelly = kelly_yes(adj_true, yes_price)
        else:
            edge = (1.0 - adj_true) - (1.0 - yes_price)
            raw_kelly = kelly_no(adj_true, yes_price)

        if edge < settings.min_edge:
            continue

        # Team form filter (fix-team-form-analysis): не ставить YES на слабую форму
        if side == Side.YES and odds_line and getattr(settings, "use_team_form_filter", True):
            form = get_team_form_sync(matched_team, odds_line.sport_key)
            if should_skip_yes_on_team(form):
                logger.info(
                    "Signal skipped (team form): YES on %s — form weak or unknown",
                    matched_team[:30],
                )
                continue

        # Tier2 лиги — половинный Kelly (Liga MX, MLS). Tier0 — skip.
        tier = league_tier(odds_line.sport_key) if odds_line else 1
        if tier == 0:
            continue
        base = kelly_base_override if kelly_base_override is not None else settings.kelly_multiplier
        kelly_mult = base * (0.4 if tier == 2 else 1.0)

        kr = compute_kelly(
            adj_true,
            yes_price,
            bankroll,
            settings,
            kelly_multiplier_override=kelly_mult,
            draw_prob=0.0,
        )

        signals.append(
            Signal(
                market=market,
                odds_line=odds_line,
                side=side,
                market_price=side_price,
                true_prob=adj_true if side == Side.YES else (1.0 - adj_true),
                edge=round(edge, 4),
                kelly_fraction=round(raw_kelly, 4),
                bet_size_usd=kr.bet_size_usd,
                ev=round(kr.ev_per_dollar, 4),
                timestamp=datetime.now(timezone.utc),
            )
        )

    signals.sort(key=lambda s: s.edge * (s.market.liquidity ** 0.5), reverse=True)
    logger.info("Generated %d signals (min_edge=%.2f)", len(signals), settings.min_edge)
    return signals


def _find_true_prob(odds_line: OddsLine, matched_team: str) -> float | None:
    """Find devigged true probability for the matched team in the odds line."""
    matched_lower = matched_team.lower()
    for outcome in odds_line.outcomes:
        if outcome.name.lower() == matched_lower:
            return outcome.true_prob
        if any(w in outcome.name.lower() for w in matched_lower.split() if len(w) > 2):
            return outcome.true_prob
    return None
