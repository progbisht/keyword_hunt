# Keyword Discovery Agent

An autonomous, 100% free Python agent that takes a single **seed keyword** and generates a structured, deduplicated list of **short-tail**, **mid-tail**, and **long-tail** keywords. Each keyword is automatically tagged with **search intent**, a **relevance score**, and zero-cost estimated **search volume** & **difficulty** metrics — ready to feed directly into downstream content generation pipelines.

---

## Features

- 🌐 **Multi-Source Discovery (100% Free)**: Parallel fan-out across Google Autosuggest, Google People Also Ask (PAA), Google Related Searches, Bing Suggest, and Google Trends without requiring any paid API keys.
- 🔄 **Second-Level Expansion Loop**: Automatically runs secondary recursive fan-out queries on top candidates to unearth high-converting long-tail search phrases.
- 🧹 **Exact & Semantic Deduplication**: Cleans formatting and merges semantically redundant keywords using local `sentence-transformers` embeddings (`all-MiniLM-L6-v2`) with cosine similarity.
- 🏷️ **Search Intent & Tail-Length Classification**:
  - **Tail Type**: Classified by word count (`short-tail`: 1–2 words, `mid-tail`: 3–4 words, `long-tail`: 5+ words).
  - **Search Intent**: Automatically classified into `informational`, `commercial`, `comparison`, `transactional`, or `navigational`.
- 📊 **Zero-Cost Volume & Difficulty Estimators**:
  - **Relative Search Volume (`volume`)**: Estimated scale computed from multi-source discovery frequency, autosuggest rank order, intent multiplier, and keyword length.
  - **Keyword Difficulty (`difficulty`)**: 0–100 difficulty score estimated from commercial intent density, search intent, and tail-length discounts.
- ⚡ **Upstash Redis Caching**: Automatically caches results in Upstash Redis to serve repeated seed queries instantly.
- 🗄️ **Supabase PostgreSQL Storage**: Automatically persists discovery jobs and discovered keyword records to Supabase DB when configured.

---

## Directory Structure

```
hunt_keyw/
├── fetchers/
│   ├── base.py                   # Abstract fetcher interface
│   ├── autosuggest_fetcher.py    # Google Suggest API & alphabet modifiers
│   ├── paa_fetcher.py            # "People Also Ask" SERP question extractor
│   ├── related_searches_fetcher.py# Related searches & adjacent phrase extractor
│   ├── trends_fetcher.py         # Google Trends / rising queries fallback
│   └── bing_suggest_fetcher.py   # Free Bing Autosuggest fetcher
├── pipeline/
│   ├── orchestrator.py           # Fan-out fetchers & 2nd-level expansion loop
│   ├── normalize.py              # Cleaning, exact & semantic deduplication
│   ├── classify.py               # Tail type mapping, intent & relevance scoring
│   └── enrich.py                 # Free zero-cost volume & difficulty estimators
├── db/
│   └── database.py               # Supabase PostgreSQL client & persistence
├── cache/
│   └── redis_cache.py            # Upstash Redis caching layer
├── models/
│   └── keyword.py                # Pydantic data models (KeywordItem, KeywordDiscoveryResult)
├── output/
│   └── writer.py                 # JSON & CSV export writers
├── tests/                        # Pytest suite
│   ├── test_models.py
│   ├── test_pipeline.py
│   └── test_fetchers.py
├── main.py                       # CLI Entrypoint
├── .env.example                  # Environment configuration template
├── requirements.txt              # Project dependencies
└── README.md                     # Documentation
```

---

## Quickstart Guide

Run keyword discovery for any seed keyword:

```bash
# Basic run (outputs to output.json)
python main.py --seed "project management software"

# Export both JSON and CSV
python main.py --seed "project management software" --csv output.csv

# Run multi-round deep expansion (default: 1 round)
python main.py --seed "how to lose weight" --rounds 2 --csv weight_loss.csv

# Force refresh (bypass Redis cache)
python main.py --seed "coffee" --force-refresh
```

### CLI Arguments

| Argument | Short | Default | Description |
|---|---|---|---|
| `--seed` | | *(Required)* | Seed keyword phrase (e.g. `"coffee"`) |
| `--output` | `-o` | `output.json` | Output JSON file path |
| `--csv` | | `None` | Optional CSV export file path |
| `--rounds` | | `1` | Number of 2nd-level expansion loop rounds |
| `--no-semantic` | | `False` | Disables SentenceTransformer semantic deduplication |
| `--force-refresh` | | `False` | Bypasses Upstash Redis cache |

---

## Environment Configuration

Create a `.env` file to enable Supabase DB storage and Upstash Redis caching:

```bash
cp .env.example .env
```

```ini
# Supabase PostgreSQL Connection String
SUPABASE_DB_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_SUPABASE_ID.supabase.co:5432/postgres

# Upstash Redis Connection String
UPSTASH_REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_UPSTASH_HOST.upstash.io:6379
```

---

## Testing

Run the automated test suite with `pytest`:

```bash
pytest
```