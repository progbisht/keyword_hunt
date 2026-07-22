import argparse
import asyncio
import logging
import time
from models.keyword import KeywordDiscoveryResult
from pipeline import (
    fan_out_fetch,
    expand_second_level,
    normalize_and_dedupe,
    classify_keywords,
    enrich_keywords,
)
from cache import get_cached_discovery, set_cached_discovery
from db import init_db, save_discovery_result
from output import write_json, write_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("main")


async def run_discovery(
    seed_keyword: str,
    rounds: int = 1,
    semantic: bool = True,
    output_json: str = "output.json",
    output_csv: str = None,
    force_refresh: bool = False,
    progress_callback = None,
    job_id = None,
) -> KeywordDiscoveryResult:
    def log_progress(msg: str):
        print(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    log_progress(f"🚀 Starting Keyword Discovery for seed: '{seed_keyword}'")
    start_time = time.time()

    # 1. Initialize Supabase DB if configured
    await init_db()

    # 2. Check Upstash Redis Cache
    if not force_refresh:
        cached_result = await get_cached_discovery(seed_keyword)
        if cached_result:
            log_progress("⚡ Loaded from Upstash Redis cache!")
            write_json(cached_result, output_json)
            if output_csv:
                write_csv(cached_result, output_csv)
            # Invoke save_discovery_result to save to local cache anyway if not saved before
            await save_discovery_result(cached_result)
            return cached_result

    # Step 1: Fan-out fetchers
    log_progress("📡 Step 1/5: Fetching initial candidates from free data sources...")
    candidates = await fan_out_fetch(seed_keyword)
    log_progress(f"   Surfaced {len(candidates)} unique candidates across sources.")

    # Step 2: Second-level expansion loop
    if rounds > 0:
        log_progress(f"🔄 Step 2/5: Running second-level expansion (rounds={rounds})...")
        candidates = await expand_second_level(candidates, seed_keyword, rounds=rounds)
        log_progress(f"   Expanded pool to {len(candidates)} candidates.")
    else:
        log_progress("⏩ Step 2/5: Skipping second-level expansion.")

    # Step 3: Normalize & dedupe
    log_progress("🧹 Step 3/5: Normalizing and deduplicating terms...")
    deduped = normalize_and_dedupe(candidates, semantic=semantic)
    log_progress(f"   Retained {len(deduped)} distinct candidate terms.")

    # Step 4: Classify
    log_progress("🏷️  Step 4/5: Classifying tail-length, search intent & relevance...")
    classified_items = classify_keywords(deduped, seed_keyword)
    log_progress(f"   Classified {len(classified_items)} relevant keywords.")

    # Step 5: Enrich free metrics
    log_progress("💎 Step 5/5: Enriching with free volume/difficulty metrics...")
    enriched_items = await enrich_keywords(classified_items)

    result = KeywordDiscoveryResult(
        seed_keyword=seed_keyword,
        keywords=enriched_items,
    )

    # 3. Export to files
    write_json(result, output_json)
    log_progress(f"✅ Output JSON written to: {output_json}")

    if output_csv:
        write_csv(result, output_csv)
        log_progress(f"📊 CSV export written to: {output_csv}")

    # 4. Save to Supabase DB and Upstash Redis
    job_id = await save_discovery_result(result, job_id=job_id)
    await set_cached_discovery(result)

    elapsed = round(time.time() - start_time, 2)
    log_progress(f"✨ Finished discovery in {elapsed}s. Found {len(result.keywords)} keywords.")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Keyword Discovery Agent — Free Multi-Source Generator & Classifier"
    )
    parser.add_argument(
        "--seed",
        type=str,
        required=True,
        help="Seed keyword phrase (e.g., 'project management')",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output.json",
        help="Output JSON file path (default: output.json)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Optional output CSV file path",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of expansion loop rounds (default: 1)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic embedding deduplication for faster execution",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass Upstash Redis cache and force a fresh discovery run",
    )

    args = parser.parse_args()

    asyncio.run(
        run_discovery(
            seed_keyword=args.seed,
            rounds=args.rounds,
            semantic=not args.no_semantic,
            output_json=args.output,
            output_csv=args.csv,
            force_refresh=args.force_refresh,
        )
    )


if __name__ == "__main__":
    main()
