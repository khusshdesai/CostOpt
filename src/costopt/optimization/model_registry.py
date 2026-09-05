"""
Model Capability Registry for CostOpt Intelligent Optimization Engine
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class ModelMetadata:
    name: str
    provider: str
    tier: str  # 'flagship', 'efficient', 'local'
    capability_score: float  # 0 to 100
    supported_tasks: List[str] = field(default_factory=list)
    cost_input_per_1k: float = 0.0
    cost_output_per_1k: float = 0.0
    latency_characteristic: str = 'moderate'  # 'fast', 'moderate', 'slow'
    fallbacks: List[str] = field(default_factory=list)

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, ModelMetadata] = {}
        self._register_default_models()

    def _register_default_models(self):
        # OpenAI Models
        self.register(ModelMetadata(
            name="gpt-4o",
            provider="openai",
            tier="flagship",
            capability_score=95.0,
            supported_tasks=["simple_classification", "extraction", "summarization", "coding", "reasoning", "creative_generation", "general_chat"],
            cost_input_per_1k=0.005,
            cost_output_per_1k=0.015,
            latency_characteristic="moderate",
            fallbacks=["claude-3-5-sonnet", "gpt-4o-mini"]
        ))

        self.register(ModelMetadata(
            name="gpt-4o-mini",
            provider="openai",
            tier="efficient",
            capability_score=75.0,
            supported_tasks=["simple_classification", "extraction", "summarization", "general_chat"],
            cost_input_per_1k=0.00015,
            cost_output_per_1k=0.0006,
            latency_characteristic="fast",
            fallbacks=["claude-3-haiku", "llama3"]
        ))

        # Anthropic Models
        self.register(ModelMetadata(
            name="claude-3-5-sonnet",
            provider="anthropic",
            tier="flagship",
            capability_score=96.0,
            supported_tasks=["simple_classification", "extraction", "summarization", "coding", "reasoning", "creative_generation", "general_chat"],
            cost_input_per_1k=0.003,
            cost_output_per_1k=0.015,
            latency_characteristic="moderate",
            fallbacks=["gpt-4o", "claude-3-haiku"]
        ))

        self.register(ModelMetadata(
            name="claude-3-haiku",
            provider="anthropic",
            tier="efficient",
            capability_score=70.0,
            supported_tasks=["simple_classification", "extraction", "summarization", "general_chat"],
            cost_input_per_1k=0.00025,
            cost_output_per_1k=0.00125,
            latency_characteristic="fast",
            fallbacks=["gpt-4o-mini", "llama3"]
        ))

        # Local / Open Models
        self.register(ModelMetadata(
            name="llama3",
            provider="ollama",
            tier="local",
            capability_score=65.0,
            supported_tasks=["simple_classification", "extraction", "general_chat"],
            cost_input_per_1k=0.0,
            cost_output_per_1k=0.0,
            latency_characteristic="fast",
            fallbacks=["deepseek-r1", "gpt-4o-mini"]
        ))

        self.register(ModelMetadata(
            name="deepseek-r1",
            provider="ollama",
            tier="local",
            capability_score=78.0,
            supported_tasks=["reasoning", "coding", "simple_classification"],
            cost_input_per_1k=0.0,
            cost_output_per_1k=0.0,
            latency_characteristic="moderate",
            fallbacks=["llama3", "gpt-4o-mini"]
        ))

    def register(self, metadata: ModelMetadata):
        self._models[metadata.name.lower()] = metadata

    def get_model(self, model_name: str) -> Optional[ModelMetadata]:
        return self._models.get(model_name.lower())

    def list_models(self) -> List[ModelMetadata]:
        return list(self._models.values())

    def find_cheapest_capable_model(
        self,
        requested_model: str,
        task_type: str,
        complexity: str
    ) -> Optional[ModelMetadata]:
        req_meta = self.get_model(requested_model)
        if not req_meta:
            # BUG-12: model not in registry — return None so DecisionEngine
            # falls back to YAML routing rules instead of silently returning DIRECT
            return None

        # For high-complexity reasoning or coding tasks, retain original model
        if complexity == "high" and task_type in ["reasoning", "coding"]:
            return req_meta

        req_cost = req_meta.cost_input_per_1k + req_meta.cost_output_per_1k

        candidates = []
        for model in self._models.values():
            if task_type in model.supported_tasks:
                model_cost = model.cost_input_per_1k + model.cost_output_per_1k
                if model_cost <= req_cost:
                    # Capability check
                    if complexity == "low" or model.capability_score >= 70.0:
                        candidates.append(model)

        if not candidates:
            return req_meta

        # Sort by total cost ascending, then by capability score descending
        candidates.sort(key=lambda m: (m.cost_input_per_1k + m.cost_output_per_1k, -m.capability_score))
        return candidates[0]
