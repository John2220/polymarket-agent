# Конкурентный анализ: агенты для ставок на prediction markets

> **Надёжность данных:** Данные собраны из поиска в интернете (март 2025). Звёзды GitHub и описания проверены на страницах репозиториев. Статистика результатов — из сторонних статей; у большинства проектов публичных P&L нет.

---

## 1. Таблица агентов (до 20 шт.)

| # | Репозиторий | ⭐ | Область | Стратегия | Язык |
|---|-------------|-----|---------|-----------|------|
| 1 | Polymarket/agents | 2,500+ | Фреймворк | LLM, RAG, Gamma API | Python |
| 2 | chrisgillam/polymarket_gambot | 25 | Спорт | Pinnacle vs Polymarket, Kelly | Jupyter |
| 3 | TrendTechVista/polymarket-finance-bot | 114 | Финансы/macro | Value betting, edge | TypeScript |
| 4 | TrendTechVista/polymarket-ai-trading-bot | 159 | General | LLM fair-value, limit orders | TypeScript |
| 5 | solship/Polymarket-Arbitrage-Trading-Bot | 339 | BTC 15-min | Арбитраж, адаптивный predictor | TypeScript |
| 6 | ImMike/polymarket-arbitrage | 58 | PM↔Kalshi | Cross-platform арбитраж, bundle | Python |
| 7 | dev-protocol/polymarket-bot | 312 | Copy/арбитраж | Copy trading, mempool, frontrun | TypeScript |
| 8 | Gabagool2-2/polymarket-trading-bot-python | 302 | Крипто | Endcycle sniper, buy-above/opposite | Python |
| 9 | 0xalberto/polymarket-arbitrage-bot | 69 | Арбитраж | Single/multi-market arb | — |
| 10 | theSchein/pamela | 40 | General | ElizaOS, 24/7, Telegram | TypeScript |
| 11 | artvandelay/polymarket-agents | 1 | Cricket/MCP | Claude Sonnet, pluggable | Python |
| 12 | BlackSkyorg/polymaket-ai-trading-bot | 70 | General | LLM, superforecasting, LangChain | Python |
| 13 | codeyourlimits/polyclawd | — | BTC 15-min | Sentiment, RSI, Kelly-inspired | Python |
| 14 | jackbeecher23/polymarket | 8 | NBA | Мультибук → true odds, Kelly | Python |
| 15 | jbram22/ev_sports_betting | 16 | NBA/NFL/NCAA | +EV scan, Kelly | Python |
| 16 | craymichael/Smart-NFL-Line-Betting | — | NFL | Statistical modeling, Kelly | Python |
| 17 | jjc256/devigger | — | Мультиспорт | FanDuel vs Pinnacle, GUI, Kelly | — |
| 18 | sasprojectdobs/predictions-trader | 66 | PM + Drift | Custom/arb strategies | — |
| 19 | agent-next/polymarket-paper-trader | — | Paper | Симулятор order book, backtest | — |
| 20 | ducksybils/polymarket-copytrading | — | Copy | Replicate monitored addresses | Python |

---

## 2. Сравнение по критериям

### Критерии оценки

| Критерий | Наш агент | Gambot | ImMike | solship | TrendTech finance | polyclawd |
|----------|-----------|--------|-------|---------|-------------------|-----------|
| **Pinnacle / sharp lines** | ✅ The Odds API | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Kelly Criterion** | ✅ Fractional 0.25 | ✅ | ❌ | ❌ | ❌ | Kelly-inspired |
| **Risk management** | ✅ Daily stop, consecutive losses, slippage | ❌ | Базовый | ❌ | Edge/liquidity | 20% max, kill switch |
| **Forward-test / backtest** | ✅ snapshots, stats | ❌ | Симуляция | ❌ | ❌ | ❌ |
| **SQLite / P&L tracking** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **FOK + slippage check** | ✅ | FOK | ❌ | ❌ | ❌ | ❌ |
| **Whitelist лиг** | ✅ Tier1/Tier2/SKIP | ❌ | ❌ | — | — | — |
| **NO при YES>0.65** | ✅ | ❌ | ❌ | — | — | — |
| **Draw prob (футбол)** | 🔶 План | ❌ | ❌ | — | — | — |
| **Временное окно 2–8ч** | ✅ | ❌ | ❌ | — | — | — |
| **LLM / RAG** | 🔶 Фаза 3 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dashboard / UI** | Rich console | ❌ | ✅ Live web | ❌ | ❌ | ❌ |
| **Telegram** | 🔶 План | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Dry-run / paper** | recommend mode | ❌ | Sim mode | ❌ | ✅ | ❌ |

