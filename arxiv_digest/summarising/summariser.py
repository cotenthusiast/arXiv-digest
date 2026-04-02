"""
summariser.py
Submits paper abstracts to the Anthropic Batch API for one-line plain English summaries.

Flow:
  1. Build a batch request — one item per paper (custom_id = arxiv_id)
  2. Submit the batch and poll until complete (Batch API is async)
  3. Parse results and write summary back to each Paper object

Only the top-N papers are summarised (to keep costs minimal).
The rest get an empty summary field in the CSV.
"""

import logging
import time

import anthropic

from arxiv_digest.fetching.fetcher import Paper

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a research assistant writing a daily arXiv digest for ML researchers. "
    "Summarise the following paper abstract in exactly one plain English sentence. "
    "Hard limit: 20 words maximum. Do not start with 'This paper'. Be direct."
)

_POLL_INTERVAL_SECONDS = 30
_MAX_POLL_ATTEMPTS = 60  # 30 minutes max wait


def _build_request(paper: Paper, model: str) -> anthropic.types.MessageCreateParamsNonStreaming:
    """Build a single batch message request for a paper."""
    return {
        "custom_id": paper.arxiv_id.replace(".", "-"),
        "params": {
            "model": model,
            "max_tokens": 100,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Title: {paper.title}\n\nAbstract: {paper.abstract}",
                }
            ],
        },
    }


def summarise_papers(papers: list[Paper], api_key: str, model: str) -> list[Paper]:
    """
    Summarise a list of papers using the Anthropic Batch API.

    Modifies each Paper in-place by setting paper.summary.
    Returns the same list for convenience.
    """
    if not papers:
        logger.info("No papers to summarise.")
        return papers

    client = anthropic.Anthropic(api_key=api_key)

    # 1. Submit batch
    requests = [_build_request(p, model) for p in papers]
    logger.info("Submitting batch of %d papers to Anthropic...", len(requests))

    batch = client.messages.batches.create(requests=requests)
    batch_id = batch.id
    logger.info("Batch submitted. ID: %s", batch_id)

    # 2. Poll until complete
    for attempt in range(1, _MAX_POLL_ATTEMPTS + 1):
        time.sleep(_POLL_INTERVAL_SECONDS)
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status

        logger.info(
            "Poll %d/%d — status: %s (%d succeeded, %d errored)",
            attempt,
            _MAX_POLL_ATTEMPTS,
            status,
            batch.request_counts.succeeded,
            batch.request_counts.errored,
        )

        if status == "ended":
            break
    else:
        raise TimeoutError(f"Batch {batch_id} did not complete within the polling window.")

    # 3. Parse results
    id_to_paper = {p.arxiv_id.replace(".", "-"): p for p in papers}
    succeeded = 0
    failed = 0

    for result in client.messages.batches.results(batch_id):
        arxiv_id = result.custom_id
        paper = id_to_paper.get(arxiv_id)
        if paper is None:
            continue

        if result.result.type == "succeeded":
            content = result.result.message.content
            # Extract text from first content block
            text_blocks = [b for b in content if b.type == "text"]
            paper.summary = text_blocks[0].text.strip() if text_blocks else ""
            succeeded += 1
        else:
            logger.warning("Batch result failed for %s: %s", arxiv_id, result.result.type)
            paper.summary = ""
            failed += 1

    logger.info("Summarisation complete. %d succeeded, %d failed.", succeeded, failed)
    return papers
