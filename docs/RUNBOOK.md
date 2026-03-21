# Runbook: команды и окружение

Краткая шпаргалка по скриптам, которые дополняют основной CLI (`main.py`).

## Предварительно

```bash
cd polymarket-agent
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполните ODDS_API_KEY и при необходимости ключи Polymarket (только для `--mode auto`).
```

---

## `check_results.py` — резолвы Gamma → SQLite

Подтягивает закрытые рынки с Polymarket (Gamma) и обновляет таблицы `snapshots` и `bets` в `agent.db`.

| Команда | Назначение |
|---------|------------|
| `python check_results.py` | Одна проверка всех незавершённых записей |
| `python check_results.py --schedule` | Цикл каждые **60 минут** (Ctrl+C — выход) |
| `python check_results.py --record-bet` | Служебно: записать тестовую ставку Aston Villa в БД |

Требуется рабочий `.env` (сеть, настройки коллектора). **Excel не трогает** — только `agent.db`.

---

## `refresh.py` — Excel + ручные исходы

Обновляет листы **«Ставки»**, **«Статистика»**, **«Рекомендации»** в файле Excel.

- Пути к Excel и к JSON-кэшу рынков задаются через **переменные окружения** (удобно для публичного репозитория без абсолютных путей). См. `.env.example`, блок `refresh.py`.
- Ручные исходы, если Gamma не дал однозначного резолва: словарь `MANUAL_RESULTS` в `refresh.py` (ключ — **точная** строка вопроса из колонки 3 Excel). См. `.cursor/AGENT_RULES.md` (R4).

```bash
python refresh.py
```

Если не задан кэш рынков, в консоли будет подсказка; таблица ставок и статистика по уже заполненному Excel всё равно пересчитываются.

**Локально (после переноса с абсолютных путей):** скопируйте JSON-кэши в `data/market_cache/` **или** добавьте в `.env` строку  
`REFRESH_MARKET_CACHE_FILES=C:\полный\путь\к\файлу1.txt;C:\полный\путь\к\файлу2.txt`  
(разделитель `;`, как раньше в коде).

---

## Основной агент

```bash
python main.py --mode recommend   # сигналы + forward-test в БД
python main.py --mode auto        # то же + ордера (нужен приватный ключ)
python main.py --mode stats       # сводка по БД
```

---

## Дашборд и API

```bash
python scripts/run_dashboard.py   # Streamlit
python scripts/run_api.py         # FastAPI, см. порт в выводе
```

---

## Сводка по SQLite

```bash
python scripts/print_bets_summary.py
```

---

## Публичный репозиторий (без утечек)

- Не коммитить: `.env`, `*.db`, `polymarket_рекомендации.xlsx`, содержимое `data/market_cache/` (локальные JSON).
- В репозитории остаются только `.env.example` и при необходимости пустой `data/market_cache/.gitkeep`.

Подробнее — раздел «Задача: runbook + публичный GitHub» в плане проекта (`.cursor/plans/...`).