🔶 = в плане или частично

---

## 3. Что реализовано лучше у конкурентов (проверено)

### 3.1 Live web dashboard — ImMike/polymarket-arbitrage

**Что у них:** Real-time web UI для мониторинга 5000+ рынков, bundle arb, market making.

**У нас:** Rich console, только CLI.

**Проверка:** Репозиторий ImMike содержит упоминание live dashboard в описании и README.

**Рекомендация:** Добавить простой web dashboard (Flask/FastAPI + WebSocket) или интеграцию с Streamlit для мониторинга сигналов и P&L в реальном времени.

---

### 3.2 Симуляция с реалистичным order book — agent-next/polymarket-paper-trader

**Что у них:** Level-by-level order book execution, реальные fees Polymarket, slippage tracking, GTC/GTD ордера. Заявлено +18% ROI за неделю в paper mode (источник: PyPI, agent-next).

**У нас:** Forward-test записывает snapshots, но без полной симуляции walk по order book.

**Проверка:** polymarket-paper-trader на PyPI, npm clawhub; описание функций подтверждено документацией.

**Рекомендация:** Изучить polymarket-paper-trader для улучшения forward-test: добавить симуляцию walk по order book и учёт комиссий при расчёте fill price.

---

### 3.3 Rust-ядро для скорости — CraftyGeezer (упомянут, репо 404)

**Что у них:** Rust core + PyO3 для микросекундного сканирования, Python для API. Kelly + GPT-4o validation.

**У нас:** Pure Python, asyncio.

**Проверка:** Описание из AgentBets.ai; репозиторий CraftyGeezer/Kalshi-Polymarket-Ai-bot возвращал 404 при проверке — данные могут быть устаревшими.

**Рекомендация:** При росте объёма сканирования рассмотреть вынос hot path (matching, edge calc) в Rust через PyO3. Не приоритет для MVP.

---

### 3.4 LLM + RAG — Polymarket/agents, BlackSkyorg

**Что у них:** Официальный agents — RAG (Chroma), news, betting services. BlackSky — superforecasting, LangChain, FastAPI, Docker.

**У нас:** Фаза 3 — probability.py с LLM; RAG не планировался.

**Проверка:** README Polymarket/agents и BlackSkyorg подтверждают RAG и LLM stack.

**Рекомендация:** Для Фазы 3 (non-sports) взять за основу Polymarket/agents или BlackSkyorg: готовые RAG-пайплайны, интеграция с Gamma. Не изобретать с нуля.

---

### 3.5 Value betting с maker-first — TrendTechVista/polymarket-finance-bot

**Что у них:** Limit orders на best bid + 1 tick, ликвидность-аware sizing, edge threshold.

**У нас:** FOK (Fill-Or-Kill), slippage check перед ордером.

**Проверка:** Описание из поиска и README; детали реализации не проверялись в коде.

**Рекомендация:** Для рынков с достаточной ликвидностью рассмотреть maker-first: limit на bid+1 tick вместо FOK — лучше fill quality. Нужен анализ spread и комиссий.

---

### 3.6 Multi-venue (Polymarket + Kalshi) — ImMike, jtdoherty/arb-bot

**Что у них:** Сканирование обоих рынков, cross-platform арбитраж.

**У нас:** Только Polymarket.

**Проверка:** ImMike — проверен; jtdoherty/arb-bot — Python, async, упомянут в поиске.

**Рекомендация:** Добавить в Фазу 2 (арбитраж) опциональный модуль Kalshi: сопоставление событий и cross-venue arb. Требует Kalshi API, другой формат (cents vs 0–1).

---

### 3.7 MCP server (10 tools) — artvandelay/polymarket-agents

**Что у них:** MCP server с odds, orderbook, spread, history — интеграция с Claude через OpenRouter.

**У нас:** CLI, нет MCP.

**Проверка:** Репозиторий 1 star; наличие MCP подтверждено описанием.

**Рекомендация:** MCP полезен для исследования и отладки в Cursor/Claude. Добавить опциональный MCP server с read-only инструментами (odds, orderbook, signals) — низкий приоритет.

---

## 4. Сводная таблица: наш агент vs конкуренты

