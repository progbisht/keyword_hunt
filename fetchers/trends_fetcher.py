from typing import List, Set
import httpx
from .base import BaseFetcher


class TrendsFetcher(BaseFetcher):
    name: str = "trends"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def fetch(self, query: str) -> List[str]:
        results: Set[str] = set()
        async with httpx.AsyncClient() as client:
            # Query trending / rising suffixes (e.g. 2026, latest, modern, new)
            suffixes = ["2026", "latest", "trends", "future of", "new", "top rated"]
            for s in suffixes:
                try:
                    q_str = f"{query} {s}" if not s.startswith("future of") else f"{s} {query}"
                    url = "https://suggestqueries.google.com/complete/search"
                    resp = await client.get(url, params={"client": "firefox", "q": q_str}, headers=self.headers, timeout=4.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if len(data) >= 2 and isinstance(data[1], list):
                            for item in data[1]:
                                results.add(str(item))
                except Exception:
                    pass

        return list(results)
