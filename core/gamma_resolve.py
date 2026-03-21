"""
Разрешение исходов Gamma API: флаг resolved часто отсутствует при closed=true.

Безопасно только для бинарных рынков с исходами Yes/No (не «Yankees vs Red Sox»).
"""
from __future__ import annotations

import json
from typing import Any, Optional


def float_or_zero(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _outcomes_list(m: dict) -> list:
    raw = m.get("outcomes", "[]")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


def binary_outcome_yes_no(m: dict) -> Optional[str]:
    """
    Исход «Yes» или «No» для стандартного бинарного рынка.
    Для прочих (два именованных исхода) — только если в поле outcome явно Yes/No.
    """
    outcomes = _outcomes_list(m)
    is_yes_no = False
    if len(outcomes) >= 2:
        o0, o1 = str(outcomes[0]).strip().lower(), str(outcomes[1]).strip().lower()
        is_yes_no = {o0, o1} == {"yes", "no"}

    o = m.get("outcome")
    if o is not None and str(o).strip():
        os_ = str(o).strip().lower()
        if os_ in ("yes", "no"):
            return "Yes" if os_ == "yes" else "No"
        if not is_yes_no:
            return None

    if not is_yes_no:
        return None

    prices = m.get("outcomePrices", [])
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            return None
    if isinstance(prices, list) and len(prices) >= 2:
        y, n = float_or_zero(prices[0]), float_or_zero(prices[1])
        if y > 0.99:
            return "Yes"
        if n > 0.99:
            return "No"
    return None


def market_fully_resolved(m: dict) -> bool:
    """Рынок закрыт с определённым исходом, с которым можно сопоставить Yes/No-ставку."""
    if m.get("resolved") and binary_outcome_yes_no(m) is not None:
        return True
    if not m.get("closed"):
        return False
    return binary_outcome_yes_no(m) is not None


def is_yes_side(side: str) -> bool:
    return str(side or "").strip().upper() in ("YES", "ДА")


def is_no_side(side: str) -> bool:
    return str(side or "").strip().upper() in ("NO", "НЕТ")


def bet_won_for_binary_market(side: str, m: dict) -> Optional[bool]:
    """
    True/False если исход однозначен для Yes/No рынка; None если авто-resolve невозможен.
    """
    ob = binary_outcome_yes_no(m)
    if ob is None:
        return None
    if is_yes_side(side):
        return ob == "Yes"
    if is_no_side(side):
        return ob == "No"
    return None
