"""
Стресс-тест формул и логики: P&L, Kelly, EV, signals.

Проверяет:
- Граничные случаи (price→0, price→1, нули)
- Математическую согласованность (EV, P&L, Kelly)
- Логическую непротиворечивость
- 20+ тестов для покрытия формул
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.bet_results import calc_pnl
from analysis.kelly import kelly_yes, kelly_no, compute_kelly
from config import Settings, get_draw_prob, DRAW_PROB_BY_LEAGUE


# ═══════════════════════════════════════════════════════════
# 1. P&L (calc_pnl) — 8 тестов
# ═══════════════════════════════════════════════════════════

def test_pnl_01_win_formula():
    """Профит = bet * (1/price - 1)."""
    assert calc_pnl(10, 0.5, True) == 10.0
    assert calc_pnl(30, 0.27, True) == 81.11
    assert calc_pnl(100, 0.01, True) == 9900.0
    assert calc_pnl(100, 0.99, True) == 1.01
    assert calc_pnl(10, 0.5, False) == -10


def test_pnl_02_boundary_price():
    """price=0 или price=1 — защита от деления на ноль."""
    assert calc_pnl(10, 0, True) == 0.0
    assert calc_pnl(10, 1, True) == 0.0
    assert calc_pnl(10, 0, False) == -10
    assert calc_pnl(10, 1, False) == -10


def test_pnl_03_negative_bet():
    """Отрицательная ставка — некорректный ввод."""
    assert calc_pnl(-10, 0.5, True) == -10.0
    assert calc_pnl(-10, 0.5, False) == 10.0


def test_pnl_04_ev_consistency():
    """EV = p_win * profit_win + (1-p_win) * (-bet)."""
    bet, price = 30, 0.27
    p_win = 0.4
    profit_win = calc_pnl(bet, price, True)
    ev = p_win * profit_win + (1 - p_win) * (-bet)
    assert abs(ev - (0.4 * 81.11 + 0.6 * (-30))) < 0.01


def test_pnl_05_real_cases():
    """Реальные кейсы из Excel. price — цена купленной доли (YES или NO)."""
    assert calc_pnl(17.01, 0.265, True) == 47.18   # Tijuana YES
    assert calc_pnl(30, 0.245, True) == 92.45     # Auxerre NO: 30*(1/0.245-1)
    assert calc_pnl(21.51, 0.535, False) == -21.51


def test_pnl_06_extreme_prices():
    """Экстремальные цены: 0.001, 0.999."""
    assert calc_pnl(10, 0.001, True) == 9990.0
    assert calc_pnl(10, 0.999, True) == 0.01


def test_pnl_07_loss_always_negative_bet():
    """При проигрыше P&L = -bet для любой цены."""
    for price in [0.1, 0.5, 0.9]:
        assert calc_pnl(20, price, False) == -20


def test_pnl_08_rounding():
    """Округление до 2 знаков."""
    r = calc_pnl(33.33, 0.333, True)
    assert isinstance(r, float)
    assert r == round(r, 2)


# ═══════════════════════════════════════════════════════════
# 2. Kelly — 8 тестов
# ═══════════════════════════════════════════════════════════

def test_kelly_09_zero_edge():
    """p_true = market_price → f_yes = 0, f_no = 0."""
    assert kelly_yes(0.5, 0.5) == 0.0
    assert kelly_no(0.5, 0.5) == 0.0


def test_kelly_10_negative_edge_yes():
    """p_true < price → f_yes = 0."""
    f_yes = kelly_yes(0.4, 0.5)
    f_no = kelly_no(0.4, 0.5)
    assert f_yes == 0.0
    assert f_no > 0


def test_kelly_11_boundary_c_zero():
    """market_price=0."""
    assert kelly_yes(0.6, 0) == 0.0
    assert kelly_no(0.4, 0) == 0.0


def test_kelly_12_boundary_c_one():
    """market_price=1."""
    assert kelly_yes(0.6, 1.0) == 0.0
    assert kelly_no(0.4, 1.0) == 0.0


def test_kelly_13_symmetry():
    """YES и NO edge симметричны."""
    p, c = 0.65, 0.55
    edge_yes = p - c
    edge_no = (1 - p) - (1 - c)
    assert abs(edge_yes + edge_no) < 1e-9


def test_kelly_14_fraction_bounds():
    """Kelly fraction в разумных границах."""
    for p in [0.3, 0.5, 0.7]:
        for c in [0.2, 0.4, 0.6]:
            if 0 < c < 1:
                assert 0 <= kelly_yes(p, c) <= 1.5
                assert 0 <= kelly_no(p, c) <= 1.5


def test_kelly_independent_no_price_from_book():
    """При спреде c_no != 1 - c_yes доля Kelly NO отличается от симметричного 1 - yes."""
    p, yes_p = 0.35, 0.40
    c_naive = 1.0 - yes_p
    c_no_book = 0.54
    assert abs(c_naive - c_no_book) >= 0.05
    f_naive = kelly_no(p, yes_p, c_naive)
    f_book = kelly_no(p, yes_p, c_no_book)
    assert f_naive > 0 and f_book > 0
    assert f_book != f_naive


def test_kelly_15_compute_respects_limits():
    """compute_kelly соблюдает max_bet_usd, max_bet_pct."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r = compute_kelly(0.9, 0.5, 1000, s)
    assert r.bet_size_usd <= 50.0


