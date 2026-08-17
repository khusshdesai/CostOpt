import os
import logging
from typing import Dict, Any, Optional
import yaml

logger = logging.getLogger("costopt.pricing")

# Dynamic cache of pricing data
# Structure: { provider_name: { model_name: { input_cost_per_1m, output_cost_per_1m, cached_input_cost_per_1m } } }
_PRICING_CACHE: Dict[str, Dict[str, Dict[str, float]]] = {}

# Default pricing path relative to this script
DEFAULT_PRICING_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "pricing", "providers")
)

def load_pricing_from_dir(pricing_dir: str) -> None:
    """Loads all yaml pricing configurations from a directory into memory cache."""
    global _PRICING_CACHE
    if not os.path.exists(pricing_dir):
        logger.warning(f"Pricing directory '{pricing_dir}' does not exist. Caching skipped.")
        return

    for filename in os.listdir(pricing_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(pricing_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data or not isinstance(data, dict):
                        continue
                    
                    provider = data.get("provider")
                    models = data.get("models")
                    if provider and isinstance(models, dict):
                        _PRICING_CACHE[provider.lower()] = {}
                        for model_name, pricing_info in models.items():
                            _PRICING_CACHE[provider.lower()][model_name.lower()] = {
                                "input_cost_per_1m": float(pricing_info.get("input_cost_per_1m", 0.0)),
                                "output_cost_per_1m": float(pricing_info.get("output_cost_per_1m", 0.0)),
                                "cached_input_cost_per_1m": float(pricing_info.get("cached_input_cost_per_1m", pricing_info.get("input_cost_per_1m", 0.0)))
                            }
                logger.info(f"Successfully loaded pricing for provider: {provider}")
            except Exception as e:
                logger.error(f"Failed to load pricing config from {filepath}: {e}")

def get_pricing(provider: str, model: str, pricing_dir: Optional[str] = None) -> Optional[Dict[str, float]]:
    """Returns pricing metadata dict for a specific provider/model, loading on demand if empty."""
    global _PRICING_CACHE
    
    provider_key = provider.lower()
    model_key = model.lower()

    if not _PRICING_CACHE:
        target_dir = pricing_dir or DEFAULT_PRICING_DIR
        load_pricing_from_dir(target_dir)

    # Try mapping exact model
    provider_data = _PRICING_CACHE.get(provider_key)
    if provider_data:
        # Check exact match
        if model_key in provider_data:
            return provider_data[model_key]
        
        # Check fuzzy/substring match (e.g. gpt-4o-2024-05-13 matches gpt-4o prefix)
        for known_model, pricing_info in provider_data.items():
            if model_key.startswith(known_model) or known_model in model_key:
                return pricing_info

    return None

def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit: bool = False,
    pricing_dir: Optional[str] = None
) -> float:
    """
    Calculate estimated cost for a given request.
    If exact prices are unknown, default rate is set to 0.0.
    """
    pricing = get_pricing(provider, model, pricing_dir)
    if not pricing:
        # Fallback to zero
        logger.debug(f"Pricing info not found for provider={provider}, model={model}. Defaulting to 0.0 cost.")
        return 0.0

    input_rate = pricing["cached_input_cost_per_1m"] if cache_hit else pricing["input_cost_per_1m"]
    output_rate = pricing["output_cost_per_1m"]

    input_cost = (input_tokens / 1_000_000.0) * input_rate
    output_cost = (output_tokens / 1_000_000.0) * output_rate

    return round(input_cost + output_cost, 6)

def get_all_loaded_models(pricing_dir: Optional[str] = None) -> Dict[str, List[str]]:
    """Returns a dictionary mapping provider -> list of model keys loaded in configuration."""
    global _PRICING_CACHE
    from typing import List
    
    if not _PRICING_CACHE:
        target_dir = pricing_dir or DEFAULT_PRICING_DIR
        load_pricing_from_dir(target_dir)
        
    return {provider: list(models.keys()) for provider, models in _PRICING_CACHE.items()}

