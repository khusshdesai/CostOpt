import os
import sqlite3
import queue
import threading
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from costopt.alerts import SlackAlertManager, AlertConfig

logger = logging.getLogger("costopt.telemetry")

class SQLiteTelemetryLogger:
    def __init__(self, db_path: str = "costopt_telemetry.db", alert_config: Optional[AlertConfig] = None):
        self.db_path = db_path
        self.alert_manager = SlackAlertManager(alert_config) if alert_config else None
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._is_initialized = False

        try:
            self._init_db()
            self._is_initialized = True
        except Exception as e:
            logger.error(f"Telemetry DB initialization failed: {e}.")
            raise e

        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _init_db(self):
        """Creates the telemetry SQLite database schema if not present."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA busy_timeout=5000;")
                cursor.execute("PRAGMA journal_mode=WAL;")
                mode_row = cursor.fetchone()
                mode = mode_row[0] if mode_row else "unknown"
                logger.debug(f"SQLite Telemetry DB initialized. Journal mode: {mode}")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry (
                        timestamp TEXT NOT NULL,
                        request_id TEXT PRIMARY KEY,
                        provider TEXT NOT NULL,
                        model_requested TEXT NOT NULL,
                        model_used TEXT NOT NULL,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        latency_ms INTEGER NOT NULL,
                        status_code INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_type TEXT,
                        cache_hit BOOLEAN NOT NULL,
                        cost_original REAL NOT NULL,
                        cost_actual REAL NOT NULL,
                        savings REAL NOT NULL,
                        prompt_hash TEXT NOT NULL,
                        environment TEXT NOT NULL,
                        application TEXT NOT NULL,
                        region TEXT NOT NULL,
                        retry_count INTEGER NOT NULL,
                        file_path TEXT DEFAULT '',
                        line_number INTEGER DEFAULT 0
                    )
                """)
                # Safe migrations for existing DBs
                for col_name, col_type in [
                    ("file_path", "TEXT DEFAULT ''"),
                    ("line_number", "INTEGER DEFAULT 0"),
                    ("task_type", "TEXT DEFAULT 'general_chat'"),
                    ("complexity", "TEXT DEFAULT 'medium'"),
                    ("confidence", "REAL DEFAULT 1.0"),
                    ("decision_reason", "TEXT DEFAULT ''"),
                    ("decision_trace", "TEXT DEFAULT ''")
                ]:
                    try:
                        cursor.execute(f"ALTER TABLE telemetry ADD COLUMN {col_name} {col_type}")
                    except Exception:
                        pass

                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_success ON telemetry (success)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_filepath ON telemetry (file_path)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize telemetry database: {e}")
            raise e

    def log(self, record: Dict[str, Any]) -> None:
        """Queues a telemetry record for asynchronous background write."""
        if not self._is_initialized:
            logger.warning("Telemetry logger is not initialized. Dropping log record.")
            return

        # Ensure timestamp is set
        if "timestamp" not in record:
            record["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        self._queue.put(record)

    def _worker(self):
        """Background worker consuming queue items and writing them to SQLite in batches."""
        batch: List[Dict[str, Any]] = []
        last_flush = time.time()

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                # Blocks for up to 1 second
                record = self._queue.get(timeout=1.0)
                batch.append(record)
                self._queue.task_done()
            except queue.Empty:
                pass

            now = time.time()
            # Flush if batch size reaches 10 or 2 seconds have passed since last flush
            if batch and (len(batch) >= 10 or (now - last_flush) >= 2.0):
                self._flush_batch(batch)
                batch.clear()
                last_flush = now

        # Final flush on shutdown
        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Performs bulk insert into the telemetry database."""
        for r in batch:
            r.setdefault("error_type", None)
            r.setdefault("file_path", "")
            r.setdefault("line_number", 0)
            r.setdefault("task_type", "general_chat")
            r.setdefault("complexity", "medium")
            r.setdefault("confidence", 1.0)
            r.setdefault("decision_reason", "")
            r.setdefault("decision_trace", "")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO telemetry (
                        timestamp, request_id, provider, model_requested, model_used,
                        input_tokens, output_tokens, latency_ms, status_code, success,
                        error_type, cache_hit, cost_original, cost_actual, savings,
                        prompt_hash, environment, application, region, retry_count,
                        file_path, line_number
                    ) VALUES (
                        :timestamp, :request_id, :provider, :model_requested, :model_used,
                        :input_tokens, :output_tokens, :latency_ms, :status_code, :success,
                        :error_type, :cache_hit, :cost_original, :cost_actual, :savings,
                        :prompt_hash, :environment, :application, :region, :retry_count,
                        :file_path, :line_number
                    )
                """, batch)
                conn.commit()
                logger.debug(f"Flushed {len(batch)} telemetry records to DB.")

                # Check budget alerts if alert manager configured
                if self.alert_manager and self.alert_manager.config.enabled:
                    try:
                        cursor.execute("SELECT SUM(cost_actual), COUNT(*), SUM(savings) FROM telemetry WHERE strftime('%Y-%m-%d', timestamp) = strftime('%Y-%m-%d', 'now')")
                        row = cursor.fetchone()
                        d_spend = float(row[0] or 0.0)
                        req_count = int(row[1] or 0)
                        tot_savings = float(row[2] or 0.0)

                        cursor.execute("SELECT SUM(cost_actual) FROM telemetry WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')")
                        m_row = cursor.fetchone()
                        m_spend = float(m_row[0] or 0.0)

                        self.alert_manager.check_and_trigger(
                            daily_spend=d_spend,
                            monthly_spend=m_spend,
                            request_count_today=req_count,
                            total_savings_today=tot_savings
                        )
                    except Exception as alert_err:
                        logger.error(f"Error evaluating budget alerts: {alert_err}")
        except Exception as e:
            logger.error(f"Error flushing telemetry batch: {e}")

    def shutdown(self):
        """Gracefully shuts down the background logger thread."""
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        logger.info("Telemetry logger shut down successfully.")
