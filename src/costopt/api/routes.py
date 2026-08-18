import sqlite3
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from costopt.anomaly import AnomalyDetector

router = APIRouter()

# Global database paths that can be configured by server init
_TELEMETRY_DB = "costopt_telemetry.db"
_CACHE_DB = "costopt_cache.db"

def set_db_paths(telemetry_db: str, cache_db: str):
    global _TELEMETRY_DB, _CACHE_DB
    _TELEMETRY_DB = telemetry_db
    _CACHE_DB = cache_db

def _get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/overview")
def get_overview(env: Optional[str] = None):
    """Retrieve key aggregate cost and efficiency metrics from logs."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            # Filters
            query = "SELECT count(*), sum(cost_original), sum(cost_actual), sum(savings), sum(cache_hit), sum(case when success = 0 then 1 else 0 end) FROM telemetry"
            params = []
            if env:
                query += " WHERE environment = ?"
                params.append(env)
                
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            count = row[0] or 0
            original = row[1] or 0.0
            actual = row[2] or 0.0
            savings = row[3] or 0.0
            cache_hits = row[4] or 0
            failures = row[5] or 0
            
            cache_rate = (cache_hits / count * 100) if count > 0 else 0.0
            error_rate = (failures / count * 100) if count > 0 else 0.0
            
            return {
                "total_requests": count,
                "cost_baseline": round(original, 4),
                "cost_actual": round(actual, 4),
                "total_savings": round(savings, 4),
                "cache_hit_rate": round(cache_rate, 2),
                "error_rate": round(error_rate, 2)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation failed: {e}")

@router.get("/charts/savings")
def get_savings_chart_data(limit: int = 30):
    """Returns daily cost, baseline cost, and savings metrics for time series plots."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d', timestamp) as date,
                    SUM(cost_original) as baseline_cost,
                    SUM(cost_actual) as actual_cost,
                    SUM(savings) as savings
                FROM telemetry
                GROUP BY date
                ORDER BY date ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            
            return [
                {
                    "date": r["date"],
                    "baseline_cost": round(r["baseline_cost"], 4),
                    "actual_cost": round(r["actual_cost"], 4),
                    "savings": round(r["savings"], 4)
                } for r in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/charts/models")
def get_model_distribution():
    """Returns total request counts and actual cost grouped by provider/model."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    provider,
                    model_used,
                    COUNT(*) as count,
                    SUM(cost_actual) as spend
                FROM telemetry
                GROUP BY provider, model_used
                ORDER BY spend DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations")
def get_recommendations():
    """Generates concrete, actionable FinOps optimization suggestions backed by database evidence."""
    recommendations = []
    
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            # Strategy A: Model Routing Check
            # Look at simple prompts (short length, containing key intent keywords) run on expensive models
            cursor.execute("""
                SELECT 
                    count(*) as count,
                    sum(cost_actual) as cost
                FROM telemetry
                WHERE model_requested IN ('gpt-4', 'claude-3-opus')
                  AND length(prompt_hash) > 0 -- just representing prompt presence
                  -- simple requests heuristic
                  AND (input_tokens < 200)
            """)
            routing_row = cursor.fetchone()
            if routing_row and routing_row["count"] > 0:
                count = routing_row["count"]
                current_cost = routing_row["cost"] or 0.0
                # Let's project saving if routed to mini/haiku (saving ~90% cost)
                estimated_savings = current_cost * 0.90
                recommendations.append({
                    "strategy": "Model Routing",
                    "title": f"Route short requests from premium models to mini equivalents",
                    "description": f"Detected {count} high-cost premium requests with low input token counts (< 200). Routing these to gpt-4o-mini / claude-3-haiku can cut token costs by 90%.",
                    "evidence": f"Acreage: {count} requests. Current cost: ${current_cost:.4f}.",
                    "estimated_savings": round(estimated_savings, 4),
                    "confidence": "HIGH"
                })

            # Strategy B: Duplicate prompt caching opportunities
            # Look at prompts that repeated but missed cache (cache_hit = 0)
            cursor.execute("""
                SELECT 
                    prompt_hash,
                    count(*) as occurrence_count,
                    sum(cost_actual) as wasted_cost
                FROM telemetry
                WHERE cache_hit = 0 AND success = 1
                GROUP BY prompt_hash
                HAVING occurrence_count > 1
                ORDER BY occurrence_count DESC
                LIMIT 5
            """)
            dup_rows = cursor.fetchall()
            if dup_rows:
                total_waste = sum(r["wasted_cost"] for r in dup_rows)
                occurrences = sum(r["occurrence_count"] for r in dup_rows)
                # Savings is the cost of duplicate runs (actual spend - 1st run spend)
                estimated_savings = sum(r["wasted_cost"] * (r["occurrence_count"] - 1) / r["occurrence_count"] for r in dup_rows)
                recommendations.append({
                    "strategy": "Duplicate Caching",
                    "title": "Enable caching for highly repetitive prompts",
                    "description": f"Identified {len(dup_rows)} distinct prompt hashes repeating {occurrences} times without caching. Enabling local SQLite caching will bypass API hits completely.",
                    "evidence": f"Total repeated runs waste: ${total_waste:.4f}.",
                    "estimated_savings": round(estimated_savings, 4),
                    "confidence": "VERY_HIGH"
                })

            # Strategy C: Retry Waste Analysis
            # Look at costs accumulated due to failed request retries
            cursor.execute("""
                SELECT 
                    count(*) as failed_count,
                    sum(cost_actual) as waste
                FROM telemetry
                WHERE success = 0 AND retry_count > 0
            """)
            retry_row = cursor.fetchone()
            if retry_row and retry_row["failed_count"] > 0:
                count = retry_row["failed_count"]
                waste_cost = retry_row["waste"] or 0.0
                recommendations.append({
                    "strategy": "Retry Optimization",
                    "title": "Reduce aggressive retry counts on server errors",
                    "description": f"Detected {count} request failures that incurred API charge penalties due to repetitive retry attempts.",
                    "evidence": f"Wasted retry budget: ${waste_cost:.4f}.",
                    "estimated_savings": round(waste_cost, 4),
                    "confidence": "MEDIUM"
                })

            return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed building recommendations: {e}")

@router.get("/anomalies")
def get_anomalies(z_score: float = 2.0):
    """Retrieve cost anomaly analysis reports using Z-score statistics."""
    detector = AnomalyDetector(_TELEMETRY_DB)
    anomalies = detector.analyze_daily_cost_anomalies(z_threshold=z_score)
    return anomalies

@router.post("/cache/clear")
def clear_cache():
    """Wipes the local cache database."""
    try:
        from costopt.cache import SQLiteCache
        cache = SQLiteCache(_CACHE_DB)
        cache.clear()
        return {"status": "success", "message": "Cache database cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry/recent")
def get_recent_telemetry(limit: int = 10):
    """Returns the most recent logged telemetry transactions."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    timestamp, request_id, model_requested, model_used,
                    input_tokens, output_tokens, latency_ms, success,
                    cache_hit, cost_original, cost_actual, savings, prompt_hash
                FROM telemetry
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/telemetry/generate")
def inject_simulation_data():
    """Injects 150 mock transactions into the telemetry database."""
    try:
        from costopt.generator import generate_telemetry_dataset
        from costopt.telemetry import SQLiteTelemetryLogger
        events = generate_telemetry_dataset(records_count=150, days=15)
        logger = SQLiteTelemetryLogger(db_path=_TELEMETRY_DB)
        logger._flush_batch(events)
        logger.shutdown()
        return {"status": "success", "message": "Injected 150 mock logs into database."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config")
def get_active_config():
    """Returns the current costopt.yaml routing rules template."""
    import os
    try:
        config_path = "costopt.yaml"
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"status": "success", "content": content}
        return {"status": "error", "message": "costopt.yaml config file not found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
class SimulationRequest(BaseModel):
    prompt: str
    model: str

@router.post("/simulate")
def simulate_sdk_call(req: SimulationRequest):
    """Simulates the SDK cache checks and routing rules for a prompt."""
    import time
    logs = []
    logs.append(f"Intercepting ChatCompletion call for requested model='{req.model}'")
    
    # Check Cache
    from costopt.cache import SQLiteCache
    cache = SQLiteCache(_CACHE_DB)
    logs.append("Step 1: Computing MD5 hash and checking SQLiteCache...")
    cached_response = cache.get(req.prompt, req.model)
    
    from costopt.pricing import calculate_cost
    
    if cached_response:
        logs.append("Cache HIT! Serving response from local SQLite cache database.")
        cost_orig = calculate_cost("openai", req.model, 45, 15)
        cost_act = calculate_cost("openai", req.model, 45, 15, cache_hit=True)
        savings = cost_orig - cost_act
        return {
            "status": "success",
            "cache_hit": True,
            "routed": False,
            "original_model": req.model,
            "final_model": req.model,
            "cost_original": round(cost_orig, 6),
            "cost_actual": round(cost_act, 6),
            "savings": round(savings, 6),
            "logs": logs
        }
        
    logs.append("Cache MISS. Evaluating routing rules...")
    
    # Check Router
    from costopt.router import CostOptRouter
    router_engine = CostOptRouter()
    target_model = router_engine.match_route(req.prompt, req.model)
    
    routed = False
    if target_model != req.model:
        logs.append(f"Routing rule match! Redirecting query to cheaper model: '{target_model}'")
        routed = True
    else:
        logs.append(f"No routing rules matched. Executing completion using requested model: '{req.model}'")
        
    # Simulated token count cost calculation
    cost_orig = calculate_cost("openai", req.model, 150, 60)
    cost_act = calculate_cost("openai", target_model, 150, 60)
    savings = cost_orig - cost_act
    
    return {
        "status": "success",
        "cache_hit": False,
        "routed": routed,
        "original_model": req.model,
        "final_model": target_model,
        "cost_original": round(cost_orig, 6),
        "cost_actual": round(cost_act, 6),
        "savings": round(savings, 6),
        "logs": logs
    }

@router.get("/features")
def get_feature_attribution():
    """Returns cost-per-feature / decision breakdown and actionable auto-optimization recommendations."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COALESCE(NULLIF(application, ''), 'default_feature') as feature,
                    COUNT(*) as call_count,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cost_actual) as total_cost,
                    SUM(savings) as total_savings,
                    SUM(cache_hit) as cache_hits,
                    AVG(latency_ms) as avg_latency_ms
                FROM telemetry
                GROUP BY feature
                ORDER BY total_cost DESC
            """)
            rows = cursor.fetchall()
            
            features = []
            recommendations = []
            
            for r in rows:
                f_name = r["feature"]
                calls = r["call_count"]
                total_cost = round(r["total_cost"] or 0.0, 4)
                avg_cost = round(total_cost / calls, 6) if calls > 0 else 0.0
                cache_hit_rate = round(((r["cache_hits"] or 0) / calls) * 100, 1) if calls > 0 else 0.0
                
                features.append({
                    "feature": f_name,
                    "call_count": calls,
                    "avg_cost_per_call": avg_cost,
                    "total_cost": total_cost,
                    "total_savings": round(r["total_savings"] or 0.0, 4),
                    "cache_hit_rate": cache_hit_rate,
                    "avg_latency_ms": int(r["avg_latency_ms"] or 0)
                })
                
                # Archaeological Auto-Recommendation Rules (Angle 3)
                if calls > 10 and cache_hit_rate < 15.0 and total_cost > 0.05:
                    recommendations.append({
                        "feature": f_name,
                        "type": "CACHE_OPTIMIZATION",
                        "severity": "HIGH",
                        "title": f"Low Cache Utilization in '{f_name}'",
                        "description": f"Feature '{f_name}' has a {cache_hit_rate}% cache hit rate across {calls} calls. Lowering the similarity threshold or extending TTL could increase cache hits.",
                        "estimated_monthly_savings": f"${round(total_cost * 0.40, 2)}"
                    })
                if total_cost > 0.10 and avg_cost > 0.002:
                    recommendations.append({
                        "feature": f_name,
                        "type": "MODEL_REROUTE",
                        "severity": "MEDIUM",
                        "title": f"Reroute Opportunity for '{f_name}'",
                        "description": f"Feature '{f_name}' averages ${avg_cost:.4f}/call. Adding a routing rule to direct short prompts (<500 chars) to a lighter model (e.g. gpt-4o-mini) can reduce cost by ~60%.",
                        "estimated_monthly_savings": f"${round(total_cost * 0.60, 2)}"
                    })

            return {
                "features": features,
                "recommendations": recommendations
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
def get_supported_models():
    """Returns a list of all model names loaded in the pricing system."""
    try:
        from costopt.pricing import get_all_loaded_models
        raw_data = get_all_loaded_models()
        models = []
        for provider, model_list in raw_data.items():
            for m in model_list:
                models.append({
                    "provider": provider,
                    "model": m,
                    "label": f"{m} ({provider})"
                })
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




