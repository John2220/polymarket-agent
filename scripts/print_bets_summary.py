"""Одноразовый вывод сводки по agent.db (ставки + snapshots)."""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB = ROOT / "agent.db"


def main() -> None:
    if not DB.exists():
        print("agent.db не найден.")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print("Таблицы:", ", ".join(tables))
    print()

    for name in ("bets", "snapshots", "daily_performance"):
        try:
            rows = list(conn.execute(f"SELECT * FROM {name}"))
        except sqlite3.OperationalError:
            continue
        if not rows:
            print(f"### {name}: пусто\n")
            continue
        cols = rows[0].keys()
        print(f"### {name} ({len(rows)} строк)\n")
        print("| " + " | ".join(cols) + " |")
        print("| " + " | ".join("---" for _ in cols) + " |")
        for r in rows:
            print("| " + " | ".join(str(r[c]) if r[c] is not None else "—" for c in cols) + " |")
        print()

    conn.close()

    async def stats():
        from storage.db import Database

        db = Database(DB)
        await db.connect()
        try:
            o = await db.get_overall_stats()
            print("### Агрегат bets (get_overall_stats)\n")
            for k, v in o.items():
                print(f"- **{k}:** {v}")
            s = await db.get_snapshot_stats()
            print("\n### Агрегат snapshots (get_snapshot_stats)\n")
            for k, v in s.items():
                print(f"- **{k}:** {v}")
        finally:
            await db.close()

    asyncio.run(stats())


if __name__ == "__main__":
    main()
