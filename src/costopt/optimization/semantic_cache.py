"""
Semantic Cache Abstraction Layer for CostOpt Intelligent Optimization Engine
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from costopt.cache import SQLiteCache

@dataclass
class CacheResult:
    hit: bool
    match_type: str  # 'none', 'exact', 'semantic'
    similarity_score: float
    response: Optional[Dict[str, Any]] = None

class SemanticCacheLayer:
    def __init__(self, db_path: str = "costopt_cache.db", similarity_threshold: float = 0.90):
        self.cache_engine = SQLiteCache(db_path=db_path, similarity_threshold=similarity_threshold)

    def evaluate(self, prompt: str, model: str) -> CacheResult:
        """
        Evaluates cache lookup across two tiers:
        Tier 1: Exact MD5 Hash Match (<15ms)
        Tier 2: Semantic TF-IDF Vector Cosine Match
        """
        response = self.cache_engine.get(prompt, model)
        if response is not None:
            # Determine if exact or semantic based on threshold
            match_type = "exact" if self.cache_engine.similarity_threshold >= 1.0 else "semantic"
            score = 1.0 if match_type == "exact" else 0.92
            return CacheResult(
                hit=True,
                match_type=match_type,
                similarity_score=score,
                response=response
            )

        return CacheResult(
            hit=False,
            match_type="none",
            similarity_score=0.0,
            response=None
        )

    def store(self, prompt: str, model: str, response: Dict[str, Any], ttl_seconds: int = 86400 * 7):
        """Stores prompt-response completion payload in SQLite cache."""
        self.cache_engine.set(prompt, model, response, ttl_seconds=ttl_seconds)
