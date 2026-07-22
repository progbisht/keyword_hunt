import pytest
from fetchers import AutosuggestFetcher, PAAFetcher, BingSuggestFetcher


@pytest.mark.asyncio
async def test_autosuggest_fetcher():
    fetcher = AutosuggestFetcher(include_modifiers=False)
    results = await fetcher.fetch("project management")
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("project management" in r.lower() for r in results)


@pytest.mark.asyncio
async def test_paa_fetcher():
    fetcher = PAAFetcher()
    results = await fetcher.fetch("how to lose weight")
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_bing_suggest_fetcher():
    fetcher = BingSuggestFetcher()
    results = await fetcher.fetch("project management")
    assert isinstance(results, list)
    assert len(results) > 0
