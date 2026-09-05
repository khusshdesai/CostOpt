import sys
import argparse
import logging
from costopt.generator import generate_telemetry_dataset, save_dataset
from costopt.api.server import start_server
from costopt.cache import SQLiteCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def cmd_generate_data(args):
    """Executes the data generator from CLI arguments."""
    print(f"Generating {args.records} synthetic telemetry events for lookback of {args.days} days...")
    events = generate_telemetry_dataset(args.records, args.days, args.seed)
    save_dataset(events, args.output, args.format)

def cmd_dashboard(args):
    """Starts the FastAPI web server."""
    start_server(host=args.host, port=args.port, telemetry_db=args.telemetry_db, cache_db=args.cache_db)

def cmd_clear_cache(args):
    """Clears the local SQLite cache."""
    cache = SQLiteCache(db_path=args.cache_db)
    cache.clear()
    print(f"Successfully cleared prompt cache DB: {args.cache_db}")

def cmd_clear_telemetry(args):
    """Clears all logs from the telemetry SQLite database."""
    import sqlite3
    db_path = getattr(args, "telemetry_db", "costopt_telemetry.db")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM telemetry;")
            conn.commit()
        print(f"Successfully cleared all telemetry logs from: {db_path}")
    except Exception as e:
        print(f"Failed to clear telemetry database: {e}")

def cmd_reset_all(args):
    """Clears both local telemetry database and cache database."""
    cmd_clear_telemetry(args)
    cmd_clear_cache(args)

def main():
    parser = argparse.ArgumentParser(
        description="LLM CostOpt — Open-Source Cost Optimization & Observability Platform",
        prog="costopt"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. generate-data
    parser_gen = subparsers.add_parser("generate-data", help="Generate deterministic synthetic telemetry data")
    parser_gen.add_argument("--records", type=int, default=1000, help="Number of records to generate")
    parser_gen.add_argument("--days", type=int, default=30, help="Number of historical days to simulate")
    parser_gen.add_argument("--seed", type=int, default=42, help="Seed value for deterministic random generation")
    parser_gen.add_argument("--output", type=str, default="costopt_telemetry.db", help="Target output database or file path. If database, inserts data.")
    parser_gen.add_argument("--format", type=str, choices=["json", "jsonl", "csv", "sqlite"], default="sqlite", help="Target output format (default: sqlite database)")

    # 2. dashboard
    parser_dash = subparsers.add_parser("dashboard", help="Start the local developer dashboard")
    parser_dash.add_argument("--host", type=str, default="127.0.0.1", help="Web host server address")
    parser_dash.add_argument("--port", type=int, default=8400, help="Web server target port")
    parser_dash.add_argument("--telemetry-db", type=str, default="costopt_telemetry.db", help="Path to telemetry SQLite database")
    parser_dash.add_argument("--cache-db", type=str, default="costopt_cache.db", help="Path to cache SQLite database")

    # 3. clear-cache
    parser_clear = subparsers.add_parser("clear-cache", help="Wipes the local prompt response cache")
    parser_clear.add_argument("--cache-db", type=str, default="costopt_cache.db", help="Path to cache SQLite database")

    # 4. clear-telemetry
    parser_cleartel = subparsers.add_parser("clear-telemetry", help="Wipes all telemetry request logs")
    parser_cleartel.add_argument("--telemetry-db", type=str, default="costopt_telemetry.db", help="Path to telemetry SQLite database")

    # 5. reset-all
    parser_reset = subparsers.add_parser("reset-all", help="Wipes both telemetry logs and prompt cache")
    parser_reset.add_argument("--telemetry-db", type=str, default="costopt_telemetry.db", help="Path to telemetry SQLite database")
    parser_reset.add_argument("--cache-db", type=str, default="costopt_cache.db", help="Path to cache SQLite database")

    args = parser.parse_args()

    if args.command == "generate-data":
        if args.format == "sqlite" or args.output.endswith(".db"):
            events = generate_telemetry_dataset(args.records, args.days, args.seed)
            from costopt.telemetry import SQLiteTelemetryLogger
            logger = SQLiteTelemetryLogger(db_path=args.output)
            logger.bulk_insert(events)
            logger.shutdown()
            print(f"Successfully generated and loaded {len(events)} telemetry rows directly into SQLite DB: {args.output}")
        else:
            cmd_generate_data(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "clear-cache":
        cmd_clear_cache(args)
    elif args.command == "clear-telemetry":
        cmd_clear_telemetry(args)
    elif args.command == "reset-all":
        cmd_reset_all(args)

if __name__ == "__main__":
    main()