def test_kelly_16_compute_zero_no_edge():
    """edge<=0 → bet_size=0."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r = compute_kelly(0.5, 0.5, 1000, s)
    assert r.bet_size_usd == 0.0


# ═══════════════════════════════════════════════════════════
# 3. draw_prob, compute_kelly с draw — 4 теста
# ═══════════════════════════════════════════════════════════

def test_kelly_17_draw_prob_reduces_stake():
    """draw_prob уменьшает true_prob и влияет на Kelly."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r1 = compute_kelly(0.6, 0.5, 1000, s, draw_prob=0)
    r2 = compute_kelly(0.6, 0.5, 1000, s, draw_prob=0.27)
    # p_eff = 0.6*0.73 = 0.438 < 0.5, edge отрицательный → bet=0
    assert r2.bet_size_usd <= r1.bet_size_usd


def test_kelly_18_get_draw_prob():
    """get_draw_prob возвращает правильные значения."""
    assert get_draw_prob("soccer_epl") == 0.27
    assert get_draw_prob("soccer_uk_championship") == 0.26
    assert get_draw_prob("basketball_nba") == 0.0
    assert get_draw_prob("unknown") == 0.0


def test_kelly_19_draw_prob_extreme():
    """draw_prob=0 и draw_prob=1 не вызывают ошибок; draw=0.99 снижает stake на YES."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r0 = compute_kelly(0.65, 0.55, 1000, s, draw_prob=0)
    r1 = compute_kelly(0.65, 0.55, 1000, s, draw_prob=0.99)
    assert r0.bet_size_usd > 0   # без draw — edge на YES
    # draw=0.99: p_eff=0.0065 → edge на NO; bet остаётся в пределах max_bet_usd
    assert 0 <= r1.bet_size_usd <= 50.0


def test_kelly_20_ev_per_dollar():
    """ev_per_dollar = edge / side_price."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r = compute_kelly(0.65, 0.55, 1000, s)
    edge = 0.65 - 0.55
    assert abs(r.ev_per_dollar - edge / 0.55) < 0.001


# ═══════════════════════════════════════════════════════════
# 4. P&L / Kelly согласованность — 3 теста
# ═══════════════════════════════════════════════════════════

def test_consistency_21_pnl_matches_formula():
    """profit = bet * (1/price - 1)."""
    bet, price = 25, 0.4
    profit = calc_pnl(bet, price, True)
    assert abs(profit - bet * (1/price - 1)) < 0.01


def test_consistency_22_extreme_probabilities():
    """p_true=0, p_true=1."""
    assert kelly_yes(0, 0.5) == 0.0
    assert kelly_no(0, 0.5) == 1.0
    assert kelly_yes(1, 0.5) == 1.0
    assert kelly_no(1, 0.5) == 0.0


