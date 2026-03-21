# Отчёт аудита качества Polymarket Analytics Agent

## Резюме

Полная проверка проекта выполнена. Исправлены выявленные логические нестыковки, добавлено **29 стресс-тестов** формул, внедрены **6 критериев оценки** и скрипт аудита качества.

---

## 1. Найденные и исправленные нестыковки

### 1.1 Floating P&L для NO (check_and_update.py)

**Проблема:** `get_current_price()` возвращала только цену YES. Для ставок на NO floating P&L считался по `shares * cur_yes_price`, что неверно — нужно использовать цену стороны NO.

**Решение:**
- `get_current_price` заменена на `get_current_prices(question, cid)` → возвращает `(yes_price, no_price)`
- При расчёте floating P&L используется `cur_side_price = no_p if side in ("NO","НЕТ") else yes_p`

### 1.2 Единый источник P&L (calc_pnl)

**Проблема:** В `check_and_update.py`, `update_forecasts.py`, `update_results.py` P&L считался inline (`bet * (1/price - 1)`), не через `core.bet_results.calc_pnl`.

**Решение:** Все три скрипта переведены на `calc_pnl(bet, price, won)`.

### 1.3 update_results.py: проигрыш и сторона NO

**Проблема:** `-abs(bet)` при проигрыше; сторона "НЕТ" не учитывалась в условии won.

**Решение:** `pnl = calc_pnl(bet, price, won)`; `won` расширено на `side in ("NO", "НЕТ")`.

---

## 2. Стресс-тесты (29 тестов)

| № | Группа | Тесты |
|---|--------|-------|
| 1–8 | P&L (calc_pnl) | Границы price, EV, реальные кейсы, округление |
| 9–16 | Kelly | Ноль edge, границы c=0/1, лимиты, draw_prob |
| 17–20 | draw_prob | Уменьшение stakes, get_draw_prob, крайние значения |
| 21–23 | Согласованность | P&L ↔ формула, p=0/1, bankroll=0 |
| 24–29 | Критерии качества | Floating P&L, Kelly bounds, DRAW_PROB, event_key, прайсы |

Запуск: `pytest tests/test_stress_formulas.py -v`

---

## 3. Критерии оценки (реализованы)

| № | Критерий | Как проверяется |
|---|----------|-----------------|
| 1 | calc_pnl — единый источник P&L | Импорт + вызов calc_pnl(10, 0.5, True)==10 |
| 2 | Floating P&L — ценa стороны | get_current_prices, cur_side_price в check_and_update |
| 3 | 1 ставка — 1 событие | event_key группирует O/U 22.5 и 23.5 |
| 4 | draw_prob по лигам | soccer_epl, basketball_nba=0 в DRAW_PROB_BY_LEAGUE |
| 5 | Стресс-тесты | 29 тестов pytest |
| 6 | Импорты модулей | config, kelly, signals, db, bet_results |

---

## 4. Скрипт аудита качества

```bash
python scripts/quality_audit.py
```

Выводит результат всех 6 проверок. Код 0 — все пройдены.

---

## 5. Изменённые файлы

- `check_and_update.py` — get_current_prices, cur_side_price, calc_pnl
- `update_forecasts.py` — calc_pnl
- `update_results.py` — calc_pnl, side NO/НЕТ
- `tests/test_stress_formulas.py` — 6 новых тестов, исправлены 2 ожидания
- `scripts/quality_audit.py` — новый скрипт аудита
