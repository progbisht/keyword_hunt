from models.keyword import KeywordItem, KeywordDiscoveryResult


def test_keyword_item_schema():
    item = KeywordItem(
        term="best project management tool for remote agile teams",
        type="long-tail",
        word_count=8,
        intent="comparison",
        source=["autosuggest", "paa"],
        volume=320,
        difficulty=24,
        relevance_score=0.87,
    )
    assert item.term == "best project management tool for remote agile teams"
    assert item.type == "long-tail"
    assert item.word_count == 8
    assert item.intent == "comparison"
    assert "autosuggest" in item.source


def test_discovery_result_schema():
    result = KeywordDiscoveryResult(
        seed_keyword="project management",
        keywords=[
            KeywordItem(
                term="project management software",
                type="mid-tail",
                word_count=3,
                intent="commercial",
                source=["autosuggest"],
                relevance_score=0.95,
            )
        ],
    )
    assert result.seed_keyword == "project management"
    assert len(result.keywords) == 1
    dump = result.model_dump()
    assert "generated_at" in dump
    assert dump["seed_keyword"] == "project management"
