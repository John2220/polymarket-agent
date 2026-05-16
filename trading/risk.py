"""Риск-менеджмент: лимиты ставок, дневной стоп-лосс, проверка проскальзывания."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from config import Settings
from data.models import Signal
from storage.db import Database

logger = logging.getLogger(__name__)


async def _risk_webhook(settings: Settings, event: str, reason: str) -> None:
    url = getattr(settings, "alert_webhook_url", "") or ""
    if not url.strip():
        return
    from integrations.webhooks import post_json_webhook

    await post_json_webhook(
        url,
        {"source": "polymarket-agent", "event": event, "reason": reason},
    )


@dataclass
class RiskVerdict:
    approved: bool
    adjusted_size: float
    reason: str = ""


class RiskManager:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db

    async def check(
        self,
        signal: Signal,
        bankroll: float,
        initial_bankroll: float | None = None,
    ) -> RiskVerdict:
        """Run all risk checks on a signal. Returns approval and possibly adjusted size."""
        s = self.settings
        init = initial_bankroll if initial_bankroll is not None else bankroll

        # 0. Drawdown limit (BACKTEST 2025)
        max_dd = getattr(s, "max_drawdown_pct", 25.0)
        if max_dd > 0 and init > 0:
            peak, dd_pct = await self.db.get_peak_equity_and_drawdown(init)
            if dd_pct >= max_dd:
                await _risk_webhook(
                    s,
                    "drawdown_block",
                    f"Drawdown {dd_pct:.1f}% >= {max_dd}%",
                )
                return RiskVerdict(
                    approved=False,
                    adjusted_size=0,
                    reason=f"Drawdown limit: {dd_pct:.1f}% >= {max_dd}%. Pause 24h.",
                )
            alert_pct = getattr(s, "drawdown_alert_pct", 15.0)
            if alert_pct > 0 and dd_pct >= alert_pct:
                logger.warning("Drawdown alert: %.1f%% (peak=%.2f)", dd_pct, peak)

        # 1. Minimum bankroll check (MIN_BANKROLL в .env или max_bet_usd * 2)
        min_br = float(s.min_bankroll) if getattr(s, "min_bankroll", 0) > 0 else s.max_bet_usd * 2
        if bankroll < min_br:
            return RiskVerdict(
                approved=False,
                adjusted_size=0,
                reason=f"Bankroll too low: ${bankroll:.2f} < ${min_br:.2f} minimum",
            )

        # 2. Daily loss limit
        todays_pnl = await self.db.get_todays_pnl()
        if todays_pnl <= -s.daily_loss_limit:
            await _risk_webhook(
                s,
                "daily_loss_block",
                f"P&L today ${todays_pnl:.2f} <= -${s.daily_loss_limit:.2f}",
            )
            return RiskVerdict(
                approved=False,
                adjusted_size=0,
                reason=f"Daily loss limit reached: ${todays_pnl:.2f} <= -${s.daily_loss_limit:.2f}",
            )

        # 2b. Consecutive losses limit
        max_cl = getattr(s, "max_consecutive_losses", 3)
        if max_cl > 0:
            consec = await self.db.get_consecutive_losses()
            if consec >= max_cl:
                return RiskVerdict(
                    approved=False,
                    adjusted_size=0,
                    reason=f"Consecutive losses limit: {consec} >= {max_cl}. Пауза 24ч.",
                )

        # 3. Cap bet size
        size = signal.bet_size_usd
        max_from_pct = bankroll * s.max_bet_pct
        size = min(size, max_from_pct, s.max_bet_usd)
        min_bet = float(s.min_bet_usd)

        if size < min_bet:
            return RiskVerdict(
                approved=False,
                adjusted_size=0,
                reason=f"Bet size too small after caps: ${size:.2f} < ${min_bet:.2f}",
            )

        # 4. Remaining daily budget (только реальный оборот auto; см. db.get_todays_wagered)
        todays_wagered = await self.db.get_todays_wagered()
        max_day_pct = float(getattr(s, "max_daily_wager_pct", 0.30) or 0.30)
        remaining_budget = max(0, bankroll * max_day_pct - todays_wagered)
        if remaining_budget < size:
            if remaining_budget >= min_bet:
                size = remaining_budget
                logger.info("Reduced bet to $%.2f (daily budget limit)", size)
            else:
                return RiskVerdict(
                    approved=False,
                    adjusted_size=0,
                    reason=f"Daily wagering limit reached: wagered ${todays_wagered:.2f}",
                )

        if size < min_bet:
            return RiskVerdict(
                approved=False,
                adjusted_size=0,
                reason=f"Bet size below minimum after daily budget: ${size:.2f} < ${min_bet:.2f}",
            )

        return RiskVerdict(approved=True, adjusted_size=round(size, 2))

    async def check_slippage(
        self, expected_price: float, current_price: float
    ) -> bool:
        """Return True if price has NOT slipped beyond threshold."""
        if expected_price <= 0:
            return False
        slippage = abs(current_price - expected_price) / expected_price
        if slippage > self.settings.max_slippage:
            logger.warning(
                "Slippage too high: expected=%.4f current=%.4f slip=%.2f%%",
                expected_price, current_price, slippage * 100,
            )
            return False
        return True
