# Аудит формул P&L и Kelly

## Механика Polymarket

- **Цена доли (share price):** 0–1. Покупаем доли по цене `price`.
- **Стоимость:** `bet` долларов покупают `bet/price` долей.
- **Выплата:** каждая доля платит $1 при победе.
- **Прибыль при выигрыше:** `bet/price - bet = bet * (1/price - 1)`.
- **Потери при проигрыше:** `-bet`.

Формула одинакова для **YES** и **NO**: `pnl = bet * (1/price - 1)` при выигрыше, где `price` — цена купленной доли (колонка 7 в Excel).

---

## Исправленные ошибки (2026-03-11)

### 1. refresh.py — формула для NO

**Было:**
```python
no_price = 1 - price
pnl = round(bet * (1/no_price - 1), 2)  # ОШИБКА
```

**Стало:** единая формула для YES и NO:
```python
pnl = round(bet * (1/price - 1), 2) if won else -bet
```

Для Auxerre (NO, price=0.27) давало 11.1 вместо 81.11.

### 2. refresh.py — floating P&L для NO

**Было:** `float_val = shares * yes_p - bet` для всех ставок (для NO неверно).

**Стало:** `cur_side_price = yes_p if YES else no_p`, `float_val = shares * cur_side_price - bet`.

### 3. update_forecasts.py — формула для NO

**Было:** `pnl = bet * (1/(1-price) - 1)` — та же логическая ошибка.

**Стало:** `pnl = bet * (1/price - 1)`.

### 4. check_and_update.py — формула для NO

**Было:** `no_price = 1 - price`, `pnl = bet * (1/no_price - 1)`.

**Стало:** `pnl = bet * (1/price - 1)`.

### 5. update_results.py — не учитывалась сторона (YES/NO)

**Было:** `won = (outcome == "Yes")` — только ставки YES.

**Стало:** проверка стороны:
```python
won = (outcome == "Yes" and side in ("YES","ДА")) or (outcome == "No" and side == "NO")
```

---

## Проверка остальных файлов

| Файл | Формула | Статус |
|------|---------|--------|
| place_bets.py | win_usd = bet*(1/no - 1) для NO | ✓ |
| analyze_and_place.py | kelly_bet использует price для стороны | ✓ |
| analysis/kelly.py | kelly_yes, kelly_no — для расчёта доли, не P&L | ✓ |
| check_results.py | virtual_pnl = bet*(1/pm_price - 1) | ✓ (pm_price = цена стороны) |
| build_excel.py | pnl_if_win = 10*(1/price - 1) | ✓ |

---

## Рекомендации

1. **Единая документация:** во всех скриптах явно указывать: «price = цена купленной доли (YES или NO)».
2. **Тесты:** добавить `test_pnl_no_bet()` в `tests/test_core.py` для проверки формулы NO.
3. **Aston Villa:** в Excel колонка 8 содержит дату вместо потенц. выигрыша — проверить источник данных.

---

## Обновления 2026-03-19

- **`core/gamma_resolve.py`:** закрытые рынки без `resolved`, но с исходом по `outcomePrices` (Yes/No); стороны **ДА/НЕТ**; авто-resolve только для бинарных Yes/No (не два кастомных исхода).
- **`check_and_update` / `update_results` / `update_forecasts`:** используют `market_fully_resolved`, `bet_won_for_binary_market`.
- **`place_bets.py`:** Kelly пересчитывается для выбранной стороны (`kelly_bet_for_side`), не переиспользуется Kelly только по YES.
- **`analysis/signals.py`:** одна поправка на ничью (`adj_true`); `compute_kelly(..., draw_prob=0)`, чтобы не применять draw дважды; `min_edge` и поле `edge` согласованы с `adj_true`.

## Forward-test P&L и order book (2026-03-18)

- **`core.bet_results.snapshot_entry_price`:** при разрешении snapshot в БД для `virtual_pnl` используется **`sim_fill_price`** (симуляция по стакану из `executor._record_snapshot`), если она есть; иначе **`pm_price`**.
- **`check_results.py` / `analysis/backtest.py`:** оба пути resolve snapshots используют эту единую цену входа — виртуальный P&L согласован со slippage в `show_signal_calibration`.
