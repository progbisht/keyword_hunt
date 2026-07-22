import asyncio
from typing import Dict, List, Set, Tuple
from fetchers import (
    BaseFetcher,
    AutosuggestFetcher,
    PAAFetcher,
    RelatedSearchesFetcher,
    TrendsFetcher,
    BingSuggestFetcher,
)


def get_default_fetchers() -> List[BaseFetcher]:
    return [
        AutosuggestFetcher(include_modifiers=True),
        PAAFetcher(),
        RelatedSearchesFetcher(),
        TrendsFetcher(),
        BingSuggestFetcher(),
    ]


async def fan_out_fetch(
    seed_keyword: str, fetchers: List[BaseFetcher] = None
) -> Dict[str, Set[str]]:
    """
    Executes parallel fetch calls across all fetchers for a single query.
    Returns a dict mapping candidate term string -> set of source names.
    """
    if fetchers is None:
        fetchers = get_default_fetchers()

    candidates_with_sources: Dict[str, Set[str]] = {}

    async def _run_fetcher(fetcher: BaseFetcher):
        try:
            results = await fetcher.fetch(seed_keyword)
            return fetcher.name, results
        except Exception:
            return fetcher.name, []

    tasks = [_run_fetcher(f) for f in fetchers]
    fetched_results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in fetched_results:
        if isinstance(res, tuple):
            source_name, terms = res
            for t in terms:
                term_clean = t.strip()
                if term_clean:
                    if term_clean not in candidates_with_sources:
                        candidates_with_sources[term_clean] = set()
                    candidates_with_sources[term_clean].add(source_name)

    return candidates_with_sources


async def expand_second_level(
    candidates_with_sources: Dict[str, Set[str]],
    seed_keyword: str,
    rounds: int = 1,
    top_k: int = 15,
    fetchers: List[BaseFetcher] = None,
) -> Dict[str, Set[str]]:
    """
    Second-level expansion loop (Section 4, Step 4 of readme.md):
    1. Select top candidates based on multi-source count & length heuristic.
    2. Re-run fetchers using selected candidates as queries.
    3. Merge new results into candidate pool.
    """
    if fetchers is None:
        fetchers = get_default_fetchers()

    current_pool = dict(candidates_with_sources)

    for round_idx in range(rounds):
        # Rank candidates to pick top candidates for expansion
        # Prioritize candidates appearing in multiple sources and candidates containing seed
        def rank_score(item: Tuple[str, Set[str]]) -> float:
            term, sources = item
            score = len(sources) * 2.0
            if seed_keyword.lower() in term.lower():
                score += 1.0
            # slight boost for word count between 3 and 7
            words = len(term.split())
            if 3 <= words <= 7:
                score += 1.5
            return score

        sorted_candidates = sorted(
            current_pool.items(), key=rank_score, reverse=True
        )
        expansion_targets = [term for term, _ in sorted_candidates[:top_k]]

        if not expansion_targets:
            break

        # Run expansion queries in batches to avoid overwhelming network
        batch_size = 5
        for i in range(0, len(expansion_targets), batch_size):
            batch = expansion_targets[i : i + batch_size]
            tasks = [fan_out_fetch(target, fetchers=fetchers) for target in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, dict):
                    for term, sources in res.items():
                        if term not in current_pool:
                            current_pool[term] = set()
                        current_pool[term].update(sources)

    return current_pool
