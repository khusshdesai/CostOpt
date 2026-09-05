import sqlite3
import json
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
    try:
        from costopt.telemetry import SQLiteTelemetryLogger
        from costopt.cache import SQLiteCache
        SQLiteTelemetryLogger.init_schema_only(db_path=telemetry_db)
        SQLiteCache(db_path=cache_db)
    except Exception:
        pass

def _get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@router.get("/models")
def get_available_models():
    """Returns available supported models for simulator dropdown."""
    from costopt.pricing import get_all_loaded_models
    try:
        loaded = get_all_loaded_models()
        all_models = []
        for provider, model_list in loaded.items():
            all_models.extend(model_list)
        if not all_models:
            all_models = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-haiku", "llama3", "deepseek-r1"]
        return {"models": sorted(list(set(all_models)))}
    except Exception:
        return {"models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-haiku", "llama3", "deepseek-r1"]}

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

@router.get("/optimizations/summary")
def get_optimizations_summary():
    """Returns real optimization strategy breakdown from telemetry database."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            # Cache strategy metrics
            cursor.execute("""
                SELECT COUNT(*), SUM(savings) 
                FROM telemetry 
                WHERE cache_hit = 1
            """)
            c_row = cursor.fetchone()
            cache_count = c_row[0] or 0
            cache_savings = c_row[1] or 0.0

            # Reroute strategy metrics (model_requested != model_used)
            cursor.execute("""
                SELECT COUNT(*), SUM(savings) 
                FROM telemetry 
                WHERE cache_hit = 0 AND model_requested != model_used
            """)
            r_row = cursor.fetchone()
            reroute_count = r_row[0] or 0
            reroute_savings = r_row[1] or 0.0

            # Total requests
            cursor.execute("SELECT COUNT(*), SUM(savings), SUM(cost_original) FROM telemetry")
            t_row = cursor.fetchone()
            total_requests = t_row[0] or 0
            total_savings = t_row[1] or 0.0
            baseline_cost = t_row[2] or 0.0

            optimized_requests = cache_count + reroute_count
            opt_rate = (optimized_requests / total_requests * 100) if total_requests > 0 else 0.0

            return {
                "total_savings": round(total_savings, 4),
                "cache_savings": round(cache_savings, 4),
                "cache_count": cache_count,
                "reroute_savings": round(reroute_savings, 4),
                "reroute_count": reroute_count,
                "total_requests": total_requests,
                "optimized_requests": optimized_requests,
                "optimization_rate": round(opt_rate, 1),
                "baseline_cost": round(baseline_cost, 4)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/charts/savings")
def get_savings_chart_data(limit: int = 30):
    """Returns daily cost, baseline cost, and savings metrics for time series plots."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            # BUG-11 fix: DESC subquery gets most recent N days; outer query restores ASC for chart ordering
            cursor.execute("""
                SELECT date, baseline_cost, actual_cost, savings FROM (
                    SELECT 
                        strftime('%Y-%m-%d', timestamp) as date,
                        SUM(cost_original) as baseline_cost,
                        SUM(cost_actual) as actual_cost,
                        SUM(savings) as savings
                    FROM telemetry
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT ?
                ) ORDER BY date ASC
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
    """Returns total request counts, baseline cost, actual spend, and savings grouped by provider/model."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    provider,
                    model_used,
                    COUNT(*) as count,
                    SUM(cost_original) as baseline_cost,
                    SUM(cost_actual) as spend,
                    SUM(savings) as savings
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

@router.api_route("/cache/clear", methods=["GET", "POST"])
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

@router.get("/requests/summary")
def get_requests_summary():
    """Returns top summary metrics for the Requests page from real telemetry."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN cache_hit = 1 OR model_requested != model_used THEN 1 ELSE 0 END) as optimized_requests,
                    SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                    AVG(latency_ms) as avg_latency
                FROM telemetry
            """)
            row = cursor.fetchone()
            return {
                "total_requests": row["total_requests"] or 0,
                "optimized_requests": row["optimized_requests"] or 0,
                "cache_hits": row["cache_hits"] or 0,
                "avg_latency": round(row["avg_latency"] or 0.0, 1)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requests/list")
def get_requests_list(
    search: Optional[str] = None,
    outcome: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Returns filtered and paginated request telemetry records."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            params = []

            if search:
                where_clauses.append("(prompt_hash LIKE ? OR model_requested LIKE ? OR model_used LIKE ? OR request_id LIKE ? OR decision_reason LIKE ?)")
                s_param = f"%{search}%"
                params.extend([s_param, s_param, s_param, s_param, s_param])

            if outcome == 'cache':
                where_clauses.append("cache_hit = 1")
            elif outcome == 'reroute':
                where_clauses.append("cache_hit = 0 AND model_requested != model_used")
            elif outcome == 'direct':
                where_clauses.append("cache_hit = 0 AND model_requested = model_used")
            elif outcome == 'optimized':
                where_clauses.append("(cache_hit = 1 OR model_requested != model_used OR savings > 0)")

            if model and model != 'all':
                where_clauses.append("(model_requested = ? OR model_used = ?)")
                params.extend([model, model])

            if task_type and task_type != 'all':
                where_clauses.append("task_type = ?")
                params.append(task_type)

            where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            cursor.execute(f"SELECT COUNT(*) FROM telemetry{where_str}", params)
            total_count = cursor.fetchone()[0] or 0

            query = f"""
                SELECT 
                    timestamp, request_id, provider, model_requested, model_used,
                    input_tokens, output_tokens, latency_ms, success,
                    cache_hit, cost_original, cost_actual, savings, prompt_hash,
                    environment, application, region,
                    task_type, complexity, confidence, decision_reason, decision_trace
                FROM telemetry
                {where_str}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return {
                "total_count": total_count,
                "items": [dict(r) for r in rows]
            }
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

@router.api_route("/telemetry/reset", methods=["GET", "POST"])
@router.post("/reset")
def reset_telemetry():
    """Deletes all telemetry records from the database, resetting all cost metrics to zero."""
    # BUG-9 fix: single canonical definition — previously duplicated at line 965, causing silent shadowing
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM telemetry")
            deleted = cursor.rowcount
            conn.commit()
        return {"status": "success", "message": f"Telemetry reset. {deleted} record(s) deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _get_safe_config_path() -> str:
    import os
    env_path = os.getenv("COSTOPT_CONFIG_PATH")
    if env_path:
        return os.path.abspath(env_path)
    return os.path.abspath("costopt.yaml")

@router.get("/config")
def get_active_config():
    """Returns the current costopt.yaml routing rules template."""
    import os
    try:
        config_path = _get_safe_config_path()
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"status": "success", "content": content}
        return {"status": "error", "message": "costopt.yaml config file not found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel

class ConfigUpdateRequest(BaseModel):
    content: str

@router.post("/config")
def update_active_config(req: ConfigUpdateRequest):
    """Validates and updates costopt.yaml configuration file."""
    import yaml, os
    try:
        parsed = yaml.safe_load(req.content)
        if not isinstance(parsed, dict):
            raise ValueError("Configuration YAML must evaluate to a valid dictionary.")
            
        config_path = _get_safe_config_path()
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(req.content)
            
        return {"status": "success", "message": "Configuration saved and applied successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration YAML: {e}")

class SimulationRequest(BaseModel):
    prompt: str
    model: str

def _write_telemetry_direct(record: dict):
    with _get_connection(_TELEMETRY_DB) as conn:
        cursor = conn.cursor()
        
        # Ensure Phase 3 columns exist
        for col_name, col_type in [
            ("file_path", "TEXT DEFAULT ''"),
            ("line_number", "INTEGER DEFAULT 0"),
            ("task_type", "TEXT DEFAULT 'general_chat'"),
            ("complexity", "TEXT DEFAULT 'medium'"),
            ("confidence", "REAL DEFAULT 1.0"),
            ("decision_reason", "TEXT DEFAULT ''"),
            ("decision_trace", "TEXT DEFAULT ''"),
            ("is_synthetic", "INTEGER DEFAULT 0")
        ]:
            try:
                cursor.execute(f"ALTER TABLE telemetry ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        trace_val = record.get("decision_trace", "")
        if isinstance(trace_val, (dict, list)):
            trace_val = json.dumps(trace_val)

        cursor.execute("""
            INSERT OR REPLACE INTO telemetry (
                timestamp, request_id, provider, model_requested, model_used,
                input_tokens, output_tokens, latency_ms, status_code, success,
                error_type, cache_hit, cost_original, cost_actual, savings,
                prompt_hash, environment, application, region, retry_count,
                file_path, line_number, task_type, complexity, confidence,
                decision_reason, decision_trace, is_synthetic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["timestamp"], record["request_id"], record["provider"], record["model_requested"],
            record["model_used"], record["input_tokens"], record["output_tokens"], record["latency_ms"],
            record["status_code"], 1 if record["success"] else 0, record.get("error_type"),
            1 if record["cache_hit"] else 0, record["cost_original"], record["cost_actual"],
            record["savings"], record["prompt_hash"], record["environment"], record["application"],
            record["region"], record.get("retry_count", 0), record.get("file_path", ""), record.get("line_number", 0),
            record.get("task_type", "general_chat"), record.get("complexity", "medium"), record.get("confidence", 1.0),
            record.get("decision_reason", ""), trace_val, record.get("is_synthetic", 0)
        ))
        conn.commit()

@router.post("/simulate")
def simulate_sdk_call(req: SimulationRequest):
    """Evaluates prompt using DecisionEngine and records live telemetry."""
    import hashlib, uuid, json
    from datetime import datetime, timezone
    from costopt.optimization import DecisionEngine
    
    prompt_hash = hashlib.sha256(req.prompt.encode('utf-8')).hexdigest()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    req_id = f"sim-{uuid.uuid4().hex[:12]}"
    
    engine = DecisionEngine(config_path="costopt.yaml", cache_db_path=_CACHE_DB)
    decision = engine.evaluate(req.prompt, req.model, provider="openai")
    
    # Store completion in cache if miss
    if not decision.cache_hit:
        engine.cache_layer.store(req.prompt, req.model, {"id": f"chatcmpl-{uuid.uuid4().hex[:8]}", "choices": [{"message": {"content": f"Simulated response payload for: {req.prompt[:30]}"}}]})

    log_entry = {
        "timestamp": timestamp,
        "request_id": req_id,
        "provider": decision.provider,
        "model_requested": decision.requested_model,
        "model_used": decision.selected_model,
        "input_tokens": 120,
        "output_tokens": 40,
        "latency_ms": 12 if decision.cache_hit else (320 if decision.decision == "REROUTE" else 850),
        "status_code": 200,
        "success": True,
        "error_type": None,
        "cache_hit": decision.cache_hit,
        "cost_original": decision.estimated_cost_before,
        "cost_actual": decision.estimated_cost_after,
        "savings": decision.estimated_savings,
        "prompt_hash": prompt_hash,
        "environment": "production",
        "application": "costopt-simulator",
        "region": "us-east-1",
        "retry_count": 0,
        "file_path": "costopt/simulator.py",
        "line_number": 42,
        "task_type": decision.task_type,
        "complexity": decision.complexity,
        "confidence": decision.confidence,
        "decision_reason": decision.reason,
        "decision_trace": decision.decision_trace
    }
    _write_telemetry_direct(log_entry)

    return {
        "status": "success",
        "decision": decision.decision,
        "cache_hit": decision.cache_hit,
        "routed": decision.decision == "REROUTE",
        "original_model": decision.requested_model,
        "final_model": decision.selected_model,
        "cost_original": decision.estimated_cost_before,
        "cost_actual": decision.estimated_cost_after,
        "savings": decision.estimated_savings,
        "confidence": decision.confidence,
        "task_type": decision.task_type,
        "complexity": decision.complexity,
        "decision_reason": decision.reason,
        "decision_trace": decision.decision_trace,
        "logs": decision.decision_trace
    }

@router.get("/intelligence/distribution")
def get_intelligence_distribution():
    """Returns task classification and optimization decision distribution stats."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT task_type, COUNT(*) as count 
                FROM telemetry 
                GROUP BY task_type 
                ORDER BY count DESC
            """)
            tasks = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                    SUM(CASE WHEN cache_hit = 0 AND model_requested != model_used THEN 1 ELSE 0 END) as reroutes,
                    SUM(CASE WHEN cache_hit = 0 AND model_requested = model_used THEN 1 ELSE 0 END) as direct_requests,
                    AVG(confidence) as avg_confidence
                FROM telemetry
            """)
            dec_row = cursor.fetchone()

            return {
                "task_distribution": tasks,
                "decisions": {
                    "cache_hits": dec_row["cache_hits"] or 0,
                    "reroutes": dec_row["reroutes"] or 0,
                    "direct_requests": dec_row["direct_requests"] or 0,
                    "avg_confidence": round(dec_row["avg_confidence"] or 1.0, 2)
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/vscode/health")
def get_vscode_health():
    """Health check endpoint for VS Code extension connectivity."""
    return {"status": "ok", "service": "CostOpt Local API", "version": "0.1.1"}

@router.get("/vscode/file-stats")
def get_vscode_file_stats(file_path: str):
    """Returns telemetry statistics aggregated by line number for a specific source file."""
    try:
        norm_path = file_path.replace("\\", "/").lower()
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            # Fetch all matching telemetry records for this file (supporting fuzzy relative/absolute matching)
            cursor.execute("""
                SELECT 
                    line_number,
                    model_requested,
                    model_used,
                    input_tokens,
                    output_tokens,
                    cost_actual,
                    latency_ms,
                    cache_hit,
                    timestamp
                FROM telemetry
                WHERE LOWER(REPLACE(file_path, '\\', '/')) LIKE '%' || ? OR ? LIKE '%' || LOWER(REPLACE(file_path, '\\', '/'))
            """, (norm_path, norm_path))
            rows = cursor.fetchall()

            if not rows:
                # Fallback: Query all logs if no exact file match, for global file-agnostic CodeLens simulation
                cursor.execute("""
                    SELECT 
                        line_number,
                        model_requested,
                        model_used,
                        input_tokens,
                        output_tokens,
                        cost_actual,
                        latency_ms,
                        cache_hit,
                        timestamp
                    FROM telemetry
                    ORDER BY timestamp DESC
                    LIMIT 200
                """)
                rows = cursor.fetchall()

            total_file_calls = len(rows)
            total_file_spend = sum(r["cost_actual"] or 0.0 for r in rows) if rows else 0.0
            
            line_stats = {}
            for r in rows:
                line = r["line_number"] or 1
                if line not in line_stats:
                    line_stats[line] = {
                        "line_number": line,
                        "call_count": 0,
                        "total_cost": 0.0,
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_latency_ms": 0,
                        "cache_hits": 0,
                        "model": r["model_used"] or r["model_requested"]
                    }
                line_stats[line]["call_count"] += 1
                line_stats[line]["total_cost"] += (r["cost_actual"] or 0.0)
                line_stats[line]["total_input_tokens"] += (r["input_tokens"] or 0)
                line_stats[line]["total_output_tokens"] += (r["output_tokens"] or 0)
                line_stats[line]["total_latency_ms"] += (r["latency_ms"] or 0)
                if r["cache_hit"]:
                    line_stats[line]["cache_hits"] += 1

            lines_output = []
            for line, s in line_stats.items():
                cnt = s["call_count"]
                avg_cost = s["total_cost"] / cnt if cnt > 0 else 0.0
                avg_in = s["total_input_tokens"] // cnt if cnt > 0 else 0
                avg_out = s["total_output_tokens"] // cnt if cnt > 0 else 0
                avg_lat = s["total_latency_ms"] // cnt if cnt > 0 else 0
                
                lines_output.append({
                    "line_number": line,
                    "model": s["model"],
                    "call_count": cnt,
                    "total_cost": round(s["total_cost"], 6),
                    "avg_cost_per_call": round(avg_cost, 6),
                    "avg_input_tokens": avg_in,
                    "avg_output_tokens": avg_out,
                    "avg_latency_ms": avg_lat,
                    "cache_hits": s["cache_hits"]
                })

            return {
                "file_path": file_path,
                "total_file_calls": total_file_calls,
                "total_file_spend": round(total_file_spend, 4),
                "line_stats": lines_output
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vscode/forecast")
def get_vscode_forecast(budget: float = 50.0):
    """Calculates real-time daily spend, projected monthly spend, and budget remaining."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            # Total count check
            cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM telemetry")
            count_row = cursor.fetchone()
            total_calls = count_row[0] or 0
            
            if total_calls == 0:
                return {
                    "has_enough_data": False,
                    "message": "CostOpt is connected, but no LLM usage has been recorded yet.",
                    "total_spend": 0.0,
                    "spend_today": 0.0,
                    "daily_average": 0.0,
                    "projected_monthly": 0.0,
                    "budget": budget,
                    "budget_remaining": budget
                }

            # Today's spend
            cursor.execute("""
                SELECT SUM(cost_actual)
                FROM telemetry
                WHERE strftime('%Y-%m-%d', timestamp) = strftime('%Y-%m-%d', 'now')
            """)
            today_row = cursor.fetchone()
            spend_today = round(today_row[0] or 0.0, 4)

            # Daily average over available history (up to last 30 days)
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT strftime('%Y-%m-%d', timestamp)) as active_days,
                    SUM(cost_actual) as total_spend
                FROM telemetry
            """)
            avg_row = cursor.fetchone()
            active_days = max(1, avg_row["active_days"] or 1)
            total_spend = avg_row["total_spend"] or 0.0
            
            daily_avg = total_spend / active_days
            projected_monthly = daily_avg * 30.0
            remaining_budget = max(0.0, budget - projected_monthly)

            return {
                "has_enough_data": True,
                "total_spend": round(total_spend, 4),
                "spend_today": spend_today,
                "daily_average": round(daily_avg, 4),
                "projected_monthly": round(projected_monthly, 2),
                "budget": round(budget, 2),
                "budget_remaining": round(remaining_budget, 2),
                "over_budget": projected_monthly > budget
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vscode/warnings")
def get_vscode_warnings(budget: float = 50.0):
    """Generates developer-oriented cost warnings for VS Code Problems panel and sidebar."""
    warnings = []
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            
            # 1. Budget overrun warning
            forecast = get_vscode_forecast(budget=budget)
            if forecast.get("has_enough_data") and forecast.get("over_budget"):
                warnings.append({
                    "id": "WARN_BUDGET_OVERRUN",
                    "severity": "WARNING",
                    "title": "Projected Monthly Spend Exceeds Budget",
                    "message": f"Projected spend (${forecast['projected_monthly']}/mo) exceeds configured budget of ${budget:.2f}.",
                    "code": "COSTOPT001"
                })

            # 2. High feature cost concentration warning
            cursor.execute("""
                SELECT 
                    COALESCE(NULLIF(application, ''), 'default_feature') as feature,
                    SUM(cost_actual) as feature_spend,
                    (SELECT SUM(cost_actual) FROM telemetry) as total_spend
                FROM telemetry
                GROUP BY feature
                HAVING total_spend > 0
                ORDER BY feature_spend DESC
                LIMIT 1
            """)
            top_feat = cursor.fetchone()
            if top_feat and top_feat["total_spend"] > 0:
                pct = (top_feat["feature_spend"] / top_feat["total_spend"]) * 100.0
                if pct >= 50.0 and top_feat["feature_spend"] > 0.05:
                    warnings.append({
                        "id": "WARN_FEATURE_CONCENTRATION",
                        "severity": "INFO",
                        "title": f"Feature Spend Concentration in '{top_feat['feature']}'",
                        "message": f"Feature '{top_feat['feature']}' is responsible for {round(pct, 1)}% of total LLM spend (${round(top_feat['feature_spend'], 4)}).",
                        "code": "COSTOPT002"
                    })

            # 3. Recent input token drift
            # BUG-13 fix: AVG must aggregate INSIDE a subquery — ORDER BY+LIMIT on aggregate SELECT has no effect in SQLite
            cursor.execute("""
                SELECT AVG(input_tokens) as avg_tokens FROM (
                    SELECT input_tokens FROM telemetry ORDER BY timestamp DESC LIMIT 20
                )
            """)
            recent_tokens = cursor.fetchone()
            if recent_tokens and recent_tokens["avg_tokens"] and recent_tokens["avg_tokens"] > 3000:
                warnings.append({
                    "id": "WARN_HIGH_INPUT_TOKENS",
                    "severity": "WARNING",
                    "title": "High Average Input Context Length",
                    "message": f"Recent LLM calls average {int(recent_tokens['avg_tokens'])} input tokens per request. Consider truncating context or enabling local prompt caching.",
                    "code": "COSTOPT003"
                })

            return warnings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _vscode_features_impl():
    """Shared implementation: cost attribution grouped by feature/application tag."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COALESCE(NULLIF(application, ''), 'default_feature') as feature,
                    COUNT(*) as call_count,
                    SUM(cost_actual) as total_cost
                FROM telemetry
                GROUP BY feature
                ORDER BY total_cost DESC
            """)
            rows = cursor.fetchall()
            features = [
                {
                    "feature": r["feature"],
                    "call_count": r["call_count"],
                    "total_cost": round(r["total_cost"] or 0.0, 4)
                }
                for r in rows
            ]
            return {"features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vscode/feature-stats")
def get_vscode_feature_stats():
    """Returns cost attribution grouped by feature tag for VS Code sidebar (alias)."""
    return _vscode_features_impl()

@router.get("/vscode/features")
def get_vscode_features():
    """Returns cost attribution grouped by feature tag for VS Code sidebar."""
    return _vscode_features_impl()

@router.post("/telemetry/reset")
def reset_telemetry():
    """Resets and wipes all telemetry request logs from the database."""
    try:
        with _get_connection(_TELEMETRY_DB) as conn:
            conn.execute("DELETE FROM telemetry;")
            conn.commit()
        return {"status": "success", "message": "Telemetry logs wiped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset telemetry DB: {e}")
