import os
import tempfile
import pytest
from unittest.mock import MagicMock
from costopt.cache import SQLiteCache
from costopt.pricing import get_pricing, calculate_cost, load_pricing_from_dir
from costopt.client import _compute_params_hash, CostOpt

def test_bug1_and_bug4_parameter_hashing_and_multimodel_cache():
    """Validates Bug 1 (params hash isolation) & Bug 4 (multi-model PRIMARY KEY non-eviction)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_cache.db")
        cache = SQLiteCache(db_path=db_path)

        # Bug 1 test: Parameters (temperature=0 vs temperature=1.0) produce distinct cache slots
        hash_temp0 = _compute_params_hash({"temperature": 0.0})
        hash_temp1 = _compute_params_hash({"temperature": 1.0})

        cache.set("hello world", "gpt-4o", {"choices": [{"message": {"content": "temp 0"}}]}, params_hash=hash_temp0)
        cache.set("hello world", "gpt-4o", {"choices": [{"message": {"content": "temp 1"}}]}, params_hash=hash_temp1)

        hit_temp0 = cache.get("hello world", "gpt-4o", params_hash=hash_temp0)
        hit_temp1 = cache.get("hello world", "gpt-4o", params_hash=hash_temp1)

        assert hit_temp0["choices"][0]["message"]["content"] == "temp 0"
        assert hit_temp1["choices"][0]["message"]["content"] == "temp 1"

        # Bug 4 test: Caching for model B does not evict model A
        cache.set("hello world", "gpt-4o-mini", {"choices": [{"message": {"content": "mini"}}]}, params_hash=hash_temp0)
        
        hit_gpt4o = cache.get("hello world", "gpt-4o", params_hash=hash_temp0)
        hit_mini = cache.get("hello world", "gpt-4o-mini", params_hash=hash_temp0)

        assert hit_gpt4o is not None
        assert hit_mini is not None
        assert hit_gpt4o["choices"][0]["message"]["content"] == "temp 0"
        assert hit_mini["choices"][0]["message"]["content"] == "mini"

def test_bug5_unversioned_alias_pricing_match():
    """Validates Bug 5: Unversioned model aliases (gpt-4, gpt-3.5-turbo, claude-3-haiku) match base pricing."""
    pricing_gpt4 = get_pricing("openai", "gpt-4")
    pricing_gpt35 = get_pricing("openai", "gpt-3.5-turbo")
    pricing_haiku = get_pricing("anthropic", "claude-3-haiku")

    assert pricing_gpt4 is not None
    assert pricing_gpt35 is not None
    assert pricing_haiku is not None

    assert pricing_gpt4["input_cost_per_1m"] > 0.0
    assert pricing_gpt35["input_cost_per_1m"] > 0.0
    assert pricing_haiku["input_cost_per_1m"] > 0.0

def test_bug9_pricing_directory_cache_isolation():
    """Validates Bug 9: Multiple pricing directories remain isolated in memory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_content = """
provider: custom_test
models:
  test-model-1:
    input_cost_per_1m: 10.0
    output_cost_per_1m: 20.0
"""
        with open(os.path.join(tmpdir, "custom.yaml"), "w") as yf:
            yf.write(yaml_content)

        pricing_custom = get_pricing("custom_test", "test-model-1", pricing_dir=tmpdir)
        pricing_default_fail = get_pricing("custom_test", "test-model-1")

        assert pricing_custom is not None
        assert pricing_custom["input_cost_per_1m"] == 10.0
        assert pricing_default_fail is None
