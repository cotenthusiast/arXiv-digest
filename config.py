"""
config.py
Reads environment variables and exposes typed, validated configuration.
All other modules import from here — nothing reads os.environ directly.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # Anthropic
    anthropic_api_key: str

    # Telegram
    telegram_bot_token: str
    telegram_channel_id: str  # e.g. "@mydigestchannel" or numeric "-1001234567890"

    # arXiv
    arxiv_categories: list[str] = field(default_factory=lambda: ["cs.CL", "cs.AI", "cs.LG"])
    max_results_per_category: int = 100  # how many to fetch per category before ranking

    # Ranking / posting
    top_n: int = 20  # total papers posted to Telegram per day

    # Summarisation
    model: str = "claude-sonnet-4-20250514"

    # Paths
    csv_path: str = "data/digest.csv"


def load_config() -> Config:
    """Load and validate config from environment. Raises if required vars are missing."""

    def _require(key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise EnvironmentError(f"Required environment variable '{key}' is not set.")
        return val

    def _int(key: str, default: int) -> int:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            raise EnvironmentError(f"Environment variable '{key}' must be an integer, got: {val!r}")

    categories_raw = os.getenv("ARXIV_CATEGORIES", "cs.CL,cs.AI,cs.LG")
    categories = [c.strip() for c in categories_raw.split(",") if c.strip()]

    return Config(
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_require("TELEGRAM_CHANNEL_ID"),
        arxiv_categories=categories,
        max_results_per_category=_int("MAX_RESULTS_PER_CATEGORY", 100),
        top_n=_int("TOP_N", 20),
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        csv_path=os.getenv("CSV_PATH", "data/digest.csv"),
    )
