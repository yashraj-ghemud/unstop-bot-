from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    """
    Loads secrets from `env/.env` if present.
    Environment variables already set (e.g. GitHub Actions Secrets) take precedence.
    """
    p = Path("env") / ".env"
    if p.exists():
        load_dotenv(p, override=False)

    # Robustness: users sometimes paste `TELEGRAM_BOT_TOKEN=...` into the value by mistake.
    # If that happens, normalize it at runtime.
    import os

    tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if tok.lower().startswith("telegram_bot_token="):
        os.environ["TELEGRAM_BOT_TOKEN"] = tok.split("=", 1)[1].strip()

