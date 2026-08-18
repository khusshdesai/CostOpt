import pytest
from fastapi.testclient import TestClient
from costopt.api.routes import router, set_db_paths
from costopt.telemetry import SQLiteTelemetryLogger
from fastapi import FastAPI
import tempfile
import os

app = FastAPI()
app.include_router(router, prefix="/api")

@pytest.fixture
def test_env():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_telemetry:
        telemetry_path = f_telemetry.name
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_cache:
        cache_path = f_cache.name
        
    set_db_paths(telemetry_path, cache_path)
    
    logger = SQLiteTelemetryLogger(db_path=telemetry_path)
    logger.log({
        "request_id": "test-1",
        "provider": "openai",
        "model_requested": "gpt-4o",
        "model_used": "gpt-4o",
        "input_tokens": 500,
        "output_tokens": 200,
        "latency_ms": 150,
        "status_code": 200,
        "success": True,
        "error_type": None,
        "cache_hit": False,
        "cost_original": 0.00325,
        "cost_actual": 0.00325,
        "savings": 0.0,
        "prompt_hash": "hash1",
        "environment": "development",
        "application": "rag_summarizer",
        "region": "us-east-1",
        "retry_count": 0
    })
    logger.shutdown()
    
    client = TestClient(app)
    yield client
    
    try:
        os.remove(telemetry_path)
    except Exception:
        pass
    try:
        os.remove(cache_path)
    except Exception:
        pass

def test_feature_attribution_endpoint(test_env):
    response = test_env.get("/api/features")
    assert response.status_code == 200
    data = response.json()
    assert "features" in data
    assert "recommendations" in data
    assert len(data["features"]) == 1
    assert data["features"][0]["feature"] == "rag_summarizer"
    assert data["features"][0]["call_count"] == 1
