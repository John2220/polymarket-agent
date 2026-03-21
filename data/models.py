from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# Tier лиг: 1 = полный Kelly, 2 = Kelly×0.10, 0 = skip
TIER1_LEAGUES = {
    "soccer_epl", "soccer_spain_la_liga", "soccer_germany_bundesliga",
    "soccer_italy_serie_a", "soccer_france_ligue_one",
    "soccer_uefa_champs_league", "basketball_nba", "americanfootball_nfl",
    "mma_mixed_martial_arts",
}
TIER2_LEAGUES = {"soccer_mexico_ligamx", "soccer_usa_mls", "soccer_uk_championship"}
SKIP_LEAGUES = {"soccer_colombia", "soccer_colombia_ligamx"}  # Liga BetPlay и др.


def league_tier(sport_key: str) -> int:
    """Возвращает 1 (Tier1), 2 (Tier2) или 0 (skip)."""
    sk = (sport_key or "").lower()
    if sk in TIER1_LEAGUES:
        return 1
    if sk in TIER2_LEAGUES:
        return 2
    if sk in SKIP_LEAGUES:
        return 0
    if "colombia" in sk or "betplay" in sk:
        return 0
    return 1  # по умолчанию Tier1 для неизвестных


class Side(str, Enum):
    YES = "YES"
    NO = "NO"


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBook(BaseModel):
    token_id: str
    bids: List[OrderBookLevel] = Field(default_factory=list)
    asks: List[OrderBookLevel] = Field(default_factory=list)

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


class Market(BaseModel):
    """A single binary market on Polymarket (one question, YES/NO)."""
    condition_id: str
    question: str
    slug: str = ""
    yes_token_id: str = ""
    no_token_id: str = ""
    yes_price: float = 0.0
    no_price: float = 0.0
    volume: float = 0.0
    volume_24h: float = 0.0
    liquidity: float = 0.0
    end_date: Optional[datetime] = None
    active: bool = True
    closed: bool = False
    resolved: bool = False
    outcome: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    description: str = ""
    event_slug: str = ""


class Event(BaseModel):
    """A Polymarket event grouping one or more markets."""
    event_id: str
    title: str
    slug: str = ""
    markets: List[Market] = Field(default_factory=list)
    volume: float = 0.0
    liquidity: float = 0.0
    end_date: Optional[datetime] = None
    active: bool = True
    closed: bool = False


class OddsOutcome(BaseModel):
    name: str
    price: float  # decimal odds (e.g. 2.10)
    implied_prob: float = 0.0  # raw implied probability (1/price)
    true_prob: float = 0.0  # devigged probability


class OddsLine(BaseModel):
    """Sharp sportsbook line for one event (e.g. from Pinnacle)."""
    sport_key: str
    sport_title: str = ""
    home_team: str
    away_team: str
    commence_time: datetime
    bookmaker: str = "pinnacle"
    outcomes: List[OddsOutcome] = Field(default_factory=list)

    def devig(self) -> None:
        """Remove bookmaker margin to derive true probabilities."""
        total = sum(o.implied_prob for o in self.outcomes)
        if total > 0:
            for o in self.outcomes:
                o.true_prob = o.implied_prob / total


class Signal(BaseModel):
    """A trading signal: market + side + edge + recommended bet size."""
    market: Market
    odds_line: Optional[OddsLine] = None
    side: Side
    market_price: float  # current PM price for this side
    true_prob: float  # our estimated true probability
    edge: float  # true_prob - market_price
    kelly_fraction: float = 0.0
    bet_size_usd: float = 0.0
    ev: float = 0.0  # expected value per dollar
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BetRecord(BaseModel):
    """A record of a bet placed or recommended."""
    id: Optional[int] = None
    market_condition_id: str
    market_question: str
    side: Side
    price: float
    size_usd: float
    edge: float
    kelly_fraction: float
    mode: str  # "recommend" or "auto"
    status: str = "pending"  # pending, filled, cancelled, rejected
    order_id: str = ""
    pnl: Optional[float] = None
    resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class SnapshotRecord(BaseModel):
    """Forward-test snapshot: Pinnacle line + PM price at signal time."""
    id: Optional[int] = None
    market_condition_id: str
    market_question: str
    sport_key: str = ""
    home_team: str = ""
    away_team: str = ""
    side: Side
    pm_price: float
    pinnacle_true_prob: float
    edge: float
    kelly_fraction: float
    recommended_bet_usd: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = False
    outcome_won: Optional[bool] = None
    virtual_pnl: Optional[float] = None
    sim_fill_price: Optional[float] = None
    slippage_bps: Optional[float] = None
