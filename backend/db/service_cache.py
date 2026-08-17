"""
SQLite cache for ServiceResolution objects + Tavily quota tracking.
Prevents burning Tavily quota on repeated idea runs.
Cache TTL: 30 days. Quota tracked per calendar month.
"""
from tools.llm_router import safe_print
import sqlite3
import json
import os
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "forge.db")


def _conn() -> sqlite3.Connection:
    """Return a connection with all required tables created."""
    # Resolve relative path against the backend directory
    db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS service_cache (
            cache_key  TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quota_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            service    TEXT NOT NULL,
            used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def get_cached(key: str):
    """
    Return the cached dict for key if it exists and is < 30 days old.
    Returns None on cache miss.
    """
    try:
        row = _conn().execute(
            "SELECT data FROM service_cache "
            "WHERE cache_key = ? AND created_at > datetime('now', '-30 days')",
            (key,)
        ).fetchone()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        safe_print(f"[CACHE] get_cached error: {e}")
        return None


def set_cached(key: str, data) -> None:
    """Store a Pydantic model (or dict) in the cache under key."""
    try:
        if hasattr(data, 'model_dump_json'):
            raw = data.model_dump_json()
        elif isinstance(data, dict):
            raw = json.dumps(data)
        else:
            raw = json.dumps(data)
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO service_cache (cache_key, data) VALUES (?, ?)",
            (key, raw)
        )
        conn.commit()
    except Exception as e:
        safe_print(f"[CACHE] set_cached error: {e}")


# ── Tavily Quota Tracking ─────────────────────────────────────────────────────

def increment_quota(service: str = 'tavily') -> None:
    """Log one API call for quota tracking."""
    try:
        conn = _conn()
        conn.execute(
            "INSERT INTO quota_log (service) VALUES (?)",
            (service,)
        )
        conn.commit()
    except Exception as e:
        safe_print(f"[QUOTA] increment_quota error: {e}")


def get_quota_used(service: str = 'tavily') -> int:
    """Return the number of API calls made this calendar month."""
    try:
        row = _conn().execute(
            "SELECT COUNT(*) as cnt FROM quota_log "
            "WHERE service = ? AND used_at > date('now', 'start of month')",
            (service,)
        ).fetchone()
        return row['cnt'] if row else 0
    except Exception as e:
        safe_print(f"[QUOTA] get_quota_used error: {e}")
        return 0


def warn_if_quota_high(limit: int = None) -> None:
    """Print a warning if Tavily usage exceeds 80% of the monthly limit."""
    limit = limit or int(os.getenv("TAVILY_MONTHLY_LIMIT", "1000"))
    used = get_quota_used('tavily')
    if used >= limit:
        safe_print(f"[QUOTA] EXHAUSTED: {used}/{limit} Tavily calls this month.")
    elif used >= int(limit * 0.8):
        safe_print(f"[QUOTA] WARNING: {used}/{limit} Tavily calls this month (>80%).")
    else:
        safe_print(f"[QUOTA] OK: {used}/{limit} Tavily calls this month.")