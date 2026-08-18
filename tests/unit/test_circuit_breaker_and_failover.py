import pytest
from unittest.mock import MagicMock
from costopt.circuit_breaker import CircuitBreaker, CostOptCircuitBreakerError
from costopt.client import CostOpt

def test_circuit_breaker_trips():
    cb = CircuitBreaker(max_calls=3, time_window_seconds=10.0)
    location = "agent.py:42"

    # First 3 calls succeed
    cb.check_and_record(location)
    cb.check_and_record(location)
    cb.check_and_record(location)

    # 4th call exceeds max_calls=3 -> must raise CostOptCircuitBreakerError
    with pytest.raises(CostOptCircuitBreakerError) as exc_info:
        cb.check_and_record(location)

    assert "CostOpt Circuit Breaker TRIPPED" in str(exc_info.value)
    assert "agent.py:42" in str(exc_info.value)

def test_circuit_breaker_resets_for_different_location():
    cb = CircuitBreaker(max_calls=2, time_window_seconds=10.0)
    cb.check_and_record("fileA.py:10")
    cb.check_and_record("fileA.py:10")
    
    # Different location should not trip
    cb.check_and_record("fileB.py:20")
    cb.check_and_record("fileB.py:20")

    with pytest.raises(CostOptCircuitBreakerError):
        cb.check_and_record("fileA.py:10")

def test_costopt_circuit_breaker_integration():
    mock_openai = MagicMock()
    mock_resp = MagicMock()
    mock_resp.id = "resp-123"
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 5
    mock_resp.model_dump.return_value = {"id": "resp-123", "choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    mock_openai.chat.completions.create.return_value = mock_resp

    client = CostOpt(mock_openai, circuit_breaker_max_calls=2)

    # 3 rapid calls in a loop from the exact same line
    with pytest.raises(CostOptCircuitBreakerError):
        for i in range(5):
            client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": f"hi_{i}"}])

def test_outage_failover_retry():
    mock_openai = MagicMock()
    mock_resp = MagicMock()
    mock_resp.id = "resp-fallback"
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 5
    mock_resp.model_dump.return_value = {"id": "resp-fallback", "choices": []}

    # Primary model call fails with 429 RateLimitError, fallback call succeeds
    mock_openai.chat.completions.create.side_effect = [Exception("429 Rate Limit Exceeded"), mock_resp]

    client = CostOpt(mock_openai)
    # Configure fallback for gpt-4o -> gpt-4o-mini
    client.router.fallbacks["gpt-4o"] = ["gpt-4o-mini"]

    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "test outage"}])
    assert res == mock_resp
    assert mock_openai.chat.completions.create.call_count == 2
