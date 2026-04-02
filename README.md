# arXiv Digest

A self-hosted tool that runs daily and publishes a digest of new LLM research papers to a public Telegram channel.

## What it does

- Pulls new submissions daily from arXiv categories `cs.CL`, `cs.AI`, and `cs.LG` via the arXiv API
- Ranks papers by **cross-category relevance** — papers appearing in multiple categories are surfaced first
- Sends each abstract to Claude (Sonnet) via the **Anthropic Batch API** for a one-line plain English summary
- Posts the top 20 papers to a public Telegram channel — one message per paper with title, summary, and arXiv link
- Appends all results to a local CSV log regardless of what gets posted

## Stack

Python · arXiv API · Anthropic Batch API · Telegram Bot API · Docker · cron

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/cotenthusiast/arXiv-digest
cd arXiv-digest
cp .env.example .env
# edit .env with your API keys
```

### 2. Create a Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot → copy the token into `TELEGRAM_BOT_TOKEN`
3. Create a public channel and add your bot as an admin
4. Set `TELEGRAM_CHANNEL_ID` to `@yourchannelname` or the numeric channel ID

### 3. Build the Docker image

```bash
docker compose build
```

### 4. Test with a dry run

```bash
docker compose run --rm arxiv-digest python -m main --dry-run
```

### 5. Set up the cron job (on ibn5100 or any Linux host)

```bash
crontab -e
```

Add (fires at 08:00 daily):

```
0 8 * * * cd /path/to/arXiv-digest && docker compose run --rm arxiv-digest >> /var/log/arxiv-digest.log 2>&1
```

### 6. Backfill a specific date

```bash
docker compose run --rm arxiv-digest python -m main --date 2026-04-01
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | required | Telegram bot token from BotFather |
| `TELEGRAM_CHANNEL_ID` | required | Channel username or numeric ID |
| `ARXIV_CATEGORIES` | `cs.CL,cs.AI,cs.LG` | Comma-separated arXiv categories to fetch |
| `TOP_N` | `20` | Number of papers to post per day |
| `MAX_RESULTS_PER_CATEGORY` | `100` | How many papers to fetch per category before ranking |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Model used for summarisation |
| `CSV_PATH` | `data/digest.csv` | Path for the local CSV log |

## CSV log

All fetched papers are logged to `data/digest.csv` with columns:

```
date, arxiv_id, title, authors, categories, cross_list_count, summary, link, posted
```

## Ranking

Papers are ranked by **cross-list count** (how many of the configured categories they appear in) with submission time as a tiebreaker. This requires no external API calls — the signal comes directly from the authors' own category choices. In the Telegram posts:

- 🔥 = appears in all 3 categories
- ⭐ = appears in 2 categories
- no badge = single category

## Cost

Well under $1/month. The Batch API processes ~20 abstracts per day at claude-sonnet pricing with a 50% discount for batch requests.