| Фича | Наш | Gambot | ImMike | solship | Polymarket/agents |
|------|-----|--------|--------|---------|-------------------|
| Pinnacle edge | ✅ | ✅ | ❌ | ❌ | ❌ |
| Kelly | ✅ | ✅ | ❌ | ❌ | ❌ |
| Risk (stop-loss, consecutive) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Forward-test | ✅ | ❌ | Sim | ❌ | ❌ |
| SQLite P&L | ✅ | ❌ | ❌ | ❌ | ❌ |
| Whitelist лиг | ✅ | ❌ | ❌ | — | ❌ |
| NO filter (YES>0.65) | ✅ | ❌ | ❌ | — | ❌ |
| Time window 2–8h | ✅ | ❌ | ❌ | — | ❌ |
| Web dashboard | ❌ | ❌ | ✅ | ❌ | ❌ |
| Paper trader (order book sim) | Частично | ❌ | ✅ | ❌ | ❌ |
| LLM/RAG | План | ❌ | ❌ | ❌ | ✅ |
| Cross-venue (Kalshi) | ❌ | ❌ | ✅ | ❌ | ❌ |

---

## 5. Итоговые рекомендации (приоритет)

| # | Рекомендация | Источник | Приоритет |
|---|--------------|----------|-----------|
| 1 | Изучить polymarket-paper-trader для улучшения forward-test (order book sim, fees) | agent-next | Высокий |
| 2 | Добавить простой web dashboard для мониторинга | ImMike | Средний |
| 3 | Для Фазы 3 LLM — использовать Polymarket/agents или BlackSky RAG как базу | PM/agents, BlackSky | Высокий (Фаза 3) |
| 4 | Рассмотреть maker-first (limit bid+1) вместо FOK на ликвидных рынках | TrendTech | Низкий |
| 5 | Cross-venue Kalshi в Фазе 2 (арбитраж) | ImMike | Средний |
| 6 | MCP server для research — опционально | artvandelay | Низкий |

---

## 6. Задачи по рекомендациям (пошагово)

### Задача 1. Улучшение forward-test через order book-симуляцию

**Цель:** Получить реалистичные оценки fill price и slippage без реальных ставок.

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 1.1 | Установить polymarket-paper-trader (`npm clawhub install` или pip) | Доступ к API симулятора |
| 1.2 | Изучить формат order book в их симуляторе (level-by-level) | Понимание, как они воспроизводят walk по book |
| 1.3 | Выгрузить снимки order book из нашего collector/snapshots | Сырые данные для симуляции |
| 1.4 | Реализовать `backtest/simulator.py`: walk по levels, учёт fees Polymarket | Расчёт предполагаемого fill для каждого сигнала |
| 1.5 | Добавить в таблицу snapshots колонку `sim_fill_price` | Сравнение: сигнальная цена vs симулированный fill |
| 1.6 | В `show_signal_calibration()` выводить: signal_price, sim_fill, diff (bps) | Метрика качества исполнения в paper mode |

**Что даст:** Оценка, насколько реальный slippage съедает edge; коррекция ожидаемого ROI до перехода в auto mode.

---

### Задача 2. Web dashboard для мониторинга

**Цель:** Удалённый просмотр сигналов и P&L в реальном времени (вместо консоли).

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 2.1 | Создать `dashboard/` с FastAPI или Streamlit | Лёгкий веб-сервер |
| 2.2 | Эндпоинт `/signals` — последние N сигналов из DB | Таблица сигналов в браузере |
| 2.3 | Эндпоинт `/stats` — P&L, WR, банкролл из performance | Сводка за сессию/день |
| 2.4 | WebSocket или polling для обновления при новом цикле main.py | Live-обновление без refresh |
| 2.5 | Опционально: график equity curve (matplotlib → PNG или plotly) | Визуализация динамики |

**Что даст:** Мониторинг без SSH; возможность поделиться дашбордом с доверенным лицом; основа для Telegram-уведомлений через webhook.

---

### Задача 3. LLM + RAG для Фазы 3 (non-sports)

**Цель:** Оценка вероятностей для политики, финансов, корпоративов через готовый стек.

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 3.1 | Клонировать Polymarket/agents или BlackSkyorg, разобрать структуру | Понимание RAG-пайплайна |
| 3.2 | Выделить модуль: news → embeddings → Chroma → LLM prompt | Переиспользуемый pipeline |
| 3.3 | Создать `analysis/probability.py`: функция `estimate_probability(market) -> float` | Единый интерфейс для p_true |
| 3.4 | Подключить к signals.py: для non-sports использовать probability.py, для sports — Pinnacle | Расширение на политику/финансы |
| 3.5 | Добавить confidence score и MIN_CONFIDENCE в config | Фильтр неопределённых прогнозов |

