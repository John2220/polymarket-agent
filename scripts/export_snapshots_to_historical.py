#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт resolved snapshots в JSON для исторического бэктеста.

Формат: historical_events.json (совместим с backtest/historical.load_historical_events)
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _snapshot_to_event(snap: dict) -> dict:
    """Преобразовать snapshot в формат HistoricalEvent."""
    side = (snap.get("side") or "YES").upper()
    outcome_won = bool(snap.get("outcome_won"))
    pinnacle_true = float(snap.get("pinnacle_true_prob") or 0.5)
    pm_price = float(snap.get("pm_price") or 0.5)

    if side == "YES":
        pinnacle_yes_prob = pinnacle_true
        pm_yes_price = pm_price
        outcome = "Yes" if outcome_won else "No"
    else:
        pinnacle_yes_prob = 1.0 - pinnacle_true
        pm_yes_price = 1.0 - pm_price
        outcome = "No" if outcome_won else "Yes"

    created = snap.get("created_at") or ""
    if isinstance(created, str):
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now()
    else:
        dt = datetime.now()

    return {
        "sport_key": snap.get("sport_key") or "",
        "home_team": snap.get("home_team") or "",
        "away_team": snap.get("away_team") or "",
        "commence_time": dt.isoformat(),
        "pinnacle_yes_prob": round(pinnacle_yes_prob, 4),
        "pm_yes_price": round(pm_yes_price, 4),
        "matched_team": snap.get("home_team") or "",
        "outcome": outcome,
    }


async def main():
    from storage.db import Database

    db = Database()
    await db.connect()
    snaps = await db.get_resolved_snapshots_for_calibration()
    await db.close()

    events = [_snapshot_to_event(s) for s in snaps]
    out_path = ROOT / "data" / "historical_events.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"events": events}, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(events)} events to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
