"""Запуск FastAPI (REST /stats, /signals). Требует: pip install fastapi uvicorn"""
from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Установите: pip install fastapi uvicorn")
        sys.exit(1)
    uvicorn.run(
        "dashboard.api_app:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )
