"""
Проверка рынков Polymarket по нашим параметрам.
Выводит рынки, подходящие под фильтры analyze_and_place + config.
"""
from __future__ import annotations
import json
import sys
import io
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Параметры из analyze_and_place + config
MIN_LIQUIDITY = 2_000
PRICE_MIN = 0.10
PRICE_MAX = 0.90
BETTING_WINDOW_MIN_H = 2.0
BETTING_WINDOW_MAX_H = 24.0

GAMMA_API = "https://gamma-api.polymarket.com/markets?closed=false&limit=500"
CACHE_DIR = Path(r"C:\Users\Lomov\.cursor\projects\c-Users-Lomov-Documents-Arduino-libraries-M5Unified-src-utility\agent-tools")
NOW = datetime.now(timezone.utc)

TIER1_KW = ["epl", "premier league", "la liga", "bundesliga", "serie a", "ligue 1",
            "champions league", "ucl", "nba", "nfl", "ufc", "mma", "stanley cup", "nhl"]
TIER2_KW = ["liga mx", "ligamx", "mls", "mexico", "championship", "efl"]
SKIP_KW = ["colombia", "betplay", "super lig", "ligue 2"]
SPORT_KW = [
    "win", "beat", " vs ", "o/u", "over", "under", "total",
    "nba", "nhl", "nfl", "ufc", "mlb", "epl", "ucl",
    "fc ", " fc", "afc", "tennis", "match", "fight", "bout",
    "arsenal", "chelsea", "liverpool", "tottenham", "manchester",
    "villa", "city", "united", "lakers", "celtics", "warriors",
    "nuggets", "bucks", "hurricanes", "stanley cup",
    "world cup", "fifa", "handicap", "rybakina", "kartal",
    "middlesbrough", "charlton", "ly ", "loud",
]


def league_tier(q: str) -> int:
    ql = (q or "").lower()
    if any(s in ql for s in SKIP_KW):
        return 0
    if any(t in ql for t in TIER2_KW):
        return 2
    if any(t in ql for t in TIER1_KW):
        return 1
    if any(k in ql for k in SPORT_KW):
        return 1
    return 0


def main():
    print("  Загрузка рынков Polymarket...")
    try:
        with urllib.request.urlopen(GAMMA_API, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        print(f"  API: загружено {len(data)} рынков")
    except Exception as e:
        print(f"  API недоступен: {e}. Пробуем кэш...")
        data = []
        for fp in sorted(CACHE_DIR.glob("*.txt"))[:10]:
            try:
                data.extend(json.load(open(fp, encoding="utf-8")))
            except Exception:
                pass
        if not data:
            print("  [!] Нет данных.")
            return
        print(f"  Кэш: загружено {len(data)} записей")

    seen_cids = set()
    in_window = []
    out_window = []
    skipped = {"sport_kw": 0, "tier": 0, "liq": 0, "price": 0, "ended": 0, "time": 0}

    for m in data:
        cid = m.get("conditionId", "") or m.get("id", "")
        if cid in seen_cids:
            continue
        seen_cids.add(cid)

        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                prices = []
        if len(prices) < 2:
            continue

        liq = float(m.get("liquidity", 0) or 0)
        if liq < MIN_LIQUIDITY:
            skipped["liq"] += 1
            continue

        yes_p = float(prices[0])
        no_p = float(prices[1])
        if not (PRICE_MIN < yes_p < PRICE_MAX):
            skipped["price"] += 1
            continue

        end_raw = m.get("endDate", "")
        end_dt = None
        if end_raw:
            try:
                end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            except Exception:
                pass
        if end_dt and end_dt < NOW:
            skipped["ended"] += 1
            continue

        q = m.get("question", "")
        if not any(kw in q.lower() for kw in SPORT_KW):
            skipped["sport_kw"] += 1
            continue

        tier = league_tier(q)
        if tier == 0:
            skipped["tier"] += 1
            continue

        hours_to_start = (end_dt - NOW).total_seconds() / 3600.0 if end_dt else 999

        rec = {
            "q": q,
            "yes": yes_p,
            "no": no_p,
            "liq": liq,
            "tier": "T1" if tier == 1 else "T2",
            "hours": hours_to_start,
            "end": end_dt.strftime("%d.%m %H:%M") if end_dt else "?",
        }

        if BETTING_WINDOW_MIN_H <= hours_to_start <= BETTING_WINDOW_MAX_H:
            in_window.append(rec)
        elif hours_to_start > 0:
            if hours_to_start > BETTING_WINDOW_MAX_H:
                skipped["time"] += 1
            out_window.append(rec)

    print("\n" + "=" * 80)
    print(f"  РЫНКИ В ОКНЕ 2–24 ЧАСА (полностью подходят) — {NOW.strftime('%d.%m.%Y %H:%M UTC')}")
    print("=" * 80)
    if not in_window:
        print("  (нет рынков в окне 2–24ч)")
    else:
        for i, r in enumerate(sorted(in_window, key=lambda x: (-x["liq"], x["hours"])), 1):
            side = "YES" if r["yes"] < 0.60 else ("NO" if r["yes"] <= 0.65 else "—")
            ou = "O/U×0.5" if any(k in r["q"].lower() for k in ["o/u", "over", "under", "total"]) else ""
            print(f"\n  #{i} [{r['tier']}] {side}  YES={r['yes']:.2f}  Liq=${r['liq']:,.0f}  через {r['hours']:.0f}ч  {ou}")
            print(f"  {r['q'][:75]}")
            print(f"  Окончание: {r['end']}")

    print("\n" + "-" * 80)
    print("  РЫНКИ ВНЕ ОКНА (подходят по лиге/ликвидности, но не по времени)")
    print("-" * 80)
    out_sorted = sorted(out_window, key=lambda x: (x["hours"], -x["liq"]))
    # Группы: слишком рано (>24ч), слишком поздно (<2ч)
    early = [r for r in out_sorted if r["hours"] > BETTING_WINDOW_MAX_H]
    late = [r for r in out_sorted if 0 < r["hours"] < BETTING_WINDOW_MIN_H]
    if early:
        print(f"\n  Слишком рано (>{BETTING_WINDOW_MAX_H}ч до матча): {len(early)}")
        for r in early[:15]:
            side = "YES" if r["yes"] < 0.60 else ("NO" if r["yes"] <= 0.65 else "—")
            print(f"    {r['hours']:.0f}ч  [{r['tier']}] {side}  Liq=${r['liq']:,.0f}  {r['q'][:55]}...")
        if len(early) > 15:
            print(f"    ... и ещё {len(early) - 15}")
    if late:
        print(f"\n  Слишком поздно (<{BETTING_WINDOW_MIN_H}ч до матча): {len(late)}")
        for r in late[:10]:
            print(f"    {r['hours']:.1f}ч  [{r['tier']}]  Liq=${r['liq']:,.0f}  {r['q'][:55]}...")

    print("\n" + "-" * 80)
    print("  СВОДКА ОТСЕВА")
    print("-" * 80)
    print(f"  Отсеяно: нет спорт-слова {skipped['sport_kw']}, tier=0 {skipped['tier']}, liq<2k {skipped['liq']},")
    print(f"           price вне 0.1–0.9 {skipped['price']}, завершён {skipped['ended']}, вне окна 2–24ч {skipped['time']}")
    print(f"  В окне 2–24ч: {len(in_window)}  |  Вне окна (но подходят): {len(out_window)}")
    print()


if __name__ == "__main__":
    main()
