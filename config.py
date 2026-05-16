from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(Path(__file__).parent / ".env")

# Вероятность ничьей по лиге (для коррекции Kelly в match-winner). 0 = нет коррекции.
DRAW_PROB_BY_LEAGUE: dict[str, float] = {
    "soccer_epl": 0.27,
    "soccer_spain_la_liga": 0.26,
    "soccer_germany_bundesliga": 0.26,
    "soccer_italy_serie_a": 0.27,
    "soccer_france_ligue_one": 0.27,
    "soccer_uefa_champs_league": 0.25,
    "soccer_uk_championship": 0.26,
    "soccer_mexico_ligamx": 0.30,
    "soccer_usa_mls": 0.28,
    "soccer_colombia": 0.30,
    "soccer_colombia_ligamx": 0.30,
}


def get_draw_prob(sport_key: str) -> float:
    """Вернуть вероятность ничьей для лиги. 0 для NBA/UFC и др."""
    sk = (sport_key or "").lower()
    return DRAW_PROB_BY_LEAGUE.get(sk, 0.0)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Polymarket (необязательно для режима рекомендаций)
    polymarket_private_key: str = ""
    polymarket_funder_address: str = ""
    # CLOB: 0 = EOA (MetaMask и т.д.), 1 = Polymarket proxy (часто email-логин) — см. py_order_utils
    polymarket_signature_type: int = 0

    # Котировки букмекеров
    odds_api_key: str = ""
    football_data_api_key: str = ""  # football-data.org (см. .env.example)
    sports: List[str] = [
        "basketball_nba",
        "soccer_epl",
        "soccer_uk_championship",
        "soccer_uefa_champs_league",
        "soccer_mexico_ligamx",
        "mma_mixed_martial_arts",
    ]

    # Стратегия
    kelly_multiplier: float = 0.25
    min_edge: float = 0.03  # 3% — только реальный edge от Pinnacle
    min_liquidity: float = 1000.0

    # Фильтры (по анализу убытков)
    no_bet_max_yes: float = 0.65  # Запрет NO если YES > 65% (ставка против рынка)
    betting_window_hours_min: float = 2.0   # Не ставить за <2ч (line movement)
    betting_window_hours_max: float = 24.0  # Не ставить за >24ч (смена состава)

    # Лимиты
    min_bet_usd: float = 18.0  # Минимальный размер ставки после всех кэпов (risk + исполнение)
    max_bet_pct: float = 0.05
    max_bet_usd: float = 18.0  # Держим равным min_bet_usd для фиксированной ставки в авто-режиме
    max_slippage: float = 0.02
    daily_loss_limit: float = 12.0
    max_daily_wager_pct: float = 0.30  # Макс. доля банкролла в обороте за сутки (только auto)
    max_consecutive_losses: int = 3  # После 3 проигрышей подряд — пауза 24ч
    max_drawdown_pct: float = 25.0  # Пауза ставок при просадке от пика (BACKTEST 2025)
    drawdown_alert_pct: float = 15.0  # Алерт в лог при просадке
    # 0 = использовать max_bet_usd * 2 (как раньше); иначе явный пол банкролла для auto/real
    min_bankroll: float = 0.0

    # Лиги: Tier1 = полный Kelly, Tier2 = Kelly×0.10 (см. league_detector)

    # Коррекция на ничью для футбола (fix-draw-probability-correction)
    # Kelly использует p_effective = true_prob * (1 - draw_prob) для match-winner
    draw_prob: float = 0.0  # 0 = без коррекции. Задаётся по sport_key в get_draw_prob()

    # Анализ формы команды (fix-team-form-analysis). Нужен FOOTBALL_DATA_API_KEY в .env
    use_team_form_filter: bool = True  # False = отключить фильтр формы

    # Калибровка Kelly (сегмент 2): после forward-test задайте CALIBRATION_KELLY_MULT < 1 при завышении edge
    kelly_calibration_enabled: bool = False
    calibration_kelly_multiplier: float = 1.0
    calibration_min_samples: int = 40
    calibration_full_confidence_samples: int = 200
    calibration_min_multiplier: float = 0.5
    calibration_max_multiplier: float = 1.4

    # Алерты: POST JSON на URL при жёстких стопах риска (drawdown / дневной лимит)
    alert_webhook_url: str = ""

    # Инфраструктура
    poll_interval: int = 60
    collector_latency_warn_ms: int = 6000

    # Исполнение (task-maker-first): GTC + post_only, цена best_bid + N тиков (не пересекает ask)
    use_maker_first: bool = False
    maker_tick_offset: int = 1
    maker_tick_size: float = 0.01

    # Kalshi (каркас; см. integrations/kalshi_client.py)
    kalshi_api_key: str = ""

    # Эндпоинты Polymarket
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"
    chain_id: int = 137

    @field_validator("sports", mode="before")
    @classmethod
    def parse_sports(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


def load_settings(mode: str = "recommend") -> Settings:
    """Загрузка и валидация настроек. Завершает работу при отсутствии обязательных ключей."""
    settings = Settings()

    if not settings.odds_api_key:
        print("[ОШИБКА] ODDS_API_KEY обязателен. Получите на https://the-odds-api.com")
        sys.exit(1)

    if mode == "auto":
        if not settings.polymarket_private_key:
            print("[ОШИБКА] POLYMARKET_PRIVATE_KEY обязателен для авто-режима.")
            sys.exit(1)
        if not settings.polymarket_funder_address:
            print("[ОШИБКА] POLYMARKET_FUNDER_ADDRESS обязателен для авто-режима.")
            sys.exit(1)
        print(
            "[ВНИМАНИЕ] Авто-режим использует приватный ключ в открытом виде. "
            "Убедитесь, что .env в .gitignore и никогда не коммитьте его."
        )

    return settings
