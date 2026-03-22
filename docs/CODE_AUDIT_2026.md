# Аудит кода — март 2026

## Выполненные изменения

### 1. Унификация resolve-логики
- **Было:** `resolve_pending_snapshots` в `analysis/backtest.py` (только snapshots) и `resolve_bets` в `check_results.py` (snapshots + bets) — дублирование.
- **Стало:** Единая точка входа `check_results.resolve_bets()`. `main.py --mode stats` и `scripts/run_recommend.py` используют её. `resolve_pending_snapshots` удалена из backtest (~65 строк).
- **Бонус:** `resolve_bets(db, collector=...)` принимает опциональный collector — при вызове из run_recommend переиспользуется существующий, без лишнего создания.

### 2. Общие Excel-утилиты
- Добавлен `core/excel_utils.py`: стили (HEADER_FILL, GREEN_FILL, RED_FILL и др.), `excel_header()`, `categorize_market()`, `SPORT_KEYWORDS`.
- `refresh.py` переведён на использование excel_utils (~30 строк удалено).

---

## Выявленные несостыковки (оставлены как есть)

### 1. Два источника данных для результатов
- **agent.db** (check_results): snapshots, bets — используется main.py, run_recommend, daily_morning.
- **Excel** (refresh.py): ставки, рекомендации, MANUAL_RESULTS — основной рабочий скрипт.
- **Риск:** Excel и agent.db не синхронизируются. Реальные ставки из Excel не попадают в agent.db автоматически.

### 2. Разные пути к кэшу
- `refresh.py`: через `.env` (REFRESH_MARKET_CACHE_FILES, REFRESH_MARKET_CACHE_DIR) или `data/market_cache/`.
- `update_results.py`, `check_and_update.py`: хардкод путей к `agent-tools/*.txt` с UUID.

### 3. Дублирование Excel-логики
- `update_forecasts.py`, `check_and_update.py`, `update_results.py` по-прежнему содержат свои копии стилей и categorize. Можно перевести на `core/excel_utils`, но они используются реже и зависят от устаревших путей.

### 4. Множество скриптов обновления
| Скрипт | Назначение | Источник данных |
|--------|------------|-----------------|
| refresh.py | Основной — ставки + рекомендации | .env / market_cache |
| update_results.py | Результаты + рекомендации | FILES (liquidity, soccer, nba, closed) |
| check_and_update.py | Результаты открытых | CLOSED_FILE, ACTIVE_FILES |
| update_forecasts.py | Gamma API напрямую | gamma-api.polymarket.com |
| check_results.py | agent.db (snapshots + bets) | PolymarketCollector |

Рекомендация: со временем свести к refresh.py + check_results.py; остальные — legacy/fallback при 403.

### 5. record_bet_to_db в check_results
Функция `record_bet_to_db()` — ручной хак для добавления ставки Aston Villa. Стоит вынести в отдельный скрипт или удалить после перехода на единый источник.

---

## Краткий итог

- Убрано ~95 строк дублирования (resolve + excel_utils).
- Одна точка resolve вместо двух.
- refresh.py использует общие утилиты.
- Документированы несостыковки для будущего рефакторинга.
