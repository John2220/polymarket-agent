# Polymarket Analytics Agent — Онбординг для агентов

## Быстрый старт

1. **Контекст и правила чата:** `.cursor/CONTEXT_AND_RULES.md`
2. **Правила для агентов:** `.cursor/AGENT_RULES.md`
3. **Формулы P&L:** `FORMULAS_AUDIT.md`
4. **План разработки:** `.cursor/plans/polymarket_analytics_agent_b5985182.plan.md` (в M5Unified)

## Основные скрипты

| Скрипт | Назначение |
|--------|------------|
| `refresh.py` | Обновление Excel: результаты ставок, рекомендации, статистика |
| `analyze_and_place.py` | Анализ рынков, прогнозы, запись ставок (без Pinnacle) |
| `main.py` | Полный цикл с Pinnacle (нужен ODDS_API_KEY в .env) |

## Пути

- **Excel:** `polymarket_рекомендации.xlsx`
- **Кэш API:** `C:\Users\Lomov\.cursor\projects\...\agent-tools\*.txt`
- **План:** `M5Unified\src\utility\.cursor\plans\polymarket_analytics_agent_*.plan.md`

## Критичные правила P&L

- Формула: `pnl = bet * (1/price - 1)` при выигрыше (YES и NO одинаково)
- `price` — цена купленной доли (колонка 7 Excel)
- Для NO **не** использовать `1/(1-price)`

## Рекомендации и чеклисты

- `.cursor/IMPROVEMENT_RECOMMENDATIONS.md`
