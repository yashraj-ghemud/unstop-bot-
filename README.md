# Unstop Hackathon Alert Agent (Telegram)

Headless automation that checks Unstop for new hackathons and sends Telegram alerts on a schedule via GitHub Actions.

## What it does

- Fetches open hackathons from Unstop (`scraper.py`)
- Stage-1 filtering (fast rules): city/mode/keywords/prize (`filter.py`)
- Stage-2 filtering (optional): Groq LLM classification for ambiguous items (`classifier.py`)
- Deduplicates with `seen.json` so you only get new alerts (`state.py`)
- Sends one Telegram message per new hackathon + a summary header (`notifier.py`)
- Runs every 6 hours using GitHub Actions and commits `seen.json` back

## Setup

### 1) Create a Telegram bot + get chat id

- Create a bot via BotFather and get `TELEGRAM_BOT_TOKEN`
- Get your `TELEGRAM_CHAT_ID`:
  - Message your bot once in Telegram
  - Call `getUpdates`:
    - `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
  - Find `message.chat.id`

### 2) Optional: Groq LLM (free)

- Create a Groq API key and save it as `GROQ_API_KEY`
- (Optional) Set `GROQ_MODEL` (default used: `llama3-70b-8192`)

### 3) Configure preferences

Edit `config.py`:
- `preferred_mode`: `"online" | "offline" | "both"`
- `include_keywords`, `exclude_keywords`
- `min_prize_inr`
- `city_must_include` (default `"Pune"`)

### 4) GitHub Secrets

In your GitHub repo: Settings → Secrets and variables → Actions → New repository secret

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GROQ_API_KEY` (optional, enables LLM)
- `GROQ_MODEL` (optional)
- `USE_LLM` (optional; set to `0` to disable LLM)

## Run locally (optional)

```bash
pip install -r requirements.txt
set TELEGRAM_BOT_TOKEN=...
set TELEGRAM_CHAT_ID=...
set GROQ_API_KEY=...   # optional
python main.py
```

## On-demand: message the bot "check"

This project also includes a simple long-polling listener (`bot_check.py`).

Important: GitHub Actions **cannot** keep a bot running 24/7. Use this on your laptop (while it's on),
or deploy it to an always-on free service.

Run locally:

```bash
set TELEGRAM_BOT_TOKEN=...
set TELEGRAM_CHAT_ID=...   # optional safety: only respond in this chat
set GROQ_API_KEY=...       # optional
python bot_check.py
```

Then in Telegram, send: `check`

## GitHub Actions

Workflow file: `.github/workflows/unstop-hackathon-alert.yml`
- Cron: every 6 hours
- Commits `seen.json` back to the repository for dedup persistence

