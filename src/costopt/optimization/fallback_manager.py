"""
Fallback & Quality Guardrails Manager for CostOpt Intelligent Optimization Engine
"""

from typing import List, Optional, Dict, Any, Tuple
from costopt.circuit_breaker import CircuitBreaker

class FallbackManager:
    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None):
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def get_safe_model(
        self,
        requested_model: str,
        candidate_model: str,
        confidence: float,
        complexity: str,
        task_type: str,
        fallbacks: List[str]
    ) -> Tuple[str, str]:
        """
        Applies safety guardrails to verify model selection.
        Returns Tuple[selected_model, decision_reason].
        """
        # Guardrail 1: Low Confidence Check (< 0.70)
        if confidence < 0.70:
            return requested_model, f"Low confidence ({confidence:.2f} < 0.70); safety guardrail selected original model '{requested_model}'"

        # Guardrail 2: High Complexity Reasoning / Coding Safeguard
        if complexity == "high" and task_type in ["reasoning", "coding"] and candidate_model.lower() != requested_model.lower():
            return requested_model, f"High-complexity {task_type} task detected; retained flagship model '{requested_model}' for accuracy"

        return candidate_model, f"Optimization criteria satisfied for '{candidate_model}'"
