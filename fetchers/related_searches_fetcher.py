import re
from typing import List, Set
import httpx
from bs4 import BeautifulSoup
from .base import BaseFetcher


class RelatedSearchesFetcher(BaseFetcher):
    name: str = "related_searches"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch(self, query: str) -> List[str]:
        results: Set[str] = set()
        async with httpx.AsyncClient() as client:
            # 1. DuckDuckGo related queries & web snippets
            try:
                url = f"https://html.duckduckgo.com/html/?q={query}"
                resp = await client.get(url, headers=self.headers, timeout=6.0)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", class_="result__snippet"):
                        text = a.get_text().strip()
                        # Extract bolded or highlighted keywords if any
                        words = re.findall(r"\b[a-zA-Z0-9\s\-]{4,40}\b", text)
                        for w in words:
                            w_clean = w.strip().lower()
                            if query.lower() in w_clean and len(w_clean.split()) >= 2:
                                results.add(w_clean)

                    # Also check bottom related searches links on DDG HTML
                    for a in soup.find_all("a"):
                        href = a.get("href", "")
                        if "q=" in href and "duckduckgo.com" not in href:
                            t = a.get_text().strip()
                            if t and len(t.split()) in (2, 3, 4, 5, 6) and query.lower() in t.lower():
                                results.add(t)
            except Exception:
                pass

            # 2. Additional targeted suggest variations ("related to X", "X alternative", "X vs", "X software")
            suffixes = ["alternative", "vs", "software", "tool", "examples", "guide", "free", "template", "framework"]
            suggest_url = "https://suggestqueries.google.com/complete/search"
            for suffix in suffixes:
                try:
                    r = await client.get(
                        suggest_url,
                        params={"client": "firefox", "q": f"{query} {suffix}"},
                        headers=self.headers,
                        timeout=4.0
                    )
                    if r.status_code == 200:
                        data = r.json()
                        if len(data) >= 2 and isinstance(data[1], list):
                            for item in data[1]:
                                results.add(str(item))
                except Exception:
                    pass

        return list(results)
