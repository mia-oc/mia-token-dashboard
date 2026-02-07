#!/usr/bin/env python3
"""Fetch historical token usage data for the past week."""
import subprocess
import sys
import os

# Add workspace to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.token_usage_report import (
    now_utc, bucket_label, load_existing_data, save_data,
    fetch_openai_usage, fetch_openai_costs, fetch_moonshot_usage,
    load_moonshot_pricing
)
import datetime

def fetch_historical_data():
    """Fetch data for past 7 days."""
    data = load_existing_data()
    now = now_utc()
    
    # Fetch last 7 days
    for days_ago in range(6, -1, -1):
        date = now - datetime.timedelta(days=days_ago)
        label = bucket_label(date)
        
        if label in data:
            print(f"Data already exists for {label}, skipping...")
            continue
        
        print(f"Fetching data for {label}...")
        
        # Calculate timestamps for this day
        start_dt = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + datetime.timedelta(days=1)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())
        
        try:
            # Fetch OpenAI data
            openai_usage = fetch_openai_usage(start_ts, end_ts)
            openai_costs = fetch_openai_costs(start_ts, end_ts)
            
            # Fetch Moonshot data
            moonshot_usage = fetch_moonshot_usage(start_ts, end_ts)
            
            # Combine usage data
            combined_usage = {**openai_usage}
            for model, usage in moonshot_usage.items():
                if model in combined_usage:
                    combined_usage[model]['input_tokens'] += usage.get('input_tokens', 0)
                    combined_usage[model]['output_tokens'] += usage.get('output_tokens', 0)
                    combined_usage[model]['requests'] += usage.get('requests', 0)
                else:
                    combined_usage[model] = usage
            
            # Calculate costs for Moonshot
            combined_costs = {**openai_costs}
            moonshot_pricing = load_moonshot_pricing()
            for model, usage in moonshot_usage.items():
                pricing = moonshot_pricing.get(model, {})
                input_cost = usage.get('input_tokens', 0) * pricing.get('input', 0)
                output_cost = usage.get('output_tokens', 0) * pricing.get('output', 0)
                cached_cost = usage.get('cached_tokens', 0) * pricing.get('cached', 0)
                combined_costs[model] = {
                    'input': input_cost,
                    'output': output_cost,
                    'cached': cached_cost,
                    'total': input_cost + output_cost + cached_cost
                }
            
            # Calculate summary
            total_tokens = sum(u.get('input_tokens', 0) + u.get('output_tokens', 0) for u in combined_usage.values())
            total_requests = sum(u.get('requests', 0) for u in combined_usage.values())
            
            # Store data
            data[label] = {
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'usage': combined_usage,
                'costs': combined_costs,
                'summary': {
                    'tokens': total_tokens,
                    'requests': total_requests,
                    'avg_tokens_per_request': total_tokens / total_requests if total_requests else 0
                }
            }
            
            print(f"  - {len(combined_usage)} models, {total_requests} requests, ${sum(c.get('total',0) for c in combined_costs.values()):.2f}")
            
        except Exception as e:
            print(f"  Error fetching {label}: {e}")
            continue
    
    # Save data
    save_data(data)
    print(f"\nData saved. Total days: {len(data)}")

if __name__ == '__main__':
    fetch_historical_data()
