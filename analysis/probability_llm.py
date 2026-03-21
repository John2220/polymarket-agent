"""
Фаза 3: вероятности для non-sports через LLM / RAG (task-fase3-use-pm-agents).

Не включать в основной пайплайн Фазы 1 (спорт → Pinnacle).

Рекомендуемая база:
  - https://github.com/Polymarket/agents (официальные примеры)
  - собственный RAG: Chroma + новостной корпус + промпт с ограничениями

Подключение: после стабилизации спортивного edge заменить/дополнить
`signals.py` для категорий вне спорта.
"""
from __future__ import annotations

from typing import Optional


def estimate_probability_from_text_stub(question: str, context: str = "") -> Optional[float]:
    """
    Заглушка: вернуть None (сигнал «нет LLM-оценки»).

    Реальная реализация: вызов LLM с цитатами из RAG, калибровка на past resolves.
    """
    _ = (question, context)
    return None
