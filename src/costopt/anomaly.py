import sqlite3
import math
import time
import logging
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger("costopt.anomaly")

class AnomalyDetector:
    def __init__(self, telemetry_db_path: str = "costopt_telemetry.db"):
        self.db_path = telemetry_db_path

    def analyze_daily_cost_anomalies(self, z_threshold: float = 2.0, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """
        Retrieves daily costs, computes rolling Z-scores, and flags anomalies.
        Returns a list of flagged daily anomaly reports.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # BUG-5 fix: subquery gets most recent N days (DESC), outer query restores ASC for Z-score ordering
                cursor.execute("""
                    SELECT date, total_cost, request_count FROM (
                        SELECT 
                            strftime('%Y-%m-%d', timestamp) as date,
                            SUM(cost_actual) as total_cost,
                            COUNT(*) as request_count
                        FROM telemetry
                        GROUP BY date
                        ORDER BY date DESC
                        LIMIT ?
                    ) ORDER BY date ASC
                """, (lookback_days,))
                
                rows = cursor.fetchall()
                if len(rows) < 3:
                    # Not enough historical baseline data points to calculate variance/stddev
                    logger.warning("Insufficient history points in telemetry database to run anomaly analysis.")
                    return []

                dates = [r["date"] for r in rows]
                costs = [float(r["total_cost"]) for r in rows]
                counts = [int(r["request_count"]) for r in rows]

                anomalies = []
                n = len(costs)

                # Compute rolling parameters
                for i in range(2, n):
                    current_cost = costs[i]
                    current_date = dates[i]
                    current_count = counts[i]

                    # History slice up to current index (excluding current point to establish clean baseline)
                    history = costs[:i]
                    mean = sum(history) / len(history)
                    
                    # Compute standard deviation
                    variance = sum((x - mean) ** 2 for x in history) / len(history)
                    stddev = math.sqrt(variance)

                    if stddev == 0.0:
                        # Zero historical variance means every past day was identical.
                        # Any deviation — up or down — has infinite z-score conceptually.
                        # We only flag upward spikes (cost increase), not drops.
                        z_score = float("inf") if current_cost > mean else 0.0
                    else:
                        z_score = (current_cost - mean) / stddev

                    # Flag anomaly if Z-score exceeds threshold
                    if z_score > z_threshold:
                        safe_z = round(z_score, 2) if math.isfinite(z_score) else 999.0
                        anomalies.append({
                            "date": current_date,
                            "actual_cost": round(current_cost, 2),
                            "expected_mean": round(mean, 2),
                            "stddev": round(stddev, 2),
                            "z_score": safe_z,
                            "request_count": current_count,
                            "severity": "CRITICAL" if z_score > 3.5 else "WARNING"
                        })
                
                return anomalies
        except Exception as e:
            logger.error(f"Error running cost anomaly detection: {e}")
            return []

    def get_highest_impact_cost_drivers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries telemetry database to locate applications or models driving the highest spend.
        Useful evidence generation for FinOps recommendations.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Spend by model
                cursor.execute("""
                    SELECT 
                        model_used,
                        provider,
                        SUM(cost_actual) as total_spend,
                        SUM(savings) as saved_amount,
                        COUNT(*) as request_count
                    FROM telemetry
                    GROUP BY model_used, provider
                    ORDER BY total_spend DESC
                    LIMIT ?
                """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error retrieving cost drivers: {e}")
            return []

    def dispatch_anomaly_alerts(
        self,
        config_path: str = "costopt.yaml",
        z_threshold: float = 2.0,
        lookback_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Runs anomaly detection and dispatches a Slack webhook for every flagged day.

        Uses the same costopt.yaml [alerts] block as SlackAlertManager — if
        alerts.enabled is false or slack_webhook_url is empty, this is a no-op.
        Returns the list of anomalies found (same as analyze_daily_cost_anomalies).
        """
        # Import here to avoid circular imports at module load time
        from costopt.alerts import load_alert_config
        import requests

        anomalies = self.analyze_daily_cost_anomalies(
            z_threshold=z_threshold, lookback_days=lookback_days
        )

        if not anomalies:
            logger.debug("No cost anomalies detected — skipping Slack dispatch.")
            return anomalies

        config = load_alert_config(config_path)
        if not config.enabled or not config.slack_webhook_url:
            logger.debug(
                "Anomaly alerts disabled or no Slack webhook configured. "
                "Set alerts.enabled=true and alerts.slack_webhook_url in costopt.yaml."
            )
            return anomalies

        url = config.slack_webhook_url
        if not (url.startswith("http://") or url.startswith("https://")):
            logger.error(f"Invalid Slack webhook URL scheme: {url}")
            return anomalies

        def _post_anomaly(anomaly: Dict[str, Any]) -> None:
            severity = anomaly.get("severity", "WARNING")
            icon = "🚨" if severity == "CRITICAL" else "⚠️"
            payload = {
                "text": (
                    f"{icon} CostOpt Cost Anomaly [{severity}] on {anomaly['date']}: "
                    f"${anomaly['actual_cost']:.2f} (expected ~${anomaly['expected_mean']:.2f})"
                ),
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{icon} Cost Anomaly Detected [{severity}]",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Date:*\n{anomaly['date']}"},
                            {"type": "mrkdwn", "text": f"*Actual Cost:*\n${anomaly['actual_cost']:.4f}"},
                            {"type": "mrkdwn", "text": f"*Expected (mean):*\n${anomaly['expected_mean']:.4f}"},
                            {"type": "mrkdwn", "text": f"*Z-Score:*\n{anomaly['z_score']:.2f} σ"},
                            {"type": "mrkdwn", "text": f"*Std Dev:*\n${anomaly['stddev']:.4f}"},
                            {"type": "mrkdwn", "text": f"*Requests that day:*\n{anomaly['request_count']:,}"},
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "⚡ *CostOpt FinOps* | Dashboard: `http://localhost:8400`",
                            }
                        ],
                    },
                ],
            }
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "CostOpt-AnomalyDetector/1.0",
                    },
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    logger.info(
                        f"Anomaly alert dispatched for {anomaly['date']} "
                        f"(severity={severity}, z={anomaly['z_score']:.2f})"
                    )
                else:
                    logger.warning(
                        f"Slack webhook returned {resp.status_code} for anomaly on {anomaly['date']}"
                    )
            except Exception as exc:
                logger.error(f"Failed to dispatch anomaly alert: {exc}")

        # Fire each anomaly alert in its own daemon thread so we never block the caller
        for anomaly in anomalies:
            thread = threading.Thread(target=_post_anomaly, args=(anomaly,), daemon=True)
            thread.start()

        return anomalies
