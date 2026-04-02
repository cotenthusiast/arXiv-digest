"""
poster.py
Posts the daily arXiv digest to a Telegram channel.

Format:
  - One header message with the date and paper count
  - One message per paper (title, categories, summary, link)

Telegram's Bot API has a rate limit of ~30 messages/second to different chats,
but for a single channel the safe practical rate is 1 message/second.
We use a small delay between messages to be safe.
"""

import logging
import time
import urllib.parse
import urllib.request
import json
from datetime import date

from arxiv_digest.fetching.fetcher import Paper

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
_MESSAGE_DELAY_SECONDS = 1.2  # stay well under rate limits

# Category display labels
_CATEGORY_LABELS = {
    "cs.CL": "Computation & Language",
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
}


def _send_message(bot_token: str, channel_id: str, text: str) -> None:
    """Send a single message to a Telegram channel (MarkdownV2 parse mode)."""
    url = _TELEGRAM_API_BASE.format(token=bot_token, method="sendMessage")
    payload = json.dumps({
        "chat_id": channel_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            if not body.get("ok"):
                logger.error("Telegram API error: %s", body)
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        raise


def _format_header(target_date: date, paper_count: int) -> str:
    """Format the digest header message."""
    date_str = target_date.strftime("%d %B %Y").lstrip("0")  # e.g. "2 April 2026"
    return (
        f"📡 <b>arXiv Digest — {date_str}</b>\n\n"
        f"{paper_count} papers today from cs.CL · cs.AI · cs.LG\n"
        f"Ranked by cross-category relevance."
    )


def _format_paper(paper: Paper, index: int) -> str:
    """Format a single paper as a Telegram message."""
    # Category tags
    cat_tags = " · ".join(paper.categories)

    # Cross-list badge
    if paper.cross_list_count >= 3:
        badge = "🔥 "  # in all 3 categories
    elif paper.cross_list_count == 2:
        badge = "⭐ "  # cross-listed
    else:
        badge = ""

    summary_line = paper.summary if paper.summary else "Summary unavailable."
    authors_short = ", ".join(paper.authors[:3])
    if len(paper.authors) > 3:
        authors_short += f" et al."

    return (
        f"{badge}<b>{paper.title}</b>\n"
        f"<i>{authors_short}</i>\n"
        f"<code>{cat_tags}</code>\n\n"
        f"{summary_line}\n\n"
        f"<a href=\"{paper.link}\">🔗 {paper.arxiv_id}</a>"
    )


def post_digest(
    papers: list[Paper],
    bot_token: str,
    channel_id: str,
    target_date: date,
) -> None:
    """
    Post the full digest to the Telegram channel.

    Sends a header message followed by one message per paper.
    """
    if not papers:
        logger.warning("No papers to post.")
        return

    # Header
    header = _format_header(target_date, len(papers))
    logger.info("Posting header to Telegram channel %s", channel_id)
    _send_message(bot_token, channel_id, header)
    time.sleep(_MESSAGE_DELAY_SECONDS)

    # One message per paper
    for i, paper in enumerate(papers, start=1):
        msg = _format_paper(paper, i)
        logger.info("Posting paper %d/%d: %s", i, len(papers), paper.arxiv_id)
        _send_message(bot_token, channel_id, msg)
        time.sleep(_MESSAGE_DELAY_SECONDS)

    logger.info("Digest posted. %d messages sent.", len(papers) + 1)
