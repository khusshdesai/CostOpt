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
def test_vscode_env():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_telemetry:
        telemetry_path = f_telemetry.name
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f_cache:
        cache_path = f_cache.name
        
    set_db_paths(telemetry_path, cache_path)
    
    logger = SQLiteTelemetryLogger(db_path=telemetry_path)
    logger.log({
        "request_id": "req-vscode-1",
        "provider": "openai",
        "model_requested": "gpt-4o",
        "model_used": "gpt-4o",
        "input_tokens": 1000,
        "output_tokens": 250,
        "latency_ms": 350,
        "status_code": 200,
        "success": True,
        "error_type": None,
        "cache_hit": False,
        "cost_original": 0.005,
        "cost_actual": 0.005,
        "savings": 0.0,
        "prompt_hash": "hash123",
        "environment": "development",
        "application": "customer_support",
        "region": "us-east-1",
        "retry_count": 0,
        "file_path": "c:/app/main.py",
        "line_number": 25
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

def test_vscode_health(test_vscode_env):
    res = test_vscode_env.get("/api/vscode/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"

def test_vscode_file_stats(test_vscode_env):
    res = test_vscode_env.get("/api/vscode/file-stats?file_path=c:/app/main.py")
    assert res.status_code == 200
    data = res.json()
    assert data["total_file_calls"] >= 1
    assert len(data["line_stats"]) >= 1

def test_vscode_forecast(test_vscode_env):
    res = test_vscode_env.get("/api/vscode/forecast?budget=50.0")
    assert res.status_code == 200
    data = res.json()
    assert data["has_enough_data"] is True
    assert data["budget"] == 50.0

def test_vscode_warnings(test_vscode_env):
    res = test_vscode_env.get("/api/vscode/warnings?budget=50.0")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
