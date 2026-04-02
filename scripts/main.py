"""
main.py
Orchestrates the daily arXiv digest pipeline.

Steps:
  1. Load config
  2. Fetch new papers from arXiv (all configured categories)
  3. Rank by cross-list count, select top N
  4. Summarise top N via Anthropic Batch API
  5. Post to Telegram channel
  6. Log all papers to CSV

Run:
  python -m main
  python -m main --date 2026-04-01   # backfill a specific date
  python -m main --dry-run           # fetch + rank + summarise, skip Telegram post
"""

import argparse
import logging
import sys
from datetime import date, datetime

from config import load_config
from arxiv_digest.fetching.fetcher import fetch_papers
from arxiv_digest.ranking.ranker import rank_papers
from arxiv_digest.summarising.summariser import summarise_papers
from arxiv_digest.posting.poster import post_digest
from arxiv_digest.logging.logger import log_papers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="arXiv Digest — daily LLM paper digest")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline but skip posting to Telegram.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Resolve target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid date format: %s. Use YYYY-MM-DD.", args.date)
            sys.exit(1)
    else:
        target_date = date.today()

    logger.info("=== arXiv Digest — %s ===", target_date.isoformat())

    # 1. Load config
    config = load_config()
    logger.info("Config loaded. Categories: %s | Top N: %d", config.arxiv_categories, config.top_n)

    # 2. Fetch papers
    logger.info("Step 1/4 — Fetching papers from arXiv...")
    all_papers = fetch_papers(config.arxiv_categories, target_date, config.max_results_per_category)

    if not all_papers:
        logger.warning("No papers fetched for %s. Exiting.", target_date)
        sys.exit(0)

    # 3. Rank and split
    logger.info("Step 2/4 — Ranking papers...")
    top_papers, rest_papers = rank_papers(all_papers, config.top_n)

    # 4. Summarise top papers
    logger.info("Step 3/4 — Summarising top %d papers via Batch API...", len(top_papers))
    summarise_papers(top_papers, config.anthropic_api_key, config.model)

    # 5. Post to Telegram
    if args.dry_run:
        logger.info("Step 4/4 — DRY RUN: skipping Telegram post.")
        for i, p in enumerate(top_papers, 1):
            logger.info("  [%d] %s | cats=%s | summary=%s", i, p.arxiv_id, p.categories, p.summary[:80])
    else:
        logger.info("Step 4/4 — Posting to Telegram channel %s...", config.telegram_channel_id)
        post_digest(top_papers, config.telegram_bot_token, config.telegram_channel_id, target_date)

    # 6. Log all papers to CSV (always, even on dry run)
    log_papers(top_papers, rest_papers, config.csv_path, target_date)

    logger.info("=== Done. ===")


if __name__ == "__main__":
    main()
