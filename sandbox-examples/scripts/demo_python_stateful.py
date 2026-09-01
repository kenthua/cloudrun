#!/usr/bin/env python3
"""
Pure Python Multi-Turn Stateful Managed Agent Pipeline

Demonstrates how the Google Gen AI Interactions API maintains full conversational
and execution state across sequential turns using `previous_interaction_id`
with Python code execution in the Cloud Run gVisor Sandbox.

Scenario:
  Turn 1: Agent creates a financial portfolio dataset in Python, calculates baseline metrics.
  Turn 2: Agent recalls Turn 1 context, computes risk metrics (Sharpe ratio, volatility) in Python.
  Turn 3: Agent performs portfolio optimization & anomaly detection in Python, synthesizing the final report.
"""

import os
import sys
import json
import time
import subprocess
import httpx

def get_auth_token():
    try:
        res = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        print(f"[Warning] Could not get gcloud auth token: {e}")
        return ""

def get_service_url():
    try:
        res = subprocess.run(
            ["gcloud", "run", "services", "describe", "sandbox-sidecar", "--region", "us-central1", "--format", "value(status.url)"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return os.environ.get("SERVICE_URL", "https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app")

def print_separator(title):
    print("\n" + "=" * 75)
    print(f"🐍 {title}")
    print("=" * 75 + "\n")

def run_python_stateful_demo():
    service_url = get_service_url()
    token = get_auth_token()
    api_key = os.environ.get("GEMINI_API_KEY", "")

    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print_separator("PURE PYTHON MULTI-TURN STATEFUL MANAGED AGENT DEMO")
    print(f"Target Service:  {service_url}/agent/task")
    print(f"AI Model:        gemini-3.7-flash (Interactions API)")
    print(f"Execution:       Pure Python 3 in Cloud Run gVisor Sandbox")

    client = httpx.Client(timeout=60.0)

    # -------------------------------------------------------------------------
    # TURN 1: Portfolio Initialization & Baseline Metrics (Python)
    # -------------------------------------------------------------------------
    print_separator("TURN 1: Portfolio Dataset Creation & Baseline Return (Python)")
    turn1_prompt = (
        "Create a stock portfolio dataset in Python with 4 assets: 'GOOGL', 'AAPL', 'MSFT', and 'AMZN'. "
        "Define their initial capital allocations ($100k total), purchase prices, and current prices. "
        "Write and execute a Python script in the sandbox using `execute_sandbox_code` to calculate the total current portfolio value "
        "and overall profit/loss percentage. Print the results."
    )
    print(f"Prompt 1:\n{turn1_prompt}\n")

    t0 = time.time()
    res1 = client.post(
        f"{service_url}/agent/task",
        headers=headers,
        json={
            "prompt": turn1_prompt,
            "api_key": api_key
        }
    )
    elapsed1 = round(time.time() - t0, 2)

    if res1.status_code != 200:
        print(f"❌ Turn 1 Failed ({res1.status_code}): {res1.text}")
        sys.exit(1)

    data1 = res1.json()
    interaction_id_1 = data1.get("interaction_id")
    print(f"✅ Turn 1 Completed in {elapsed1}s")
    print(f"📌 Hosted Interaction ID 1: {interaction_id_1}")
    print(f"Agent Output:\n{data1.get('output')}\n")

    # -------------------------------------------------------------------------
    # TURN 2: Risk Analysis & Volatility Calculations (Pure Python)
    # -------------------------------------------------------------------------
    print_separator("TURN 2: Stateful Recall -> Risk & Volatility Analysis (Python)")
    turn2_prompt = (
        "Without me repeating the assets or their prices from Turn 1, recall the 4 stocks and allocations. "
        "Simulate 5 daily return periods for each asset in Python, calculate the annualized volatility (standard deviation of returns) "
        "and the Sharpe Ratio (assume risk-free rate of 4.0%). "
        "Execute the Python script in the sandbox and report the metrics."
    )
    print(f"Prompt 2 (Continuing Hosted Session {interaction_id_1}):\n{turn2_prompt}\n")

    t0 = time.time()
    res2 = client.post(
        f"{service_url}/agent/task",
        headers=headers,
        json={
            "prompt": turn2_prompt,
            "previous_interaction_id": interaction_id_1,
            "api_key": api_key
        }
    )
    elapsed2 = round(time.time() - t0, 2)

    if res2.status_code != 200:
        print(f"❌ Turn 2 Failed ({res2.status_code}): {res2.text}")
        sys.exit(1)

    data2 = res2.json()
    interaction_id_2 = data2.get("interaction_id")
    print(f"✅ Turn 2 Completed in {elapsed2}s")
    print(f"📌 Hosted Interaction ID 2: {interaction_id_2}")
    print(f"Agent Output:\n{data2.get('output')}\n")

    # -------------------------------------------------------------------------
    # TURN 3: Portfolio Rebalancing Recommendation (Pure Python)
    # -------------------------------------------------------------------------
    print_separator("TURN 3: Stateful Synthesis -> Portfolio Optimization (Python)")
    turn3_prompt = (
        "Building directly on the returns from Turn 1 and the risk metrics from Turn 2, "
        "write a Python script to compute the optimal rebalanced target weights that maximize the Sharpe ratio. "
        "Execute the optimization in Python in the sandbox and provide a clear final summary table with old weights vs new recommended weights."
    )
    print(f"Prompt 3 (Continuing Hosted Session {interaction_id_2}):\n{turn3_prompt}\n")

    t0 = time.time()
    res3 = client.post(
        f"{service_url}/agent/task",
        headers=headers,
        json={
            "prompt": turn3_prompt,
            "previous_interaction_id": interaction_id_2,
            "api_key": api_key
        }
    )
    elapsed3 = round(time.time() - t0, 2)

    if res3.status_code != 200:
        print(f"❌ Turn 3 Failed ({res3.status_code}): {res3.text}")
        sys.exit(1)

    data3 = res3.json()
    interaction_id_3 = data3.get("interaction_id")
    print(f"✅ Turn 3 Completed in {elapsed3}s")
    print(f"📌 Hosted Interaction ID 3: {interaction_id_3}")
    print(f"Agent Output:\n{data3.get('output')}\n")

    print_separator("🎉 PURE PYTHON STATEFUL DEMO COMPLETED SUCCESSFULLY")
    print(f"Session State Chain:")
    print(f"  Turn 1 ID: {interaction_id_1} ({elapsed1}s)")
    print(f"  Turn 2 ID: {interaction_id_2} ({elapsed2}s)")
    print(f"  Turn 3 ID: {interaction_id_3} ({elapsed3}s)")
    print(f"Total Execution Time: {round(elapsed1 + elapsed2 + elapsed3, 2)}s")

if __name__ == "__main__":
    run_python_stateful_demo()
