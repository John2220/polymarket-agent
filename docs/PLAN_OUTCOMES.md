# Итоги по плану Polymarket Analytics Agent

Дата сводки: 2026-03-18.

## Все пункты YAML плана

| ID | Статус | Комментарий |
|----|--------|-------------|
| scaffold … agent-rules | completed | Как в плане |
| task-order-book-sim | completed | Симулятор стакана, `snapshot_entry_price`, калибровка |
| task-web-dashboard | completed | Streamlit `dashboard/app.py` |
| **task-maker-first** | **completed** | `USE_MAKER_FIRST` + GTC/post_only, исправлен вызов `post_order` (раньше лишний аргумент у `create_and_post_order`) |
| **task-mcp-server** | **completed (альтернатива)** | REST: `dashboard/api_app.py` — `/health`, `/stats`, `/signals`, `/bets/summary`. Полноценный MCP stdio — опционально позже |
| **task-kalshi-cross-venue** | **каркас** | `integrations/kalshi_client.py`, `analysis/arb_signals.py` — без ключей API торговля не активна |
| **task-fase3-use-pm-agents** | **каркас** | `analysis/probability_llm.py` + ссылки на Polymarket/agents; не влияет на спортивный пайплайн |

## Влияние на проект

- **MAKER:** только при `USE_MAKER_FIRST=true` в `.env`; иначе поведение как раньше (FOK). Лимиты остаются в `RiskManager`.
- **REST API:** отдельный процесс, не трогает `main.py`; нужны `fastapi` и `uvicorn`.
- **Kalshi / LLM:** новые модули не импортируются из `main.py` — нулевое влияние до явного подключения.

## Команды

```bash
# Streamlit
python scripts/run_dashboard.py

# REST
pip install fastapi uvicorn
python scripts/run_api.py
# → http://127.0.0.1:8765/docs
```