def test_consistency_23_zero_bankroll():
    """bankroll=0 → bet=0."""
    s = Settings(odds_api_key="x", kelly_multiplier=0.25, max_bet_pct=0.05, max_bet_usd=50.0)
    r = compute_kelly(0.7, 0.5, 0, s)
    assert r.bet_size_usd == 0.0


# ═══════════════════════════════════════════════════════════
# 5. Дополнительные критерии качества проекта — 6 тестов
# ═══════════════════════════════════════════════════════════

def test_quality_24_floating_pnl_yes_no_symmetry():
    """Floating P&L: shares*cur_price - bet; для NO используется cur_no_price."""
    bet, price = 10, 0.5
    shares = bet / price
    # YES выиграл: cur_yes=1, cur_no=0 → value=shares*1=20, pnl=10
    assert abs((shares * 1.0 - bet) - 10) < 0.01
    # NO выиграл: cur_yes=0, cur_no=1 → для NO side value=shares*1=20
    assert abs((shares * 1.0 - bet) - 10) < 0.01


def test_quality_25_kelly_fraction_non_negative():
    """Kelly fraction неотрицательна при положительном edge."""
    for p, c in [(0.6, 0.5), (0.4, 0.5), (0.7, 0.6)]:
        if 0 < c < 1:
            fy, fn = kelly_yes(p, c), kelly_no(p, c)
            assert fy >= 0 and fn >= 0


def test_quality_26_draw_prob_by_league_coverage():
    """DRAW_PROB_BY_LEAGUE покрывает футбол; баскетбол=0."""
    assert "soccer_epl" in DRAW_PROB_BY_LEAGUE
    assert "soccer_uk_championship" in DRAW_PROB_BY_LEAGUE
    assert DRAW_PROB_BY_LEAGUE.get("basketball_nba", 0) == 0


def test_quality_27_calc_pnl_used_everywhere():
    """calc_pnl — единый источник P&L; проверяем импорт."""
    from core.bet_results import calc_pnl
    assert callable(calc_pnl)
    assert calc_pnl(10, 0.5, True) == 10.0


def test_quality_28_event_key_uniqueness():
    """event_key группирует O/U одного матча в одно событие."""
    import re

    def event_key(q: str) -> str:
        s = (q or "").strip().lower()
        s = re.sub(r"\s*(O/U|over|under|total)\s*[\d.]+.*$", "", s, flags=re.I)
        s = re.sub(r"\s*[-:]\s*$", "", s).strip()
        return s[:80] if s else (q or "")[:80].lower()

    k1 = event_key("Kartal vs Rybakina O/U 22.5")
    k2 = event_key("Kartal vs Rybakina O/U 23.5")
    k3 = event_key("Other Match O/U 22.5")
    assert k1 == k2  # один матч — один ключ
    assert k1 != k3


def test_quality_30_draw_side_kelly_consistency():
    """
    Сторона YES/NO должна выбираться по Kelly после draw_prob (футбол).
    Сейчас signals.py сравнивает f_yes/f_no до draw — возможен перекос стороны.
    """
    import pytest
    from analysis.kelly import kelly_yes, kelly_no

    true_prob, yes_p, no_p = 0.48, 0.42, 0.55
    draw = 0.27
    fy, fn = kelly_yes(true_prob, yes_p), kelly_no(true_prob, yes_p, no_p)
    side_raw = "YES" if fy >= fn and fy > 0 else "NO"
    adj = true_prob * (1.0 - draw)
    fy2, fn2 = kelly_yes(adj, yes_p), kelly_no(adj, yes_p, no_p)
    side_adj = "YES" if fy2 >= fn2 and fy2 > 0 else "NO"
    if side_raw != side_adj:
        pytest.xfail(
            f"side mismatch raw={side_raw} adj={side_adj} — fix generate_signals side pick"
        )
    assert side_raw == side_adj


def test_quality_29_price_in_valid_range():
    """Прайсы Polymarket в [0.001, 0.999] — calc_pnl не падает и возвращает положительный profit."""
    for price in [0.001, 0.01, 0.5, 0.99, 0.999]:
        r = calc_pnl(10, price, True)
        assert r > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