**Что даст:** Торговля не только спортом; использование переоценки на политических/финансовых рынках; RAG ускоряет разработку (не писать с нуля).

---

### Задача 4. Maker-first (limit bid+1) вместо FOK

**Цель:** Улучшить fill quality на ликвидных рынках, снизить проскальзывание.

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 4.1 | Замерить типичный spread и частоту partial fill на наших рынках | Основание для выбора FOK vs limit |
| 4.2 | Добавить в config `ORDER_TYPE: "FOK" | "MAKER"` | Переключатель режима |
| 4.3 | В executor.py: при MAKER — post limit на best_bid + 1 tick, не FOK | Ордер как maker |
| 4.4 | Отменять/переставлять ордер при изменении book (таймаут 5–10 мин) | Защита от зависших ордеров |
| 4.5 | Сравнить fill rate и slippage FOK vs MAKER за 2 недели | Данные для решения |

**Что даст:** Потенциально выше fill rate и меньше проскальзывание; при низкой ликвидности FOK остаётся надёжнее.

---

### Задача 5. Cross-venue Kalshi (Фаза 2)

**Цель:** Арбитраж между Polymarket и Kalshi при расхождении цен.

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 5.1 | Зарегистрировать Kalshi API, изучить форматы (cents, event_id) | Доступ к данным |
| 5.2 | Создать `data/kalshi_client.py` — аналог collector для Kalshi | Единый интерфейс markets/orderbook |
| 5.3 | Функция `match_events(market_pm, market_kalshi)` — по названию, дате, outcome | Сопоставление событий |
| 5.4 | Модуль `analysis/arb_signals.py`: detect cross-venue arb (pm_price vs kalshi_price) | Сигналы арбитража |
| 5.5 | Отдельный executor для Kalshi или единый с маршрутизацией по venue | Исполнение на двух площадках |
| 5.6 | Лимиты по cross-venue позициям (max exposure на одну пару PM–Kalshi) | Риск-контроль |

**Что даст:** Дополнительный источник edge; диверсификация по площадкам; требования по капиталу и API выше.

---

### Задача 6. MCP server для research

**Цель:** Интеграция с Cursor/Claude для исследования рынков через инструменты.

| Шаг | Действие | Результат |
|-----|----------|-----------|
| 6.1 | Добавить зависимости: mcp, fastmcp или аналог | Базовый MCP-стек |
| 6.2 | Создать `mcp_server/tools.py` с tools: get_odds(market_id), get_orderbook(market_id), get_signals() | Read-only доступ к данным |
| 6.3 | Зарегистрировать сервер в Cursor MCP config | Появление инструментов в чате |
| 6.4 | Документировать использование в README | Простота онбординга |

**Что даст:** Быстрый анализ «какие odds у рынка X» без запуска скриптов; удобство при отладке и исследовании.

---

## 7. Приоритизация и зависимости

| Задача | Зависимости | Оценка (дни) |
|--------|-------------|--------------|
| 1. Order book forward-test | Нет | 3–5 |
| 2. Web dashboard | DB, main.py loop | 2–3 |
| 3. LLM/RAG Фаза 3 | Завершённая Фаза 1–2 | 5–7 |
| 4. Maker-first | Executor, данные по spread | 2–3 |
| 5. Kalshi cross-venue | Kalshi API, Фаза 2 | 4–6 |
| 6. MCP server | Нет | 1–2 |

**Рекомендуемый порядок:** 1 → 2 → 4 (при росте ликвидности) → 5 (Фаза 2) → 3 (Фаза 3) → 6 (по необходимости).

---

## 8. Ограничения анализа (исходного)

- **Звёзды GitHub:** сведения на момент поиска; возможны расхождения.
- **Результаты P&L:** у большинства репо нет публичных метрик; цитируемые цифры — из статей (PolyTrack, AgentBets, DEV).
- **Репозитории:** vladmeer, CraftyGeezer — 404 при прямой проверке; в таблице указаны только подтверждённые.
- **Статус кода:** не все репозитории проверялись на актуальность и работоспособность.
