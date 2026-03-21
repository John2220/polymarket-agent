"""
Заготовка клиента Kalshi для cross-venue арбитража (task-kalshi-cross-venue).

Требуется: API-ключи Kalshi, спецификация контрактов (см. docs.kalshi.com).
Реализацию методов добавить после получения доступа.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class KalshiEventStub:
    """Упрощённое событие Kalshi для сопоставления с Polymarket."""

    ticker: str
    title: str
    yes_bid: float = 0.0
    yes_ask: float = 0.0


class KalshiClient:
    """Клиент Kalshi API — каркас, вызовы без настроенного окружения не выполняются."""

    def __init__(self, api_key: str = "", base_url: str = "https://api.elections.kalshi.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def list_events(self, limit: int = 50) -> List[KalshiEventStub]:
        if not self.is_configured():
            raise RuntimeError(
                "KalshiClient: задайте KALSHI_API_KEY в .env и реализуйте HTTP-запросы "
                "по официальной документации."
            )
        return []

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        raise NotImplementedError("kalshi_client.get_orderbook: реализовать после API key")


def match_events_pm_to_kalshi(
    pm_questions: List[str],
    kalshi_events: List[KalshiEventStub],
) -> List[tuple[str, str]]:
    """
    Сопоставить вопросы Polymarket с тикерами Kalshi (заглушка: пустой список).

    Полная версия: нормализация команд/дат, fuzzy match, ручной whitelist.
    """
    _ = (pm_questions, kalshi_events)
    return []
