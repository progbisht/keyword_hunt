import re
import asyncio
from typing import List, Set
import httpx
from bs4 import BeautifulSoup
from .base import BaseFetcher


class PAAFetcher(BaseFetcher):
    name: str = "paa"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch(self, query: str) -> List[str]:
        results: Set[str] = set()
        question_prefixes = ["how to", "what is", "why does", "is", "can", "best", "which"]
        
        async with httpx.AsyncClient() as client:
            # 1. Fetch question-oriented autosuggestions
            tasks = [
                self._fetch_suggest(client, f"{prefix} {query}")
                for prefix in question_prefixes
            ]
            
            # 2. Fetch SERP HTML from DuckDuckGo / Google search to extract questions
            tasks.append(self._fetch_ddg_questions(client, query))

            fetched = await asyncio.gather(*tasks, return_exceptions=True)
            for res in fetched:
                if isinstance(res, list):
                    for item in res:
                        if self._is_question_like(item):
                            results.add(item)

        return list(results)

    async def _fetch_suggest(self, client: httpx.AsyncClient, q: str) -> List[str]:
        url = "https://suggestqueries.google.com/complete/search"
        params = {"client": "firefox", "q": q}
        try:
            resp = await client.get(url, params=params, headers=self.headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 2 and isinstance(data[1], list):
                    return [str(x) for x in data[1]]
        except Exception:
            pass
        return []

    async def _fetch_ddg_questions(self, client: httpx.AsyncClient, query: str) -> List[str]:
        questions = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = await client.get(url, headers=self.headers, timeout=6.0)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for snippet in soup.find_all(["a", "span", "div"]):
                    text = snippet.get_text().strip()
                    if "?" in text and len(text) < 120 and self._is_question_like(text):
                        clean_q = re.sub(r"^[0-9\.\s\-]+", "", text).strip()
                        questions.append(clean_q)
        except Exception:
            pass
        return questions

    def _is_question_like(self, text: str) -> bool:
        lower = text.lower().strip()
        starts = ("how", "what", "why", "where", "who", "when", "can", "is", "should", "are", "which", "do", "does")
        return lower.startswith(starts) or "?" in lower or " vs " in lower
