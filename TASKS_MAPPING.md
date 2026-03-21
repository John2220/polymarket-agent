# Сопоставление плана проекта и задач по конкурентному анализу

> Сводка соответствия между `polymarket_analytics_agent_b5985182.plan.md` и задачами из `COMPETITIVE_ANALYSIS.md`.

---

## 1. Матрица соответствия

| Задача из конкурентного анализа | Элемент плана | Статус | Комментарий |
|---------------------------------|---------------|--------|-------------|
| **1. Order book forward-test** | `fix-forward-test-volume`, `fix-historical-backtest-module`, `backtest` | Частично | План: snapshots, show_signal_calibration, historical. **Нет** в плане: walk по order book, sim_fill_price, polymarket-paper-trader |
| **2. Web dashboard** | «Telegram — добавить позже», «Dashboard: rich Console» | Частично | План: только rich console + отложенный Telegram. **Нет** в плане: web UI, /signals, /stats, equity curve |
| **3. LLM + RAG (Фаза 3)** | Фаза 3, `probability.py`, «RAG для новостного контекста» | Совпадает | План уже включает probability.py, RAG, политика. Задача уточняет: взять Polymarket/agents как базу |
| **4. Maker-first вместо FOK** | executor.py: «FOK», «slippage check» | Нет в плане | План только FOK. Maker-first — **новая** идея из TrendTech |
| **5. Cross-venue Kalshi (Фаза 2)** | Фаза 2: «esports + арбитраж», «арбитраж под-рынков» в Фазе 3 | Частично | План: арбитраж под-рынков (Polymarket). **Нет**: cross-venue PM↔Kalshi |
| **6. MCP server** | — | Нет в плане | **Полностью новая** задача для research/отладки |

---

## 2. Сопоставление по фазам плана

### Фаза 1 (Sports Value Betting — MVP)

| Todo плана | Соответствие задачам конкурентного анализа |
|------------|---------------------------------------------|
| scaffold, data-models, signals-kelly, risk-executor | Базовый скелет — не связано с 6 задачами |
| backtest | **Задача 1 (часть):** forward-test есть; добавить order book sim |
| fix-forward-test-volume | **Задача 1:** запись всех сигналов, show_signal_calibration — уже в плане. Расширение: sim_fill_price |
| fix-historical-backtest-module | **Задача 1:** historical backtest — есть. Расширение: polymarket-paper-trader для walk по book |

**Вывод:** Задача 1 (order book forward-test) **расширяет** существующие fix-forward-test-volume и fix-historical-backtest-module, не заменяет их.

---

### Фаза 2 (Auto Mode + Esports)

| Элемент плана | Соответствие |
|---------------|--------------|
| Auto mode, slippage protection | Есть |
| Esports (Dota 2, LoL, CS2) | Есть |
| Telegram | **Задача 2:** web dashboard может быть альтернативой/дополнением перед Telegram |
| Арбитраж | **Задача 5:** планируется «арбитраж» — уточнение: cross-venue Kalshi как часть Фазы 2 |

**Вывод:** Задача 2 (dashboard) дополняет «Telegram — добавить позже». Задача 5 (Kalshi) уточняет «арбитраж» в Фазе 2.

---

### Фаза 3 (LLM + Non-Sports)

| Элемент плана | Соответствие |
|---------------|--------------|
| probability.py с LLM | **Задача 3:** полное совпадение |
| Арбитраж под-рынков (multi-outcome) | План — только внутри Polymarket |
| RAG для новостного контекста | **Задача 3:** использовать Polymarket/agents или BlackSky как базу |

**Вывод:** Задача 3 совпадает с Фазой 3; добавляет конкретику: брать готовый RAG из Polymarket/agents.

---

## 3. Новые задачи (отсутствуют в плане)

| Задача | Где разместить в плане |
|--------|------------------------|
| **Задача 4. Maker-first** | Фаза 2 или после стабилизации auto mode; раздел «Исполнение ордеров» |
| **Задача 6. MCP server** | Вне фаз; опциональная инфраструктура для разработки |

---

## 4. Рекомендуемые todos для добавления в план

Ниже — формулировки для новых/уточнённых todo в плане.

### Новый todo: `task-order-book-sim` (расширение backtest)

```yaml
- id: task-order-book-sim
  content: "[СРЕДНИЙ] Улучшить forward-test: симуляция walk по order book (polymarket-paper-trader). Добавить sim_fill_price в snapshots, выводить slippage (bps) в show_signal_calibration(). Файлы: backtest/simulator.py, storage/db.py, analysis/backtest.py"
  status: pending
```

### Новый todo: `task-web-dashboard`

```yaml
- id: task-web-dashboard
  content: "[СРЕДНИЙ] Web dashboard: FastAPI/Streamlit, /signals, /stats, polling/WebSocket для live. Альтернатива или дополнение к Telegram. Папка dashboard/"
  status: pending
```

### Новый todo: `task-fase3-use-pm-agents`

```yaml
- id: task-fase3-use-pm-agents
  content: "[Фаза 3] Использовать Polymarket/agents или BlackSky как базу для probability.py: RAG (Chroma), news→embeddings→LLM. Не писать с нуля."
  status: pending
```

### Новый todo: `task-maker-first`

```yaml
- id: task-maker-first
  content: "[НИЗКИЙ] Опционально: ORDER_TYPE MAKER (limit bid+1) вместо FOK на ликвидных рынках. Замерить spread, сравнить fill rate за 2 нед."
  status: pending
```

### Новый todo: `task-kalshi-cross-venue`

```yaml
- id: task-kalshi-cross-venue
  content: "[Фаза 2] Cross-venue арбитраж Polymarket↔Kalshi: kalshi_client.py, match_events(), arb_signals.py. Требует Kalshi API."
  status: pending
```

### Новый todo: `task-mcp-server`

```yaml
- id: task-mcp-server
  content: "[ОПЦИОНАЛЬНО] MCP server с tools get_odds, get_orderbook, get_signals для Cursor/Claude research."
  status: pending
```

---

## 5. Сводная таблица: план ↔ задачи

| # | Задача (конкурентный анализ) | В плане? | Действие |
|---|------------------------------|----------|----------|
| 1 | Order book forward-test | Частично (backtest, fix-forward-test, fix-historical) | Добавить task-order-book-sim |
| 2 | Web dashboard | Частично (Telegram отложен) | Добавить task-web-dashboard |
| 3 | LLM + RAG Фаза 3 | Да (Фаза 3, probability.py) | Добавить task-fase3-use-pm-agents как уточнение |
| 4 | Maker-first | Нет | Добавить task-maker-first |
| 5 | Kalshi cross-venue | Частично (арбитраж в Фазе 2) | Добавить task-kalshi-cross-venue |
| 6 | MCP server | Нет | Добавить task-mcp-server |

---

## 6. Порядок внедрения (с учётом плана)

1. **Сначала:** Завершить текущие fix-* (все completed в плане).
2. **Задача 1:** После накопления 50+ snapshots — добавить order book sim для уточнения ROI.
3. **Задача 2:** Web dashboard — параллельно или вместо раннего Telegram.
4. **Фаза 2:** Включить task-kalshi-cross-venue и task-maker-first (при росте объёма).
5. **Фаза 3:** task-fase3-use-pm-agents — при старте probability.py.
6. **Задача 6:** MCP server — по необходимости при отладке.
