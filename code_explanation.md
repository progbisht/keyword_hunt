# Code Explanation & Architecture Deep Dive — Keyword Discovery Agent

This document provides a line-by-line and module-by-module technical explanation of how the Keyword Discovery Agent is built and executed.

---

## 1. High-Level Architecture & End-to-End Pipeline

When you run `python main.py --seed "project management"`, the application executes through 5 core sequential stages:

```
 Seed Keyword ──► [1. Async Fan-Out Fetchers] ──► [2. 2nd-Level Expansion] 
                        │
                        ▼
                 [3. Normalization & Semantic Dedupe]
                        │
                        ▼
                 [4. Intent & Relevance Classifier]
                        │
                        ▼
                 [5. Zero-Cost Volume & KD Engine] ──► output.json / output.csv
```

---

## 2. Module-by-Module Technical Breakdown

### A. Data Schemas (`models/keyword.py`)
The application uses **Pydantic v2** models to guarantee strict type safety and schema validation for downstream APIs.

* **`KeywordItem`**:
  * `term`: The clean keyword string.
  * `type`: Categorized strictly as `"short-tail"` (1–2 words), `"mid-tail"` (3–4 words), or `"long-tail"` (5+ words).
  * `word_count`: `len(term.split())`.
  * `intent`: High-level intent (`informational`, `commercial`, `transactional`, `comparison`, `navigational`).
  * `source`: List of fetchers that surfaced this keyword (e.g. `["autosuggest", "bing_suggest", "paa"]`).
  * `volume`: Estimated relative search volume index.
  * `difficulty`: Estimated keyword competition score (0–100 scale).
  * `relevance_score`: Cosine similarity score (0.00 – 1.00) relative to the seed keyword.

* **`KeywordDiscoveryResult`**:
  * `seed_keyword`: The input seed.
  * `generated_at`: ISO 8601 UTC timestamp.
  * `keywords`: List of validated `KeywordItem` objects.

---

### B. Fetchers Engine (`fetchers/`)
Each fetcher inherits from `BaseFetcher` (`fetchers/base.py`) and implements an `async def fetch(query: str) -> List[str]` method using `httpx.AsyncClient`.

1. **`AutosuggestFetcher` (`fetchers/autosuggest_fetcher.py`)**:
   * Queries Google's Firefox autosuggest endpoint: `https://suggestqueries.google.com/complete/search?client=firefox&q=<query>`
   * To maximize fan-out, it concurrently fires queries for letter modifiers (`seed a`, `seed b`, ..., `seed z`) and modifier prefixes (`seed how`, `seed best`, `seed vs`, `seed for`).

2. **`PAAFetcher` (`fetchers/paa_fetcher.py`)**:
   * Target: Question-based long-tail keywords ("People Also Ask").
   * Fires question-prefix completions (`how to <seed>`, `what is <seed>`, `why does <seed>`) and scrapes DuckDuckGo HTML SERP snippet text for question patterns.

3. **`RelatedSearchesFetcher` (`fetchers/related_searches_fetcher.py`)**:
   * Extracts related search links and targeted commercial suffixes (`alternative`, `software`, `tool`, `framework`, `examples`).

4. **`TrendsFetcher` (`fetchers/trends_fetcher.py`)**:
   * Discovers rising / trending queries by attaching modern time and trend suffixes (`2026`, `latest`, `trends`, `new`).

5. **`BingSuggestFetcher` (`fetchers/bing_suggest_fetcher.py`)**:
   * Queries Bing's free suggestion endpoint: `https://api.bing.com/qsonhs.aspx?q=<query>`

---

### C. Pipeline Processing (`pipeline/`)

#### 1. Async Fan-Out & Expansion (`pipeline/orchestrator.py`)
* **`fan_out_fetch(seed_keyword)`**:
  Executes all active fetchers concurrently using `asyncio.gather(*tasks)`. Keeps track of which source(s) produced each raw string candidate.
* **`expand_second_level(candidates, seed, rounds=1, top_k=15)`**:
  Ranks candidates using a cross-source frequency heuristic:
  $$\text{Score} = (\text{source\_count} \times 2.0) + \text{seed\_presence} + \text{length\_bonus}$$
  It picks the top $K$ candidates and re-runs the full fan-out fetcher suite on them recursively. This surfaces authentic 5–8 word long-tail keywords.

