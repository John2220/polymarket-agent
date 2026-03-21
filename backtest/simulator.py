"""
Симуляция исполнения по order book (paper trader).

Вычисляет sim_fill_price и slippage_bps для forward-test.
"""
from __future__ import annotations

from typing import Tuple

from data.models import OrderBook


def sim_fill_orderbook(
    ob: OrderBook,
    side: str,
    shares: float,
    ref_price: float,
) -> Tuple[float, float]:
    """
    Симулировать исполнение по стакану.

    Для BUY (YES/NO): идём по asks (ascending by price).
    Возвращает (volume_weighted_avg_fill_price, slippage_bps).
    slippage_bps = (fill_price - ref_price) / ref_price * 10000.
    """
    if shares <= 0 or ref_price <= 0:
        return ref_price, 0.0

    if side.upper() in ("YES", "NO"):
        # Buy — идём по asks
        levels = sorted(ob.asks, key=lambda x: x.price) if ob.asks else []
    else:
        return ref_price, 0.0

    if not levels:
        return ref_price, 0.0

    filled = 0.0
    cost = 0.0
    remaining = shares

    for lev in levels:
        if remaining <= 0:
            break
        take = min(lev.size, remaining)
        cost += lev.price * take
        filled += take
        remaining -= take

    if filled <= 0:
        return ref_price, 0.0

    fill_price = cost / filled
    slippage_bps = (fill_price - ref_price) / ref_price * 10000.0
    return round(fill_price, 4), round(slippage_bps, 1)
