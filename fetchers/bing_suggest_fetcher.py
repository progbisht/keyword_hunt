import asyncio
from typing import List, Set
import httpx
from .base import BaseFetcher


class BingSuggestFetcher(BaseFetcher):
    name: str = "bing_suggest"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    async def fetch(self, query: str) -> List[str]:
        results: Set[str] = set()
        url = "https://api.bing.com/qsonhs.aspx"
        params = {"q": query}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=self.headers, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    AS = data.get("AS", {})
                    results_groups = AS.get("Results", [])
                    for group in results_groups:
                        for item in group.get("Suggests", []):
                            txt = item.get("Txt")
                            if txt:
                                results.add(txt)
            except Exception:
                pass

            # Modifier completions
            modifiers = ["best", "vs", "how", "top", "software", "tool"]
            tasks = [
                client.get(url, params={"q": f"{query} {mod}"}, headers=self.headers, timeout=4.0)
                for mod in modifiers
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for r in responses:
                if isinstance(r, httpx.Response) and r.status_code == 200:
                    try:
                        d = r.json()
                        groups = d.get("AS", {}).get("Results", [])
                        for g in groups:
                            for item in g.get("Suggests", []):
                                txt = item.get("Txt")
                                if txt:
                                    results.add(txt)
                    except Exception:
                        pass

        return list(results)
