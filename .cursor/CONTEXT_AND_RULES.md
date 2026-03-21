# Контекст и правила чата — Polymarket Analytics Agent

## 1. Контекст проекта

### 1.1 Расположение
- **Проект:** `C:\Users\Lomov\Desktop\polymarket-agent\`
- **План:** `c:\Users\Lomov\Documents\Arduino\libraries\M5Unified\src\utility\.cursor\plans\polymarket_analytics_agent_b5985182.plan.md`
- **Excel:** `C:\Users\Lomov\Desktop\polymarket-agent\polymarket_рекомендации.xlsx`
- **Кэш API:** `C:\Users\Lomov\.cursor\projects\c-Users-Lomov-Documents-Arduino-libraries-M5Unified-src-utility\agent-tools\`

### 1.2 Назначение
Python-агент для value betting на Polymarket:
- **Фаза 1:** спорт (сравнение с Pinnacle / The Odds API)
- **Фаза 2:** esports + арбитраж
- **Фаза 3:** LLM для non-sports

### 1.3 Основные скрипты
| Скрипт | Назначение |
|--------|------------|
| `refresh.py` | Обновление Excel: результаты ставок, рекомендации, статистика. Основной рабочий скрипт. |
| `analyze_and_place.py` | Анализ рынков, 15 прогнозов, запись ставок в Excel (без Pinnacle). |
| `place_bets.py` | Старые ставки по кэшу (до 5), EDGE_EST. |
| `update_from_cache.py` | Обновление вкладки «Рекомендации» из кэша. |
| `update_forecasts.py` | Обновление через Gamma API (часто 403). |
| `check_and_update.py` | Проверка результатов через закрытые рынки. |
| `main.py` | Полный цикл: Polymarket + Pinnacle → сигналы → исполнение (нужен ODDS_API_KEY). |

### 1.4 Структура Excel
- **Ставки:** №, Condition ID, Рынок, Направление, Коэф., Ставка, Цена доли, Потенц. выигрыш, EV, Результат, P&L, Статус, Даты
- **Рекомендации:** Рынок, Категория, ДА/НЕТ, Ликвидность, Рекомендация
- **Статистика:** Закрыто, Побед, Проигрышей, WR, P&L, дата обновления
- **Правила и тайминги, Анализ ошибок**

---

## 2. Правила, используемые в чате

### 2.1 Формулы P&L (критично)
- **Polymarket:** покупаем доли по цене `price` (0–1). При победе каждая доля платит $1.
- **Единая формула для YES и NO:**
  ```python
  pnl = bet * (1/price - 1)  # при выигрыше
  pnl = -bet                 # при проигрыше
  ```
- **`price`** — цена **купленной** доли (колонка 7). Для YES — `yes_price`, для NO — `no_price`.
- Ошибка: использовать для NO `1/(1-price)` или `no_price = 1 - price` — **запрещено**.

### 2.2 Floating P&L для активных ставок
- **YES:** `float_val = (bet/price) * cur_yes_price - bet`
- **NO:** `float_val = (bet/price) * cur_no_price - bet`
- Не использовать `yes_p` для оценки NO-позиции.

### 2.3 Определение выигрыша
- **YES:** `won = (outcome == "Yes")`
- **NO:** `won = (outcome == "No")`
- При обновлении результатов обязательно проверять сторону ставки (YES/NO).

### 2.4 MANUAL_RESULTS (refresh.py)
- Словарь `{ "вопрос рынка": {"outcome": "Yes"|"No", "note": "..." } }`
- `outcome = None` — пропуск (заполнить после матча)
- Ключ — полный текст вопроса из Excel (колонка 3).

### 2.5 Фильтры ставок (из плана)
- **NO при YES > 65%** — не ставить (NO_BET_MAX_YES)
- **Whitelist лиг:** Tier1 (EPL, NBA, NHL…), Tier2 (Liga MX, MLS, Championship), SKIP (Colombia, BetPlay)
- **Ликвидность:** мин. 2000–3000$
- **Kelly:** 0.25 для Tier1, 0.5× для Tier2
- **Окно времени:** 2–24ч до матча (analyze_and_place, executor)
- **O/U без Pinnacle:** дополнительный ×0.5 Kelly (волатильность тоталов)
- **Одна ставка — одно событие:** максимум 1 ставка на один матч/событие (избегать коррелированных ставок, напр. O/U 22.5 и O/U 23.5 на одном теннис-матче)

### 2.6 API и кэш
- **Gamma API** часто даёт 403 — используются кэши из `agent-tools/*.txt`
- **ODDS_API_KEY** — нужен для main.py и Pinnacle (в .env обычно отсутствует)
- `update_from_cache.py` читает все `*.txt` в agent-tools и дедуплицирует по conditionId

---

## 3. История ключевых изменений в этом чате

1. Обновлён результат Auxerre vs Strasbourg O/U 1.5: 0:0 → NO (UNDER) выиграл.
2. Добавлены 13 прогнозов через `analyze_and_place.py`.
3. Исправлена формула P&L для NO в refresh, update_forecasts, check_and_update, update_results.
4. Исправлен floating P&L для NO в refresh.
5. Auxerre P&L исправлен с 11.10 на 81.11.
6. В MANUAL_RESULTS добавлены заглушки для Middlesbrough, Kartal, LY vs LOUD.
7. Рекомендации по анализу Middlesbrough: Championship→Tier2, окно 2–24ч, O/U×0.5 Kelly, soccer_uk_championship в config.
8. Правило п.4: одна ставка — одно событие (анализ Kartal x2). Реализовано в analyze_and_place (event_key, seen_events).

---

## 4. Текущая статистика (на момент последнего refresh — 16.03.2026)

- Закрытых: 8
- Побед: 2 (Tijuana, Auxerre)
- Проигрышей: 6 (Aston Villa, Tolima, Puebla/Tigres, Middlesbrough, Kartal 22.5, Kartal 23.5 и др.)
- WR: 25.0%
- P&L: +$21.82
- Активных: 11 (Carolina Hurricanes, World Cup, NBA Finals, NHL, LY vs LOUD и др.)
