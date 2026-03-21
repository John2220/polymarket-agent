# Запуск recommend mode на 1+ неделю (testing-launch)

## Цель
Накопить данные forward-test перед включением auto mode. Рекомендуемый период: **1–2 недели**.

## Подготовка

1. Создайте `.env` из `.env.example`:
   ```
   ODDS_API_KEY=ваш_ключ_the-odds-api
   ```

2. Установите зависимости: `pip install -r requirements.txt`

## Варианты запуска

### Вариант A: Один цикл (для cron/scheduler)
```bash
python scripts/run_recommend.py
# или с кастомным банкроллом:
python scripts/run_recommend.py --bankroll 2000
```

### Вариант B: Цикл с интервалом (ручной запуск)
```bash
python main.py --mode recommend --once
# Повторять вручную или через внешний scheduler
```

### Вариант C: Непрерывный режим (фон)
```bash
python main.py --mode recommend
# Сканирует каждые POLL_INTERVAL сек (по умолчанию 60)
# Остановить: Ctrl+C
```

## Cron (Windows Task Scheduler / Linux cron)

Каждые 2 часа:
```cron
0 */2 * * * cd /path/to/polymarket-agent && .venv/Scripts/python scripts/run_recommend.py
```

## Просмотр статистики
```bash
python main.py --mode stats
```
- Статистика forward-test (snapshots)
- Калибровка сигналов (predicted vs actual WR)
- Статистика ставок

## Результаты
- Данные пишутся в `agent.db` (таблица `snapshots`)
- После 50+ записей — анализ калибровки
- При WR реальный > WR ожидаемый — стратегия работает → можно включать auto mode
