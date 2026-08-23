"""
Cost Estimator for CostOpt Intelligent Optimization Engine
"""

from typing import Dict
from costopt.pricing import calculate_cost

class CostEstimator:
    def estimate(
        self,
        provider: str,
        requested_model: str,
        selected_model: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit: bool = False
    ) -> Dict[str, float]:
        cost_before = calculate_cost(provider, requested_model, input_tokens, output_tokens, cache_hit=False)
        cost_after = calculate_cost(provider, selected_model, input_tokens, output_tokens, cache_hit=cache_hit)
        savings = max(0.0, cost_before - cost_after)

        return {
            "cost_before": round(cost_before, 6),
            "cost_after": round(cost_after, 6),
            "savings": round(savings, 6)
        }
