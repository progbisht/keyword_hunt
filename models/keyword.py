from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class KeywordItem(BaseModel):
    term: str = Field(..., description="The keyword phrase")
    type: Literal["short-tail", "mid-tail", "long-tail"] = Field(
        ..., description="Tail classification based on word length"
    )
    word_count: int = Field(..., description="Number of words in the keyword term")
    intent: str = Field(
        ..., description="Search intent (informational, commercial, transactional, comparison, navigational)"
    )
    source: List[str] = Field(
        default_factory=list, description="List of data sources that surfaced this keyword"
    )
    volume: Optional[int] = Field(
        default=None, description="Search volume (where available)"
    )
    difficulty: Optional[int] = Field(
        default=None, description="Keyword difficulty score (where available)"
    )
    relevance_score: float = Field(
        ..., description="Cosine similarity score relative to the seed keyword"
    )


class KeywordDiscoveryResult(BaseModel):
    seed_keyword: str = Field(..., description="The original seed keyword")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    keywords: List[KeywordItem] = Field(
        default_factory=list, description="Structured keyword discoveries"
    )
