# Отчёт стресс-теста формул

**Дата:** 2026-03-11  
**Тестов:** 57 (17 stress + 11 core + 29 integration)  
**Результат:** Все пройдены ✓

---

## 1. P&L (calc_pnl)

| Тест | Проверка | Результат |
|------|----------|-----------|
| Win formula | profit = bet×(1/price−1) | ✓ |
| Boundary price=0,1 | Возврат 0 при won (защита от деления) | ✓ |
| Negative bet | Обработка некорректного ввода | ✓ |
| EV consistency | E[PnL] = p×profit + (1−p)×(−bet) | ✓ |
| Extreme prices | 0.001, 0.01, 0.99, 0.999 | ✓ |

**Вывод:** Формула корректна, граничные случаи обрабатываются.

---

## 2. Kelly (kelly_yes, kelly_no)

| Тест | Проверка | Результат |
|------|----------|-----------|
| No edge | p=c → f=0 | ✓ |
| Negative edge YES | p<c → f_yes=0, f_no>0 | ✓ |
| Boundary c=0, c=1 | Guard возвращает 0 | ✓ |
| Symmetry | edge_yes + edge_no = 0 | ✓ |
| Fraction bounds | 0 ≤ f ≤ 1.5 при разумных входах | ✓ |
| Extreme p=0, p=1 | Границы вероятности | ✓ |

**Вывод:** Математика Kelly согласована с share-based механикой Polymarket.

---

## 3. compute_kelly

| Тест | Проверка | Результат |
|------|----------|-----------|
| Respects limits | bet ≤ max_bet_usd, bankroll×pct | ✓ |
| Zero when no edge | edge≤0 → bet=0 | ✓ |
| ev_per_dollar | ev/side_price | ✓ |
| Zero bankroll | bet=0 | ✓ |

---

## 4. Согласованность P&L / Kelly

| Тест | Проверка |
|------|----------|
| profit = bet×(1/price−1) | Согласуется с calc_pnl |
| ev_per_dollar = edge/side_price | Согласуется с compute_kelly |

---

## 5. Рекомендации

1. **Граничные случаи:** price=0 и price=1 при won возвращают 0 — корректно, реальные рынки не имеют таких цен.
2. **Отрицательная ставка:** calc_pnl обрабатывает, но скрипты должны валидировать bet>0 до вызова.
3. **Deprecation:** Исправить `datetime.utcnow()` в `storage/db.py` (не критично).
