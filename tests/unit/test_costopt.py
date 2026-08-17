import os
import tempfile
import pytest
from unittest.mock import MagicMock

from costopt.pricing import calculate_cost, get_pricing, load_pricing_from_dir
from costopt.cache import SQLiteCache
from costopt.router import CostOptRouter
from costopt.client import CostOpt

@pytest.fixture
def temp_db():
    """Fixture creating a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

@pytest.fixture
def temp_yaml():
    """Fixture creating a temporary config file path."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    yield path
    import gc
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# 1. Test pricing calculation logic
def test_pricing_calculation():
    # Load default pricing or verify calculation works with loaded mock pricing
    # Let's inspect default values
    pricing = get_pricing("openai", "gpt-4o")
    assert pricing is not None
    assert pricing["input_cost_per_1m"] == 2.5
    assert pricing["output_cost_per_1m"] == 10.0

    # Calculate normal cost: 1000 input, 2000 output.
    # Cost = (1000/1e6)*2.5 + (2000/1e6)*10.0 = 0.0025 + 0.0200 = 0.0225
    cost = calculate_cost("openai", "gpt-4o", 1000, 2000)
    assert cost == 0.02250

    # Cache hits serve from local SQLite — $0.00 marginal API cost
    cost_cached = calculate_cost("openai", "gpt-4o", 1000, 2000, cache_hit=True)
    assert cost_cached == 0.0

# 2. Test SQLite Cache engine
def test_cache_engine(temp_db):
    cache = SQLiteCache(db_path=temp_db, similarity_threshold=1.0)
    
    prompt = "How many legs does a spider have?"
    model = "gpt-4o"
    mock_response = {"id": "chatcmpl-123", "choices": [{"message": {"content": "8 legs"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    # Verify miss initially
    assert cache.get(prompt, model) is None

    # Write to cache
    cache.set(prompt, model, mock_response)

    # Verify hit
    hit = cache.get(prompt, model)
    assert hit is not None
    assert hit["choices"][0]["message"]["content"] == "8 legs"

# 3. Test Fuzzy Cache matching
def test_fuzzy_cache_matching(temp_db):
    # Set similarity threshold to 0.90 (90%)
    cache = SQLiteCache(db_path=temp_db, similarity_threshold=0.90)

    prompt_original = "Translate hello to Spanish please"
    prompt_variant = "Translate hello to Spanish please." # added period
    model = "gpt-4o"
    mock_response = {"id": "chatcmpl-456", "choices": [{"message": {"content": "Hola"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}

    cache.set(prompt_original, model, mock_response)

    # Exact match on variant should miss if threshold is 1.0, but hit on 0.90
    hit = cache.get(prompt_variant, model)
    assert hit is not None
    assert hit["choices"][0]["message"]["content"] == "Hola"

# 4. Test Model Routing rules
def test_router_rules(temp_yaml):
    # Write a custom YAML config
    import yaml
    config_data = {
        "routing": {
            "rules": [
                {
                    "name": "Translation route rule",
                    "keywords": ["translate", "spanish"],
                    "max_prompt_length": 200,
                    "original_model": "gpt-4o",
                    "target_model": "gpt-4o-mini"
                }
            ],
            "fallbacks": {
                "gpt-4o": ["claude-3-5-sonnet"]
            }
        }
    }
    with open(temp_yaml, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f)

    router = CostOptRouter(config_path=temp_yaml)
    
    # Matching prompt
    model = router.match_route("Please translate my name to Spanish", "gpt-4o")
    assert model == "gpt-4o-mini"

    # Non-matching prompt
    model_non = router.match_route("Write a massive code application", "gpt-4o")
    assert model_non == "gpt-4o"

    # Fallbacks check
    fallbacks = router.get_fallbacks("gpt-4o")
    assert fallbacks == ["claude-3-5-sonnet"]

# 5. Test SDK Client wrapping
def test_client_wrapper_intercept(temp_db, temp_yaml):
    # Mock original openai completions class
    mock_completions = MagicMock()
    mock_chat = MagicMock()
    mock_chat.completions = mock_completions
    mock_openai = MagicMock()
    mock_openai.chat = mock_chat

    # Configure mock return value of completions.create
    mock_response = MagicMock()
    mock_response.id = "chatcmpl-mock"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 4
    mock_response.model_dump.return_value = {
        "id": "chatcmpl-mock",
        "choices": [{"message": {"content": "Mocked call successful"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4}
    }
    mock_completions.create.return_value = mock_response

    # Wrap the client
    client = CostOpt(
        client=mock_openai,
        config_path=temp_yaml,
        cache_db_path=temp_db,
        telemetry_db_path=temp_db,
        environment="test",
        application="test-suite"
    )

    # Run intercepted call
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Query something"}]
    )

    # Verify original completions.create was called
    assert mock_completions.create.called
    assert res.id == "chatcmpl-mock"

    # Clean shutdown of background logging thread
    client.shutdown()


# 6. Test TF-IDF Cosine Vector Cache similarity
def test_semantic_vector_cosine_cache(temp_db):
    cache = SQLiteCache(db_path=temp_db, similarity_threshold=0.70)
    prompt1 = "What is the capital city of France?"
    prompt2 = "Tell me the capital of France city"
    mock_resp = {"id": "chatcmpl-vector", "choices": [{"message": {"content": "Paris"}}]}

    cache.set(prompt1, "gpt-4o", mock_resp)
    match = cache.get(prompt2, "gpt-4o")
    assert match is not None
    assert match["choices"][0]["message"]["content"] == "Paris"

