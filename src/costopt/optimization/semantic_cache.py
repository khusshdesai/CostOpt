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
        Tier 1: Exact SHA-256 Hash Match  -> similarity_score = 1.0
        Tier 2: Fuzzy TF-IDF/Jaccard Match -> similarity_score = real computed score
        """
        response, similarity_score = self.cache_engine.get(prompt, model)

        if response is not None:
            # Exact hits return 1.0 from cache.get(); fuzzy hits return the real score.
            match_type = "exact" if similarity_score == 1.0 else "semantic"
            return CacheResult(
                hit=True,
                match_type=match_type,
                similarity_score=similarity_score,
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