#### 2. Normalization & Semantic Deduplication (`pipeline/normalize.py`)
* **Exact Cleaning**: Lowercases, strips punctuation, leading numbers (`1. `), and extra whitespace. Merges source lists for identical strings.
* **Semantic Deduplication**:
  * Loads `SentenceTransformer('BAAI/bge-base-en-v1.5')` to embed all candidate terms into 768-dimensional dense vectors.
  * Computes an $N \times N$ cosine similarity matrix:
    $$\text{CosSim}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
  * For pairs with similarity $\ge 0.92$, the shorter/redundant term is merged into the more specific term, preventing duplicate variations.
  * *Fallback*: If heavy ML dependencies are missing, degrades gracefully to TF-IDF n-gram cosine similarity.

#### 3. Classification & Relevance (`pipeline/classify.py`)
* **Intent Rules**:
  * **Question Prefixes** (`how`, `what`, `why`, `where`, `who`) $\rightarrow$ `informational`
  * **Comparison Signals** (`vs`, `versus`, `compare`, `alternative`, `best ...`) $\rightarrow$ `comparison`
  * **Transactional Signals** (`buy`, `pricing`, `cost`, `order`, `download`, `sale`) $\rightarrow$ `transactional`
  * **Commercial Signals** (`review`, `software`, `tool`, `service`, `platform`, `app`) $\rightarrow$ `commercial`
  * **Navigational Signals** (`login`, `sign in`, `official site`, `portal`) $\rightarrow$ `navigational`
* **Relevance Scoring**:
  Calculates cosine similarity between term embedding $\vec{E}_{\text{term}}$ and seed embedding $\vec{E}_{\text{seed}}$. Drops any keyword scoring below the relevance threshold (0.35) to eliminate off-topic noise.

#### 4. Zero-Cost Volume & Difficulty Estimator (`pipeline/enrich.py`)
Because paid APIs like DataForSEO cost money, the agent estimates volume and difficulty for free:

* **Relative Search Volume Index**:
  $$\text{Volume} = 1200 \times (\text{source\_count})^{1.4} \times \frac{1}{\sqrt{\text{word\_count}}} \times (\text{relevance\_score})^{1.5} \times \text{intent\_mult}$$
  Multi-source terms that appear near top autosuggest positions receive high relative volume (e.g. 1,800 to 10,000+), while niche long-tail terms receive lower volume (e.g. 100 to 400).

* **Keyword Difficulty (0–100 Scale)**:
  $$\text{KD} = 35 + (12 \times N_{\text{commercial\_words}}) - \text{tail\_discount} - \text{question\_discount}$$
  * Commercial terms ("best", "vs", "software", "pricing") increase difficulty score.
  * Long-tail phrases (5+ words) and informational question phrases receive difficulty discounts, reflecting lower competitive barriers.

---

### D. Export Writers & CLI (`output/writer.py`, `main.py`)

* **`output/writer.py`**:
  * `write_json()`: Dumps Pydantic `KeywordDiscoveryResult` to formatted JSON.
  * `write_csv()`: Exports flat CSV file suitable for Excel/Google Sheets.
* **`main.py`**:
  Entrypoint script parsing CLI flags (`--seed`, `--output`, `--csv`, `--rounds`, `--no-semantic`, `--force-refresh`) and running the async loop.

---

### E. Database & Fallback Storage (`db/database.py`)
* **Tables**: Creates `discovery_jobs` and `keywords` tables in Supabase PostgreSQL (via `asyncpg`) if `SUPABASE_DB_URL` is set in the environment.
* **Fallback Storage**: If no DB connection exists, it automatically falls back to local in-memory storage (`_local_jobs`, `_local_keywords`). This ensures that the CLI and the Web Server work seamlessly out of the box without requiring any external database configuration.

---

### F. FastAPI Web Server & Dashboard (`server.py`, `static/index.html`)
* **`server.py`**:
  * Exposes backend API endpoints for triggering and reading discovery runs:
    * `POST /api/discover`: Launches a discovery background task.
    * `GET /api/jobs`: Lists running and historical discovery jobs.
    * `GET /api/jobs/{job_id}`: Retrieves job execution logs and status.
    * `GET /api/jobs/{job_id}/keywords`: Returns the generated keyword items.
  * Serves the single-page application dashboard `static/index.html` at the root path (`/`).
* **`static/index.html`**:
  * A modern web interface displaying real-time task progress, status logs, interactive data tables with search filters (by intent, tail length), and instant CSV downloads.

---

## 3. How to Run & Extend

### Run command (CLI):
```bash
./venv/bin/python main.py --seed "remote work software" --csv output.csv
```

### Run command (Web Dashboard):
```bash
uvicorn server:app --reload
# Or run server directly: python server.py
```

### Extending with New Fetchers:
To add a new data source (e.g. YouTube Suggest or Reddit), simply create `fetchers/youtube_fetcher.py` inheriting from `BaseFetcher`, implement `async def fetch(query: str)`, and add it to `get_default_fetchers()` in `pipeline/orchestrator.py`.
