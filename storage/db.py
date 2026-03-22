"""SQLite WAL хранилище для ставок, снимков и отслеживания результатов."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import aiosqlite

from data.models import BetRecord, Side, SnapshotRecord

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_condition_id TEXT NOT NULL,
    market_question TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size_usd REAL NOT NULL,
    edge REAL NOT NULL,
    kelly_fraction REAL NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    order_id TEXT DEFAULT '',
    pnl REAL,
    resolved INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_condition_id TEXT NOT NULL,
    market_question TEXT NOT NULL,
    sport_key TEXT DEFAULT '',
    home_team TEXT DEFAULT '',
    away_team TEXT DEFAULT '',
    side TEXT NOT NULL,
    pm_price REAL NOT NULL,
    pinnacle_true_prob REAL NOT NULL,
    edge REAL NOT NULL,
    kelly_fraction REAL NOT NULL,
    recommended_bet_usd REAL NOT NULL,
    created_at TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    outcome_won INTEGER,
    virtual_pnl REAL,
    sim_fill_price REAL,
    slippage_bps REAL
);

CREATE TABLE IF NOT EXISTS daily_performance (
    date TEXT PRIMARY KEY,
    total_bets INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_wagered REAL DEFAULT 0.0,
    total_pnl REAL DEFAULT 0.0,
    daily_roi REAL DEFAULT 0.0
);
"""


