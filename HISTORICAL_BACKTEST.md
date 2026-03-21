# Исторический бэктест (fix-historical-backtest-module)

## Запуск

### Демо на синтетических данных
```bash
python scripts/run_historical_backtest.py --demo --events 150
```
Или напрямую:
```bash
python -m backtest.historical
```

### С файлом данных
```bash
python scripts/run_historical_backtest.py --file data/historical_events.json
```

## Формат JSON
```json
{
  "events": [
    {
      "sport_key": "basketball_nba",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "commence_time": "2024-01-15T19:00:00Z",
      "pinnacle_yes_prob": 0.55,
      "pm_yes_price": 0.50,
      "matched_team": "Lakers",
      "outcome": "Yes"
    }
  ]
}
```

- `pinnacle_yes_prob` — devigged Pinnacle вероятность для YES (напр. победа home)
- `pm_yes_price` — цена Polymarket YES на момент сигнала
- `matched_team` — команда, на которую ставим (для YES)
- `outcome` — фактический исход: "Yes" (выигрыш matched_team) или "No"

## Источники данных
- **The Odds API** (платно): `https://api.the-odds-api.com/v4/historical/...` — нужна подписка ~$15/мес
- **Экспорт**: можно собирать данные из forward-test (snapshots) после разрешения рынков

## Метрики
- Equity curve, Win Rate, ROI
- Sharpe Ratio (годовой)
- Max Drawdown (%)
- WR по лигам
