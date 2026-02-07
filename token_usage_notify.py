#!/usr/bin/env python3
"""Run the token usage report and send the summary to Telegram."""
import datetime
import json
import os
import subprocess
import sys

from token_usage_report import (  # type: ignore # module located in same directory
    bucket_label,
    format_day_report,
    load_existing_data,
    now_utc,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_SCRIPT = os.path.join(ROOT, "scripts", "token_usage_report.py")
MSG_CMD = "openclaw"
TARGET = os.environ.get("TELEGRAM_TARGET", "")
CHANNEL = os.environ.get("NOTIFY_CHANNEL", "telegram")


def run_report() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, REPORT_SCRIPT],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def build_message(data: dict, now: datetime.datetime) -> str:
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_midnight = today_midnight - datetime.timedelta(days=1)
    today_label = bucket_label(today_midnight)
    yesterday_label = bucket_label(yesterday_midnight)
    if today_label not in data or yesterday_label not in data:
        return "Token usage data not available for both days."
    today_lines = format_day_report("Today", data[today_label], now=now, is_today=True)
    yesterday_lines = format_day_report("Yesterday", data[yesterday_label])
    return "\n".join(today_lines + ["", *yesterday_lines])


def send_message(message: str):
    subprocess.run(
        [
            MSG_CMD,
            "message",
            "send",
            "--channel",
            CHANNEL,
            "--target",
            TARGET,
            "--message",
            message,
        ],
        cwd=ROOT,
        check=False,
    )


def main():
    report_proc = run_report()
    if report_proc.returncode != 0:
        send_message(
            f"Token usage report failed:\n{report_proc.stderr.strip()}"
        )
        sys.exit(report_proc.returncode)
    data = load_existing_data()
    now = now_utc()
    message = build_message(data, now)
    send_message(message)


if __name__ == "__main__":
    main()
