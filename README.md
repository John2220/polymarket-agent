# Polymarket Аналитический Агент

Автоматизированный value-betting на Polymarket с использованием котировок от sharp-букмекеров (Pinnacle) как источника истинных вероятностей. Размер ставок по критерию Келли с полным риск-менеджментом.

## Стратегия

1. Получаем активные спортивные рынки с Polymarket (Gamma API + CLOB API)
2. Получаем точные котировки от Pinnacle через The Odds API
3. Убираем маржу букмекера (devig) для получения истинных вероятностей
4. Сравниваем с ценами на Polymarket для нахождения edge (преимущества)
5. Рассчитываем размер ставки по дробному критерию Келли
6. Исполняем через **FOK** (по умолчанию) или опционально **лимит GTC post-only** (`USE_MAKER_FIRST=true`), либо выводим рекомендации

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

cp .env.example .env
# Заполните .env своими API-ключами
```

### Необходимые API-ключи

- **The Odds API** (`ODDS_API_KEY`): бесплатный план — 500 запросов/мес. Регистрация на https://the-odds-api.com
- **Polymarket** (`POLYMARKET_PRIVATE_KEY`, `POLYMARKET_FUNDER_ADDRESS`): нужны только для auto-режима. Найти в настройках Polymarket → Экспорт приватного ключа.

## Использование

```bash
# Режим рекомендаций: сканирование, вывод сигналов, запись forward-test
python main.py --mode recommend

# Авто-режим: то же + размещение FOK-ордеров (нужен приватный ключ)
python main.py --mode auto

# Статистика: анализ forward-test и истории ставок
python main.py --mode stats

# Streamlit-дашборд (forward-test)
python scripts/run_dashboard.py

# REST API: /stats, /signals (http://127.0.0.1:8765/docs)
python scripts/run_api.py

# Утро (планировщик): сначала результаты ставок, затем один цикл сигналов
python scripts/daily_morning.py --mode recommend
# Подробнее: docs/DAILY_SCHEDULE.md и scripts/daily_morning.bat

# Резолвы в БД (Gamma → SQLite) и обновление Excel — см. docs/RUNBOOK.md
# python check_results.py
# python refresh.py
```

Полный список вспомогательных команд: **[docs/RUNBOOK.md](docs/RUNBOOK.md)**.

## Публикация на GitHub

Секреты только в `.env` (не коммитится). См. **[SECURITY.md](SECURITY.md)** и пошаговые команды: **[docs/GITHUB_PUBLISH.md](docs/GITHUB_PUBLISH.md)**.

## Конфигурация

Все параметры задаются через файл `.env`. Шаблон — в `.env.example`.

Ключевые параметры:
- `KELLY_MULTIPLIER` (0.25): доля от оптимальной ставки Келли. Ниже = меньше волатильность.
- `MIN_EDGE` (0.03): минимальный порог преимущества (3%). Только реальный edge от Pinnacle.
- `MAX_BET_PCT` (0.05): максимум 5% банкролла на одну ставку.
- `DAILY_LOSS_LIMIT` (50): стоп-торговля после $50 дневных потерь (5% от $1000).
- `NO_BET_MAX_YES` (0.65): запрет ставки NO при YES>65% (ставка против рынка без sharp).

**Важно:** Скрипты `place_bets.py` и `build_excel.py` работают отдельно от основного пайплайна и **не используют Pinnacle** (edge оценивается приближённо). Для торговли и рекомендаций с реальным edge используйте `python main.py --mode recommend` или `--mode auto`.

**Проверка sport keys:** При первом запуске вызовите `GET https://api.the-odds-api.com/v4/sports/?apiKey=YOUR_KEY` и сравните ключи с `TIER1_LEAGUES` в `data/models.py`.

## Архитектура

```
polymarket-agent/
├── config.py          # Настройки из .env
├── main.py            # CLI точка входа, asyncio цикл, rich вывод
├── data/
│   ├── collector.py   # Получение данных Gamma API + CLOB API
│   ├── odds_api.py    # The Odds API (котировки Pinnacle)
│   └── models.py      # Pydantic модели данных
├── analysis/
│   ├── signals.py     # Поиск edge: Pinnacle p_true vs PM цена
│   ├── kelly.py       # Расчёт ставки по Келли
│   └── backtest.py    # Запись forward-test данных
├── trading/
│   ├── executor.py    # Исполнение ордеров (recommend / auto)
│   └── risk.py        # Риск-менеджмент
└── storage/
    └── db.py          # SQLite хранилище
```