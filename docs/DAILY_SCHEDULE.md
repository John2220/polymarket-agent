# Ежедневный запуск: результаты + новые ставки

## Скрипт

Из корня репозитория `polymarket-agent/`:

```bat
python scripts/daily_morning.py
```

По умолчанию:
1. **`check_results.py`** (логика `resolve_bets`) — закрытые рынки Polymarket → обновление **snapshots** и **bets** в `agent.db`.
2. **Один цикл** как в `main.py --once` — котировки Pinnacle, сопоставление с рынками, **сигналы только при edge ≥ MIN_EDGE** и после **RiskManager** (окно до события, лимиты банкролла, дневной стоп и т.д.).

Режим **`recommend`** (по умолчанию) — в БД пишутся рекомендации и snapshots, ордера на цепочку **не** отправляются.

Режим **`auto`** — нужны `POLYMARKET_PRIVATE_KEY` и `POLYMARKET_FUNDER_ADDRESS` в `.env`; иначе `load_settings` завершит процесс с ошибкой.

### Параметры

| Параметр | Описание |
|----------|----------|
| `--mode recommend` | Только рекомендации (безопаснее для планировщика) |
| `--mode auto` | Реальные ордера |
| `--bankroll 1000` | Банкролл для Kelly/лимитов |
| `--skip-resolve` | Пропустить шаг проверки результатов |
| `--strict` | Если шаг 1 упал — не запускать шаг 2 |
| `--log-file PATH` | Лог (по умолчанию `logs/daily_morning.log`); `--no-log-file` — только консоль |

Переменная окружения **`PM_MAX_SIGNAL_ROWS`** (по умолчанию `200`) ограничивает **вывод** таблицы сигналов в консоль; исполнение по-прежнему идёт по **всем** сгенерированным сигналам (как в `main.py`).

На **Windows** для кириллицы/Unicode в Rich используйте `daily_morning.bat` или `PYTHONUTF8=1` (батник уже выставляет `chcp 65001`).

## Планировщик заданий Windows

1. **Планировщик заданий** → **Создать простую задачу…**
2. **Триггер:** ежедневно, например **08:00**.
3. **Действие:** запуск программы  
   - **Программа:** полный путь к `python.exe` (например `C:\Users\...\AppData\Local\Programs\Python\Python312\python.exe` или `...\polymarket-agent\.venv\Scripts\python.exe`).
   - **Аргументы:** `scripts\daily_morning.py` (или `--mode recommend` при необходимости).
   - **Рабочая папка:** корень проекта, например `C:\Users\Lomov\Desktop\polymarket-agent`.
4. Убедитесь, что в этой папке есть `.env` с `ODDS_API_KEY` (и ключи Polymarket для `auto`).

Готовый батник (подставьте свой путь):

```bat
@echo off
cd /d C:\Users\Lomov\Desktop\polymarket-agent
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python scripts\daily_morning.py --mode recommend
```

В планировщике укажите **запуск этого `.bat`**.

## Linux (cron)

```cron
0 8 * * * cd /path/to/polymarket-agent && . .venv/bin/activate && python scripts/daily_morning.py --mode recommend >> logs/cron.log 2>&1
```

## Примечание

«Благоприятство для выигрыша» в коде означает **положительный ожидаемый edge** от сравнения с Pinnacle и прохождение **фильтров риска**, а не предсказание исхода матча «на глаз». Реальная прибыль зависит от калибровки модели и дисциплины лимитов.
