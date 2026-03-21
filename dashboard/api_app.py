"""
Лёгкий REST API: /stats и /signals (JSON) — альтернатива MCP для инструментов и дашбордов.

Запуск: python scripts/run_api.py
  или: uvicorn dashboard.api_app:app --host 127.0.0.1 --port 8765

Зависимости: pip install fastapi uvicorn
"""
from __future__ import annotations

from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from storage.db import Database, DB_PATH

app = FastAPI(
    title="Polymarket Agent API",
    description="Forward-test stats и последние snapshots",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    """Агрегированная статистика snapshots (как вкладка Streamlit)."""
    db = Database(DB_PATH)
    await db.connect()
    try:
        s = await db.get_snapshot_stats()
        return JSONResponse(s)
    finally:
        await db.close()


@app.get("/signals")
async def signals(limit: int = 50):
    """Последние сигналы / snapshots."""
    limit = max(1, min(limit, 500))
    db = Database(DB_PATH)
    await db.connect()
    try:
        rows = await db.get_recent_snapshots(limit=limit)
        return JSONResponse({"count": len(rows), "items": rows})
    finally:
        await db.close()


@app.get("/bets/summary")
async def bets_summary():
    """Кратко по таблице bets (если используется)."""
    db = Database(DB_PATH)
    await db.connect()
    try:
        st = await db.get_overall_stats()
        return JSONResponse(st)
    finally:
        await db.close()
