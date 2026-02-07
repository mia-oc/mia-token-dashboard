#!/usr/bin/env python3
"""Fetch OpenAI and Moonshot usage/cost data, store per-model tokens, and compare yesterday vs today."""
import datetime
import json
import os
import subprocess
import urllib.request
import urllib.error
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_KEY_PATH = os.path.join(ROOT, "credentials", "openai_admin_key")
DATA_PATH = os.path.join(ROOT, "data", "token_usage.json")
MOONSHOT_PRICING_PATH = os.path.join(ROOT, "config", "moonshot_pricing.json")

SERVICES = {
    "completions": "https://api.openai.com/v1/organization/usage/completions",
    "embeddings": "https://api.openai.com/v1/organization/usage/embeddings",
}
PROJECT_ID = os.environ.get("OPENAI_PROJECT_ID", "")

# Moonshot model mappings
MOONSHOT_MODELS = {
    "kimi-k2": "kimi-k2",
    "kimi-k2-thinking": "kimi-k2-thinking", 
    "kimi-k2.5": "kimi-k2.5",
    "moonshot/kimi-k2": "kimi-k2",
    "moonshot/kimi-k2-thinking": "kimi-k2-thinking",
    "moonshot/kimi-k2.5": "kimi-k2.5",
}


def load_admin_key():
    try:
        with open(ADMIN_KEY_PATH, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise SystemExit("Admin key not found at %s" % ADMIN_KEY_PATH)


def load_moonshot_pricing():
    """Load Moonshot model pricing from config."""
    try:
        with open(MOONSHOT_PRICING_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"models": {}}


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def bucket_label(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def fetch_openai_usage(start_ts: int, end_ts: int) -> dict:
    """Fetch usage data from OpenAI API."""
    key = load_admin_key()
    usage_by_model = {}
    for service, url in SERVICES.items():
        params = {
            "start_time": start_ts,
            "end_time": end_ts,
            "group_by": "model",
            "bucket_width": "1d",
            "limit": 1,
            "project_ids": PROJECT_ID,
        }
        next_page = None
        while True:
            if next_page:
                params["page"] = next_page
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query_string}"
            req = urllib.request.Request(
                full_url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                raise SystemExit(f"OpenAI Usage API error {e.code}: {e.read().decode()}")
            for bucket in body.get("data", []):
                for result in bucket.get("results", []):
                    model = result.get("model") or "unknown"
                    entry = usage_by_model.setdefault(model, {
                        "model": model,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cached_tokens": 0,
                        "requests": 0,
                        "services": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "requests": 0}),
                    })
                    input_tokens = result.get("input_tokens", 0)
                    cached = result.get("input_cached_tokens", 0)
                    output_tokens = result.get("output_tokens", 0)
                    requests_count = result.get("num_model_requests", 0)
                    entry["input_tokens"] += input_tokens
                    entry["cached_tokens"] += cached
                    entry["output_tokens"] += output_tokens
                    entry["requests"] += requests_count
                    svc = entry["services"][service]
                    svc["input_tokens"] += input_tokens
                    svc["cached_tokens"] += cached
                    svc["output_tokens"] += output_tokens
                    svc["requests"] += requests_count
            next_page = body.get("next_page")
            if not next_page:
                break
    # convert services defaultdict to dicts
    for model_entry in usage_by_model.values():
        model_entry["services"] = {svc: data for svc, data in model_entry["services"].items()}
    return usage_by_model


