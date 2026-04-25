"""Load and validate environment-backed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    deepseek_api_key: str

    @staticmethod
    def from_env() -> Settings:
        bot_token = (os.getenv("BOT_TOKEN") or "").strip()
        deepseek_api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        missing = [name for name, val in (
            ("BOT_TOKEN", bot_token),
            ("DEEPSEEK_API_KEY", deepseek_api_key),
        ) if not val]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Missing required environment variable(s): {joined}. "
                "Copy .env.example to .env and set values, or export them in your shell."
            )
        return Settings(bot_token=bot_token, deepseek_api_key=deepseek_api_key)
