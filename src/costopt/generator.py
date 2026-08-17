import os
import json
import csv
import random
import uuid
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# Target model choices
PROVIDERS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"],
    "google": ["gemini-1.5-pro", "gemini-1.5-flash"]
}

APPLICATIONS = ["chat-assistant", "document-parser", "translation-service", "code-generator"]
ENVIRONMENTS = ["production", "staging", "dev"]
REGIONS = ["us-east-1", "us-west-2", "eu-central-1", "ap-northeast-1"]

# Mock pricing rules for calculation inside generator (should match YAML rates closely)
MOCK_PRICING = {
    "openai": {
        "gpt-4o": {"in": 5.00, "out": 15.00, "cached": 2.50},
        "gpt-4o-mini": {"in": 0.15, "out": 0.60, "cached": 0.075},
        "gpt-4": {"in": 30.00, "out": 60.00, "cached": 30.00},
        "gpt-3.5-turbo": {"in": 0.50, "out": 1.50, "cached": 0.50}
    },
    "anthropic": {
        "claude-3-5-sonnet": {"in": 3.00, "out": 15.00, "cached": 0.30},
        "claude-3-opus": {"in": 15.00, "out": 75.00, "cached": 1.50},
        "claude-3-haiku": {"in": 0.25, "out": 1.25, "cached": 0.03}
    },
    "google": {
        "gemini-1.5-pro": {"in": 1.25, "out": 5.00, "cached": 0.3125},
        "gemini-1.5-flash": {"in": 0.075, "out": 0.30, "cached": 0.01875}
    }
}

# Standard queries that get run repeatedly (caching simulation)
DUPLICATE_PROMPTS = [
    ("What is the capital of France?", "8a8f1146"),
    ("Translate 'Hello' to Spanish.", "c1b590e8"),
    ("Write a python function to add two numbers.", "f2b3e810"),
    ("Summarize the following text: OpenAI is an AI research laboratory...", "7b9d10e3"),
    ("Check if this feedback is positive: I loved the product!", "a6e91f0a")
]

