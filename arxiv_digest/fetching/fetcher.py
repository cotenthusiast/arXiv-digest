"""
fetcher.py
Fetches new arXiv submissions for a given date across configured categories.

Uses the arXiv API (atom feed via urllib — no extra dependencies).
Deduplicates by arXiv ID so cross-listed papers are not double-counted.
Each paper is annotated with the list of categories it appeared in,
which the ranker uses as its cross-list signal.
"""

import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)

# arXiv Atom feed namespace
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# arXiv API base
_API_BASE = "https://export.arxiv.org/api/query"

# Polite delay between category requests (arXiv asks for ≥3s between calls)
_REQUEST_DELAY_SECONDS = 4


@dataclass
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    link: str
    submitted: str          # ISO date string, e.g. "2026-04-02"
    categories: list[str]   # all categories this paper was found in (cross-list signal)

    # Filled in later by ranker and summariser
    cross_list_count: int = 0
    summary: str = ""


def _build_query(category: str, target_date: date, max_results: int = 200) -> str:
    """
    Build an arXiv API query URL for new submissions in a category on a given date.

    arXiv's submittedDate filter uses the format YYYYMMDDHHMMSS.
    We query the full UTC day: 0000 to 2359.
    """
    date_str = target_date.strftime("%Y%m%d")
    search_query = f"cat:{category} AND submittedDate:[{date_str}0000 TO {date_str}2359]"
    params = urllib.parse.urlencode({
        "search_query": search_query,
        "start": 0,
        "max_results": 200,  # fetch generously; ranker will cap
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    return f"{_API_BASE}?{params}"


def _parse_feed(xml_bytes: bytes, category: str) -> list[Paper]:
    """Parse an arXiv Atom feed response into a list of Paper objects."""
    root = ET.fromstring(xml_bytes)
    papers = []

    for entry in root.findall("atom:entry", _NS):
        # arXiv ID is the last segment of the id URL
        id_url = entry.findtext("atom:id", default="", namespaces=_NS)
        arxiv_id = id_url.rstrip("/").split("/")[-1]
        if not arxiv_id:
            continue

        title_el = entry.find("atom:title", _NS)
        title = " ".join(title_el.text.split()) if title_el is not None and title_el.text else ""

        abstract_el = entry.find("atom:summary", _NS)
        abstract = " ".join(abstract_el.text.split()) if abstract_el is not None and abstract_el.text else ""

        authors = [
            a.findtext("atom:name", default="", namespaces=_NS)
            for a in entry.findall("atom:author", _NS)
        ]

        # Submission date: <published> tag, e.g. "2026-04-02T00:00:00Z"
        published_el = entry.find("atom:published", _NS)
        submitted = ""
        if published_el is not None and published_el.text:
            submitted = published_el.text[:10]  # take YYYY-MM-DD

        link = f"https://arxiv.org/abs/{arxiv_id}"

        papers.append(Paper(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            link=link,
            submitted=submitted,
            categories=[category],
        ))

    return papers


def fetch_papers(categories: list[str], target_date: date, max_results_per_category: int = 200) -> list[Paper]:
    """
    Fetch all new submissions for the given date across all categories.

    Papers that appear in multiple categories are merged into a single Paper
    object with all their categories listed (used by the ranker).

    Returns a deduplicated list of Paper objects.
    """
    # arxiv_id -> Paper (merged across categories)
    seen: dict[str, Paper] = {}

    for i, category in enumerate(categories):
        if i > 0:
            time.sleep(_REQUEST_DELAY_SECONDS)

        url = _build_query(category, target_date, max_results_per_category)
        logger.info("Fetching %s for %s", category, target_date)

        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                xml_bytes = resp.read()
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", category, exc)
            continue

        papers = _parse_feed(xml_bytes, category)
        logger.info("  → %d papers from %s", len(papers), category)

        for paper in papers:
            if paper.arxiv_id in seen:
                # Already seen from another category — merge category list
                seen[paper.arxiv_id].categories.append(category)
            else:
                seen[paper.arxiv_id] = paper

    all_papers = list(seen.values())
    logger.info("Total unique papers fetched: %d", len(all_papers))
    return all_papers
