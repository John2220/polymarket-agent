"""Исполнение ордеров: режим рекомендаций (вывод в консоль) и авто-режим (FOK через py-clob-client)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from config import Settings
from data.collector import PolymarketCollector
from data.models import BetRecord, Side, Signal, SnapshotRecord
from storage.db import Database
from trading.risk import RiskManager
from backtest.simulator import sim_fill_orderbook

logger = logging.getLogger(__name__)


class Executor:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        risk: RiskManager,
        collector: PolymarketCollector,
        mode: str = "recommend",
    ):
        self.settings = settings
        self.db = db
        self.risk = risk
        self.collector = collector
        self.mode = mode
        self._clob_client = None

    def _in_betting_window(self, signal) -> bool:
        """Проверка: матч в окне 2-8 часов до начала (настраивается в config)."""
        market = signal.market
        if not market.end_date:
            return True
        now = datetime.now(timezone.utc)
        end = market.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        hours = (end - now).total_seconds() / 3600
        min_h = getattr(self.settings, "betting_window_hours_min", 2.0)
        max_h = getattr(self.settings, "betting_window_hours_max", 8.0)
        if hours < 0:
            return False  # уже закончился
        return min_h <= hours <= max_h

    def _get_trading_client(self):
        """Initialize authenticated CLOB client for auto mode."""
        if self._clob_client is None:
            from py_clob_client.client import ClobClient

            client = ClobClient(
                self.settings.clob_api_url,
                key=self.settings.polymarket_private_key,
                chain_id=self.settings.chain_id,
                signature_type=0,
                funder=self.settings.polymarket_funder_address,
            )
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            self._clob_client = client
        return self._clob_client

    async def execute_signals(
        self,
        signals: List[Signal],
        bankroll: float,
        initial_bankroll: float | None = None,
    ) -> List[BetRecord]:
        """Process all signals through risk checks and execute or record."""
        records: List[BetRecord] = []

        for signal in signals:
            # Всегда записываем snapshot для forward-test (в т.ч. пропущенные сигналы)
            await self._record_snapshot(signal)

            # Окно времени до матча: 2–24 ч (настраивается в config)
            if not self._in_betting_window(signal):
                logger.info(
                    "Signal skipped (outside time window): %s",
                    signal.market.question[:60],
                )
                continue

            verdict = await self.risk.check(signal, bankroll, initial_bankroll or bankroll)

            if not verdict.approved:
                logger.info(
                    "Signal rejected: %s — %s",
                    signal.market.question[:60],
                    verdict.reason,
                )
                continue

            signal.bet_size_usd = verdict.adjusted_size

            if self.mode == "auto":
                record = await self._place_order(signal)
            else:
                record = self._create_recommendation(signal)

            records.append(record)
            bet_id = await self.db.insert_bet(record)
            record.id = bet_id

        return records

    async def _maker_limit_price(self, token_id: str, ref_price: float) -> float:
        """Лимитная цена для post-only BUY: улучшаем лучший bid на N тиков, не пересекаем ask."""
        tick = float(getattr(self.settings, "maker_tick_size", 0.01) or 0.01)
        off = int(getattr(self.settings, "maker_tick_offset", 1) or 1)
        try:
            ob = await self.collector.fetch_orderbook(token_id)
            bids = sorted(ob.bids, key=lambda x: -x.price)
            asks = sorted(ob.asks, key=lambda x: x.price)
            best_bid = bids[0].price if bids else max(tick, ref_price - tick)
            best_ask = asks[0].price if asks else min(1.0 - tick, ref_price + tick)
        except Exception:
            best_bid = max(tick, ref_price - tick)
            best_ask = min(1.0 - tick, ref_price + tick)
        candidate = best_bid + off * tick
        max_post_only = best_ask - tick
        if candidate >= best_ask:
            candidate = max_post_only
        candidate = max(tick, min(candidate, 1.0 - tick))
        return round(candidate, 2)

    async def _place_order(self, signal: Signal) -> BetRecord:
        """Place a FOK order via py-clob-client."""
        market = signal.market
        token_id = (
            market.yes_token_id if signal.side == Side.YES else market.no_token_id
        )

        if not token_id:
            logger.error("No token_id for %s side %s", market.question[:40], signal.side)
            return self._create_record(signal, status="rejected", order_id="no_token_id")

        # Slippage check: re-fetch price before FOK (plan: risk-executor)
        current_price = await self.collector.fetch_price(token_id)
        if current_price is None:
            logger.warning("Could not fetch current price for %s — skipping order", token_id[:20])
            return self._create_record(signal, status="cancelled", order_id="price_unavailable")
        ok = await self.risk.check_slippage(signal.market_price, current_price)
        if not ok:
            return self._create_record(signal, status="cancelled", order_id="slippage")

        try:
            client = self._get_trading_client()
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY

            size = signal.bet_size_usd / signal.market_price if signal.market_price > 0 else 0
            size = round(size, 2)

            neg_risk = False
            use_maker = bool(getattr(self.settings, "use_maker_first", False))
            if use_maker:
                limit_price = await self._maker_limit_price(token_id, signal.market_price)
                order_type = OrderType.GTC
                post_only = True
            else:
                limit_price = round(signal.market_price, 2)
                order_type = OrderType.FOK
                post_only = False

            options = {"tick_size": "0.01", "neg_risk": neg_risk}

            def _create_and_post():
                signed = client.create_order(
                    OrderArgs(
                        token_id=token_id,
                        price=limit_price,
                        size=size,
                        side=BUY,
                    ),
                    options,
                )
                return client.post_order(
                    signed,
                    orderType=order_type,
                    post_only=post_only,
                )

            response = await asyncio.to_thread(_create_and_post)

            order_id = response.get("orderID", "")
            if use_maker:
                status = "pending"  # лимит в стакане; проверять fill отдельно
            else:
                status = "filled" if response.get("status") == "matched" else "pending"
            logger.info(
                "Order placed: %s %s $%.2f @ %.4f (limit) type=%s — %s",
                signal.side.value,
                market.question[:40],
                signal.bet_size_usd,
                limit_price,
                getattr(order_type, "value", str(order_type)),
                status,
            )
            return self._create_record(signal, status=status, order_id=order_id)

        except Exception as exc:
            logger.error("Order failed for %s: %s", market.question[:40], exc)
            return self._create_record(signal, status="rejected", order_id=str(exc)[:100])

    def _create_recommendation(self, signal: Signal) -> BetRecord:
        """Create a BetRecord in recommend mode (no actual order)."""
        return self._create_record(signal, status="recommended", order_id="")

    def _create_record(
        self, signal: Signal, status: str, order_id: str = ""
    ) -> BetRecord:
        return BetRecord(
            market_condition_id=signal.market.condition_id,
            market_question=signal.market.question,
            side=signal.side,
            price=signal.market_price,
            size_usd=signal.bet_size_usd,
            edge=signal.edge,
            kelly_fraction=signal.kelly_fraction,
            mode=self.mode,
            status=status,
            order_id=order_id,
            created_at=datetime.utcnow(),
        )

    async def _record_snapshot(self, signal: Signal):
        """Record signal data for forward-test analysis (incl. order-book sim fill)."""
        line = signal.odds_line
        sim_fill_price: float | None = None
        slippage_bps: float | None = None
        token_id = (
            signal.market.yes_token_id
            if signal.side == Side.YES
            else signal.market.no_token_id
        )
        if token_id and signal.bet_size_usd > 0 and signal.market_price > 0:
            try:
                ob = await self.collector.fetch_orderbook(token_id)
                shares = signal.bet_size_usd / signal.market_price
                sim_fill_price, slippage_bps = sim_fill_orderbook(
                    ob, signal.side.value, shares, signal.market_price
                )
            except Exception:
                pass
        snap = SnapshotRecord(
            market_condition_id=signal.market.condition_id,
            market_question=signal.market.question,
            sport_key=line.sport_key if line else "",
            home_team=line.home_team if line else "",
            away_team=line.away_team if line else "",
            side=signal.side,
            pm_price=signal.market_price,
            pinnacle_true_prob=signal.true_prob,
            edge=signal.edge,
            kelly_fraction=signal.kelly_fraction,
            recommended_bet_usd=signal.bet_size_usd,
            created_at=datetime.utcnow(),
            sim_fill_price=sim_fill_price,
            slippage_bps=slippage_bps,
        )
        await self.db.insert_snapshot(snap)
