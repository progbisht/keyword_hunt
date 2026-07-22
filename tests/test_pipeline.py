import pytest
from pipeline.normalize import exact_dedupe, clean_term
from pipeline.classify import classify_tail_type, classify_intent, classify_keywords


def test_clean_term():
    assert clean_term("  1. Project Management Tool! ") == "project management tool"
    assert clean_term("Coffee?") == "coffee"


def test_exact_dedupe():
    candidates = {
        "project management": {"autosuggest"},
        "Project Management": {"paa"},
        "project management software": {"related_searches"},
    }
    result = exact_dedupe(candidates)
    assert "project management" in result
    assert set(result["project management"]) == {"autosuggest", "paa"}


def test_classify_tail_type():
    assert classify_tail_type(1) == "short-tail"
    assert classify_tail_type(2) == "short-tail"
    assert classify_tail_type(3) == "mid-tail"
    assert classify_tail_type(4) == "mid-tail"
    assert classify_tail_type(5) == "long-tail"
    assert classify_tail_type(8) == "long-tail"


def test_classify_intent():
    assert classify_intent("best project management software vs jira") == "comparison"
    assert classify_intent("buy project management template") == "transactional"
    assert classify_intent("project management tool review") == "commercial"
    assert classify_intent("how to manage remote software teams") == "informational"


def test_classify_keywords():
    candidates = {
        "best project management tool": ["autosuggest", "paa"],
        "project management software": ["autosuggest"],
    }
    items = classify_keywords(candidates, seed_keyword="project management", min_relevance=0.2)
    assert len(items) >= 1
    terms = [item.term for item in items]
    assert "best project management tool" in terms


@pytest.mark.asyncio
async def test_free_enrichment():
    from pipeline.enrich import enrich_keywords
    candidates = {
        "best project management software": ["autosuggest", "bing_suggest"],
        "how to do project management": ["paa"],
    }
    items = classify_keywords(candidates, seed_keyword="project management", min_relevance=0.2)
    enriched = await enrich_keywords(items)
    for item in enriched:
        assert item.volume is not None and item.volume > 0
        assert item.difficulty is not None and 0 <= item.difficulty <= 100
