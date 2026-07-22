import asyncio
from typing import List, Set
import httpx
from .base import BaseFetcher


class AutosuggestFetcher(BaseFetcher):
    name: str = "autosuggest"

    def __init__(self, include_modifiers: bool = True):
        self.include_modifiers = include_modifiers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def _fetch_single(self, client: httpx.AsyncClient, query: str) -> List[str]:
        url = "https://suggestqueries.google.com/complete/search"
        params = {"client": "firefox", "q": query}
        try:
            response = await client.get(url, params=params, headers=self.headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 2 and isinstance(data[1], list):
                    return [str(item) for item in data[1]]
        except Exception:
            pass
        return []

    async def fetch(self, query: str) -> List[str]:
        results: Set[str] = set()
        async with httpx.AsyncClient() as client:
            # 1. Base query completion
            base_results = await self._fetch_single(client, query)
            results.update(base_results)

            # 2. Additional modifiers if enabled (letters + question words)
            if self.include_modifiers:
                modifiers = [
                    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
                    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
                    "how", "why", "best", "vs", "for", "with", "without", "near", "top"
                ]
                tasks = [
                    self._fetch_single(client, f"{query} {mod}") for mod in modifiers
                ]
                modifier_results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in modifier_results:
                    if isinstance(res, list):
                        results.update(res)

        return list(results)
