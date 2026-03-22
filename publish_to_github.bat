@echo off
setlocal
set GITHUB_USER=YOUR_GITHUB_USERNAME
set REPO=polymarket-agent

cd /d "%~dp0"

if exist "C:\Program Files\Git\bin\git.exe" set PATH=C:\Program Files\Git\bin;%PATH%
if exist "C:\Program Files (x86)\Git\bin\git.exe" set PATH=C:\Program Files (x86)\Git\bin;%PATH%

echo [1/5] Checking Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git not found. Install from https://git-scm.com/download/win
    pause
    exit /b 1
)

if "%GITHUB_USER%"=="YOUR_GITHUB_USERNAME" (
    set /p GITHUB_USER="Enter your GitHub username: "
)

echo [2/5] Init and remote...
if not exist ".git" (
    git init
    git branch -M main
)
git remote remove origin 2>nul
git remote add origin https://github.com/%GITHUB_USER%/%REPO%.git

echo [3/5] Verifying .gitignore...
if exist ".env" (
    echo WARNING: .env exists - make sure it is in .gitignore
) else (
    echo OK: .env excluded
)

echo [4/5] Add and commit...
git add .
git commit -m "Initial commit: Polymarket value betting agent" 2>nul

echo [5/5] Push...
git push -u origin main

if errorlevel 1 (
    echo.
    echo Push failed. Check: username, token at GitHub Settings
) else (
    echo Done: https://github.com/%GITHUB_USER%/%REPO%
)
pause