def fetch_openai_costs(start_ts: int, end_ts: int) -> dict:
    """Fetch cost data from OpenAI API."""
    key = load_admin_key()
    params = {
        "start_time": start_ts,
        "end_time": end_ts,
        "bucket_width": "1d",
        "group_by": "line_item",
        "limit": 100,
        "project_ids": PROJECT_ID,
    }
    url = "https://api.openai.com/v1/organization/costs"
    totals = {}
    next_page = None
    while True:
        if next_page:
            params["page"] = next_page
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(
            full_url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"OpenAI Costs API error {e.code}: {e.read().decode()}")
        for bucket in body.get("data", []):
            for result in bucket.get("results", []):
                line_item = (result.get("line_item") or "").strip()
                amount = float(result.get("amount", {}).get("value") or 0.0)
                model, metric = parse_line_item(line_item)
                if not model or not metric:
                    continue
                entry = totals.setdefault(model, {"input": 0.0, "output": 0.0, "cached": 0.0, "other": 0.0})
                if metric in entry:
                    entry[metric] += amount
        next_page = body.get("next_page")
        if not next_page:
            break
    for entry in totals.values():
        entry["total"] = entry.get("input", 0.0) + entry.get("output", 0.0) + entry.get("cached", 0.0) + entry.get("other", 0.0)
    return totals


