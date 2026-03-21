@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM Утренний цикл: обновить результаты + один проход сигналов
REM Укажите свой путь к проекту при копировании на другой ПК.

cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python scripts\daily_morning.py --mode recommend %*
exit /b %ERRORLEVEL%
