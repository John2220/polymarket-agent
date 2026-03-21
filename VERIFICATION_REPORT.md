# Отчёт верификации доработок

## 1. Проверка методологии и логики

### Критичные доработки — обоснованы

| # | Доработка | Логика | Статус |
|---|-----------|--------|--------|
| 1 | Реальный edge от Pinnacle | main.py уже вызывает odds_api и match_odds_to_markets. Проблема: place_bets.py — отдельный скрипт, не использует пайплайн. Также config.sports не включает soccer_epl, soccer_mexico_ligamx | ✅ Корректно |
| 2 | Kelly = 0 без edge | kelly.py уже возвращает 0 при raw_f <= 0. Проблема: edge передаётся из signals.py. Если true_prob из Pinnacle — корректно. Скрипты place_bets/update_excel используют edge_est=0.05 | ✅ Корректно |
| 3 | Активация стоп-лосса | risk.py уже проверяет daily_loss_limit. config.py: daily_loss_limit=100. Нужно: снизить до 50, добавить MAX_CONSECUTIVE_LOSSES | ✅ Корректно |

### Высокие доработки — уточнения

| # | Доработка | Формула/допущение | Верификация |
|---|-----------|-------------------|-------------|
| 4 | Draw correction | p_win = p_yes / (1 - draw_prob) | **Уточнение**: Pinnacle h2h для soccer даёт 3-way (home/draw/away). true_prob для команды уже исключает draw. Коррекция нужна только если используем 2-way источник. Оставляем как опциональную для лиг без Pinnacle. |
| 5 | NO при YES > 0.65 | Запрет ставки NO | **Верифицировано**: Liga MX Over 1.5 — 77.2% матчей (внешние данные). Рынок 75.5% YES был консервативен. Ставка UNDER была ошибкой. Порог 0.65 — разумный. |
| 6 | League whitelist | Tier1/Tier2/Skip | **The Odds API**: soccer_epl, soccer_mexico_ligamx есть. Liga BetPlay (Колумбия) — НЕ в стандартном списке. SKIP для малых лиг — корректно. |
| 7 | Временное окно 2-8 ч | hours_to_start | Логика верна. У разных спортов разные окна (NBA быстрее, футбол стабильнее). |
| 8 | Team form (Football-data.org) | 10 req/min free | **Верифицировано**: Free tier = 10 requests per MINUTE (не 10/день). docs.football-data.org. |

### Допущения — исправления по внешним данным

| Допущение в плане | Реальность | Коррекция |
|-------------------|------------|-----------|
| Draw 27-30% | EPL 2024/25: **30%**, La Liga: **22-26%** | Использовать 0.28 для EPL, 0.24 для La Liga, 0.30 для Liga MX |
| Liga MX Over 1.5 — 73% | **77.2%** (footystats, accaplanner) | Наше допущение было занижено — ставка UNDER ещё хуже |
| Football-data 10 req | **10 req/min** (не 10 всего) | Лимит достаточен для 5-10 команд за цикл |

### Зависимости — проверка

| Зависимость | Статус |
|-------------|--------|
| The Odds API (Pinnacle) | ✅ Pinnacle в regions=eu. Liga MX, EPL поддерживаются |
| Football-data.org | ✅ Бесплатный tier, 10 req/min. Нужна регистрация для API key |
| odds_api.io historical | Платно. the-odds-api.com historical — $15/мес за архив |

---

## 2. Реализация — приоритеты

**Фаза 1 (сегодня):**
1. config.py: MIN_EDGE=0.03, DAILY_LOSS_LIMIT=50, sports добавить soccer_epl
2. risk.py: MAX_CONSECUTIVE_LOSSES
3. signals.py: фильтр NO при yes_price > NO_BET_MAX_YES (0.65)

**Фаза 2 (эта неделя):**
4. config.py: DRAW_PROB_BY_LEAGUE, TIER1/TIER2_LEAGUES
5. league_detector() в data/models.py
6. executor.py: BETTING_WINDOW_HOURS
7. kelly.py: draw_prob (опционально)

**Фаза 3 (позже):**
8. data/team_stats.py — после получения API key
9. backtest: расширить запись snapshots
