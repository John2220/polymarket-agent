"""Получение данных рынков с Polymarket Gamma API и CLOB API."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from data.models import Event, Market, OrderBook, OrderBookLevel

logger = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class PolymarketCollector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.gamma_url = settings.gamma_api_url
        self.clob_url = settings.clob_api_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._clob_client = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_clob_client(self):
        if self._clob_client is None:
            from py_clob_client.client import ClobClient
            self._clob_client = ClobClient(self.clob_url)
        return self._clob_client

    # ── Gamma API ──────────────────────────────────────────────

    @retry(wait=wait_exponential(min=1, max=16), stop=stop_after_attempt(3))
    async def fetch_active_events(
        self,
        tag: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Event]:
        session = await self._get_session()
        params = {
            "active": "true",
            "closed": "false",
            "limit": str(limit),
            "offset": str(offset),
        }
        if tag:
            params["tag"] = tag

        async with session.get(
            f"{self.gamma_url}/events", params=params
        ) as resp:
            resp.raise_for_status()
            raw_events = await resp.json()

        events: List[Event] = []
        for re in raw_events:
            markets = []
            for rm in re.get("markets", []):
                markets.append(_parse_market(rm, event_slug=re.get("slug", "")))
            events.append(
                Event(
                    event_id=str(re.get("id", "")),
                    title=re.get("title", ""),
                    slug=re.get("slug", ""),
                    markets=markets,
                    volume=_float(re.get("volume")),
                    liquidity=_float(re.get("liquidity")),
                    end_date=_parse_dt(re.get("endDate")),
                    active=re.get("active", True),
                    closed=re.get("closed", False),
                )
            )
        logger.info("Fetched %d events from Gamma API (offset=%d)", len(events), offset)
        return events

    @retry(wait=wait_exponential(min=1, max=16), stop=stop_after_attempt(3))
    async def fetch_active_markets(
        self, limit: int = 100, offset: int = 0
    ) -> List[Market]:
        session = await self._get_session()
        params = {
            "active": "true",
            "closed": "false",
            "limit": str(limit),
            "offset": str(offset),
        }
        async with session.get(
            f"{self.gamma_url}/markets", params=params
        ) as resp:
            resp.raise_for_status()
            raw = await resp.json()

        markets = [_parse_market(rm) for rm in raw]
        logger.info("Fetched %d markets from Gamma API (offset=%d)", len(markets), offset)
        return markets

    async def fetch_all_active_markets(self, batch: int = 100) -> List[Market]:
        """Paginate through all active markets."""
        all_markets: List[Market] = []
        offset = 0
        while True:
            batch_markets = await self.fetch_active_markets(limit=batch, offset=offset)
            if not batch_markets:
                break
            all_markets.extend(batch_markets)
            if len(batch_markets) < batch:
                break
            offset += batch
        return all_markets

    @retry(wait=wait_exponential(min=1, max=16), stop=stop_after_attempt(3))
    async def fetch_resolved_markets(self, limit: int = 200, offset: int = 0) -> List[Market]:
        """Fetch recently resolved/closed markets for snapshot resolution (forward-test)."""
        session = await self._get_session()
        params = {
            "closed": "true",
            "active": "false",
            "limit": str(limit),
            "offset": str(offset),
        }
        async with session.get(f"{self.gamma_url}/markets", params=params) as resp:
            resp.raise_for_status()
            raw = await resp.json()
        # Gamma API может не возвращать "resolved" — включаем closed и определяем outcome по outcomePrices
        markets = [_parse_market(rm) for rm in raw if rm.get("closed") and _has_resolvable_outcome(rm)]
        logger.info("Fetched %d resolved markets (offset=%d)", len(markets), offset)
        return markets

    # ── CLOB API (via py-clob-client, sync → to_thread) ──────

    async def fetch_orderbook(self, token_id: str) -> OrderBook:
        client = self._get_clob_client()
        raw = await asyncio.to_thread(client.get_order_book, token_id)
        bids = [
            OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
            for b in raw.get("bids", [])
        ]
        asks = [
            OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
            for a in raw.get("asks", [])
        ]
        return OrderBook(token_id=token_id, bids=bids, asks=asks)

    async def fetch_midpoint(self, token_id: str) -> Optional[float]:
        client = self._get_clob_client()
        raw = await asyncio.to_thread(client.get_midpoint, token_id)
        try:
            return float(raw.get("mid", 0))
        except (TypeError, ValueError):
            return None

    async def fetch_price(self, token_id: str) -> Optional[float]:
        client = self._get_clob_client()
        raw = await asyncio.to_thread(client.get_last_trade_price, token_id)
        try:
            return float(raw.get("price", 0))
        except (TypeError, ValueError):
            return None


# ── Helpers ──────────────────────────────────────────────────


def _has_resolvable_outcome(rm: dict) -> bool:
    """Закрытый рынок с определённым исходом (Yes или No по outcomePrices)."""
    outcome = rm.get("outcome")
    if outcome and str(outcome).upper() in ("YES", "NO"):
        return True
    prices = rm.get("outcomePrices", [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            return False
    if isinstance(prices, list) and len(prices) >= 2:
        yes_p = _float(prices[0])
        no_p = _float(prices[1])
        return yes_p > 0.99 or no_p > 0.99
    return False


def _infer_outcome_from_prices(rm: dict) -> Optional[str]:
    """Определить outcome из outcomePrices: Yes если yes>0.99, No если no>0.99."""
    if rm.get("outcome"):
        o = str(rm.get("outcome", "")).strip().upper()
        if o in ("YES", "NO"):
            return "Yes" if o == "YES" else "No"
    prices = rm.get("outcomePrices", [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            return None
    if isinstance(prices, list) and len(prices) >= 2:
        yes_p = _float(prices[0])
        no_p = _float(prices[1])
        if yes_p > 0.99:
            return "Yes"
        if no_p > 0.99:
            return "No"
    return None


def _float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v
    except (ValueError, TypeError):
        return None


def _parse_market(rm: dict, event_slug: str = "") -> Market:
    tokens = rm.get("clobTokenIds", []) or rm.get("tokens", [])
    yes_token = ""
    no_token = ""
    if isinstance(tokens, list) and len(tokens) >= 2:
        if isinstance(tokens[0], str):
            yes_token, no_token = tokens[0], tokens[1]
        elif isinstance(tokens[0], dict):
            yes_token = tokens[0].get("token_id", "")
            no_token = tokens[1].get("token_id", "")

    outcome_prices = rm.get("outcomePrices", [])
    yes_price = 0.0
    no_price = 0.0
    if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
        yes_price = _float(outcome_prices[0])
        no_price = _float(outcome_prices[1])
    elif isinstance(outcome_prices, str):
        try:
            import json
            prices = json.loads(outcome_prices)
            if len(prices) >= 2:
                yes_price = _float(prices[0])
                no_price = _float(prices[1])
        except Exception:
            pass

    tags_raw = rm.get("tags", [])
    tags = []
    if isinstance(tags_raw, list):
        for t in tags_raw:
            if isinstance(t, dict):
                tags.append(t.get("label", t.get("slug", "")))
            elif isinstance(t, str):
                tags.append(t)

    return Market(
        condition_id=rm.get("conditionId", rm.get("condition_id", "")),
        question=rm.get("question", ""),
        slug=rm.get("slug", ""),
        yes_token_id=yes_token,
        no_token_id=no_token,
        yes_price=yes_price,
        no_price=no_price,
        volume=_float(rm.get("volume")),
        volume_24h=_float(rm.get("volume24hr")),
        liquidity=_float(rm.get("liquidity")),
        end_date=_parse_dt(rm.get("endDate")),
        active=rm.get("active", True),
        closed=rm.get("closed", False),
        resolved=bool(rm.get("resolved") or _infer_outcome_from_prices(rm)),
        outcome=rm.get("outcome") or _infer_outcome_from_prices(rm),
        tags=tags,
        description=rm.get("description", ""),
        event_slug=event_slug or rm.get("eventSlug", ""),
    )
