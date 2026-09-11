"""
CostOpt – Cache Latency Benchmark
==================================
Measures real p50 / p95 / p99 latency (in milliseconds) for:

  1. Cold MISS   – prompt not in cache (500-row DB)
  2. Exact HIT   – SHA-256 key matches, response returned immediately
  3. Fuzzy HIT   – near-duplicate matched via Jaccard + TF-IDF
                   (bounded to 50 most recent entries)

Uses a temporary SQLite database that is deleted after the run.
NEVER touches your real costopt_cache.db. Safe to run at any time.

Usage:
  python benchmarks/cache_latency_bench.py

  Optional flags:
    --iterations N   Number of timing samples per scenario (default: 300)
    --db-rows N      Number of rows pre-seeded in DB (default: 500)
    --threshold F    Fuzzy similarity threshold, 0.0-1.0 (default: 0.75)
"""

import argparse
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
import os

# ---------------------------------------------------------------------------
# Ensure the project source is importable when run from the repo root
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from costopt.cache import SQLiteCache  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(data: list, pct: float) -> float:
    """Return the pct-th percentile of a list of floats."""
    return statistics.quantiles(sorted(data), n=100)[int(pct) - 1]


def _print_header(iterations: int, db_rows: int, threshold: float) -> None:
    print("=" * 60)
    print("CostOpt - Cache Latency Benchmark")
    print("=" * 60)
    print(f"Python       : {sys.version.split()[0]}")
    print(f"SQLite       : {sqlite3.sqlite_version}")
    print(f"Platform     : {platform.platform()}")
    print(f"DB rows      : {db_rows} pre-seeded (realistic cache size)")
    print(f"Iterations   : {iterations} per scenario")
    print(f"Fuzzy thresh : {threshold}")
    print(f"Fuzzy window : 50 most recently inserted entries (ORDER BY rowid DESC LIMIT 50)")
    print("=" * 60)
    print()


def _preflight(label: str, fn, expect_hit: bool) -> None:
    """
    Run fn() once before timing and assert the result is correct.
    Aborts with a clear message if the scenario would silently measure
    the wrong thing (e.g. a miss timed as a hit).
    """
    result = fn()
    if expect_hit and result is None:
        print(f"  PREFLIGHT FAILED: '{label}'")
        print(f"  Expected a cache HIT but got None.")
        print(f"  Check that the seed prompt was written before timing,")
        print(f"  and that the similarity threshold is not too strict.")
        sys.exit(1)
    if not expect_hit and result is not None:
        print(f"  PREFLIGHT FAILED: '{label}'")
        print(f"  Expected a cache MISS (None) but got a result.")
        print(f"  The cold-miss prompt may accidentally match a seeded entry.")
        sys.exit(1)


