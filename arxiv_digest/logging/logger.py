"""
logger.py
Appends all fetched papers (top + rest) to a local CSV log.

Every paper fetched on a given day is recorded regardless of whether
it was posted to Telegram. This gives a complete historical record.

CSV columns: date, arxiv_id, title, authors, categories, cross_list_count,
             summary, link, posted
"""

import csv
import logging
import os
from datetime import date

from arxiv_digest.fetching.fetcher import Paper

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "date",
    "arxiv_id",
    "title",
    "authors",
    "categories",
    "cross_list_count",
    "summary",
    "link",
    "posted",
]


def _ensure_csv(path: str) -> None:
    """Create the CSV file with headers if it doesn't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
        logger.info("Created new CSV log at %s", path)


def log_papers(
    top_papers: list[Paper],
    rest_papers: list[Paper],
    csv_path: str,
    target_date: date,
) -> None:
    """
    Append all papers to the CSV log.

    top_papers are marked posted=True, rest_papers posted=False.
    """
    _ensure_csv(csv_path)

    rows = []
    for paper in top_papers:
        rows.append(_to_row(paper, target_date, posted=True))
    for paper in rest_papers:
        rows.append(_to_row(paper, target_date, posted=False))

    if not rows:
        logger.info("No papers to log.")
        return

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerows(rows)

    logger.info(
        "Logged %d papers to CSV (%d posted, %d not posted).",
        len(rows),
        len(top_papers),
        len(rest_papers),
    )


def _to_row(paper: Paper, target_date: date, posted: bool) -> dict:
    return {
        "date": target_date.isoformat(),
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "authors": "; ".join(paper.authors),
        "categories": "; ".join(paper.categories),
        "cross_list_count": paper.cross_list_count,
        "summary": paper.summary,
        "link": paper.link,
        "posted": posted,
    }
