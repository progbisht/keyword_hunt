import os
import uuid
import logging
from typing import Dict, List, Optional
from dotenv import load_dotenv
from models.keyword import KeywordDiscoveryResult

load_dotenv()

logger = logging.getLogger("db")

# Fallback in-memory storage for local execution when Supabase is not connected
_local_jobs = []
_local_keywords = {}


def get_db_connection_url() -> Optional[str]:
    return os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")


async def init_db() -> bool:
    """Creates discovery_jobs and keywords tables if PostgreSQL connection is configured."""
    db_url = get_db_connection_url()
    if not db_url:
        logger.info("ℹ️ SUPABASE_DB_URL not set. Skipping DB table creation. Running in local fallback mode.")
        return False

    try:
        import asyncpg
        conn = await asyncpg.connect(db_url)
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS discovery_jobs (
                    id UUID PRIMARY KEY,
                    seed_keyword VARCHAR(255) NOT NULL,
                    total_keywords INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS keywords (
                    id BIGSERIAL PRIMARY KEY,
                    job_id UUID REFERENCES discovery_jobs(id) ON DELETE CASCADE,
                    seed_keyword VARCHAR(255) NOT NULL,
                    term VARCHAR(500) NOT NULL,
                    type VARCHAR(20) NOT NULL,
                    word_count INTEGER NOT NULL,
                    intent VARCHAR(30) NOT NULL,
                    sources TEXT[] NOT NULL,
                    volume INTEGER,
                    difficulty INTEGER,
                    relevance_score NUMERIC(5,3) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_keywords_job_id ON keywords(job_id);
                CREATE INDEX IF NOT EXISTS idx_keywords_seed ON keywords(seed_keyword);
            """)
            logger.info("✅ Supabase PostgreSQL tables initialized.")
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.warning(f"⚠️ Could not initialize Supabase DB tables: {e}")
        return False


async def save_discovery_result(result: KeywordDiscoveryResult, job_id: Optional[str] = None) -> Optional[str]:
    """Persists KeywordDiscoveryResult and keywords into Supabase PostgreSQL (or fallback memory)."""
    if not job_id:
        job_id = str(uuid.uuid4())
    created_at_iso = result.generated_at

    # Always save to local fallback memory store first
    from datetime import datetime
    _local_jobs.insert(0, {
        "job_id": job_id,
        "seed_keyword": result.seed_keyword,
        "total_keywords": len(result.keywords),
        "created_at": created_at_iso
    })
    
    # Store list of dicts for local keywords
    _local_keywords[job_id] = [
        {
            "term": kw.term,
            "type": kw.type,
            "word_count": kw.word_count,
            "intent": kw.intent,
            "source": kw.source,
            "volume": kw.volume,
            "difficulty": kw.difficulty,
            "relevance_score": float(kw.relevance_score),
        }
        for kw in result.keywords
    ]

    db_url = get_db_connection_url()
    if not db_url:
        logger.info(f"ℹ️ Saved discovery result ({len(result.keywords)} keywords) to local fallback. Job ID: {job_id}")
        return job_id

    try:
        import asyncpg
        conn = await asyncpg.connect(db_url)
        try:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO discovery_jobs (id, seed_keyword, total_keywords)
                    VALUES ($1, $2, $3)
                    """,
                    uuid.UUID(job_id),
                    result.seed_keyword,
                    len(result.keywords),
                )

                if result.keywords:
                    records = [
                        (
                            uuid.UUID(job_id),
                            result.seed_keyword,
                            kw.term,
                            kw.type,
                            kw.word_count,
                            kw.intent,
                            kw.source,
                            kw.volume,
                            kw.difficulty,
                            float(kw.relevance_score),
                        )
                        for kw in result.keywords
                    ]
                    await conn.copy_records_to_table(
                        "keywords",
                        records=records,
                        columns=[
                            "job_id",
                            "seed_keyword",
                            "term",
                            "type",
                            "word_count",
                            "intent",
                            "sources",
                            "volume",
                            "difficulty",
                            "relevance_score",
                        ],
                    )

            logger.info(f"✅ Saved discovery result ({len(result.keywords)} keywords) to Supabase DB. Job ID: {job_id}")
            return job_id
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Error saving result to Supabase DB: {e}")
        return job_id  # still return the job_id since we successfully saved to local fallback memory


async def get_job_history(limit: int = 20) -> List[Dict]:
    """Fetches recent discovery runs from Supabase DB, falling back to local memory if needed."""
    db_url = get_db_connection_url()
    if not db_url:
        return _local_jobs[:limit]

    try:
        import asyncpg
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """
                SELECT id, seed_keyword, total_keywords, created_at
                FROM discovery_jobs
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [
                {
                    "job_id": str(r["id"]),
                    "seed_keyword": r["seed_keyword"],
                    "total_keywords": r["total_keywords"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Error fetching job history from Supabase: {e}. Falling back to local cache.")
        return _local_jobs[:limit]


async def get_keywords_by_job_id(job_id: str) -> List[Dict]:
    """Fetches keywords for a given job_id from Supabase DB, falling back to local memory."""
    db_url = get_db_connection_url()
    if not db_url:
        return _local_keywords.get(job_id, [])

    try:
        import asyncpg
        import uuid as uuid_pkg
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """
                SELECT term, type, word_count, intent, sources as source, volume, difficulty, relevance_score
                FROM keywords
                WHERE job_id = $1
                ORDER BY relevance_score DESC, word_count DESC
                """,
                uuid_pkg.UUID(job_id),
            )
            if not rows:
                # Fallback to local memory if not found in DB
                return _local_keywords.get(job_id, [])
            return [
                {
                    "term": r["term"],
                    "type": r["type"],
                    "word_count": r["word_count"],
                    "intent": r["intent"],
                    "source": list(r["source"]) if r["source"] else [],
                    "volume": r["volume"],
                    "difficulty": r["difficulty"],
                    "relevance_score": float(r["relevance_score"]),
                }
                for r in rows
            ]
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"❌ Error fetching keywords for job {job_id} from Supabase: {e}. Falling back to local cache.")
        return _local_keywords.get(job_id, [])

