#!/usr/bin/env python3
"""
Stateful Managed Agent Demonstration: Multi-Turn Data Analysis Pipeline

This script demonstrates multi-turn statefulness across separate HTTP invocations
using the Google Gen AI Interactions API (`client.interactions.create`) and Cloud Run gVisor Sandbox.

Workflow:
  Turn 1 (Data Generation):   Agent generates a mock e-commerce dataset and writes /tmp/orders.json.
  Turn 2 (Stateful Python):   Agent recalls Turn 1, computes financial analytics, and writes /tmp/summary.json.
  Turn 3 (Cross-Runtime JS):  Agent uses Node.js to validate /tmp/summary.json and generate an executive report.
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
    print("\n" + "=" * 70)
    print(f"🔹 {title}")
    print("=" * 70 + "\n")

def run_stateful_demo():
    service_url = get_service_url()
    token = get_auth_token()
    api_key = os.environ.get("GEMINI_API_KEY", "")

    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print_separator("STATEFUL MANAGED AGENT PIPELINE DEMO")
    print(f"Target Cloud Run Service: {service_url}/agent/task")
    print(f"Google Gen AI Model:      gemini-2.5-flash")
    print(f"Architecture:             Interactions API + Cloud Run gVisor Sandbox")

    client = httpx.Client(timeout=60.0)

    # -------------------------------------------------------------------------
    # TURN 1: Ingestion & Dataset Creation
    # -------------------------------------------------------------------------
    print_separator("TURN 1: Ingestion & Dataset Creation in Sandbox")
    turn1_prompt = (
        "Create a customer orders dataset with 5 transactions (order_id, customer_name, amount, status: 'COMPLETED' or 'PENDING') "
        "and write it as a JSON file to `/tmp/orders.json`. "
        "Execute a Python script using `execute_sandbox_code` to verify the file contents and report the records."
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
    print(f"📌 Interaction ID 1: {interaction_id_1}")
    print(f"Agent Output:\n{data1.get('output')}\n")

    # -------------------------------------------------------------------------
    # TURN 2: Stateful Analysis & Statistical Aggregation
    # -------------------------------------------------------------------------
    print_separator("TURN 2: Stateful Memory Recall & Analytics Aggregation")
    turn2_prompt = (
        "Recall the orders dataset you created in the previous step. "
        "Write a Python script to calculate: "
        "1. Total revenue from completed orders. "
        "2. Count of completed vs pending orders. "
        "3. Average order value. "
        "Save this summary as JSON to `/tmp/analytics_summary.json` and print the summary."
    )
    print(f"Prompt 2 (Continuing Session {interaction_id_1}):\n{turn2_prompt}\n")

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
    print(f"📌 Interaction ID 2: {interaction_id_2}")
    print(f"Agent Output:\n{data2.get('output')}\n")

    # -------------------------------------------------------------------------
    # TURN 3: Cross-Language Node.js Validation & Executive Briefing
    # -------------------------------------------------------------------------
    print_separator("TURN 3: Cross-Language (Node.js) Validation & Report Generation")
    turn3_prompt = (
        "Now switch to Node.js in the sandbox. "
        "Read `/tmp/analytics_summary.json` that you saved in the previous turn using `fs.readFileSync`. "
        "Validate the values and return a clean formatted markdown executive briefing."
    )
    print(f"Prompt 3 (Continuing Session {interaction_id_2}):\n{turn3_prompt}\n")

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
    print(f"📌 Interaction ID 3: {interaction_id_3}")
    print(f"Agent Output:\n{data3.get('output')}\n")

    print_separator("🎉 STATEFUL PIPELINE DEMONSTRATION SUCCESSFUL")
    print(f"Turn 1 Session: {interaction_id_1} ({elapsed1}s)")
    print(f"Turn 2 Session: {interaction_id_2} ({elapsed2}s)")
    print(f"Turn 3 Session: {interaction_id_3} ({elapsed3}s)")
    print(f"Total Pipeline Runtime: {round(elapsed1 + elapsed2 + elapsed3, 2)}s")

if __name__ == "__main__":
    run_stateful_demo()
