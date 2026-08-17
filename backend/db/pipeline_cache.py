"""
SQLite cache for full pipeline results.
Key: SHA-256 hash of the normalized user_idea string.
TTL: 24 hours. If the same idea is submitted again within 24h,
     the cached ForgeState dict is returned instantly.
"""
import sqlite3
import json
import hashlib
import os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "forge.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_cache (
            idea_hash  TEXT PRIMARY KEY,
            idea_text  TEXT NOT NULL,
            result     TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def _hash_idea(user_idea: str) -> str:
    """Normalize and SHA-256 hash the idea string."""
    normalized = " ".join(user_idea.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_cached_pipeline(user_idea: str) -> dict | None:
    """
    Return cached ForgeState dict if it exists and is < 24 hours old.
    Returns None on cache miss.
    """
    try:
        key = _hash_idea(user_idea)
        row = _conn().execute(
            "SELECT result FROM pipeline_cache "
            "WHERE idea_hash = ? AND created_at > datetime('now', '-24 hours')",
            (key,)
        ).fetchone()
        if row:
            return json.loads(row["result"])
        return None
    except Exception as e:
        print(f"[PIPELINE CACHE] get error: {e}")
        return None


def _make_safe(v):
    """Recursively convert Pydantic models and other non-serializables to JSON-safe dicts/lists."""
    from pydantic import BaseModel
    if isinstance(v, BaseModel):
        return v.model_dump()
    if isinstance(v, list):
        return [_make_safe(item) for item in v]
    if isinstance(v, dict):
        return {k: _make_safe(val) for k, val in v.items()}
    return v


def set_cached_pipeline(user_idea: str, result: dict) -> None:
    """
    Store a serializable pipeline result dict.
    Only caches if docx_path exists (i.e., pipeline completed successfully).
    """
    try:
        if not result.get("docx_path"):
            return  # Don't cache incomplete runs
        key = _hash_idea(user_idea)
        
        # Recursively convert everything to JSON-safe primitives
        safe_result = _make_safe(result)
        
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_cache (idea_hash, idea_text, result) VALUES (?, ?, ?)",
            (key, user_idea[:500], json.dumps(safe_result))
        )
        conn.commit()
    except Exception as e:
        print(f"[PIPELINE CACHE] set error: {e}")


def clear_expired_cache() -> int:
    """Delete all cache entries older than 24 hours. Returns rows deleted."""
    try:
        conn = _conn()
        cursor = conn.execute(
            "DELETE FROM pipeline_cache WHERE created_at <= datetime('now', '-24 hours')"
        )
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"[PIPELINE CACHE] clear error: {e}")
        return 0