def fetch_moonshot_usage(start_ts: int, end_ts: int) -> dict:
    """Fetch Moonshot usage from OpenClaw session data via sessions_list tool."""
    usage_by_model = {}
    
    # Map of Moonshot model identifiers
    moonshot_models = {
        "kimi-k2", "kimi-k2-thinking", "kimi-k2.5",
        "moonshot/kimi-k2", "moonshot/kimi-k2-thinking", "moonshot/kimi-k2.5"
    }
    
    try:
        # Query sessions from the last 2 days
        result = subprocess.run(
            ["openclaw", "sessions", "list", "--limit", "100", "--json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"Warning: Could not fetch sessions: {result.stderr}")
            return {}
        
        sessions = json.loads(result.stdout)
        for session in sessions.get("sessions", []):
            model = session.get("model", "")
            # Check if this is a Moonshot model
            is_moonshot = any(m in model.lower() for m in moonshot_models)
            if not is_moonshot:
                continue
            
            # Normalize model name
            normalized_model = model.replace("moonshot/", "")
            
            # Get session timestamp
            updated_at = session.get("updatedAt", 0)
            if updated_at:
                # Convert milliseconds to seconds if needed
                if updated_at > 1e12:
                    updated_at = updated_at / 1000
                
                # Check if within our time range
                if not (start_ts <= updated_at <= end_ts):
                    continue
            
            # Get token counts
            total_tokens = session.get("totalTokens", 0)
            # Estimate input/output split (typically 90% input, 10% output for queries)
            estimated_input = int(total_tokens * 0.9)
            estimated_output = int(total_tokens * 0.1)
            
            entry = usage_by_model.setdefault(normalized_model, {
                "model": normalized_model,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "requests": 0,
                "services": {},
            })
            
            entry["input_tokens"] += estimated_input
            entry["output_tokens"] += estimated_output
            entry["requests"] += 1
    
    except Exception as e:
        print(f"Warning: Error fetching Moonshot usage: {e}")
        return {}
    
    return usage_by_model


def calculate_moonshot_costs(usage: dict) -> dict:
    """Calculate Moonshot costs based on usage and pricing."""
    pricing = load_moonshot_pricing()
    costs = {}
    
    for model_key, model_pricing in pricing.get("models", {}).items():
        if model_key not in usage:
            continue
        
        u = usage[model_key]
        p = model_pricing.get("pricing", {})
        
        input_cost = u.get("input_tokens", 0) * p.get("input", 0)
        output_cost = u.get("output_tokens", 0) * p.get("output", 0)
        cached_cost = u.get("cached_tokens", 0) * p.get("cached", 0)
        
        costs[model_key] = {
            "input": input_cost,
            "output": output_cost,
            "cached": cached_cost,
            "total": input_cost + output_cost + cached_cost,
            "per_token": {
                "input": p.get("input"),
                "output": p.get("output"),
                "cached": p.get("cached"),
            }
        }
    
    return costs


def parse_line_item(line_item: str):
    parts = [p.strip() for p in line_item.split(",") if p.strip()]
    if not parts:
        return None, None
    model = parts[0]
    metric = "other"
    if len(parts) > 1:
        metric_candidate = parts[1].lower()
        if "cached" in metric_candidate:
            metric = "cached"
        elif "input" in metric_candidate:
            metric = "input"
        elif "output" in metric_candidate:
            metric = "output"
    return model, metric


def load_existing_data() -> dict:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def summarize(label: str, usage: dict):
    total_input = sum(v["input_tokens"] for v in usage.values())
    total_output = sum(v["output_tokens"] for v in usage.values())
    total_requests = sum(v["requests"] for v in usage.values())
    tokens = total_input + total_output
    avg = (tokens / total_requests) if total_requests else 0
    return {
        "tokens": tokens,
        "requests": total_requests,
        "avg_tokens_per_request": avg,
        "input": total_input,
        "output": total_output,
    }


def attach_cost_rates(costs: dict, usage: dict):
    for model, cost_entry in costs.items():
        usage_entry = usage.get(model, {})
        rates = {}
        def rate(kind, tokens):
            if tokens:
                return cost_entry.get(kind, 0.0) / tokens
            return None
        rates["input"] = rate("input", usage_entry.get("input_tokens", 0))
        rates["output"] = rate("output", usage_entry.get("output_tokens", 0))
        rates["cached"] = rate("cached", usage_entry.get("cached_tokens", 0))
        cost_entry["per_token"] = rates
    return costs


def format_rate(value):
    if value is None:
        return "n/a"
    return f"${value:.6f}"


def format_day_report(label, day_data, now=None, is_today=False):
    """Format a day report showing both OpenAI and Moonshot costs."""
    summary = day_data["summary"]
    
    # Separate OpenAI and Moonshot costs
    openai_costs = {}
    moonshot_costs = {}
    for model, cost in day_data.get("costs", {}).items():
        if model.startswith("kimi-") or model.startswith("moonshot/"):
            moonshot_costs[model] = cost
        else:
            openai_costs[model] = cost
    
    openai_total = sum(c.get("total", 0) for c in openai_costs.values())
    moonshot_total = sum(c.get("total", 0) for c in moonshot_costs.values())
    total_cost = openai_total + moonshot_total
    
    cost_per_query = total_cost / summary["requests"] if summary["requests"] else 0
    avg_input = summary["input"] / summary["requests"] if summary["requests"] else 0
    avg_output = summary["output"] / summary["requests"] if summary["requests"] else 0
    
    openai_models = sorted(m for m in day_data.get("usage", {}).keys() if not (m.startswith("kimi-") or m.startswith("moonshot/")))
    moonshot_models = sorted(m for m in day_data.get("usage", {}).keys() if m.startswith("kimi-") or m.startswith("moonshot/"))
    
    lines = [f"{label} total spend: ${total_cost:.5f} (OpenAI: ${openai_total:.5f}, Moonshot: ${moonshot_total:.5f})"]
    
    if is_today and now is not None:
        start = datetime.datetime.fromisoformat(day_data["start"])
        elapsed_hours = max((now - start).total_seconds() / 3600, 0.01)
        requests_per_hour = summary["requests"] / elapsed_hours
        projected_requests = requests_per_hour * 24
        projected_spend = cost_per_query * projected_requests
        lines.append(
            f"{label} projected spend (24h trend): ${projected_spend:.5f} based on {requests_per_hour:.2f} requests/hour"
        )
    
    lines.extend([
        f"{label} cost per query: ${cost_per_query:.6f}",
        f"{label} avg tokens in per query: {avg_input:.1f}",
        f"{label} avg tokens out per query: {avg_output:.1f}",
    ])
    
    if openai_models:
        lines.append(f"{label} OpenAI models: {', '.join(openai_models)}")
    if moonshot_models:
        lines.append(f"{label} Moonshot models: {', '.join(moonshot_models)}")
    
    return lines


def print_comparison(yesterday_label, today_label, data):
    print("Daily comparison (tokens + costs) by model")
    models = sorted({*data[yesterday_label]["usage"].keys(), *data[today_label]["usage"].keys()})
    for model in models:
        y_usage = data[yesterday_label]["usage"].get(model, {})
        t_usage = data[today_label]["usage"].get(model, {})
        y_cost = data[yesterday_label]["costs"].get(model, {})
        t_cost = data[today_label]["costs"].get(model, {})
        token_diff = (t_usage.get("input_tokens", 0) + t_usage.get("output_tokens", 0)) - (
            y_usage.get("input_tokens", 0) + y_usage.get("output_tokens", 0)
        )
        cost_diff = t_cost.get("total", 0.0) - y_cost.get("total", 0.0)
        y_rates = y_cost.get("per_token", {})
        t_rates = t_cost.get("per_token", {})
        
        # Identify provider
        provider = "Moonshot" if model.startswith("kimi-") or model.startswith("moonshot/") else "OpenAI"
        
        print(
            f"{provider} {model}: yesterday {y_usage.get('input_tokens',0)+y_usage.get('output_tokens',0):,} tokens / ${y_cost.get('total',0):.5f} "
            f"(in {format_rate(y_rates.get('input'))}, out {format_rate(y_rates.get('output'))}) | "
            f"today {t_usage.get('input_tokens',0)+t_usage.get('output_tokens',0):,} tokens / ${t_cost.get('total',0):.5f} "
            f"(in {format_rate(t_rates.get('input'))}, out {format_rate(t_rates.get('output'))}) | "
            f"delta tokens {token_diff:+,} | delta cost ${cost_diff:+.5f}"
        )


def main():
    today = now_utc()
    today_midnight = today.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_midnight = today_midnight - datetime.timedelta(days=1)
    tomorrow_midnight = today_midnight + datetime.timedelta(days=1)
    yesterday_label = bucket_label(yesterday_midnight)
    today_label = bucket_label(today_midnight)
    periods = [
        (yesterday_label, yesterday_midnight, today_midnight),
        (today_label, today_midnight, tomorrow_midnight),
    ]
    data = load_existing_data()
    
    for label, period_start, period_end in periods:
        start_ts = int(period_start.timestamp())
        end_ts = int(period_end.timestamp())
        
        print(f"Fetching OpenAI usage for {label} ({start_ts}–{end_ts})")
        openai_usage = fetch_openai_usage(start_ts, end_ts)
        
        print(f"Fetching OpenAI costs for {label}")
        openai_costs = fetch_openai_costs(start_ts, end_ts)
        openai_costs = attach_cost_rates(openai_costs, openai_usage)
        
        print(f"Fetching Moonshot usage for {label}")
        moonshot_usage = fetch_moonshot_usage(start_ts, end_ts)
        
        print(f"Calculating Moonshot costs for {label}")
        moonshot_costs = calculate_moonshot_costs(moonshot_usage)
        
        # Combine OpenAI and Moonshot data
        combined_usage = {**openai_usage, **moonshot_usage}
        combined_costs = {**openai_costs, **moonshot_costs}
        
        summary = summarize(label, combined_usage)
        data[label] = {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "usage": combined_usage,
            "costs": combined_costs,
            "summary": summary,
            "providers": {
                "openai": {
                    "usage": openai_usage,
                    "costs": openai_costs,
                },
                "moonshot": {
                    "usage": moonshot_usage,
                    "costs": moonshot_costs,
                }
            }
        }
    
    save_data(data)
    now = now_utc()
    print()
    print(f"Summary {yesterday_label}: {data[yesterday_label]['summary']}")
    print(f"Summary {today_label}: {data[today_label]['summary']}")
    print()
    print_comparison(yesterday_label, today_label, data)
    print()
    for line in format_day_report(yesterday_label, data[yesterday_label]):
        print(line)
    for line in format_day_report(today_label, data[today_label], now=now, is_today=True):
        print(line)


if __name__ == "__main__":
    main()
