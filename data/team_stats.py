"""
Анализ формы команды через Football-data.org API.
Фильтр: не ставить YES на победу, если команда выиграла < 2 из последних 5.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# sport_key -> Football-data competition code
COMPETITION_MAP = {
    "soccer_epl": "PL",
    "soccer_spain_la_liga": "PD",
    "soccer_germany_bundesliga": "BL1",
    "soccer_italy_serie_a": "SA",
    "soccer_france_ligue_one": "FL1",
    "soccer_uefa_champs_league": "CL",
    "soccer_uk_championship": "ELC",
    # soccer_mexico_ligamx — код уточнить в /competitions (free tier может не включать MX)
}


@dataclass
class TeamForm:
    wins: int
    draws: int
    losses: int
    form_pct: float  # wins / (wins+draws+losses) * 100


_last_request_time: float = 0.0
_MIN_INTERVAL = 6.0  # 10 req/min -> ~6 sec between requests


def get_team_form_sync(team_name: str, sport_key: str, last_n: int = 5) -> Optional[TeamForm]:
    """
    Получить форму команды (W/D/L за последние матчи). Синхронная версия.
    Возвращает None при отсутствии API key, ошибке или команда не найдена.
    """
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not api_key:
        return None

    comp_code = COMPETITION_MAP.get((sport_key or "").lower())
    if not comp_code:
        return None

    global _last_request_time
    now = time.monotonic()
    if now - _last_request_time < _MIN_INTERVAL:
        return None  # rate limit
    _last_request_time = now

    base = "https://api.football-data.org/v4"

    def _get(url: str) -> Optional[dict]:
        req = urllib.request.Request(url, headers={"X-Auth-Token": api_key})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            logger.debug("Football-data API: %s", e)
            return None

    # 1. Получить команды лиги
    data = _get(f"{base}/competitions/{comp_code}/teams")
    if not data:
        return None
    teams = data.get("teams", [])
    if not teams:
        return None

    # 2. Найти команду по имени (частичное совпадение)
    team_id = None
    tname_lower = (team_name or "").lower()
    for t in teams:
        name = (t.get("name") or "").lower()
        short = (t.get("shortName") or "").lower()
        if tname_lower in name or tname_lower in short:
            team_id = t.get("id")
            break
        words = [w for w in tname_lower.split() if len(w) > 3]
        if words and any(w in name or w in short for w in words):
            team_id = t.get("id")
            break
    if not team_id:
        return None

    # 3. Получить последние матчи
    data = _get(f"{base}/teams/{team_id}/matches?status=FINISHED&limit={last_n}")
    if not data:
        return None
    result = data.get("resultSet", {})
    wins = result.get("wins", 0) or 0
    draws = result.get("draws", 0) or 0
    losses = result.get("losses", 0) or 0
    total = wins + draws + losses
    if total == 0:
        return None
    form_pct = wins / total * 100
    return TeamForm(wins=wins, draws=draws, losses=losses, form_pct=form_pct)


def should_skip_yes_on_team(form: Optional[TeamForm], min_wins: int = 2, min_form_pct: float = 40.0) -> bool:
    """
    Рекомендация: пропустить YES на победу, если форма слабая.
    """
    if form is None:
        return False  # нет данных — не фильтруем
    if form.wins < min_wins:
        return True  # меньше 2 побед из 5
    if form.form_pct < min_form_pct:
        return True
    return False
