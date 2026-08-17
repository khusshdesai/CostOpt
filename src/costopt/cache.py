import os
import sqlite3
import json
import hashlib
import time
import logging
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("costopt.cache")

class SQLiteCache:
    def __init__(self, db_path: str = "costopt_cache.db", similarity_threshold: float = 1.0):
        """
        Initialize the SQLite cache engine.
        similarity_threshold: 1.0 means exact match only. 
                              Values < 1.0 enable token-based Jaccard similarity fallback.
        """
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self._init_db()

    def _init_db(self):
        """Create cache database and schema if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_cache (
                        prompt_hash TEXT PRIMARY KEY,
                        model TEXT NOT NULL,
                        prompt_text TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        created_at INTEGER NOT NULL,
                        expires_at INTEGER NOT NULL
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_model ON prompt_cache (model)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize SQLite cache database: {e}")

    def _get_hash(self, text: str) -> str:
        """Returns MD5 hash for exact matching."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculates fast Jaccard similarity index based on lowercase word sets, stripping punctuation."""
        import string
        words1 = {w.strip(string.punctuation).lower() for w in text1.split() if w.strip(string.punctuation)}
        words2 = {w.strip(string.punctuation).lower() for w in text2.split() if w.strip(string.punctuation)}
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _tfidf_similarity(self, text1: str, text2: str) -> float:
        """Calculates fast TF-IDF word and character n-gram Cosine Vector Similarity."""
        import math, string
        def extract_features(t: str) -> Dict[str, int]:
            t_clean = t.lower().translate(str.maketrans("", "", string.punctuation))
            words = t_clean.split()
            counts: Dict[str, int] = {}
            for w in words:
                counts[w] = counts.get(w, 0) + 1
            for i in range(len(t_clean) - 2):
                gram = t_clean[i:i+3]
                counts[gram] = counts.get(gram, 0) + 1
            return counts

        v1 = extract_features(text1)
        v2 = extract_features(text2)
        all_features = set(v1.keys()) | set(v2.keys())
        if not all_features:
            return 0.0
            
        dot_product = sum(v1.get(f, 0) * v2.get(f, 0) for f in all_features)
        mag1 = math.sqrt(sum(val ** 2 for val in v1.values()))
        mag2 = math.sqrt(sum(val ** 2 for val in v2.values()))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product / (mag1 * mag2)


    def get(self, prompt_text: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a prompt.
        First attempts exact hash matching. Falls back to fast Jaccard token similarity if configured.
        """
        prompt_hash = self._get_hash(prompt_text)
        now = int(time.time())

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. Exact Match
                cursor.execute(
                    "SELECT response_json, expires_at FROM prompt_cache WHERE prompt_hash = ? AND model = ?",
                    (prompt_hash, model)
                )
                row = cursor.fetchone()
                if row:
                    response_json, expires_at = row
                    if expires_at > now:
                        logger.debug("Cache HIT (exact match)")
                        return json.loads(response_json)
                    else:
                        # Expired, clean it up
                        cursor.execute("DELETE FROM prompt_cache WHERE prompt_hash = ?", (prompt_hash,))
                        conn.commit()
                        logger.debug("Cache expired (exact match found but expired)")
                        return None

                # 2. Near-Duplicate Matching (Fuzzy Caching) if similarity threshold < 1.0
                if self.similarity_threshold < 1.0:
                    cursor.execute(
                        "SELECT prompt_hash, prompt_text, response_json, expires_at FROM prompt_cache WHERE model = ?",
                        (model,)
                    )
                    rows = cursor.fetchall()
                    best_similarity = 0.0
                    best_match = None

                    for r_hash, r_text, r_json, r_expires in rows:
                        if r_expires <= now:
                            continue
                        
                        jaccard = self._jaccard_similarity(prompt_text, r_text)
                        tfidf = self._tfidf_similarity(prompt_text, r_text)
                        similarity = max(jaccard, tfidf)

                        if similarity >= self.similarity_threshold and similarity > best_similarity:
                            best_similarity = similarity
                            best_match = (r_json, r_hash)

                    if best_match:
                        response_json, matched_hash = best_match
                        logger.info(f"Cache HIT (fuzzy match, similarity: {best_similarity:.2f}, match_hash: {matched_hash})")
                        return json.loads(response_json)

        except Exception as e:
            logger.error(f"Error querying cache database: {e}")
        
        logger.debug("Cache MISS")
        return None

    def set(self, prompt_text: str, model: str, response: Dict[str, Any], ttl_seconds: int = 3600) -> None:
        """Stores a prompt completion response in the local cache database."""
        prompt_hash = self._get_hash(prompt_text)
        response_json = json.dumps(response)
        now = int(time.time())
        expires_at = now + ttl_seconds

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.conn.cursor() if hasattr(conn, "conn") else conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO prompt_cache (prompt_hash, model, prompt_text, response_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (prompt_hash, model, prompt_text, response_json, now, expires_at))
                conn.commit()
                logger.debug(f"Cache SET for hash {prompt_hash}")
        except Exception as e:
            logger.error(f"Error writing to cache database: {e}")

    def clear(self) -> None:
        """Clears all records in the cache table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM prompt_cache")
                conn.commit()
                logger.info("Cache database cleared.")
        except Exception as e:
            logger.error(f"Error clearing cache database: {e}")
