# Отчёт бэктеста 2025 (симулированные данные)

## Важно
**Использованы синтетические данные**, т.к. реальные исторические котировки Pinnacle + Polymarket за 2025 требуют платной подписки The Odds API (~$15/мес). Результаты — ориентировочные.

## Результаты (500 событий, 261 ставка)

| Метрика        | Значение  |
|----------------|-----------|
| Win Rate       | 54.0%     |
| P&L            | +$815.62  |
| ROI            | 7.6%      |
| Sharpe Ratio   | 1.31      |
| Max Drawdown   | 31.3%     |

### По лигам
| Лига                    | Ставок | WR    | P&L      |
|-------------------------|--------|-------|----------|
| soccer_epl              | 69     | 55.1% | +$381.82 |
| basketball_nba          | 52     | 57.7% | +$134.92 |
| soccer_uefa_champs_league | 69  | 52.2% | +$289.39 |
| soccer_mexico_ligamx    | 71     | 52.1% | +$9.49   |

---

## Рекомендации: что добавить в проект

### 1. Реальные исторические данные
- **The Odds API Historical** — подписка ~$15/мес, endpoint `/v4/historical/...`
- Добавить `backtest/fetch_historical_odds.py` — загрузка архива по датам
- Экспорт resolved snapshots из forward-test в формат `historical_events.json`

### 2. Мониторинг drawdown в live
- Алерт при достижении 15–20% drawdown от пика
- Пауза ставок на 24ч при max_drawdown_pct > 25%

### 3. Фильтр по лиге на основе бэктеста
- Liga MX показала WR 52.1% и минимальный P&L — рассмотреть понижение tier или skip
- NBA — лучший ROI; приоритизировать в matching

### 4. Консервативный Kelly при высокой просадке
- При drawdown > 20%: `kelly_multiplier *= 0.5` до восстановления

### 5. Экспорт forward-test → historical
- Скрипт `scripts/export_snapshots_to_historical.py`: resolved snapshots → JSON для бэктеста
- Позволит накапливать реальные данные без платного API
