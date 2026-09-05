import sqlite3
import math
import logging
from typing import List, Dict, Any, Tuple

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
                        z_score = 0.0
                    else:
                        z_score = (current_cost - mean) / stddev

                    # Flag anomaly if Z-score exceeds threshold
                    if z_score > z_threshold:
                        anomalies.append({
                            "date": current_date,
                            "actual_cost": round(current_cost, 2),
                            "expected_mean": round(mean, 2),
                            "stddev": round(stddev, 2),
                            "z_score": round(z_score, 2),
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
