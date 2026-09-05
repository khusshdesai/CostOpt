import os
import time
import json
import logging
import threading
import urllib.request
import urllib.error
import yaml
from dataclasses import dataclass
from typing import Optional, Dict, Any

logger = logging.getLogger("costopt.alerts")

@dataclass
class AlertConfig:
    enabled: bool = False
    daily_budget_usd: float = 10.0
    monthly_budget_usd: float = 50.0
    cooldown_minutes: int = 60
    slack_webhook_url: Optional[str] = None

def load_alert_config(config_path: str = "costopt.yaml") -> AlertConfig:
    """Parses AlertConfig from YAML file and merges environment overrides."""
    config = AlertConfig()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                raw_alerts = data.get("alerts", {})
                if isinstance(raw_alerts, dict):
                    config.enabled = bool(raw_alerts.get("enabled", False))
                    config.daily_budget_usd = float(raw_alerts.get("daily_budget_usd", 10.0))
                    config.monthly_budget_usd = float(raw_alerts.get("monthly_budget_usd", 50.0))
                    config.cooldown_minutes = int(raw_alerts.get("cooldown_minutes", 60))
                    config.slack_webhook_url = raw_alerts.get("slack_webhook_url") or None
        except Exception as e:
            logger.warning(f"Error parsing alert config from {config_path}: {e}")

    # Environment Variable Overrides
    env_url = os.getenv("COSTOPT_SLACK_WEBHOOK_URL")
    if env_url:
        config.slack_webhook_url = env_url
        config.enabled = True

    env_daily = os.getenv("COSTOPT_DAILY_BUDGET_USD")
    if env_daily:
        try:
            config.daily_budget_usd = float(env_daily)
        except ValueError:
            pass

    return config

class SlackAlertManager:
    """
    Asynchronous Budget Alert Manager.
    Evaluates daily and monthly spend against configured thresholds and dispatches Slack webhooks.
    Includes thread safety, cooldown timers, and network exception isolation.
    """
    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self._last_daily_alert_time: float = 0.0
        self._last_monthly_alert_time: float = 0.0
        self._lock = threading.Lock()

    def check_and_trigger(
        self,
        daily_spend: float,
        monthly_spend: float,
        request_count_today: int = 0,
        total_savings_today: float = 0.0
    ) -> None:
        """Evaluates daily/monthly spend against thresholds and fires alerts asynchronously."""
        if not self.config.enabled or not self.config.slack_webhook_url:
            return

        now = time.time()
        cooldown_sec = max(60.0, self.config.cooldown_minutes * 60.0)

        # Check Daily Budget
        if daily_spend >= self.config.daily_budget_usd:
            with self._lock:
                if (now - self._last_daily_alert_time) >= cooldown_sec:
                    self._last_daily_alert_time = now
                    self._dispatch_async(
                        alert_type="Daily Budget Threshold Breached",
                        current_spend=daily_spend,
                        limit=self.config.daily_budget_usd,
                        request_count=request_count_today,
                        total_savings=total_savings_today
                    )

        # Check Monthly Budget
        if monthly_spend >= self.config.monthly_budget_usd:
            with self._lock:
                if (now - self._last_monthly_alert_time) >= cooldown_sec:
                    self._last_monthly_alert_time = now
                    self._dispatch_async(
                        alert_type="Monthly Budget Threshold Breached",
                        current_spend=monthly_spend,
                        limit=self.config.monthly_budget_usd,
                        request_count=request_count_today,
                        total_savings=total_savings_today
                    )

    def _dispatch_async(
        self,
        alert_type: str,
        current_spend: float,
        limit: float,
        request_count: int,
        total_savings: float
    ) -> None:
        """Launches a background daemon thread to dispatch the Slack webhook request without blocking main execution."""
        thread = threading.Thread(
            target=self._send_slack_payload,
            args=(alert_type, current_spend, limit, request_count, total_savings),
            daemon=True
        )
        thread.start()

    def _send_slack_payload(
        self,
        alert_type: str,
        current_spend: float,
        limit: float,
        request_count: int,
        total_savings: float
    ) -> bool:
        """Formulates and posts a Slack Block Kit webhook message."""
        if not self.config.slack_webhook_url:
            return False

        payload = {
            "text": f"⚠️ CostOpt Alert: {alert_type} (${current_spend:.2f} / ${limit:.2f})",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"⚠️ CostOpt Alert: {alert_type}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Current Spend:*\n${current_spend:.4f}"},
                        {"type": "mrkdwn", "text": f"*Budget Threshold:*\n${limit:.2f}"},
                        {"type": "mrkdwn", "text": f"*Requests Today:*\n{request_count:,}"},
                        {"type": "mrkdwn", "text": f"*Cache Savings Today:*\n${total_savings:.4f}"}
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "⚡ *CostOpt FinOps Alert* | Local Dashboard Console: `http://localhost:8400`"}
                    ]
                }
            ]
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.config.slack_webhook_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "CostOpt-Alerts/0.1.8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    logger.info(f"Slack alert successfully dispatched: [{alert_type}]")
                    return True
                else:
                    logger.warning(f"Slack webhook returned status code {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to dispatch Slack alert webhook: {e}")
            return False
