# 📱 Slack Budget Alert Notification Preview

When your application's daily or monthly LLM API spend crosses the threshold configured in `costopt.yaml`, CostOpt automatically dispatches a formatted **Slack Block Kit** alert to your team's Slack channel.

---

## 🎨 Visual Preview (Inside Slack Desktop / Mobile App)

Below is the exact visual representation of the alert card as displayed inside Slack:

> ### ⚠️ **CostOpt Alert: Daily Budget Threshold Breached**
> 
> | Current Spend | Budget Threshold |
> | :--- | :--- |
> | **$10.2500** | **$10.00** |
> 
> | Requests Today | Cache Savings Today |
> | :--- | :--- |
> | **42** | **+$3.1500** |
> 
> _⚡ CostOpt FinOps Alert &bull; Open Local Dashboard_

---

## 📲 Push Notification Preview (Mobile / Smartwatch)

On mobile lock screens and desktop push toasts, the alert text appears as:

> **⚠️ CostOpt Alert: Daily Budget Threshold Breached ($10.25 / $10.00)**

---

## ⚙️ Raw Slack Block Kit JSON Payload Dispatched

Under the hood, CostOpt sends the following structured Slack Block Kit JSON payload to your `slack_webhook_url`:

```json
{
  "text": "⚠️ CostOpt Alert: Daily Budget Threshold Breached ($10.25 / $10.00)",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "⚠️ CostOpt Alert: Daily Budget Threshold Breached",
        "emoji": true
      }
    },
    {
      "type": "section",
      "fields": [
        {
          "type": "mrkdwn",
          "text": "*Current Spend:*\n$10.2500"
        },
        {
          "type": "mrkdwn",
          "text": "*Budget Threshold:*\n$10.00"
        },
        {
          "type": "mrkdwn",
          "text": "*Requests Today:*\n42"
        },
        {
          "type": "mrkdwn",
          "text": "*Cache Savings Today:*\n$3.1500"
        }
      ]
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": "⚡ *CostOpt FinOps Alert* | Local Dashboard Console: `http://localhost:8400`"
        }
      ]
    }
  ]
}
```

---

## 🛠️ How to Enable in `costopt.yaml`

To enable alerts in your local project, simply update your `costopt.yaml`:

```yaml
alerts:
  enabled: true
  daily_budget_usd: 10.00
  monthly_budget_usd: 50.00
  cooldown_minutes: 60
  slack_webhook_url: "https://hooks.slack.com/services/T00/B00/XXXXX"
```

Or set the environment variable:
```bash
export COSTOPT_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00/B00/XXXXX"
export COSTOPT_DAILY_BUDGET_USD="10.00"
```
