"""
Centralized Decision Engine for CostOpt Intelligent Optimization Engine
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from costopt.optimization.analyzer import RequestAnalyzer, AnalysisResult
from costopt.optimization.model_registry import ModelRegistry, ModelMetadata
from costopt.optimization.semantic_cache import SemanticCacheLayer, CacheResult
from costopt.optimization.cost_estimator import CostEstimator
from costopt.optimization.fallback_manager import FallbackManager

@dataclass
class OptimizationDecision:
    decision: str  # 'CACHE', 'REROUTE', 'DIRECT', 'FALLBACK'
    requested_model: str
    selected_model: str
    provider: str
    reason: str
    confidence: float
    estimated_cost_before: float
    estimated_cost_after: float
    estimated_savings: float
    cache_hit: bool
    task_type: str
    complexity: str
    decision_trace: List[str] = field(default_factory=list)
    cached_payload: Optional[Dict[str, Any]] = None

class DecisionEngine:
    def __init__(
        self,
        config_path: str = "costopt.yaml",
        cache_db_path: str = "costopt_cache.db",
        similarity_threshold: float = 1.0  # BUG-14 fix: default matches CostOpt default (exact match)
    ):
        self.analyzer = RequestAnalyzer()
        self.registry = ModelRegistry()
        self.cache_layer = SemanticCacheLayer(db_path=cache_db_path, similarity_threshold=similarity_threshold)
        self.estimator = CostEstimator()
        self.fallback_manager = FallbackManager()

    def evaluate(self, prompt: str, requested_model: str, provider: str = "openai") -> OptimizationDecision:
        trace: List[str] = []
        trace.append(f"Request Intercepted: requested_model='{requested_model}', provider='{provider}'")

        # 1. Request Analysis Layer
        analysis: AnalysisResult = self.analyzer.analyze(prompt, requested_model)
        trace.append(f"Task Analysis: task_type='{analysis.task_type}', complexity='{analysis.complexity}', confidence={analysis.confidence:.2f}")

        req_model_meta = self.registry.get_model(requested_model)
        prov_name = req_model_meta.provider if req_model_meta else provider

        # 2. Cache Evaluation Layer (MD5 Exact & Vector Cosine)
        cache_res: CacheResult = self.cache_layer.evaluate(prompt, requested_model)
        if cache_res.hit:
            trace.append(f"Cache Evaluation: HIT ({cache_res.match_type.upper()} match, score={cache_res.similarity_score:.2f})")
            cost_res = self.estimator.estimate(
                provider=prov_name,
                requested_model=requested_model,
                selected_model=requested_model,
                input_tokens=analysis.estimated_prompt_tokens,
                output_tokens=15,
                cache_hit=True
            )
            trace.append(f"Decision: CACHE (0ms local SQLite response, saved ${cost_res['savings']:.4f})")

            return OptimizationDecision(
                decision="CACHE",
                requested_model=requested_model,
                selected_model=requested_model,
                provider=prov_name,
                reason=f"Served via local {cache_res.match_type.upper()} cache match",
                confidence=1.0,
                estimated_cost_before=cost_res["cost_before"],
                estimated_cost_after=cost_res["cost_after"],
                estimated_savings=cost_res["savings"],
                cache_hit=True,
                task_type=analysis.task_type,
                complexity=analysis.complexity,
                decision_trace=trace,
                cached_payload=cache_res.response
            )

        trace.append("Cache Evaluation: MISS (Proceeding to Routing Engine)")

        # 3. Model Capability & Routing Evaluation
        candidate_meta = self.registry.find_cheapest_capable_model(
            requested_model=requested_model,
            task_type=analysis.task_type,
            complexity=analysis.complexity
        )
        if candidate_meta:
            candidate_name = candidate_meta.name
        else:
            # BUG-12 fix: unknown model — registry has no metadata for it.
            # Keep the requested model; routing will be handled by YAML router rules in CostOptRouter.
            candidate_name = requested_model
            trace.append(f"Routing Evaluation: Model '{requested_model}' not in internal registry. Routing deferred to YAML rules.")

        # 4. Fallback & Quality Guardrails Evaluation
        fallbacks = req_model_meta.fallbacks if req_model_meta else []
        selected_model, reason = self.fallback_manager.get_safe_model(
            requested_model=requested_model,
            candidate_model=candidate_name,
            confidence=analysis.confidence,
            complexity=analysis.complexity,
            task_type=analysis.task_type,
            fallbacks=fallbacks
        )
        trace.append(f"Routing Evaluation: {reason}")

        # 5. Cost & Savings Estimation
        cost_res = self.estimator.estimate(
            provider=prov_name,
            requested_model=requested_model,
            selected_model=selected_model,
            input_tokens=analysis.estimated_prompt_tokens,
            output_tokens=60,
            cache_hit=False
        )

        decision_type = "DIRECT"
        if selected_model.lower() != requested_model.lower():
            if cost_res["savings"] > 0:
                decision_type = "REROUTE"
            else:
                decision_type = "FALLBACK"

        trace.append(f"Final Decision: {decision_type} -> Selected model '{selected_model}' (Est. Savings: ${cost_res['savings']:.4f})")

        return OptimizationDecision(
            decision=decision_type,
            requested_model=requested_model,
            selected_model=selected_model,
            provider=prov_name,
            reason=reason,
            confidence=analysis.confidence,
            estimated_cost_before=cost_res["cost_before"],
            estimated_cost_after=cost_res["cost_after"],
            estimated_savings=cost_res["savings"],
            cache_hit=False,
            task_type=analysis.task_type,
            complexity=analysis.complexity,
            decision_trace=trace,
            cached_payload=None
        )
