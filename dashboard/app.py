"""
Streamlit dashboard для Polymarket Analytics Agent.

Запуск: streamlit run dashboard/app.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from storage.db import Database, DB_PATH


def run_async(coro):
    """Выполнить async-корутину в sync контексте Streamlit."""
    return asyncio.run(coro)


async def load_snapshot_stats():
    db = Database(DB_PATH)
    await db.connect()
    try:
        return await db.get_snapshot_stats()
    finally:
        await db.close()


async def load_snapshots_by_league():
    db = Database(DB_PATH)
    await db.connect()
    try:
        return await db.get_snapshot_stats_by_league()
    finally:
        await db.close()


async def load_recent_snapshots(limit: int = 50):
    db = Database(DB_PATH)
    await db.connect()
    try:
        return await db.get_recent_snapshots(limit=limit)
    finally:
        await db.close()


async def load_betting_stats():
    db = Database(DB_PATH)
    await db.connect()
    try:
        return await db.get_overall_stats()
    finally:
        await db.close()


def main():
    st.set_page_config(
        page_title="Polymarket Analytics",
        page_icon="📊",
        layout="wide",
    )
    st.title("📊 Polymarket Analytics Agent")
    st.caption("Value betting на Polymarket + Pinnacle | Forward-test статистика")

    tab1, tab2, tab3 = st.tabs(["📈 Forward-Test Stats", "🏆 По лигам", "📋 Последние записи"])

    with tab1:
        st.subheader("Общая статистика Forward-Test")
        try:
            stats = run_async(load_snapshot_stats())
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")
        else:
            total = stats.get("total", 0) or 0
            wins = stats.get("wins", 0) or 0
            losses = stats.get("losses", 0) or 0
            pending = stats.get("pending", 0) or 0
            virtual_pnl = stats.get("virtual_pnl", 0.0) or 0.0
            virtual_wagered = stats.get("virtual_wagered", 0.0) or 0.0
            resolved = wins + losses

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Всего записей", total)
            c2.metric("Завершено", resolved)
            c3.metric("Ожидают", pending)
            if resolved > 0:
                wr = wins / resolved * 100
                roi = virtual_pnl / virtual_wagered * 100 if virtual_wagered > 0 else 0
                c4.metric("Win Rate", f"{wr:.1f}%")
                c5.metric("ROI", f"{roi:.1f}%")
            st.metric("Виртуальный P&L", f"${virtual_pnl:.2f}")
            st.metric("Виртуальный оборот", f"${virtual_wagered:.2f}")

    with tab2:
        st.subheader("WR и ROI по лигам")
        try:
            rows = run_async(load_snapshots_by_league())
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")
        else:
            if not rows:
                st.info("Нет данных по лигам (sport_key)")
            else:
                data = []
                for r in rows:
                    wins = r.get("wins", 0) or 0
                    losses = r.get("losses", 0) or 0
                    resolved = wins + losses
                    wagered = r.get("wagered", 0) or 0
                    pnl = r.get("pnl", 0) or 0
                    data.append({
                        "Лига": r.get("sport_key", ""),
                        "N": r.get("total", 0),
                        "WR %": round(wins / resolved * 100, 1) if resolved > 0 else 0.0,
                        "ROI %": round(pnl / wagered * 100, 1) if wagered > 0 else 0.0,
                        "P&L $": f"${pnl:.2f}",
                    })
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)

    with tab3:
        st.subheader("Последние записи Forward-Test")
        try:
            snaps = run_async(load_recent_snapshots(50))
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")
        else:
            if not snaps:
                st.info("Нет записей")
            else:
                df = pd.DataFrame([
                    {
                        "Дата": str(s.get("created_at", ""))[:19],
                        "Рынок": (s.get("market_question") or "")[:50],
                        "Сторона": "ДА" if s.get("side") == "YES" else "НЕТ",
                        "PM цена": s.get("pm_price"),
                        "Sim fill": s.get("sim_fill_price"),
                        "Slip bps": s.get("slippage_bps"),
                        "Edge": s.get("edge"),
                        "Ставка $": s.get("recommended_bet_usd"),
                        "Результат": (
                            "ВЫИГРЫШ" if s.get("outcome_won") else "ПРОИГРЫШ"
                            if s.get("resolved") else "ожидание"
                        ),
                        "P&L": s.get("virtual_pnl"),
                    }
                    for s in snaps
                ])
                st.dataframe(df, use_container_width=True)

    st.sidebar.markdown("### Обновление")
    if st.sidebar.button("Обновить данные"):
        st.rerun()


if __name__ == "__main__":
    main()
