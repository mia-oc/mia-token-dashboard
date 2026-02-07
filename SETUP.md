# Token Usage Setup

## Overview
Single source of truth: `mia-token-dashboard/` repo (private)

## File Locations
- **Repo**: `/home/node/.openclaw/workspace/mia-token-dashboard/`
- **Local scripts**: Symlinked/copied from repo to `/home/node/.openclaw/workspace/scripts/`
- **Config**: `.env` file in workspace root
- **Data**: `data/token_usage.json`

## Configuration
Edit `/home/node/.openclaw/workspace/.env`:

```bash
OPENAI_ADMIN_KEY=sk-proj-...
MOONSHOT_API_KEY=sk-...
OPENAI_PROJECT_ID=proj_...
TELEGRAM_TARGET=your-telegram-id
NOTIFY_CHANNEL=telegram
```

## Automated Jobs

### 1. Hourly Data Update (No Notification)
Runs at **:59 minutes past every hour** (London time)
- Updates today's token usage data
- Overwrites previous data for the day (last run is representative)
- No notification sent
- Ensures dashboard is reasonably accurate throughout the day
- The 23:59 run captures the final daily spend

**Script**: `scripts/run_token_hourly.sh`

### 2. Daily Notification (12:05 London Time)
Runs at **12:05 daily** (London time)
- First updates today's data (for accuracy)
- Then sends Telegram notification with yesterday vs today comparison
- Keeps the existing notification format

**Script**: `scripts/run_token_notify.sh`

**Logs**: Both write to `logs/token_hourly.log`

## Updating
After editing repo files:
```bash
cp mia-token-dashboard/*.py scripts/
```

## Dashboard
- Running on port 18888
- URL: http://localhost:18888/mia-apps/token-dashboard
