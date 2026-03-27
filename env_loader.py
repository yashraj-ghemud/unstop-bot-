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

