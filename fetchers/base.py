from abc import ABC, abstractmethod
from typing import List


class BaseFetcher(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, query: str) -> List[str]:
        """
        Fetches candidate keywords for the given query.
        Returns a list of raw keyword strings.
        """
        pass
