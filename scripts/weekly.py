"""
weekly.py
Posts a weekly roundup of all logged papers to the Telegram channel.

Reads the past 7 days of entries from the CSV log (all rows, not just posted=True)
and sends one message per day's batch. Intended to run every Sunday morning.

Cron: 0 9 * * 0
"""

import csv
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from config import load_config
from arxiv_digest.posting.poster import _send_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Telegram hard limit; we stay safely under it
_MAX_MESSAGE_CHARS = 3800
_MESSAGE_DELAY_SECONDS = 1.2


def _load_week_entries(csv_path: str) -> list[dict]:
    """Return all CSV rows from the past 7 days, sorted by date ascending."""
    path = Path(csv_path)
    if not path.exists():
        logger.warning("CSV not found at %s — nothing to summarise.", csv_path)
        return []

    cutoff = date.today() - timedelta(days=7)
    entries = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_date = date.fromisoformat(row["date"])
            except (KeyError, ValueError):
                continue
            if row_date >= cutoff:
                entries.append(row)

    entries.sort(key=lambda r: r.get("date", ""))
    return entries


def _format_entry(entry: dict) -> str:
    """Format a single paper entry as an HTML snippet."""
    title = entry.get("title", "Untitled").strip()
    link = entry.get("link", "").strip()
    summary = entry.get("summary", "").strip()
    cats = entry.get("categories", "").strip()

    line = f'<a href="{link}"><b>{title}</b></a>'
    if cats:
        line += f'\n<code>{cats}</code>'
    if summary:
        line += f'\n{summary}'
    return line


def _build_chunks(entries: list[dict], header: str) -> list[str]:
    """
    Split entries into messages that fit within Telegram's character limit.

    The header is prepended only to the first chunk.
    Subsequent chunks get a plain continuation header.
    """
    CONT_HEADER = "📋 <b>Weekly Digest (cont.)</b>\n\n"
    chunks = []
    current = header

    for entry in entries:
        snippet = _format_entry(entry)
        separator = "\n\n" if current.endswith("\n") else "\n\n"
        candidate = current + separator + snippet

        if len(candidate) > _MAX_MESSAGE_CHARS:
            # Flush current chunk and start a new one
            chunks.append(current)
            current = CONT_HEADER + snippet
        else:
            current = candidate

    if current.strip():
        chunks.append(current)

    return chunks


def _build_header(entries: list[dict]) -> str:
    today = date.today()
    week_start = today - timedelta(days=6)
    posted = [e for e in entries if e.get("posted", "").lower() == "true"]

    # %-d is Linux-only; use lstrip for portability
    start_str = week_start.strftime("%d %b").lstrip("0")
    end_str = today.strftime("%d %b %Y").lstrip("0")

    return (
        f"📋 <b>Weekly Digest — {start_str}–{end_str}</b>\n\n"
        f"{len(entries)} papers this week · {len(posted)} featured in daily digests\n"
    )


def post_weekly(csv_path: str, bot_token: str, channel_id: str) -> None:
    """Load the week's entries and post the roundup to Telegram."""
    entries = _load_week_entries(csv_path)

    if not entries:
        logger.info("No entries for the past 7 days. Skipping weekly post.")
        return

    logger.info("Building weekly roundup from %d entries.", len(entries))

    header = _build_header(entries)
    chunks = _build_chunks(entries, header)

    logger.info("Sending %d message(s) for weekly roundup.", len(chunks))
    for i, chunk in enumerate(chunks, 1):
        _send_message(bot_token, channel_id, chunk)
        logger.info("Sent chunk %d/%d.", i, len(chunks))
        if i < len(chunks):
            time.sleep(_MESSAGE_DELAY_SECONDS)

    logger.info("Weekly roundup posted.")


def main() -> None:
    config = load_config()
    post_weekly(config.csv_path, config.telegram_bot_token, config.telegram_channel_id)


if __name__ == "__main__":
    main()