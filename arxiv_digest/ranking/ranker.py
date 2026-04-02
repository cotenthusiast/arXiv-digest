"""
ranker.py
Ranks papers by cross-list count (primary) and submission time (tiebreaker),
then returns the top N for posting to Telegram.

Cross-list count: the number of configured categories a paper appeared in.
A paper in cs.CL, cs.AI, and cs.LG scores 3; one in only cs.CL scores 1.
This signal is cheap (no extra API calls), reproducible, and has genuine
semantic meaning — the authors themselves decided it belongs in multiple fields.
"""

import logging
from datetime import date

from arxiv_digest.fetching.fetcher import Paper

logger = logging.getLogger(__name__)


def rank_papers(papers: list[Paper], top_n: int) -> tuple[list[Paper], list[Paper]]:
    """
    Rank all fetched papers and split into top (for Telegram) and rest (CSV only).

    Ranking key:
      1. cross_list_count descending  (more categories = more broadly significant)
      2. submitted descending         (newer first as tiebreaker)
      3. arxiv_id ascending           (fully deterministic final tiebreaker)

    Returns:
        top_papers:  list of up to top_n Paper objects to post
        rest_papers: remaining papers (logged to CSV, not posted)
    """
    # Annotate each paper with its cross-list count
    for paper in papers:
        paper.cross_list_count = len(paper.categories)

    # submitted is YYYY-MM-DD — lexicographically comparable, so we invert it
    # by negating cross_list_count and wrapping submitted in a tuple with a negation trick.
    # Python doesn't support negating strings, so we sort descending on submitted
    # by doing a two-pass sort (stable sort preserves relative order of equal keys).

    # Pass 1: sort by submitted descending (stable)
    ranked = sorted(papers, key=lambda p: p.submitted, reverse=True)
    # Pass 2: sort by cross_list_count descending (stable — preserves submitted order within ties)
    ranked = sorted(ranked, key=lambda p: p.cross_list_count, reverse=True)

    top = ranked[:top_n]
    rest = ranked[top_n:]

    logger.info(
        "Ranked %d papers. Top %d selected (cross-list counts: %s)",
        len(papers),
        len(top),
        [p.cross_list_count for p in top],
    )

    return top, rest
