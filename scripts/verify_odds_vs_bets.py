#!/usr/bin/env python3
"""Проверка The Odds API и сопоставление Pinnacle h2h со ставками в agent.db."""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import Settings  # noqa: E402
from data.models import Market  # noqa: E402
from data.odds_api import OddsApiClient, match_odds_to_markets  # noqa: E402

DB_PATH = ROOT / "agent.db"
SPORTS_URL = "https://api.the-odds-api.com/v4/sports/"


async def check_quota(api_key: str) -> tuple[int, str, str]:
    """Один лёгкий запрос к API — статус и лимиты."""
    async with aiohttp.ClientSession() as session:
        async with session.get(SPORTS_URL, params={"apiKey": api_key}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            rem = resp.headers.get("x-requests-remaining", "?")
            used = resp.headers.get("x-requests-used", "?")
            return resp.status, rem, used


def load_bets(limit: int = 200) -> list[sqlite3.Row]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """SELECT id, market_condition_id, market_question, side, price, edge, resolved, status
           FROM bets ORDER BY id DESC LIMIT ?""",
        (limit,),
    )
    rows = list(cur.fetchall())
    conn.close()
    return rows


def markets_from_bets(rows: list[sqlite3.Row]) -> list[Market]:
    seen: set[str] = set()
    out: list[Market] = []
    for r in rows:
        cid = str(r["market_condition_id"] or "")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append(
            Market(
                condition_id=cid,
                question=str(r["market_question"] or ""),
            )
        )
    return out


async def main() -> None:
    settings = Settings()
    if not settings.odds_api_key:
        print("[ОШИБКА] В .env нет ODDS_API_KEY")
        sys.exit(1)

    print("=== 1. Проверка The Odds API (список sports) ===")
    status, rem, used = await check_quota(settings.odds_api_key)
    if status == 401:
        print(f"HTTP {status}: неверный API-ключ.")
        sys.exit(1)
    if status == 429:
        print(f"HTTP {status}: лимит запросов.")
        sys.exit(1)
    if status != 200:
        print(f"HTTP {status}: неожиданный ответ.")
        sys.exit(1)
    print(f"OK. x-requests-remaining={rem}, x-requests-used={used}")

    print("\n=== 2. Загрузка Pinnacle h2h по лигам из настроек ===")
    client = OddsApiClient(settings)
    try:
        lines = await client.fetch_all_odds()
    finally:
        await client.close()
    print(f"Событий (линий) получено: {len(lines)}")

    rows = load_bets()
    print(f"\n=== 3. Ставки в {DB_PATH.name} (последние записи) ===")
    if not rows:
        print("Таблица bets пуста или БД отсутствует — сопоставлять нечего.")
        return

    markets = markets_from_bets(rows)
    matches = match_odds_to_markets(lines, markets)
    by_cid: dict[str, tuple] = {}
    for line, market, team in matches:
        if market.condition_id not in by_cid:
            by_cid[market.condition_id] = (line, team)

    matched = sum(1 for r in rows if str(r["market_condition_id"] or "") in by_cid)
    print(f"Строк ставок в выборке: {len(rows)}; уникальных рынков: {len(markets)}")
    print(f"Сопоставлено с текущей линией Pinnacle: {matched} строк / {len(by_cid)} рынков\n")

    print("=== 4. Детали (до 40 последних ставок) ===")
    shown = 0
    for r in rows:
        if shown >= 40:
            break
        shown += 1
        cid = str(r["market_condition_id"] or "")
        q = (r["market_question"] or "").replace("\n", " ")[:100]
        side = r["side"]
        price = float(r["price"] or 0)
        edge_db = r["edge"]
        res = "закрыта" if r["resolved"] else "открыта"

        if cid in by_cid:
            line, matched_team = by_cid[cid]
            outs = " | ".join(
                f"{o.name}: {o.price:.2f} (p*~{o.true_prob:.3f})" for o in line.outcomes
            )
            print(f"[MATCH] #{r['id']} {res} {side} @ {price:.3f}  edge_в_бд={edge_db}")
            print(f"        {line.sport_key}  {line.home_team} — {line.away_team}")
            print(f"        Pinnacle: {outs}")
            print(f"        Вопрос: {q}")
            print(f"        matched_team: {matched_team}")
        else:
            print(f"[ --- ] #{r['id']} {res} {side} @ {price:.3f} — нет совпадения с h2h из API")
            print(f"        {q}")
        print()

    print("Примечание: совпадение только для рынков, где в тексте вопроса узнаются")
    print("команды из события (как в main.py). Политика/прочее — [ --- ].")


if __name__ == "__main__":
    asyncio.run(main())
