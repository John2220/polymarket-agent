"""Получение точных котировок от The Odds API (Pinnacle) и сопоставление с рынками Polymarket."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from data.models import Market, OddsLine, OddsOutcome

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
TIMEOUT = aiohttp.ClientTimeout(total=30)


class OddsApiClient:
    def __init__(self, settings: Settings):
        self.api_key = settings.odds_api_key
        self.sports = settings.sports
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @retry(wait=wait_exponential(min=1, max=16), stop=stop_after_attempt(3))
    async def fetch_odds(self, sport_key: str) -> List[OddsLine]:
        """Fetch Pinnacle h2h odds for a single sport."""
        session = await self._get_session()
        params = {
            "apiKey": self.api_key,
            "regions": "eu",
            "markets": "h2h",
            "bookmakers": "pinnacle",
            "oddsFormat": "decimal",
        }
        url = f"{BASE_URL}/sports/{sport_key}/odds/"
        async with session.get(url, params=params) as resp:
            if resp.status == 401:
                logger.error("Invalid Odds API key")
                return []
            if resp.status == 429:
                logger.warning("Odds API rate limit reached for %s", sport_key)
                return []
            resp.raise_for_status()
            data = await resp.json()

        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(
            "Fetched %d events for %s (API requests remaining: %s)",
            len(data), sport_key, remaining,
        )

        lines: List[OddsLine] = []
        for event in data:
            for bm in event.get("bookmakers", []):
                if bm["key"] != "pinnacle":
                    continue
                for mkt in bm.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    outcomes = []
                    for o in mkt.get("outcomes", []):
                        price = float(o["price"])
                        imp = 1.0 / price if price > 0 else 0.0
                        outcomes.append(
                            OddsOutcome(
                                name=o["name"],
                                price=price,
                                implied_prob=imp,
                            )
                        )
                    line = OddsLine(
                        sport_key=event.get("sport_key", sport_key),
                        sport_title=event.get("sport_title", ""),
                        home_team=event.get("home_team", ""),
                        away_team=event.get("away_team", ""),
                        commence_time=datetime.fromisoformat(
                            event["commence_time"].replace("Z", "+00:00")
                        ),
                        bookmaker="pinnacle",
                        outcomes=outcomes,
                    )
                    line.devig()
                    lines.append(line)
        return lines

    async def fetch_all_odds(self) -> List[OddsLine]:
        """Fetch Pinnacle odds for all configured sports."""
        all_lines: List[OddsLine] = []
        for sport in self.sports:
            try:
                lines = await self.fetch_odds(sport)
                all_lines.extend(lines)
            except Exception as exc:
                logger.error("Failed to fetch odds for %s: %s", sport, exc)
        return all_lines


# ── Matching logic: OddsLine → Polymarket Market ────────────

def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _team_in_question(team: str, question: str) -> bool:
    """Check if any significant word of a team name appears in question."""
    norm_q = _normalize(question)
    words = _normalize(team).split()
    significant = [w for w in words if len(w) > 2]
    if not significant:
        significant = words
    return any(w in norm_q for w in significant)


def match_odds_to_markets(
    odds_lines: List[OddsLine],
    markets: List[Market],
) -> List[Tuple[OddsLine, Market, str]]:
    """
    Match OddsLine events to Polymarket markets.

    Returns list of (odds_line, market, matched_team_name).
    Only matches markets whose question mentions both teams
    or one team in a "will X win" pattern.
    """
    matches: List[Tuple[OddsLine, Market, str]] = []

    for line in odds_lines:
        for market in markets:
            q = market.question
            home_match = _team_in_question(line.home_team, q)
            away_match = _team_in_question(line.away_team, q)

            if home_match and away_match:
                # Market mentions both teams — figure out which side is YES
                # Usually the question asks "Will <team> win?"
                for outcome in line.outcomes:
                    if _team_in_question(outcome.name, q):
                        matches.append((line, market, outcome.name))
                        break
                else:
                    matches.append((line, market, line.home_team))
            elif home_match or away_match:
                matched_team = line.home_team if home_match else line.away_team
                matches.append((line, market, matched_team))

    logger.info("Matched %d (odds_line, market) pairs", len(matches))
    return matches