def _run_scenario(label: str, fn, iterations: int) -> list:
    """Run fn() N times and return ms timings. No warm-up — cold measurement."""
    timings_ms = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        timings_ms.append((t1 - t0) * 1000.0)

    p50 = _percentile(timings_ms, 50)
    p95 = _percentile(timings_ms, 95)
    p99 = _percentile(timings_ms, 99)

    print(f"  {label}")
    print(f"    p50 : {p50:.3f} ms")
    print(f"    p95 : {p95:.3f} ms")
    print(f"    p99 : {p99:.3f} ms")
    print(f"    mean: {statistics.mean(timings_ms):.3f} ms")
    print()

    return timings_ms


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="CostOpt cache latency benchmark")
    parser.add_argument("--iterations", type=int, default=300,
                        help="Timing samples per scenario (default: 300)")
    parser.add_argument("--db-rows", type=int, default=500,
                        help="Rows pre-seeded in test DB (default: 500)")
    parser.add_argument("--threshold", type=float, default=0.70,
                        help="Fuzzy similarity threshold (default: 0.70)")
    args = parser.parse_args()

    _print_header(args.iterations, args.db_rows, args.threshold)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        cache = SQLiteCache(db_path=tmp_path, similarity_threshold=args.threshold)

        MODEL = "gpt-4o"

        # Derive exact-hit prompt from db_rows so it is always in the seeded range.
        # Using db_rows // 2 guarantees the target index exists regardless of --db-rows.
        exact_target_idx = args.db_rows // 2
        STORED_PROMPT = f"Tell me about topic number {exact_target_idx} in detail and explain the concept thoroughly"

        # Near-duplicate pair — verified similarity: Jaccard=0.81, TF-IDF=0.93
        # Both exceed the default 0.70 threshold with comfortable headroom.
        FUZZY_SEED = (
            "Explain transformer attention mechanisms and how they differ "
            "from recurrent neural networks in NLP."
        )
        FUZZY_QUERY = (
            "Explain transformer attention mechanisms and how they are different "
            "from recurrent neural networks in NLP."
        )

        # A completely unseen prompt — guaranteed cold miss
        COLD_PROMPT = "What is the GDP of Singapore in 2024 adjusted for purchasing power parity?"

        FAKE_RESPONSE = {
            "id": "chatcmpl-bench",
            "object": "chat.completion",
            "model": MODEL,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Benchmark placeholder response.",
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "usage": {"prompt_tokens": 42, "completion_tokens": 80, "total_tokens": 122},
        }

        # ------------------------------------------------------------------
        # Seed the database
        # ------------------------------------------------------------------
        print(f"Seeding {args.db_rows} rows into temporary database...")
        for i in range(args.db_rows):
            cache.set(
                f"Tell me about topic number {i} in detail and explain the concept thoroughly",
                MODEL,
                FAKE_RESPONSE,
                ttl_seconds=3600,
            )

        # Seed the fuzzy target in the most recent window (after bulk seeding)
        cache.set(FUZZY_SEED, MODEL, FAKE_RESPONSE, ttl_seconds=3600)
        print("Done.\n")

        print("Preflight checks (validating each scenario before timing)...")
        _preflight("Cold MISS",  lambda: cache.get(COLD_PROMPT,   MODEL), expect_hit=False)
        _preflight("Exact HIT",  lambda: cache.get(STORED_PROMPT, MODEL), expect_hit=True)
        if args.threshold < 1.0:
            _preflight("Fuzzy HIT", lambda: cache.get(FUZZY_QUERY, MODEL), expect_hit=True)
        print("All preflight checks passed.")
        print()

        print("Results")
        print("-" * 60)

        # 1. Cold MISS
        _run_scenario(
            label=f"1. Cold MISS  ({args.db_rows}-row DB, prompt never cached)",
            fn=lambda: cache.get(COLD_PROMPT, MODEL),
            iterations=args.iterations,
        )

        # 2. Exact HIT
        _run_scenario(
            label=f"2. Exact HIT  (SHA-256 hash match, index={exact_target_idx}/{args.db_rows})",
            fn=lambda: cache.get(STORED_PROMPT, MODEL),
            iterations=args.iterations,
        )

        # 3. Fuzzy HIT
        if args.threshold < 1.0:
            _run_scenario(
                label=f"3. Fuzzy HIT  (Jaccard+TF-IDF, LIMIT 50 window, threshold={args.threshold})",
                fn=lambda: cache.get(FUZZY_QUERY, MODEL),
                iterations=args.iterations,
            )
        else:
            print("  3. Fuzzy HIT  - skipped (--threshold=1.0 means exact-only mode)")
            print()

        print("-" * 60)
        print("Note: Exact HIT uses a direct SHA-256 hash lookup — O(1) at any DB size.")
        print("      Fuzzy HIT scans the 50 most recent entries — latency is bounded")
        print("      regardless of total rows in the database.")
        print("      Cold MISS scans LIMIT 50 recent entries and returns nothing.")
        print()
        print("Results reflect SQLite I/O on this specific machine and will vary")
        print("with disk type (SSD vs HDD), OS page cache state, and system load.")
        print()

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
