# unstop-bot-
> Small, modular Python agent that scrapes Unstop for hackathons, applies rule-based (and optional LLM) filtering, deduplicates with seen.json, and sends Telegram alerts on a schedule via GitHub Actions.

## Overview
This repository implements an agent that regularly checks Unstop for open hackathons and notifies a Telegram chat about new items. It is organized into focused modules for scraping, filtering, optional LLM classification, deduplication, and notification delivery. A GitHub Actions workflow runs the agent on a schedule and persists seen state back to the repository. An interactive long-polling bot mode is also included for on-demand checks.

## What it does
- Loads environment and configuration.
- Fetches open hackathons from Unstop (scraper.py).
- Applies a fast stage-1 rule-based filter (filter.py).
- Optionally runs a Groq LLM classifier for ambiguous items (classifier.py).
- Deduplicates items using seen.json (state.py).
- Sends a Telegram summary + one message per new hackathon, with retry/backoff logic (notifier.py).
- Scheduled run: GitHub Actions workflow (.github/workflows/unstop-hackathon-alert.yml) — runs periodically and commits updated seen.json back.
- Provides an interactive long-polling mode for on-demand checks (bot_check.py) and utilities (get_chat_id.py, user_prefs.py).

## Key capabilities
- Scrapes Unstop for hackathon listings.
- Fast stage-1 filtering by mode/status/paid/domain/keywords.
- Optional stage-2 LLM classification (Groq-compatible) for ambiguous cases.
- Persistent deduplication via seen.json so only new alerts are sent.
- Telegram notifications with retry/backoff.
- On-demand long-polling bot mode and per-user preferences stored as JSON.

## Technology
- Python 3.11 (project references Python 3.11)
- requests
- python-dotenv
- beautifulsoup4 (bs4)
- playwright (optional runtime)
- Telegram Bot API
- Optional: Groq LLM (OpenAI-compatible chat completions endpoint)
- GitHub Actions (cron runner)

Requirements are listed in requirements.txt:
- requests>=2.31.0
- python-dotenv>=1.0.1
- beautifulsoup4>=4.12.3
- playwright>=1.57.0

## Repository structure
Top-level files (as present in the repository):
- README.md
- bot_check.py
- classifier.py
- config.py
- env (directory)
- env_loader.py
- filter.py
- get_chat_id.py
- main.py
- notifier.py
- requirements.txt
- scraper.py
- seen.json
- state.py
- user_prefs.py
- .github/workflows/unstop-hackathon-alert.yml (workflow present in repo)

Main orchestration happens in main.py: load env (env_loader.py) -> fetch (scraper.py) -> check seen (state.py) -> stage1 filter (filter.py) -> optional LLM classify (classifier.py) -> notify (notifier.py) -> persist seen.json.

## Getting started
The repository includes an existing README excerpt with setup guidance. Evidence-backed steps present in the repo include:

- Install dependencies:
  - pip install -r requirements.txt

- Prepare environment and secrets:
  - The existing README mentions copying an env/.env.example to env/.env and filling secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, optional GROQ_API_KEY, GROQ_MODEL, USE_LLM).
  - Note: I did not find an env/.env.example file in the supplied manifests. Inspect env/, env_loader.py, and config.py to determine expected environment variable names and formats before creating env/.env.

- Run the agent locally:
  - python main.py

- Run the long-polling bot locally:
  - python bot_check.py

- Get numeric TELEGRAM_CHAT_ID (utility provided):
  - python get_chat_id.py

If you plan to run locally, inspect env_loader.py and config.py to see how environment variables are loaded and normalized.

## Configuration
- Environment and GitHub Secrets referenced in repository materials:
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID
  - GROQ_API_KEY (optional)
  - GROQ_MODEL (optional; default mentioned in docs: llama3-70b-8192)
  - USE_LLM (optional; set to 0 to disable LLM)

- Preferences:
  - The repository documentation references configuration/preferences such as preferred_mode, include_keywords, exclude_keywords, min_prize_inr, and city_must_include (default "Pune"). However, the audit notes a mismatch between README and config.py: some referenced preference fields (for example city_must_include) are not exposed in config.py as surfaced in the dossier. Inspect config.py directly to confirm available settings before editing.

- State persistence:
  - seen.json is used for deduplication and is committed back by the GitHub Actions workflow to persist state across runs. Review .github/workflows/unstop-hackathon-alert.yml if you need to change persistence behavior.

## Development and quality notes
Known issues (from repository analysis):
- Some source files appear truncated in the supplied dossier (filter.py and scraper.py excerpts end mid-function). Confirm full file contents in the repository.
- classifier.py contains a syntactic problem in the supplied dossier (an invalid default parameter signature). That will prevent import/execution until corrected.
- No unit tests, no test framework or test files were found.
- No CI job is present that validates syntax or runs tests before the scheduled workflow run; the workflow simply runs the main script on a cron.
- The codebase uses prints rather than a structured logging framework in the supplied materials.
- There is limited guidance or example env/.env in the supplied manifests; inspect env_loader.py for exact variable names and normalization logic.

Suggested immediate improvements (from the audit):
- Fix syntactic error(s) in classifier.py and restore any truncated function contents.
- Add a lightweight test suite and a pre-run CI job (syntax checks, unit tests, linting).
- Avoid committing runtime state (seen.json) into the main repository if that is undesirable for your workflow.

## Safety and responsible use
- No secrets appear committed in the supplied files. seen.json in the repository contains only URLs as supplied.
- The GitHub Actions workflow commits seen.json back into the repository. If the contents of seen.json were to include sensitive data in future changes, committing it could expose secrets in repository history. Consider alternative state persistence if this is a concern.
- Environment loading normalizes TELEGRAM_BOT_TOKEN values. The current code does not appear to print secrets, but ensure workflows and local runs do not echo secrets to logs.
- user_prefs.json and user_state.json (per-user JSON files) are stored locally without explicit validation in the supplied materials — do not share repository copies containing private user data.

## Contributing
- Inspect the key orchestration modules first: main.py, scraper.py, filter.py, classifier.py, notifier.py, state.py, and env_loader.py.
- If you intend to run locally, verify environment variable names in env_loader.py and create a local env/.env accordingly.
- Open issues or pull requests for bug fixes (e.g., classifier syntax, truncated files), tests, or documentation updates.
- Because there is no contribution workflow documented in the repository materials, follow standard GitHub contribution practices: branch, commit, and open a PR with a clear description of changes.

(There is no license file present in the supplied dossier; consult the repository to determine licensing.)
