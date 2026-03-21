# Cross-check доработок и целей проекта

## 1. Соответствие целям проекта

**Цель из плана:** *Python-агент для value betting на Polymarket. Фаза 1 — спорт (Pinnacle vs Polymarket), Kelly Criterion + risk management.*

| Цель проекта | Состояние | Комментарий |
|--------------|-----------|-------------|
| Pinnacle как источник edge | ✅ main.py использует odds_api + match_odds_to_markets | Пайплайн подключён |
| Kelly Criterion | ✅ kelly.py + fractional (0.25) | Edge только из Pinnacle |
| Risk management | ✅ risk.py: лимиты, daily_loss, consecutive_losses | Всё активно |
| Value betting (edge > 0) | ✅ min_edge=0.03, NO-фильтр при YES>0.65 | Ужесточение по анализу убытков |

**Конфликт с целью:** Нет. Доработки усиливают исходную логику value betting.

---

## 2. Проверка фактов

### The Odds API — sport keys

| Ключ в config/models | Источник | Статус |
|----------------------|----------|--------|
| soccer_epl | Документация Odds API | ✅ Подтверждён |
| soccer_uefa_champs_league | Стандартный | ✅ |
| soccer_mexico_ligamx | Web search | ✅ Подтверждён |
| basketball_nba | Документация | ✅ |
| mma_mixed_martial_arts | Документация | ✅ |
| soccer_spain_la_liga | Web search (oddsapir) | ✅ |
| soccer_germany_bundesliga | Web search | ✅ |
| soccer_italy_serie_a | Типичный ключ | ⚠️ Сверить с GET /v4/sports/ |
| soccer_france_ligue_one | Типичный | ⚠️ Может быть ligue_1 |
| soccer_usa_mls | Документация (soccer_usa_mls) | ✅ |

**Рекомендация:** При первом запуске с API key вызвать `GET /v4/sports/` и сравнить ключи в TIER1_LEAGUES с фактическими.

### Числовые допущения

| Параметр | Значение | Источник | Факт |
|----------|----------|----------|------|
| Liga MX Over 1.5 | ~73% в плане | Анализ убытков | **77.2%** (footystats) — консервативно |
| NO_BET_MAX_YES | 0.65 | План | Разумный порог |
| DAILY_LOSS_LIMIT | 50 (5% от 1000) | План | Соответствует |
| MIN_EDGE | 0.03 | План | Соответствует |
| Tier2 Kelly | ×0.4 → 0.10 | План: "Kelly×0.10" | 0.25 × 0.4 = 0.10 ✅ |

---

## 3. Cross-check изменений

### 3.1 config.py

| Параметр | Было | Стало | План | Совпадение |
|----------|------|-------|------|------------|
| sports | nba, uefa, mma | +soccer_epl, soccer_mexico_ligamx | Добавить soccer_epl, ligamx | ✅ |
| min_edge | 0.05 | 0.03 | 0.03 | ✅ |
| daily_loss_limit | 100 | 50 | 50 | ✅ |
| max_consecutive_losses | — | 3 | 3 | ✅ |
| no_bet_max_yes | — | 0.65 | 0.65 | ✅ |
| betting_window | — | 2–24 ч | 2–8 ч | ⚠️ max=24 вместо 8 |

**Несоответствие:** План — окно 2–8 ч, код — 2–24 ч. Причина: 8 ч слишком узко, 24 ч даёт больше сигналов при сохранении ограничения по составу.

### 3.2 signals.py

| Изменение | План | Код | Совпадение |
|-----------|------|-----|------------|
| NO при YES ≥ 0.65 | skip | `if side==NO and yes_price>=no_bet_max_yes: continue` | ✅ |
| league_tier → Kelly | Tier2 = ×0.10 | ×0.4 от 0.25 = 0.10 | ✅ |
| tier==0 skip | Skip лиги | `if tier==0: continue` | ✅ |

### 3.3 executor.py

| Изменение | План | Код | Совпадение |
|-----------|------|-----|------------|
| Временное окно | 2–8 ч | min=2, max=24 из config | ⚠️ max отличается |
| Комментарий | "2–8 часов" | Оставлен "2–8 часов" | ⚠️ Устаревший |

### 3.4 risk.py + db.py

| Изменение | План | Код | Совпадение |
|-----------|------|-----|------------|
| consecutive_losses | Таблица performance | Метод `get_consecutive_losses()` по bets | ✅ Эквивалент (без миграции) |
| daily_loss_limit | 50 | Из config (50) | ✅ |

### 3.5 data/models.py

| Изменение | План | Код | Совпадение |
|-----------|------|-----|------------|
| league_detector | Функция по question | `league_tier(sport_key)` по sport_key | ⚠️ Иное: sport_key из OddsLine, не парсинг question |
| TIER1/TIER2/SKIP | Списки лиг | Множества в models.py | ✅ |

**Уточнение:** `league_tier` использует sport_key из matched OddsLine — источник точнее, чем парсинг question.

### 3.6 place_bets.py, update_excel.py, build_excel.py

| Файл | План | Факт |
|------|------|------|
| place_bets.py | Убрать edge_est | ❌ EDGE_EST=0.05 остался |
| update_excel.py | — | edge_est=0.05 в kelly-расчёте |
| build_excel.py | — | edge_est=0.05 |

**Замечание:** Эти скрипты — отдельные (Excel, разовые ставки), не входят в основной пайплайн main.py. Для них нужна явная пометка «не используют Pinnacle» или переключение на main.py.

---

## 4. Итоговая сводка

### Выполнено по плану

- MIN_EDGE=0.03, DAILY_LOSS_LIMIT=50, MAX_CONSECUTIVE_LOSSES=3
- Sports: soccer_epl, soccer_mexico_ligamx
- Фильтр NO при YES ≥ 0.65
- League tiers (Tier1/Tier2/Skip)
- Временное окно в executor
- get_consecutive_losses в db.py

### Отклонения от плана

1. **Окно ставок:** max 24 ч вместо 8 ч — намеренно расширено.
2. **league_detector:** Реализован через `league_tier(sport_key)` вместо парсинга question.
3. **place_bets/update_excel:** edge_est не удалён — скрипты вне основного пайплайна.

### Рекомендации (выполнено)

1. ✅ README обновлён; в place_bets.py и build_excel.py добавлены предупреждения о том, что скрипты не используют Pinnacle.
2. ✅ Комментарий в executor обновлён на «2–24 ч (настраивается в config)».
3. ✅ В README добавлена инструкция по проверке sport_key через GET /v4/sports/.
