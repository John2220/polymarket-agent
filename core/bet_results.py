"""
Расчёт P&L для ставок Polymarket — единый модуль для всех скриптов.

См. FORMULAS_AUDIT.md (2026-03-11)
"""
from __future__ import annotations


def snapshot_entry_price(snap: dict) -> float:
    """
    Цена входа для forward-test P&L: при наличии симуляции стакана — sim_fill_price,
    иначе pm_price (оценка по лучшему уровню / mid без проскальзывания).
    """
    sim = snap.get("sim_fill_price")
    try:
        if sim is not None and float(sim) > 0:
            return float(sim)
    except (TypeError, ValueError):
        pass
    try:
        pm = float(snap.get("pm_price") or 0)
        return pm if pm > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def calc_pnl(bet: float, price: float, won: bool) -> float:
    """
    P&L для ставки на Polymarket (YES или NO).

    price — цена купленной доли (колонка 7 Excel).
    Одинаковая формула для YES и NO.
    """
    if won:
        if price <= 0 or price >= 1:
            return 0.0
        return round(bet * (1 / price - 1), 2)
    return round(-bet, 2)
