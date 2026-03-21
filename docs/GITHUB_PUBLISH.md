# Публикация на GitHub

На этой машине **Git не найден в PATH** — команды ниже выполните локально (Git for Windows + аккаунт GitHub).

## Уже сделано в проекте

- Удалён реальный `ODDS_API_KEY` из `.env` (заполните снова из [the-odds-api.com](https://the-odds-api.com); **старый ключ лучше отозвать/заменить** в кабинете).
- `.gitignore`: `.env`, `.env.*` (кроме `.env.example`), `*.db`, `.venv`, Excel, `data/market_cache/*`.
- Добавлены `LICENSE` (MIT), `SECURITY.md`.

## Команды (PowerShell, каталог проекта)

```powershell
cd $HOME\Desktop\polymarket-agent

git init
git add .
git status   # убедитесь: нет .env, нет *.xlsx, нет data/market_cache/*.txt

git branch -M main
git commit -m "Initial commit: Polymarket analytics agent"
```

### Вариант A: GitHub CLI (`gh`)

```powershell
gh auth login
gh repo create polymarket-agent --public --source=. --remote=origin --push
```

При занятом имени: `gh repo create YOUR_USERNAME/polymarket-agent --public --source=. --remote=origin --push`

### Вариант B: вручную

1. На https://github.com/new создайте репозиторий **без** README (пустой).
2. Выполните (подставьте свой URL):

```powershell
git remote add origin https://github.com/YOUR_USERNAME/polymarket-agent.git
git push -u origin main
```

## После пуша

- В корне репозитория на GitHub: описание, темы (`polymarket`, `python`, `trading`).
- Локально снова пропишите ключи в `.env` (файл не коммитится).