class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._db = await aiosqlite.connect(str(self.path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        # Миграция: добавить sim_fill_price, slippage_bps в snapshots
        for col in ("sim_fill_price", "slippage_bps"):
            try:
                await self._db.execute(f"ALTER TABLE snapshots ADD COLUMN {col} REAL")
                await self._db.commit()
                logger.info("Migration: added column %s to snapshots", col)
            except Exception:
                pass  # колонка уже есть
        logger.info("Database connected: %s", self.path)

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Bets ─────────────────────────────────────────────────

    async def insert_bet(self, bet: BetRecord) -> int:
        cursor = await self._db.execute(
            """INSERT INTO bets
               (market_condition_id, market_question, side, price, size_usd,
                edge, kelly_fraction, mode, status, order_id, pnl, resolved,
                created_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bet.market_condition_id,
                bet.market_question,
                bet.side.value,
                bet.price,
                bet.size_usd,
                bet.edge,
                bet.kelly_fraction,
                bet.mode,
                bet.status,
                bet.order_id,
                bet.pnl,
                int(bet.resolved),
                bet.created_at.isoformat(),
                bet.resolved_at.isoformat() if bet.resolved_at else None,
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def update_bet_status(self, bet_id: int, status: str, order_id: str = ""):
        await self._db.execute(
            "UPDATE bets SET status=?, order_id=? WHERE id=?",
            (status, order_id, bet_id),
        )
        await self._db.commit()

    async def resolve_bet(self, bet_id: int, pnl: float):
        await self._db.execute(
            "UPDATE bets SET resolved=1, pnl=?, resolved_at=?, status='resolved' WHERE id=?",
            (pnl, datetime.utcnow().isoformat(), bet_id),
        )
        await self._db.commit()

    async def get_unresolved_bets(self) -> List[dict]:
        """Незавершённые ставки (resolved=0) для обновления результатов."""
        cursor = await self._db.execute(
            "SELECT * FROM bets WHERE resolved=0 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    async def get_todays_bets(self) -> List[dict]:
        today = self._today_utc_prefix()
        cursor = await self._db.execute(
            "SELECT * FROM bets WHERE created_at LIKE ?", (f"{today}%",)
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    def _today_utc_prefix(self) -> str:
        """Префикс даты для LIKE по created_at (ISO UTC в БД)."""
        return datetime.now(timezone.utc).date().isoformat()

    async def get_todays_pnl(self) -> float:
        """Сумма P&L за календарные сутки UTC только по реальным ставкам (mode=auto)."""
        today = self._today_utc_prefix()
        cursor = await self._db.execute(
            """SELECT COALESCE(SUM(pnl), 0) FROM bets
               WHERE resolved=1 AND LOWER(mode) = 'auto' AND created_at LIKE ?""",
            (f"{today}%",),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else 0.0

    async def get_todays_wagered(self) -> float:
        """Оборот за сутки UTC только auto — recommend не тратит лимит дневного оборота."""
        today = self._today_utc_prefix()
        cursor = await self._db.execute(
            """SELECT COALESCE(SUM(size_usd), 0) FROM bets
               WHERE LOWER(mode) = 'auto' AND created_at LIKE ?""",
            (f"{today}%",),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row else 0.0

    async def get_consecutive_losses(self) -> int:
        """Подряд реальных проигрышей (auto, pnl < 0), от новых к старым."""
        cursor = await self._db.execute(
            """SELECT pnl FROM bets WHERE resolved=1 AND LOWER(mode) = 'auto'
               ORDER BY created_at DESC LIMIT 20"""
        )
        rows = await cursor.fetchall()
        count = 0
        for row in rows:
            pnl = row[0]
            if pnl is None:
                continue
            if pnl < 0:
                count += 1
            else:
                break
        return count

    # ── Snapshots (forward-test) ─────────────────────────────

    async def insert_snapshot(self, snap: SnapshotRecord) -> int:
        cursor = await self._db.execute(
            """INSERT INTO snapshots
               (market_condition_id, market_question, sport_key, home_team,
                away_team, side, pm_price, pinnacle_true_prob, edge,
                kelly_fraction, recommended_bet_usd, created_at,
                resolved, outcome_won, virtual_pnl, sim_fill_price, slippage_bps)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap.market_condition_id,
                snap.market_question,
                snap.sport_key,
                snap.home_team,
                snap.away_team,
                snap.side.value,
                snap.pm_price,
                snap.pinnacle_true_prob,
                snap.edge,
                snap.kelly_fraction,
                snap.recommended_bet_usd,
                snap.created_at.isoformat(),
                int(snap.resolved),
                snap.outcome_won,
                snap.virtual_pnl,
                snap.sim_fill_price,
                snap.slippage_bps,
            ),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_unresolved_snapshots(self) -> List[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM snapshots WHERE resolved=0"
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    async def resolve_snapshot(self, snap_id: int, won: bool, virtual_pnl: float):
        await self._db.execute(
            "UPDATE snapshots SET resolved=1, outcome_won=?, virtual_pnl=? WHERE id=?",
            (int(won), virtual_pnl, snap_id),
        )
        await self._db.commit()

    # ── Stats ────────────────────────────────────────────────

    async def get_overall_stats(self) -> dict:
        cursor = await self._db.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN resolved=1 AND pnl>0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN resolved=1 AND pnl<=0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(size_usd), 0) as wagered,
                COALESCE(SUM(CASE WHEN resolved=1 THEN pnl ELSE 0 END), 0) as pnl
               FROM bets"""
        )
        row = await cursor.fetchone()
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    async def get_snapshot_stats_by_league(self) -> List[dict]:
        """Агрегация WR и ROI по sport_key (лигам)."""
        cursor = await self._db.execute(
            """SELECT
                sport_key,
                COUNT(*) as total,
                SUM(CASE WHEN resolved=1 AND outcome_won=1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN resolved=1 AND outcome_won=0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(CASE WHEN resolved=1 THEN recommended_bet_usd ELSE 0 END), 0) as wagered,
                COALESCE(SUM(CASE WHEN resolved=1 THEN virtual_pnl ELSE 0 END), 0) as pnl
               FROM snapshots
               WHERE sport_key IS NOT NULL AND sport_key != ''
               GROUP BY sport_key
               HAVING total > 0
               ORDER BY total DESC"""
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    async def get_snapshot_stats(self) -> dict:
        cursor = await self._db.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN resolved=1 AND outcome_won=1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN resolved=1 AND outcome_won=0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(recommended_bet_usd), 0) as virtual_wagered,
                COALESCE(SUM(CASE WHEN resolved=1 THEN virtual_pnl ELSE 0 END), 0) as virtual_pnl,
                SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) as pending
               FROM snapshots"""
        )
        row = await cursor.fetchone()
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))

    async def get_recent_bets(self, limit: int = 20) -> List[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM bets ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    async def get_recent_snapshots(self, limit: int = 20) -> List[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM snapshots ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    async def get_resolved_snapshots_for_calibration(self) -> List[dict]:
        """Resolved snapshots для show_signal_calibration: predicted vs actual."""
        cursor = await self._db.execute(
            "SELECT * FROM snapshots WHERE resolved=1 ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    # ── Equity & Drawdown (recommendations BACKTEST 2025) ──────

    async def get_current_equity(self, initial_bankroll: float) -> float:
        """initial_bankroll + сумма PnL по всем разрешённым ставкам."""
        stats = await self.get_overall_stats()
        pnl = stats.get("pnl") or 0
        return initial_bankroll + pnl

    async def get_peak_equity_and_drawdown(self, initial_bankroll: float) -> tuple[float, float]:
        """(peak_equity, current_drawdown_pct). Только auto-ставки — бумажные recommend не влияют."""
        cursor = await self._db.execute(
            """SELECT created_at, pnl FROM bets
               WHERE resolved=1 AND LOWER(mode) = 'auto' ORDER BY created_at ASC"""
        )
        rows = await cursor.fetchall()
        equity = initial_bankroll
        peak = equity
        for _, pnl in rows:
            if pnl is not None:
                equity += pnl
                if equity > peak:
                    peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
        return peak, dd
