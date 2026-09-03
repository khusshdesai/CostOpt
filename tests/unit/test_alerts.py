"""
Unit tests for CostOpt Budget Alerting & Slack Webhooks
"""

import time
import os
import unittest
from unittest.mock import patch, MagicMock
from costopt.alerts import AlertConfig, SlackAlertManager, load_alert_config


class TestSlackAlertManager(unittest.TestCase):
    def test_alert_config_defaults(self):
        config = AlertConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.daily_budget_usd, 10.0)
        self.assertEqual(config.monthly_budget_usd, 50.0)
        self.assertEqual(config.cooldown_minutes, 60)
        self.assertIsNone(config.slack_webhook_url)

    def test_load_alert_config_yaml(self):
        config = load_alert_config("costopt.yaml")
        self.assertIsInstance(config, AlertConfig)

    @patch.dict(os.environ, {"COSTOPT_SLACK_WEBHOOK_URL": "https://hooks.slack.com/test", "COSTOPT_DAILY_BUDGET_USD": "5.50"})
    def test_load_alert_config_env_override(self):
        config = load_alert_config("non_existent_config.yaml")
        self.assertTrue(config.enabled)
        self.assertEqual(config.slack_webhook_url, "https://hooks.slack.com/test")
        self.assertEqual(config.daily_budget_usd, 5.50)

    @patch("costopt.alerts.SlackAlertManager._send_slack_payload")
    def test_check_and_trigger_daily_threshold(self, mock_send):
        config = AlertConfig(
            enabled=True,
            daily_budget_usd=10.0,
            cooldown_minutes=60,
            slack_webhook_url="https://hooks.slack.com/services/test"
        )
        manager = SlackAlertManager(config)

        # Under threshold -> Should NOT trigger
        manager.check_and_trigger(daily_spend=5.0, monthly_spend=15.0)
        mock_send.assert_not_called()

        # Over threshold -> Should trigger
        manager.check_and_trigger(daily_spend=10.5, monthly_spend=15.0, request_count_today=10, total_savings_today=2.5)
        time.sleep(0.1)
        mock_send.assert_called_once()

    @patch("costopt.alerts.SlackAlertManager._send_slack_payload")
    def test_cooldown_suppression(self, mock_send):
        config = AlertConfig(
            enabled=True,
            daily_budget_usd=10.0,
            cooldown_minutes=60,
            slack_webhook_url="https://hooks.slack.com/services/test"
        )
        manager = SlackAlertManager(config)

        # First trigger -> Fires alert
        manager.check_and_trigger(daily_spend=12.0, monthly_spend=20.0)
        time.sleep(0.1)
        self.assertEqual(mock_send.call_count, 1)

        # Second trigger within cooldown window -> Suppressed
        manager.check_and_trigger(daily_spend=15.0, monthly_spend=20.0)
        time.sleep(0.1)
        self.assertEqual(mock_send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
