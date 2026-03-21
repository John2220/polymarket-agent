"""
Сигналы кросс-площадочного арбитража Polymarket ↔ Kalshi (task-kalshi-cross-venue).

Использование после реализации integrations.kalshi_client.KalshiClient.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from data.models import Market


@dataclass
class ArbOpportunity:
    venue_a: str
    venue_b: str
    edge_estimate: float
    note: str


def find_simple_binary_arb(
    pm_market: Market,
    other_yes_ask: float,
    other_yes_bid: float,
) -> List[ArbOpportunity]:
    """
    Упрощённая проверка: если YES на PM + YES на другой площадке < 1 (после комиссий).

    Заглушка — возвращает пустой список; дополнить fee schedule и ликвидность.
    """
    _ = (pm_market, other_yes_ask, other_yes_bid)
    return []
