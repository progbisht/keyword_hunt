import math
from typing import List
from models.keyword import KeywordItem


def estimate_search_volume(item: KeywordItem) -> int:
    """
    Estimates relative monthly search volume (100 - 15,000+ range) without paid APIs.
    Uses multi-source count, word length, intent, and relevance score.
    """
    source_count = len(item.source)
    word_count = item.word_count

    # Base volume multiplier from cross-source presence
    source_multiplier = math.pow(source_count, 1.4)

    # Word count decay factor (short tail keywords have higher aggregate volume)
    length_factor = 1.0 / math.sqrt(max(1, word_count))

    # Intent multiplier
    intent_multiplier = 1.0
    if item.intent in ("commercial", "transactional"):
        intent_multiplier = 1.25
    elif item.intent == "comparison":
        intent_multiplier = 1.1

    raw_volume = 1200 * source_multiplier * length_factor * (item.relevance_score ** 1.5) * intent_multiplier

    # Round to realistic search volume figures (multiples of 10 or 50)
    vol = int(max(10, min(25000, raw_volume)))
    if vol > 1000:
        vol = round(vol, -2)  # round to nearest hundred
    elif vol > 100:
        vol = round(vol, -1)  # round to nearest ten

    return vol


def estimate_keyword_difficulty(item: KeywordItem) -> int:
    """
    Estimates keyword difficulty (0 - 100 scale) without paid APIs.
    Uses intent density, tail length, and term characteristics.
    """
    term_lower = item.term.lower()
    words = term_lower.split()

    # Base difficulty
    diff = 35.0

    # Commercial & competitive terms increase competition difficulty
    competitive_words = {"best", "top", "software", "tool", "platform", "solution", "buy", "pricing", "cost", "vs", "review", "agency"}
    matching_comp = sum(1 for w in words if w in competitive_words)
    diff += matching_comp * 12.0

    # Long tail keywords are significantly easier to rank for
    if item.word_count >= 6:
        diff -= 20.0
    elif item.word_count >= 4:
        diff -= 10.0
    elif item.word_count <= 2:
        diff += 15.0

    # Question-based informational phrases are easier to rank
    if item.intent == "informational" or term_lower.startswith(("how", "why", "what", "can", "is")):
        diff -= 12.0

    # Ensure difficulty stays within realistic 0-100 bounds
    final_kd = int(max(5, min(95, round(diff))))
    return final_kd


async def enrich_keywords(keywords: List[KeywordItem]) -> List[KeywordItem]:
    """
    Step 7 Pipeline function: Populates zero-cost volume and difficulty estimations.
    """
    for item in keywords:
        item.volume = estimate_search_volume(item)
        item.difficulty = estimate_keyword_difficulty(item)

    return keywords