def generate_telemetry_dataset(
    records_count: int,
    days: int,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Generates realistic synthetic telemetry events representing normal, spike, and anomalous behaviors."""
    random.seed(seed)
    
    events = []
    base_time = datetime.now(timezone.utc) - timedelta(days=days)

    # We distribute times evenly or with standard hourly distributions (higher during working hours)
    for i in range(records_count):
        # Calculate timestamp with random distribution
        progress = i / records_count
        time_offset_seconds = random.randint(0, int(days * 24 * 3600))
        timestamp = base_time + timedelta(seconds=time_offset_seconds)
        
        # Decide if this event is part of an anomaly day (higher load / rate-limits / expensive models)
        is_anomaly_period = (timestamp.day % 10 == 0) # Every 10th of the month has anomaly patterns
        
        # Choose provider & model
        if is_anomaly_period and random.random() < 0.7:
            # Overuse of expensive models during anomaly period
            provider = "openai"
            model = "gpt-4"
        else:
            provider = random.choice(list(PROVIDERS.keys()))
            # Bias toward cost-effective models except for anomaly periods
            model_weights = [0.1, 0.6, 0.05, 0.25] if provider == "openai" else [0.5, 0.1, 0.4]
            if provider == "google":
                model_weights = [0.2, 0.8]
            model = random.choices(PROVIDERS[provider], weights=model_weights)[0]

        application = random.choices(APPLICATIONS, weights=[0.5, 0.2, 0.1, 0.2])[0]
        environment = random.choices(ENVIRONMENTS, weights=[0.7, 0.2, 0.1])[0]
        region = random.choice(REGIONS)

        # Simulate cache hits
        is_duplicate = random.random() < 0.25
        cache_hit = False
        prompt_hash = str(uuid.uuid4())[:8]

        if is_duplicate:
            # Pick a pre-set duplicate prompt
            prompt_text, prompt_hash = random.choice(DUPLICATE_PROMPTS)
            # 70% cache hit rate for duplicates
            if random.random() < 0.7:
                cache_hit = True

        # Input & Output tokens configuration
        if model in ["gpt-4", "claude-3-opus", "gemini-1.5-pro"]:
            # Complex reasoning: more tokens
            input_tokens = random.randint(500, 8000)
            output_tokens = random.randint(200, 3000)
        else:
            # Cheaper models: lighter prompts
            input_tokens = random.randint(50, 1500)
            output_tokens = random.randint(50, 800)

        # Latency calculations
        base_latency = 800 if model in ["gpt-4o-mini", "claude-3-haiku", "gemini-1.5-flash"] else 2500
        # If cache hit, latency is near 0 (e.g. 10-50ms local SDK hit)
        if cache_hit:
            latency_ms = random.randint(10, 45)
        else:
            latency_ms = int(base_latency * random.uniform(0.7, 1.5))
            if is_anomaly_period:
                latency_ms = int(latency_ms * random.uniform(1.5, 3.0)) # Latency spike simulation

        # Success & Status code
        success = True
        status_code = 200
        error_type = None
        retry_count = 0

        # Failures simulation
        failure_prob = 0.02
        if is_anomaly_period:
            failure_prob = 0.12 # Spikes in error rates

        if random.random() < failure_prob and not cache_hit:
            success = False
            status_code = random.choice([429, 500, 503])
            error_type = "rate_limit" if status_code == 429 else "server_error"
            # Simulate automatic retries
            retry_count = random.randint(1, 3)
            # A retry storm adds cost if they didn't succeed, or cost + latency if successful
            latency_ms += retry_count * random.randint(500, 1500)

        # Calculate estimated cost
        original_model = model
        cost_info = MOCK_PRICING[provider][model]
        
        # Original cost (cost of running the requested model)
        input_rate = cost_info["cached"] if cache_hit else cost_info["in"]
        output_rate = cost_info["out"]
        
        cost_actual = ((input_tokens / 1000000.0) * input_rate) + ((output_tokens / 1000000.0) * output_rate)
        if not success:
            # Failed requests might still consume input tokens depending on provider,
            # or charge zero. Let's charge input tokens if it failed halfway, or zero.
            cost_actual = cost_actual * 0.3
            
        cost_actual = round(cost_actual, 6)

        # What-if calculations: Let's assume we wanted to route to mini if simple
        cost_original = cost_actual
        # Let's say if we didn't optimize, we wouldn't have caching or routing
        # So we simulate the baseline cost (no cache hit, expensive model)
        baseline_rate = cost_info["in"]
        baseline_cost = ((input_tokens / 1000000.0) * baseline_rate) + ((output_tokens / 1000000.0) * cost_info["out"])
        cost_original = round(baseline_cost, 6)

        savings = max(0.0, round(cost_original - cost_actual, 6))

        events.append({
            "timestamp": timestamp.isoformat() + "Z",
            "request_id": str(uuid.uuid4()),
            "provider": provider,
            "model_requested": original_model,
            "model_used": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "success": success,
            "error_type": error_type,
            "cache_hit": cache_hit,
            "cost_original": cost_original,
            "cost_actual": cost_actual,
            "savings": savings,
            "prompt_hash": prompt_hash,
            "environment": environment,
            "application": application,
            "region": region,
            "retry_count": retry_count
        })

    # Sort events by timestamp
    events.sort(key=lambda x: x["timestamp"])
    return events

def save_dataset(events: List[Dict[str, Any]], output_path: str, format_type: str) -> None:
    """Saves telemetry dataset to disk in CSV, JSON, or JSONL format."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    if format_type == "jsonl":
        with open(output_path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
    elif format_type == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    elif format_type == "csv":
        if not events:
            return
        keys = events[0].keys()
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(events)
    print(f"Successfully generated {len(events)} telemetry events and saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Deterministic LLM Telemetry Dataset Generator")
    parser.add_argument("--records", type=int, default=1000, help="Number of records to generate")
    parser.add_argument("--days", type=int, default=30, help="Number of historical days")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default="data/synthetic_telemetry.jsonl", help="Output file path")
    parser.add_argument("--format", type=str, choices=["json", "jsonl", "csv"], default="jsonl", help="Output format")

    args = parser.parse_args()
    events = generate_telemetry_dataset(args.records, args.days, args.seed)
    save_dataset(events, args.output, args.format)

if __name__ == "__main__":
    main()
