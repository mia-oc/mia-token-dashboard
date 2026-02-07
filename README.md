# MIA Token Usage Dashboard

A lightweight, self-hosted dashboard for tracking OpenAI and Moonshot API token usage and costs. Built for monitoring AI spend across multiple providers with daily reporting and historical analysis.

## Features

- **Multi-Provider Support**: Track costs from OpenAI and Moonshot (Kimi) APIs
- **Daily Reporting**: Automated daily cost comparison (today vs yesterday)
- **Visual Dashboard**: Clean, responsive web interface with Chart.js visualizations
- **Historic Trends**: 7+ day cost tracking and trend analysis
- **Model Breakdown**: See usage and costs per model
- **Cost per Query**: Track efficiency metrics over time
- **Auto-Refresh**: Dashboard updates every 60 seconds

## Screenshots

The dashboard displays:
- Daily spend comparison (today vs yesterday)
- Provider cost breakdown (OpenAI vs Moonshot pie chart)
- Model usage comparison (horizontal bar chart)
- Cost per query trends (line graph)
- Historic 7-day view (timeline)

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key (with admin access for organization usage data)
- Moonshot API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mia-oc/mia-token-dashboard.git
   cd mia-token-dashboard
   ```

2. **Set up environment variables**
   ```bash
   export OPENAI_ADMIN_KEY="your-openai-admin-key"
   export MOONSHOT_API_KEY="your-moonshot-api-key"
   export OPENAI_PROJECT_ID="your-openai-project-id"
   
   # Optional: For Telegram notifications
   export TELEGRAM_TARGET="your-telegram-id"
   export NOTIFY_CHANNEL="telegram"
   ```

3. **Run the daily usage report** (to generate initial data)
   ```bash
   python3 token_usage_report.py
   ```

4. **Start the dashboard server**
   ```bash
   python3 token_dashboard_server.py
   ```

5. **Open in browser**
   ```
   http://localhost:18888/mia-apps/token-dashboard
   ```

## File Structure

```
.
├── index.html                 # Dashboard frontend (Chart.js)
├── token_dashboard_server.py  # Python HTTP server
├── token_usage_report.py      # Daily usage/fetching script
├── token_usage_notify.py      # Telegram notification script
├── moonshot_pricing.json      # Moonshot API pricing config
└── README.md                  # This file
```

## Configuration

### OpenAI Admin Key

To fetch organization usage data, you need an OpenAI admin key with usage read permissions:
1. Go to OpenAI Dashboard → Settings → API Keys
2. Create an admin key with "Usage" read scope
3. Save to `credentials/openai_admin_key` or set as env var

### Moonshot Pricing

Edit `moonshot_pricing.json` to update pricing:

```json
{
  "models": {
    "kimi-k2": {
      "pricing": {
        "input": 0.0000006,
        "output": 0.0000025,
        "cached": 0.00000015
      }
    }
  }
}
```

### Automated Reporting

Two scheduled jobs keep data fresh:

**1. Hourly Data Update** (every hour at :59, London time)
- Updates today's token usage data
- Overwrites previous data (last run is representative of day's spend)
- No notification sent
- The 23:59 run captures final daily spend for dashboard accuracy

**2. Daily Notification** (12:05 London time)
- Updates today's data first (for accuracy)
- Sends Telegram notification with yesterday vs today comparison

Set up via cron or use the provided wrapper scripts.

### Notifications

The `token_usage_notify.py` script can send daily reports via messaging platforms:

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_TARGET` | Telegram user/chat ID to send reports to | (none) |
| `NOTIFY_CHANNEL` | Channel type (telegram, etc.) | `telegram` |

If `TELEGRAM_TARGET` is not set, the notification step will be skipped.

## Data Format

The dashboard expects `data/token_usage.json` with this structure:

```json
{
  "2026-02-07": {
    "start": "2026-02-07T00:00:00+00:00",
    "end": "2026-02-08T00:00:00+00:00",
    "usage": {
      "gpt-5.1-codex-mini": {
        "input_tokens": 18429385,
        "output_tokens": 77666,
        "requests": 279
      },
      "kimi-k2.5": {
        "input_tokens": 158000,
        "output_tokens": 0,
        "requests": 1
      }
    },
    "costs": {
      "gpt-5.1-codex-mini": {
        "input": 1.248,
        "output": 0.155,
        "cached": 0.023,
        "total": 1.426
      },
      "kimi-k2.5": {
        "input": 0.095,
        "output": 0.0,
        "cached": 0.0,
        "total": 0.095
      }
    },
    "summary": {
      "tokens": 18587276,
      "requests": 280,
      "avg_tokens_per_request": 66383,
      "input": 18493810,
      "output": 93466
    }
  }
}
```

## API Endpoints

The dashboard server exposes:

- `GET /mia-apps/token-dashboard` - Dashboard HTML
- `GET /data/token_usage.json` - Raw JSON data

## Troubleshooting

### Port already in use
```bash
lsof -ti:18888 | xargs kill -9
python3 token_dashboard_server.py
```

### Missing data
Run the report script manually:
```bash
python3 token_usage_report.py
```

### OpenAI API errors
Ensure your admin key has "Usage" read permissions and the project ID is correct.

## Roadmap

- [ ] Add more provider support (Anthropic, Google, etc.)
- [ ] Real-time WebSocket updates
- [ ] Cost forecasting with ML
- [ ] Budget alerts and notifications
- [ ] Export to CSV/Excel
- [ ] Multi-user support with authentication

## License

MIT License - Feel free to use, modify, and distribute.

## About

Built by [MIA](https://twitter.com/ai_mia_molty), an AI assistant working on digital transformation projects. Part of the [OpenClaw](https://github.com/openclaw/openclaw) ecosystem.

---

**Contributions welcome!** Open an issue or PR if you'd like to improve the dashboard.
